"""
Unggah ke TikTok, Facebook, dan Instagram.

Satu klip vertikal cocok untuk keempat tempat sekaligus — YouTube Shorts,
TikTok, Reels Facebook, Reels Instagram — dan mengunggahnya satu per satu lewat
HP adalah pekerjaan yang paling tidak layak dikerjakan manusia: berkas yang sama,
judul yang sama, empat kali.

Tiga hal yang harus dipahami sebelum membaca kode ini, karena ketiganya
membentuk seluruh bentuknya:

1. **Kredensial aplikasi milik pemiliknya, bukan milik OmniClip.** TikTok dan
   Meta mewajibkan tiap aplikasi didaftarkan, ditinjau, dan dipegang oleh yang
   memakainya. Jadi OmniClip tidak membawa kunci apa pun; pemiliknya mendaftar
   sekali di portal pengembang masing-masing, lalu menempelkan kuncinya di
   Pengaturan. Facebook dan Instagram berbagi satu aplikasi Meta.

2. **Token milik PROFIL, kredensial milik aplikasi.** Satu aplikasi Meta bisa
   menyambungkan banyak akun; tiap profil OmniClip menyambungkan akunnya
   sendiri, persis seperti akun Google.

3. **Instagram tidak menerima berkas lewat graph.facebook.com.** Videonya
   dikirim ke rupload.facebook.com dengan tajuk `offset` dan `file_size`,
   sesudah "wadah" dibuat. Facebook Reels memakai pola yang sama. TikTok
   memakai pola ketiga lagi: init, lalu PUT berpotongan dengan Content-Range.
   Tidak ada satu jalan yang berlaku untuk ketiganya, dan berpura-pura ada
   hanya akan menghasilkan lapisan abstraksi yang bocor di tiga tempat.

Catatan jujur: seluruh berkas ini belum pernah menyentuh server TikTok maupun
Meta, karena aplikasi terdaftarnya belum ada. Bentuk permintaannya mengikuti
dokumentasi resmi per September 2026, dan yang pertama kali memakainya harus
membaca pesan galatnya apa adanya — bukan menganggapnya mustahil.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from ..errors import AppError

log = logging.getLogger("omniclip.sosial")

GRAF = "https://graph.facebook.com"
RUPLOAD = "https://rupload.facebook.com"
GRAF_VERSI = "v25.0"
TIKTOK_API = "https://open.tiktokapis.com/v2"

# Potongan unggahan TikTok. Di bawah 64 MB boleh dikirim sekaligus; di atas itu
# harus dipecah, dan potongan terakhir tidak boleh lebih kecil dari 5 MB.
TIKTOK_POTONG = 50 * 1024 * 1024
TIKTOK_SEKALIGUS = 60 * 1024 * 1024

PLATFORM = {
    "tiktok": {
        "label": "TikTok",
        "daftar": "https://developers.tiktok.com/apps",
        "kunci": ("client_key", "client_secret"),
        "izin": ["video.upload", "user.info.basic"],
        "catatan": "Unggahan masuk ke kotak draf TikTok; Anda yang menekan "
                   "terbit di aplikasinya. Terbit langsung butuh izin "
                   "video.publish yang harus ditinjau TikTok lebih dulu.",
    },
    "facebook": {
        "label": "Facebook",
        "daftar": "https://developers.facebook.com/apps",
        "kunci": ("app_id", "app_secret"),
        "izin": ["pages_show_list", "pages_read_engagement", "pages_manage_posts"],
        "catatan": "Mengunggah Reels ke Halaman Facebook (bukan profil pribadi).",
    },
    "instagram": {
        "label": "Instagram",
        "daftar": "https://developers.facebook.com/apps",
        "kunci": ("app_id", "app_secret"),
        "izin": ["pages_show_list", "pages_read_engagement",
                 "instagram_basic", "instagram_content_publish"],
        "catatan": "Butuh akun Instagram Bisnis/Kreator yang tertaut ke Halaman "
                   "Facebook. Akun pribadi tidak bisa diunggahi lewat API.",
    },
}

# Facebook dan Instagram adalah dua tujuan dari satu aplikasi Meta yang sama.
META = ("facebook", "instagram")
_KUNCI_META = "sosial.meta"

_kunci = threading.Lock()
_menunggu: dict[str, dict] = {}       # state -> {platform, waktu}


def _gagal(pesan: str, code: str = "SOSIAL", status: int = 400) -> AppError:
    return AppError(pesan, code=code, status=status)


# --- Kredensial aplikasi -------------------------------------------------------
def _nama_simpanan(platform: str) -> str:
    return _KUNCI_META if platform in META else f"sosial.{platform}"


def kredensial(platform: str) -> dict:
    from ..repos import settings as settings_repo
    try:
        return json.loads(settings_repo.get(_nama_simpanan(platform)) or "{}")
    except Exception:
        return {}


def simpan_kredensial(platform: str, nilai: dict) -> None:
    from ..repos import settings as settings_repo
    if platform not in PLATFORM:
        raise _gagal(f"Platform '{platform}' tidak dikenali.", status=422)
    butuh = PLATFORM[platform]["kunci"]
    bersih = {k: str(nilai.get(k) or "").strip() for k in butuh}
    kosong = [k for k, v in bersih.items() if not v]
    if kosong:
        raise _gagal(f"Masih kosong: {', '.join(kosong)}.", status=422)
    settings_repo.set_value(_nama_simpanan(platform), json.dumps(bersih))
    log.info("Kredensial %s tersimpan.", platform)


def siap(platform: str) -> bool:
    k = kredensial(platform)
    return all(k.get(x) for x in PLATFORM[platform]["kunci"])


def redirect_uri(platform: str) -> str:
    """
    Alamat balik sesudah pengguna memberi izin.

    Harus didaftarkan persis seperti ini di portal pengembangnya, jadi ia
    ditampilkan apa adanya di Pengaturan. Nomor portnya ikut yang sedang
    dipakai, karena aplikasi desktop memilih port kosong sendiri.
    """
    from ..config import PORT
    nama = "meta" if platform in META else platform
    return f"http://127.0.0.1:{PORT}/api/uploads/sosial/{nama}/callback"


# --- Token per profil ----------------------------------------------------------
def _jalur_token(platform: str, pid: Optional[int] = None) -> Path:
    from . import profil
    return profil.folder_akun(pid or profil.kini()) / f"sosial_{platform}.json"


def _baca(platform: str, pid: Optional[int] = None) -> dict:
    p = _jalur_token(platform, pid)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _tulis(platform: str, data: dict, pid: Optional[int] = None) -> None:
    p = _jalur_token(platform, pid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        p.chmod(0o600)
    except OSError:
        pass


def status(platform: str, pid: Optional[int] = None) -> dict:
    d = _baca(platform, pid)
    sisa = d.get("kedaluwarsa", 0) - time.time() if d.get("kedaluwarsa") else None
    return {
        "platform": platform,
        "label": PLATFORM[platform]["label"],
        "siap": siap(platform),
        "tersambung": bool(d.get("access_token")),
        "akun": d.get("akun") or "",
        "catatan": PLATFORM[platform]["catatan"],
        "redirect_uri": redirect_uri(platform),
        "daftar": PLATFORM[platform]["daftar"],
        # Hari tersisa, bukan detik: yang perlu diketahui pemiliknya adalah
        # "masih lama" atau "harus disambung ulang minggu ini".
        "sisa_hari": round(sisa / 86400, 1) if sisa else None,
    }


def putus(platform: str, pid: Optional[int] = None) -> None:
    _jalur_token(platform, pid).unlink(missing_ok=True)


# --- HTTP ----------------------------------------------------------------------
def _minta(alamat: str, *, data=None, tajuk: Optional[dict] = None,
           metode: str = "GET", batas: int = 120) -> dict:
    isi = None
    if isinstance(data, dict):
        isi = urllib.parse.urlencode(data).encode()
    elif isinstance(data, (bytes, str)):
        isi = data.encode() if isinstance(data, str) else data
    permintaan = urllib.request.Request(alamat, data=isi, method=metode,
                                        headers=tajuk or {})
    try:
        with urllib.request.urlopen(permintaan, timeout=batas) as r:
            mentah = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        badan = ""
        try:
            badan = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise _gagal(_pesan_galat(badan) or f"HTTP {e.code}: {e.reason}",
                     status=502) from e
    except urllib.error.URLError as e:
        raise _gagal(f"Tidak bisa menghubungi server: {e.reason}", status=502) from e
    if not mentah.strip():
        return {}
    try:
        return json.loads(mentah)
    except json.JSONDecodeError:
        return {"mentah": mentah}


def _pesan_galat(badan: str) -> str:
    """Pesan yang bisa dibaca orang dari jawaban galat TikTok atau Meta."""
    try:
        d = json.loads(badan)
    except Exception:
        return (badan or "")[:300]
    g = d.get("error")
    if isinstance(g, dict):
        pesan = g.get("message") or g.get("error_user_msg") or g.get("code") or ""
        # TikTok menaruh keterangan sebenarnya di `log_id` + `message`.
        if g.get("code") and g.get("code") != "ok" and pesan:
            return f"{pesan} ({g['code']})"
        return str(pesan)[:300]
    return (badan or "")[:300]


class _BerkasLapor:
    """Berkas yang melaporkan kemajuan saat dibaca urllib."""

    def __init__(self, path: Path, awal: int, panjang: int,
                 lapor: Optional[Callable[[float], None]],
                 batal: Optional[Callable[[], bool]]):
        self._f = path.open("rb")
        self._f.seek(awal)
        self._sisa = panjang
        self._total = panjang
        self._lapor = lapor
        self._batal = batal

    def read(self, n: int = -1) -> bytes:
        if self._batal is not None and self._batal():
            raise _gagal("Unggahan dibatalkan.", code="CANCELLED")
        if self._sisa <= 0:
            return b""
        ambil = self._sisa if n is None or n < 0 else min(n, self._sisa)
        data = self._f.read(ambil)
        self._sisa -= len(data)
        if self._lapor is not None and self._total:
            self._lapor(1.0 - self._sisa / self._total)
        return data

    def close(self) -> None:
        try:
            self._f.close()
        except Exception:
            pass


def _kirim_biner(alamat: str, path: Path, *, tajuk: dict, awal: int = 0,
                 panjang: Optional[int] = None, metode: str = "POST",
                 lapor=None, batal=None) -> dict:
    besar = path.stat().st_size
    panjang = besar - awal if panjang is None else panjang
    berkas = _BerkasLapor(path, awal, panjang, lapor, batal)
    tajuk = {**tajuk, "Content-Length": str(panjang)}
    permintaan = urllib.request.Request(alamat, data=berkas, method=metode, headers=tajuk)
    try:
        with urllib.request.urlopen(permintaan, timeout=3600) as r:
            mentah = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        badan = ""
        try:
            badan = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise _gagal(_pesan_galat(badan) or f"HTTP {e.code}: {e.reason}", status=502) from e
    except urllib.error.URLError as e:
        raise _gagal(f"Pengiriman terputus: {e.reason}", status=502) from e
    finally:
        berkas.close()
    if not mentah.strip():
        return {}
    try:
        return json.loads(mentah)
    except json.JSONDecodeError:
        return {"mentah": mentah}


# --- Izin (OAuth) --------------------------------------------------------------
def mulai_izin(platform: str) -> str:
    if platform not in PLATFORM:
        raise _gagal(f"Platform '{platform}' tidak dikenali.", status=422)
    if not siap(platform):
        raise _gagal(f"Kunci aplikasi {PLATFORM[platform]['label']} belum diisi.",
                     code="SOSIAL_BELUM_SIAP", status=409)
    k = kredensial(platform)
    from . import profil as profil_svc
    state = secrets.token_urlsafe(24)
    with _kunci:
        # Profil peminta diingat bersama sesinya. Halaman balik dari TikTok
        # atau Meta datang sebagai kunjungan biasa dari peramban dan TIDAK
        # membawa header profil — tanpa ini, akun kedua selalu tersimpan ke
        # profil pertama, dan pemiliknya baru sadar saat klipnya naik ke kanal
        # yang salah.
        _menunggu[state] = {"platform": platform, "waktu": time.time(),
                            "profil": profil_svc.kini()}
        # Sesi izin yang ditinggalkan tidak perlu disimpan selamanya.
        for s, v in list(_menunggu.items()):
            if time.time() - v["waktu"] > 900:
                _menunggu.pop(s, None)

    if platform == "tiktok":
        q = urllib.parse.urlencode({
            "client_key": k["client_key"],
            "response_type": "code",
            "scope": ",".join(PLATFORM[platform]["izin"]),
            "redirect_uri": redirect_uri(platform),
            "state": state,
        })
        return f"https://www.tiktok.com/v2/auth/authorize/?{q}"

    q = urllib.parse.urlencode({
        "client_id": k["app_id"],
        "redirect_uri": redirect_uri(platform),
        "scope": ",".join(sorted(set(PLATFORM["facebook"]["izin"] + PLATFORM["instagram"]["izin"]))),
        "response_type": "code",
        "state": state,
    })
    return f"https://www.facebook.com/{GRAF_VERSI}/dialog/oauth?{q}"


def selesaikan_izin(code: str, state: str, pid: Optional[int] = None) -> dict:
    with _kunci:
        sesi = _menunggu.pop(state, None)
    if not sesi:
        raise _gagal("Sesi izin sudah kedaluwarsa. Coba sambungkan lagi.", status=409)
    platform = sesi["platform"]
    pid = pid or sesi.get("profil")
    return (_tiktok_token(code, pid) if platform == "tiktok"
            else _meta_token(code, platform, pid))


def _tiktok_token(code: str, pid: Optional[int]) -> dict:
    k = kredensial("tiktok")
    jawab = _minta(f"{TIKTOK_API}/oauth/token/", metode="POST",
                   tajuk={"Content-Type": "application/x-www-form-urlencoded"},
                   data={"client_key": k["client_key"],
                         "client_secret": k["client_secret"],
                         "code": code, "grant_type": "authorization_code",
                         "redirect_uri": redirect_uri("tiktok")})
    if not jawab.get("access_token"):
        raise _gagal(_pesan_galat(json.dumps(jawab)) or "TikTok tidak memberi token.")
    nama = ""
    try:
        info = _minta(f"{TIKTOK_API}/user/info/?fields=display_name",
                      tajuk={"Authorization": f"Bearer {jawab['access_token']}"})
        nama = ((info.get("data") or {}).get("user") or {}).get("display_name") or ""
    except Exception:
        pass
    data = {"access_token": jawab["access_token"],
            "refresh_token": jawab.get("refresh_token", ""),
            "kedaluwarsa": time.time() + float(jawab.get("expires_in") or 86400),
            "akun": nama or "TikTok"}
    _tulis("tiktok", data, pid)
    return {"platform": "tiktok", "akun": data["akun"]}


def _meta_token(code: str, platform: str, pid: Optional[int]) -> dict:
    """
    Token Meta, lalu Halaman dan akun Instagram yang menempel padanya.

    Token pengguna ditukar jadi token panjang (60 hari) lebih dulu. Tanpa itu
    sambungannya mati dalam dua jam — dan matinya diam-diam, saat unggahan
    berikutnya berjalan tanpa ada orang di depan layar.
    """
    k = kredensial(platform)
    jawab = _minta(f"{GRAF}/{GRAF_VERSI}/oauth/access_token?" + urllib.parse.urlencode({
        "client_id": k["app_id"], "client_secret": k["app_secret"],
        "redirect_uri": redirect_uri(platform), "code": code}))
    token = jawab.get("access_token")
    if not token:
        raise _gagal("Meta tidak memberi token.")
    panjang = _minta(f"{GRAF}/{GRAF_VERSI}/oauth/access_token?" + urllib.parse.urlencode({
        "grant_type": "fb_exchange_token", "client_id": k["app_id"],
        "client_secret": k["app_secret"], "fb_exchange_token": token}))
    token = panjang.get("access_token", token)
    umur = float(panjang.get("expires_in") or 60 * 86400)

    halaman = (_minta(f"{GRAF}/{GRAF_VERSI}/me/accounts?" + urllib.parse.urlencode({
        "fields": "id,name,access_token,instagram_business_account{id,username}",
        "access_token": token})).get("data") or [])
    if not halaman:
        raise _gagal(
            "Akun ini tidak mengelola satu Halaman Facebook pun. Reels hanya bisa "
            "diunggah ke Halaman, bukan ke profil pribadi.", status=409)

    hasil: dict = {}
    fb = halaman[0]
    _tulis("facebook", {
        "access_token": fb.get("access_token") or token,
        "kedaluwarsa": time.time() + umur,
        "page_id": fb.get("id"), "akun": fb.get("name") or "Halaman Facebook",
        # Semua Halaman ikut disimpan supaya bisa dipilih tanpa izin ulang.
        "halaman": [{"id": h.get("id"), "nama": h.get("name")} for h in halaman],
    }, pid)
    hasil["facebook"] = fb.get("name")

    ig = next((h for h in halaman if (h.get("instagram_business_account") or {}).get("id")), None)
    if ig:
        akun_ig = ig["instagram_business_account"]
        _tulis("instagram", {
            "access_token": ig.get("access_token") or token,
            "kedaluwarsa": time.time() + umur,
            "ig_user_id": akun_ig.get("id"),
            "page_id": ig.get("id"),
            "akun": akun_ig.get("username") or "Instagram",
        }, pid)
        hasil["instagram"] = akun_ig.get("username")
    return {"platform": platform, "akun": hasil.get(platform) or "", "terhubung": hasil}


def _token_hidup(platform: str, pid: Optional[int]) -> dict:
    d = _baca(platform, pid)
    if not d.get("access_token"):
        raise _gagal(f"Akun {PLATFORM[platform]['label']} profil ini belum tersambung.",
                     code="SOSIAL_BELUM_SAMBUNG", status=409)
    if d.get("kedaluwarsa") and d["kedaluwarsa"] < time.time() + 60:
        if platform == "tiktok" and d.get("refresh_token"):
            k = kredensial("tiktok")
            jawab = _minta(f"{TIKTOK_API}/oauth/token/", metode="POST",
                           tajuk={"Content-Type": "application/x-www-form-urlencoded"},
                           data={"client_key": k["client_key"],
                                 "client_secret": k["client_secret"],
                                 "grant_type": "refresh_token",
                                 "refresh_token": d["refresh_token"]})
            if jawab.get("access_token"):
                d.update({"access_token": jawab["access_token"],
                          "refresh_token": jawab.get("refresh_token", d["refresh_token"]),
                          "kedaluwarsa": time.time() + float(jawab.get("expires_in") or 86400)})
                _tulis("tiktok", d, pid)
                return d
        raise _gagal(
            f"Izin {PLATFORM[platform]['label']} sudah kedaluwarsa. Sambungkan "
            "lagi akunnya di halaman Profil.", code="SOSIAL_KEDALUWARSA", status=409)
    return d


# --- Unggah --------------------------------------------------------------------
def unggah(platform: str, path: Path, *, judul: str = "", deskripsi: str = "",
           privasi: str = "private", pid: Optional[int] = None,
           lapor: Optional[Callable[[float], None]] = None,
           batal: Optional[Callable[[], bool]] = None) -> dict:
    if platform not in PLATFORM:
        raise _gagal(f"Platform '{platform}' tidak dikenali.", status=422)
    d = _token_hidup(platform, pid)
    path = Path(path)
    if not path.is_file():
        raise _gagal("Berkas klipnya tidak ada.", status=404)
    fungsi = {"tiktok": _unggah_tiktok, "facebook": _unggah_facebook,
              "instagram": _unggah_instagram}[platform]
    return fungsi(d, path, judul=judul, deskripsi=deskripsi, privasi=privasi,
                  lapor=lapor, batal=batal)


def _unggah_tiktok(d: dict, path: Path, *, judul: str, deskripsi: str,
                   privasi: str, lapor, batal) -> dict:
    """
    Init, kirim berkas berpotongan, lalu tunggu TikTok selesai memprosesnya.

    Yang dipakai jalur "inbox": videonya masuk ke draf, dan pemiliknya yang
    menekan terbit di aplikasi TikTok. Terbit langsung butuh izin yang harus
    ditinjau TikTok lebih dulu, dan meminta izin yang belum dimiliki hanya
    menghasilkan penolakan yang membingungkan.
    """
    besar = path.stat().st_size
    if besar <= TIKTOK_SEKALIGUS:
        potong, jumlah = besar, 1
    else:
        jumlah = max(1, besar // TIKTOK_POTONG)
        potong = TIKTOK_POTONG
    tajuk = {"Authorization": f"Bearer {d['access_token']}",
             "Content-Type": "application/json; charset=UTF-8"}
    awal = _minta(f"{TIKTOK_API}/post/publish/inbox/video/init/", metode="POST",
                  tajuk=tajuk,
                  data=json.dumps({"source_info": {
                      "source": "FILE_UPLOAD", "video_size": besar,
                      "chunk_size": potong, "total_chunk_count": jumlah}}))
    data = awal.get("data") or {}
    alamat, publish_id = data.get("upload_url"), data.get("publish_id")
    if not alamat:
        raise _gagal(_pesan_galat(json.dumps(awal)) or "TikTok menolak memulai unggahan.")

    terkirim = 0
    for i in range(jumlah):
        mulai = i * potong
        panjang = besar - mulai if i == jumlah - 1 else potong
        _kirim_biner(alamat, path, metode="PUT", awal=mulai, panjang=panjang,
                     tajuk={"Content-Type": "video/mp4",
                            "Content-Range": f"bytes {mulai}-{mulai + panjang - 1}/{besar}"},
                     lapor=(lambda f, m=terkirim, p=panjang: lapor and lapor(
                         min(0.97, (m + f * p) / besar))),
                     batal=batal)
        terkirim += panjang

    # Diproses TikTok sesudah berkasnya sampai. Ditunggu sebentar supaya
    # kegagalan (video terlalu pendek, rasio ditolak) ketahuan di sini, bukan
    # dilaporkan "berhasil" lalu tidak pernah muncul di mana pun.
    for _ in range(20):
        if batal is not None and batal():
            break
        time.sleep(3)
        cek = _minta(f"{TIKTOK_API}/post/publish/status/fetch/", metode="POST",
                     tajuk=tajuk, data=json.dumps({"publish_id": publish_id}))
        keadaan = ((cek.get("data") or {}).get("status") or "").upper()
        if keadaan in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            break
        if keadaan == "FAILED":
            raise _gagal("TikTok menolak videonya: "
                         + str((cek.get("data") or {}).get("fail_reason") or "tanpa alasan"))
    return {"remote_id": publish_id or "",
            "remote_url": "https://www.tiktok.com/upload?lang=id",
            "catatan": "Masuk ke draf TikTok — terbitkan dari aplikasinya."}


def _unggah_facebook(d: dict, path: Path, *, judul: str, deskripsi: str,
                     privasi: str, lapor, batal) -> dict:
    """Reels Halaman Facebook: mulai, kirim ke rupload, selesaikan."""
    page_id, token = d.get("page_id"), d["access_token"]
    if not page_id:
        raise _gagal("Halaman Facebook tujuan belum dipilih.", status=409)
    awal = _minta(f"{GRAF}/{GRAF_VERSI}/{page_id}/video_reels", metode="POST",
                  data={"upload_phase": "start", "access_token": token})
    video_id = awal.get("video_id")
    if not video_id:
        raise _gagal(_pesan_galat(json.dumps(awal)) or "Facebook menolak memulai unggahan.")

    _kirim_biner(f"{RUPLOAD}/video-upload/{GRAF_VERSI}/{video_id}", path,
                 tajuk={"Authorization": f"OAuth {token}", "offset": "0",
                        "file_size": str(path.stat().st_size)},
                 lapor=lambda f: lapor and lapor(min(0.95, f)), batal=batal)

    selesai = _minta(f"{GRAF}/{GRAF_VERSI}/{page_id}/video_reels", metode="POST",
                     data={"access_token": token, "video_id": video_id,
                           "upload_phase": "finish",
                           # "private" pada Facebook = draf yang belum terbit.
                           "video_state": "DRAFT" if privasi == "private" else "PUBLISHED",
                           "description": (deskripsi or judul)[:2200]})
    if not selesai.get("success", True):
        raise _gagal(_pesan_galat(json.dumps(selesai)) or "Facebook menolak menerbitkan.")
    return {"remote_id": video_id,
            "remote_url": f"https://www.facebook.com/reel/{video_id}"}


def _unggah_instagram(d: dict, path: Path, *, judul: str, deskripsi: str,
                      privasi: str, lapor, batal) -> dict:
    """
    Reels Instagram: wadah, kirim berkas ke rupload, tunggu siap, terbitkan.

    Instagram tidak punya "draf" lewat API — yang terunggah akan terbit. Jadi
    privasi "private" ditolak di sini, bukan diam-diam diterbitkan.
    """
    ig = d.get("ig_user_id")
    token = d["access_token"]
    if not ig:
        raise _gagal("Akun Instagram Bisnis belum tertaut ke Halaman ini.", status=409)
    if privasi == "private":
        raise _gagal(
            "Instagram tidak menerima unggahan privat lewat API — yang terkirim "
            "akan langsung terbit. Ganti privasinya, atau matikan Instagram pada "
            "unggahan otomatis.", code="SOSIAL_PRIVASI", status=409)

    wadah = _minta(f"{GRAF}/{GRAF_VERSI}/{ig}/media", metode="POST",
                   data={"media_type": "REELS", "upload_type": "resumable",
                         "caption": (deskripsi or judul)[:2200],
                         "access_token": token})
    cid = wadah.get("id")
    if not cid:
        raise _gagal(_pesan_galat(json.dumps(wadah)) or "Instagram menolak membuat wadah.")

    _kirim_biner(f"{RUPLOAD}/ig-api-upload/{GRAF_VERSI}/{cid}", path,
                 tajuk={"Authorization": f"OAuth {token}", "offset": "0",
                        "file_size": str(path.stat().st_size)},
                 lapor=lambda f: lapor and lapor(min(0.9, f)), batal=batal)

    # Instagram memproses videonya dulu; menerbitkan sebelum selesai dijawab
    # galat yang tidak menjelaskan apa-apa.
    for _ in range(40):
        if batal is not None and batal():
            raise _gagal("Unggahan dibatalkan.", code="CANCELLED")
        cek = _minta(f"{GRAF}/{GRAF_VERSI}/{cid}?fields=status_code,status&"
                     + urllib.parse.urlencode({"access_token": token}))
        keadaan = (cek.get("status_code") or "").upper()
        if keadaan == "FINISHED":
            break
        if keadaan == "ERROR":
            raise _gagal("Instagram menolak videonya: " + str(cek.get("status") or ""))
        time.sleep(3)

    terbit = _minta(f"{GRAF}/{GRAF_VERSI}/{ig}/media_publish", metode="POST",
                    data={"creation_id": cid, "access_token": token})
    mid = terbit.get("id")
    if not mid:
        raise _gagal(_pesan_galat(json.dumps(terbit)) or "Instagram menolak menerbitkan.")
    if lapor:
        lapor(1.0)
    return {"remote_id": mid, "remote_url": f"https://www.instagram.com/reel/{mid}/"}
