"""
Satu kata sandi, satu pintu.

Sampai hari ini OmniClip tidak punya pemeriksaan siapa pun. Itu bukan kelalaian
— ia hanya mendengar di 127.0.0.1, dan di komputer satu pengguna itu memang
cukup. Tapi begitu ia dijangkau lewat terowongan, "tidak ada yang memeriksa"
berubah artinya: siapa pun yang sampai ke alamatnya bisa mengunggah ke kanal
YouTube pemiliknya, membaca API key-nya, dan mengunduh seluruh isi
penyimpanannya.

Yang dibangun di sini sengaja kecil:

  * Kata sandi disimpan sebagai turunan PBKDF2-SHA256 bergaram, tidak pernah
    sebagai teks. Tabel `settings` ikut tersalin saat basis data dicadangkan,
    dan basis data itu berada di partisi yang tidak menghormati izin berkas.
  * Sesi adalah cookie ber-HMAC, bukan daftar sesi di memori: backend boleh
    dimulai ulang tanpa melempar keluar HP yang sedang dipakai.
  * Kunci penanda tangan lahir sekali dan tinggal di basis data. Mengganti kata
    sandi menaikkan nomor sesi, dan itulah yang membuat seluruh sesi lama mati
    seketika — termasuk sesi di perangkat yang sudah tidak Anda pegang.

Lapis ini bukan pengganti Cloudflare Access. Ia lapis kedua, untuk saat
terowongan salah setel — kegagalan yang jauh lebih mungkin daripada kata sandi
yang tertebak.
"""

import base64
import hashlib
import hmac
import logging
import os
import secrets
import time

from ..repos import settings as settings_repo

log = logging.getLogger("omniclip.auth")

COOKIE_NAME = "omniclip_session"
SESSION_MAX_AGE = 30 * 24 * 3600  # 30 hari

_KEY_HASH = "auth.password_hash"
_KEY_SECRET = "auth.session_secret"
_KEY_EPOCH = "auth.session_epoch"

PBKDF2_ROUNDS = 240_000

# Jalur yang harus tetap terbuka, kalau tidak layar masuknya sendiri tidak bisa
# memuat dan tidak ada cara untuk masuk sama sekali.
OPEN_PATHS = frozenset({
    "/api/health",
    "/api/auth/status",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/setup",
})


# --- Kata sandi ---------------------------------------------------------------

def _hash(password: str, salt: bytes, rounds: int = PBKDF2_ROUNDS) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${salt.hex()}${dk.hex()}"


def set_password(password: str) -> None:
    """Menyimpan kata sandi baru dan mematikan seluruh sesi yang sedang jalan."""
    settings_repo.set_value(_KEY_HASH, _hash(password, secrets.token_bytes(16)))
    settings_repo.set_value(_KEY_EPOCH, str(int(time.time())))


def clear_password() -> None:
    settings_repo.delete(_KEY_HASH)
    settings_repo.set_value(_KEY_EPOCH, str(int(time.time())))


def has_password() -> bool:
    return bool(settings_repo.get(_KEY_HASH))


def verify_password(password: str) -> bool:
    stored = settings_repo.get(_KEY_HASH)
    if not stored:
        return False
    try:
        algo, rounds, salt_hex, _ = stored.split("$")
    except ValueError:
        log.warning("Turunan kata sandi tersimpan tidak bisa dibaca; masuk ditolak.")
        return False
    if algo != "pbkdf2_sha256":
        return False
    candidate = _hash(password, bytes.fromhex(salt_hex), int(rounds))
    return hmac.compare_digest(candidate, stored)


# --- Sesi ---------------------------------------------------------------------

def _secret() -> bytes:
    value = settings_repo.get(_KEY_SECRET)
    if not value:
        value = secrets.token_hex(32)
        settings_repo.set_value(_KEY_SECRET, value)
    return bytes.fromhex(value)


def _epoch() -> str:
    return settings_repo.get(_KEY_EPOCH, "0")


def issue_session() -> str:
    expires = int(time.time()) + SESSION_MAX_AGE
    payload = f"{expires}.{_epoch()}"
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()
    return f"{payload}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def valid_session(token: str | None) -> bool:
    if not token:
        return False
    try:
        expires_s, epoch, sig_b64 = token.split(".")
        expires = int(expires_s)
    except ValueError:
        return False
    if expires < time.time():
        return False
    # Kata sandi diganti sejak cookie ini terbit -> cookie mati. Inilah cara
    # mencabut akses dari perangkat yang tidak lagi Anda pegang.
    if epoch != _epoch():
        return False
    payload = f"{expires_s}.{epoch}"
    expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()
    try:
        given = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
    except Exception:
        return False
    return hmac.compare_digest(expected, given)


# --- Kebijakan ----------------------------------------------------------------

def auth_mode() -> str:
    """`auto` (bawaan) | `on` | `off`. Lihat PANDUAN-AKSES-JARAK-JAUH.md."""
    return os.getenv("OMNICLIP_AUTH", "auto").strip().lower()


def auth_required() -> bool:
    mode = auth_mode()
    if mode == "off":
        return False
    if mode == "on":
        return True
    return has_password()


def check_startup_policy() -> None:
    """
    Dipanggil saat startup. `OMNICLIP_AUTH=on` tanpa kata sandi adalah salah
    setel yang harus berbunyi sekarang, bukan nanti saat halaman masuk menolak
    setiap kata sandi tanpa alasan yang terlihat.
    """
    if auth_mode() == "on" and not has_password():
        raise RuntimeError(
            "OMNICLIP_AUTH=on tapi belum ada kata sandi. Jalankan sekali tanpa "
            "variabel itu, pasang kata sandi di halaman Catatan main, lalu "
            "nyalakan lagi."
        )
    if auth_mode() == "off":
        log.warning("Gerbang kata sandi DIMATIKAN (OMNICLIP_AUTH=off). "
                    "Jangan pernah pakai ini bersama terowongan.")
    elif not auth_required():
        log.info("Belum ada kata sandi: mode lokal. Pasang kata sandi di "
                 "halaman Catatan main sebelum membuka akses jarak jauh.")


# --- Pembatas percobaan masuk -------------------------------------------------

_failures: dict[str, list[float]] = {}
_LOCKOUT_AFTER = 8
_LOCKOUT_WINDOW = 300.0


def note_failure(client: str) -> None:
    now = time.time()
    hits = [t for t in _failures.get(client, []) if now - t < _LOCKOUT_WINDOW]
    hits.append(now)
    _failures[client] = hits
    if len(_failures) > 512:  # jangan biarkan tumbuh tanpa batas
        for k in [k for k, v in _failures.items()
                  if not v or now - v[-1] > _LOCKOUT_WINDOW]:
            _failures.pop(k, None)


def note_success(client: str) -> None:
    _failures.pop(client, None)


def locked_out(client: str) -> int:
    """Sisa detik penguncian, 0 bila tidak terkunci."""
    now = time.time()
    hits = [t for t in _failures.get(client, []) if now - t < _LOCKOUT_WINDOW]
    if len(hits) < _LOCKOUT_AFTER:
        return 0
    return max(1, int(_LOCKOUT_WINDOW - (now - hits[0])))
