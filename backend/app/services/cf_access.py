"""
Mempercayai identitas yang sudah diperiksa Cloudflare Access.

Masalah yang diselesaikan berkas ini: Cloudflare Access sudah meminta Anda masuk
dengan Google sebelum permintaan sampai ke sini. Kalau OmniClip lalu meminta
kata sandi lagi, Anda masuk dua kali untuk membuka satu aplikasi — dan pintu
kedua yang mengganggu adalah pintu yang cepat atau lambat dimatikan orang.

Jadi: bila Cloudflare sudah mengatakan siapa Anda, dan buktinya sah, OmniClip
menerima itu sebagai sesi. Kata sandi tetap ada, tapi berpindah peran — ia
menjadi jalan masuk saat Anda duduk di depan komputer ini (di mana tidak ada
Cloudflare sama sekali), dan jaring pengaman saat terowongannya salah setel.

Buktinya adalah JWT bertanda tangan RS256 di header `Cf-Access-Jwt-Assertion`,
dan ia diperiksa sungguhan:

  * tanda tangannya dicocokkan dengan kunci publik milik tim Anda,
  * `aud` harus sama persis dengan tag aplikasi Access Anda,
  * `iss` harus tim Anda,
  * `exp` belum lewat.

Tanpa pemeriksaan `aud`, token sah dari aplikasi Access LAIN — milik siapa pun
di internet yang punya akun Cloudflare — akan diterima di sini. Itu bukan
kehalusan teori; itu cara paling umum integrasi seperti ini dibobol.

Dan satu pagar lagi: header ini hanya dipercaya bila permintaannya datang dari
loopback. `cloudflared` menyambung dari dalam mesin ini, jadi hanya dari sanalah
header itu bisa sah. Dari jaringan lain, header bernama sama hanyalah teks yang
diketik pengirimnya sendiri.
"""

import asyncio
import json
import logging
import os
import time
import urllib.request

log = logging.getLogger("omniclip.cf_access")

HEADER = "cf-access-jwt-assertion"
COOKIE = "CF_Authorization"

CERTS_TTL = 3600.0
CERTS_TIMEOUT = 6.0

_certs: dict[str, str] = {}
_certs_at = 0.0
_lock = asyncio.Lock()


def team() -> str:
    """Subdomain tim Zero Trust, mis. `yosafat` untuk yosafat.cloudflareaccess.com."""
    return os.getenv("OMNICLIP_CF_ACCESS_TEAM", "").strip().strip("/").lower()


def aud() -> str:
    """Tag Application Audience dari aplikasi Access. Tanpa ini, tidak aktif."""
    return os.getenv("OMNICLIP_CF_ACCESS_AUD", "").strip()


def allowed_emails() -> set[str]:
    """
    Pagar tambahan di sisi kita sendiri.

    Kosong berarti "percayai siapa pun yang diloloskan Access" — yang memang
    benar, karena daftar siapa yang boleh sudah ada di kebijakan Access. Diisi
    berarti dua daftar harus sepakat, dan itu berguna kalau kebijakan Access
    suatu saat tidak sengaja dilonggarkan.
    """
    raw = os.getenv("OMNICLIP_CF_ACCESS_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def configured() -> bool:
    return bool(team() and aud())


def issuer() -> str:
    return f"https://{team()}.cloudflareaccess.com"


def _fetch_certs() -> dict[str, str]:
    """Sertifikat publik tim. Dipanggil di thread — urllib memblokir."""
    url = f"{issuer()}/cdn-cgi/access/certs"
    with urllib.request.urlopen(url, timeout=CERTS_TIMEOUT) as r:
        data = json.load(r)
    certs = {c["kid"]: c["cert"] for c in data.get("public_certs", []) if c.get("kid")}
    if not certs:
        raise ValueError("daftar sertifikat Cloudflare kosong")
    return certs


async def _certs_cached(force: bool = False) -> dict[str, str]:
    global _certs, _certs_at
    async with _lock:
        stale = force or not _certs or (time.time() - _certs_at) > CERTS_TTL
        if stale:
            fresh = await asyncio.to_thread(_fetch_certs)
            _certs, _certs_at = fresh, time.time()
        return _certs


def _token(request) -> str:
    return (request.headers.get(HEADER, "").strip()
            or request.cookies.get(COOKIE, "").strip())


def _from_tunnel(request) -> bool:
    peer = request.client.host if request.client else ""
    return peer in ("127.0.0.1", "::1", "localhost")


async def verify(request) -> tuple[str | None, str]:
    """
    Mengembalikan `(email, alasan)`.

    `email` terisi hanya bila tokennya benar-benar sah. `alasan` selalu terisi
    dan ditujukan untuk manusia yang sedang menyetel Cloudflare — salah setel di
    sini gejalanya adalah "minta kata sandi terus" tanpa petunjuk apa pun, dan
    itu berjam-jam yang tidak perlu.
    """
    if not configured():
        return None, "belum disetel"

    token = _token(request)
    if not token:
        return None, "tidak ada token Access pada permintaan ini"

    if not _from_tunnel(request):
        # Bukan kasus tepi: tanpa ini, siapa pun di jaringan yang sama bisa
        # mengetik sendiri header bernama Cf-Access-Jwt-Assertion.
        return None, "token Access hanya dipercaya dari terowongan di mesin ini"

    from google.auth import jwt as gjwt

    for attempt in (False, True):  # sekali lagi dengan kunci segar bila gagal
        try:
            certs = await _certs_cached(force=attempt)
        except Exception as e:
            return None, f"tidak bisa mengambil kunci publik Cloudflare: {e}"
        try:
            # `audience=` sengaja TIDAK dipakai di sini. Cloudflare menulis
            # `aud` sebagai DAFTAR, sementara google.auth membandingkannya
            # sebagai nilai tunggal — sehingga token yang sah pun selalu
            # ditolak. Jadi tanda tangan dan kedaluwarsa diperiksa pustaka,
            # `aud` diperiksa di bawah ini.
            claims = await asyncio.to_thread(gjwt.decode, token, certs=certs)
            break
        except Exception as e:
            if attempt:
                return None, f"token ditolak: {e}"

    raw_aud = claims.get("aud")
    auds = [str(a) for a in (raw_aud if isinstance(raw_aud, (list, tuple))
                             else [raw_aud])]
    if aud() not in auds:
        # Tanpa pemeriksaan ini, token sah dari aplikasi Access MANA PUN —
        # milik siapa saja yang punya akun Cloudflare — diterima di sini.
        return None, f"aud token ({', '.join(auds)[:60]}) bukan aplikasi ini"

    if claims.get("iss") != issuer():
        return None, f"penerbit token bukan {issuer()}"

    email = str(claims.get("email") or "").strip().lower()
    if not email:
        return None, "token sah tapi tidak memuat email"

    allow = allowed_emails()
    if allow and email not in allow:
        log.warning("Access meloloskan %s tapi OMNICLIP_CF_ACCESS_EMAILS tidak.", email)
        return None, f"{email} tidak ada di daftar OMNICLIP_CF_ACCESS_EMAILS"

    return email, "ok"
