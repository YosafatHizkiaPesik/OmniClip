"""
Unggah klip ke Google Drive dan YouTube.

Modul ini menggantikan `drive_manager.py` yang lama, yang tidak pernah melakukan
satu pun panggilan jaringan: ia mengarang `drive_file_id`, dan UI menampilkan
"Berhasil mengunggah ke Google Drive" untuk berkas yang tidak pernah ke mana-mana.
Di sini semuanya sungguhan — dan karena sungguhan, ia bisa gagal, jadi setiap
kegagalan diberi pesan yang menyebut apa yang harus dilakukan.

Kredensial disimpan di dua berkas di dalam OmniClip_Storage, keduanya di luar
git:

  google_client_secret.json — OAuth client dari Google Cloud Console, dipasang
                              sekali oleh pengguna;
  google_token.json         — token hasil izin, diperbarui sendiri.

Tidak ada rahasia yang pernah dikirim ke browser. `status()` hanya menjawab
sudah tersambung atau belum, dan alamat surel akunnya.
"""

import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Optional

from ..config import STORAGE_DIR
from ..errors import AppError

log = logging.getLogger("omniclip.upload")

CLIENT_SECRET_PATH = STORAGE_DIR / "google_client_secret.json"


def _token_path(pid: Optional[int] = None, layanan: str = "youtube") -> Path:
    """
    Token Google milik satu profil. Setiap profil boleh menyambungkan akunnya
    sendiri — Drive dan kanal YouTube yang berbeda (services/profil.py).
    Rahasia klien OAuth dipakai bersama: satu project Google Cloud cukup untuk
    banyak akun.
    """
    from . import profil
    # YouTube memakai nama berkas yang lama supaya sambungan yang sudah ada
    # tidak putus begitu versi ini dipasang.
    nama = "google_token.json" if layanan == "youtube" else f"google_token_{layanan}.json"
    return profil.folder_akun(pid or profil.kini()) / nama

# Cakupan sekecil mungkin yang masih menyelesaikan pekerjaannya, DIPISAH PER
# LAYANAN.
#
# Pemisahannya bukan pilihan rasa. Google menolak permintaan yang memuat izin
# YouTube dan Drive sekaligus:
#
#   Access blocked: Authorization Error
#   This request contains scopes that cannot be requested together:
#   [.../auth/drive.file, .../auth/youtube.upload]
#   Error 400: invalid_request
#
# Jadi keduanya diminta terpisah, dan tokennya disimpan terpisah pula. Akibatnya
# terlihat di antarmuka: menyambungkan YouTube dan menyambungkan Drive adalah
# dua tombol, bukan satu.
#
# drive.file memberi akses HANYA ke berkas yang dibuat aplikasi ini sendiri,
# bukan ke seluruh Drive. youtube.upload hanya bisa mengunggah, tidak bisa
# membaca atau menghapus video yang sudah ada di kanal.
_IDENTITAS = ["openid", "https://www.googleapis.com/auth/userinfo.email"]
SCOPES_LAYANAN = {
    "youtube": ["https://www.googleapis.com/auth/youtube.upload"] + _IDENTITAS,
    "drive": ["https://www.googleapis.com/auth/drive.file"] + _IDENTITAS,
}
LAYANAN = tuple(SCOPES_LAYANAN)
# Nama lama, masih dipakai beberapa pemanggil untuk menampilkan daftar izin.
SCOPES = sorted({s for v in SCOPES_LAYANAN.values() for s in v})

def redirect_uri() -> str:
    """
    Alamat yang dituju Google setelah pengguna memberi izin.

    Dulu dipatok ke port 8000. Itu benar selama aplikasi dijalankan dari sumber,
    yang memang selalu memakai 8000 — dan salah begitu ia jadi aplikasi desktop:
    peluncurnya mencari port kosong sendiri, jadi di komputer yang port 8000-nya
    sudah terpakai, Google akan mengantar pengguna ke alamat yang tidak ada
    apa-apanya. Gejalanya halaman kosong setelah menekan "izinkan", tanpa
    petunjuk apa pun bahwa yang salah adalah nomor port.

    Alamat ini juga yang harus didaftarkan pengguna di Google Cloud Console,
    jadi ia ditampilkan apa adanya di halaman Pengaturan.
    """
    from ..config import PORT
    return f"http://127.0.0.1:{PORT}/api/uploads/google/callback"

def _loopback(alamat: str) -> bool:
    """Apakah alamat balik ini menunjuk komputer ini sendiri."""
    from urllib.parse import urlparse

    nama = (urlparse(alamat).hostname or "").lower()
    return nama in ("127.0.0.1", "::1", "localhost")


@contextmanager
def _izinkan_loopback(alamat: str):
    """
    Melonggarkan syarat HTTPS oauthlib, HANYA untuk alamat balik loopback.

    oauthlib menolak menukar kode izin lewat `http://`, dengan pesan
    "(insecure_transport) OAuth 2 MUST utilize https." Aturan itu benar untuk
    aplikasi web, dan salah untuk aplikasi yang dipasang di komputer orang:
    RFC 8252 justru MEWAJIBKAN alamat balik loopback memakai http, karena tidak
    ada otoritas sertifikat yang bisa menerbitkan sertifikat sah untuk
    127.0.0.1. Google sendiri yang menerbitkan jenis klien "Desktop app" dengan
    alamat balik seperti itu.

    Pelonggarannya dipagari dua kali: hanya berlaku untuk alamat loopback, dan
    hanya selama satu penukaran kode. Bila suatu saat OmniClip dijalankan di
    belakang Cloudflare dengan https, syarat aslinya kembali berlaku penuh, dan
    permintaan lain yang kebetulan berjalan bersamaan tidak ikut dilonggarkan
    lebih lama daripada perlu.
    """
    if not _loopback(alamat):
        yield
        return
    sebelum = os.environ.get("OAUTHLIB_INSECURE_TRANSPORT")
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    try:
        yield
    finally:
        if sebelum is None:
            os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)
        else:
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = sebelum


# Nama folder yang dibuat sendiri di Drive bila pengguna tidak memilih tujuan.
DRIVE_FOLDER_NAME = "OmniClip"

_lock = threading.Lock()
# Sesi izin yang sedang berjalan: state -> Flow. Umurnya sepanjang satu
# kunjungan ke halaman izin Google, jadi ia tidak perlu bertahan lintas restart.
_pending: dict[str, Any] = {}


def _fail(message: str, code: str = "GOOGLE_UPLOAD", status: int = 400) -> AppError:
    return AppError(message, code=code, status=status)


def _client_config() -> Optional[dict]:
    """
    Identitas aplikasi Google yang berlaku: milik pemiliknya, lalu bawaan.

    Urutannya disengaja. Berkas yang dipasang sendiri MENANG atas identitas
    bawaan, karena kuota Google dihitung per project: pemilik yang mendaftarkan
    projectnya sendiri mendapat jatah sendiri, dan tidak berbagi dengan semua
    pemakai OmniClip yang lain.
    """
    if CLIENT_SECRET_PATH.is_file():
        try:
            return json.loads(CLIENT_SECRET_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log.warning("Berkas OAuth client tidak terbaca: %s", str(e)[:160])
    from ..config import google_bawaan
    return google_bawaan()


def client_bawaan_dipakai() -> bool:
    """Apakah yang berlaku identitas bawaan, bukan berkas milik pemiliknya."""
    from ..config import google_bawaan
    return not CLIENT_SECRET_PATH.is_file() and google_bawaan() is not None


def client_configured() -> bool:
    return _client_config() is not None


def save_client_secret(raw: str) -> dict:
    """
    Menyimpan berkas OAuth client dari Google Cloud Console.

    Bentuknya diperiksa di sini, bukan dibiarkan gagal nanti saat mengunggah:
    berkas yang salah (misalnya kunci API biasa, atau service account) menghasilkan
    galat OAuth yang tidak menyebutkan sama sekali bahwa berkasnya yang keliru.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise _fail("Berkas itu bukan JSON yang sah.") from e

    section = data.get("installed") or data.get("web")
    if not section or not section.get("client_id") or not section.get("client_secret"):
        raise _fail(
            "Berkas itu bukan OAuth client ID. Di Google Cloud Console pilih "
            "APIs & Services → Credentials → Create credentials → OAuth client ID, "
            "jenis Desktop app atau Web application, lalu unduh JSON-nya."
        )

    CLIENT_SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLIENT_SECRET_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # Rahasia klien tidak boleh terbaca pengguna lain di mesin yang sama.
    os.chmod(CLIENT_SECRET_PATH, 0o600)
    return {"kind": "web" if "web" in data else "installed",
            "redirect_uri_needed": "web" in data}


def _load_credentials(pid: Optional[int] = None, layanan: str = "youtube"):
    """Token tersimpan untuk satu layanan, disegarkan bila sudah kedaluwarsa."""
    TOKEN_PATH = _token_path(pid, layanan)
    if not TOKEN_PATH.is_file():
        return None
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    try:
        creds = Credentials.from_authorized_user_file(
            str(TOKEN_PATH), SCOPES_LAYANAN.get(layanan, SCOPES))
    except Exception:
        return None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _write_token(creds, pid, layanan)
        except Exception as e:
            log.warning("Menyegarkan token Google gagal: %s", e)
            return None
    return creds if creds and creds.valid else None


def _write_token(creds, pid: Optional[int] = None, layanan: str = "youtube") -> None:
    tujuan = _token_path(pid, layanan)
    # Surel akun disimpan di token yang sama; menulis ulang token yang
    # disegarkan tidak boleh menghapusnya.
    payload = json.loads(creds.to_json())
    payload["_omniclip_email"] = _stored_email(pid, layanan)
    tujuan.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.chmod(tujuan, 0o600)


def _stored_email(pid: Optional[int] = None, layanan: str = "youtube") -> str:
    try:
        return json.loads(_token_path(pid, layanan)
                          .read_text(encoding="utf-8")).get("_omniclip_email", "")
    except Exception:
        return ""


def status(pid: Optional[int] = None) -> dict:
    """
    Keadaan tiap layanan, plus ringkasannya.

    `connected` tetap ada dan berarti "ADA yang tersambung", supaya pemanggil
    lama tidak ikut berubah saat izinnya dipisah dua.
    """
    per = {}
    for nama in LAYANAN:
        creds = _load_credentials(pid, nama)
        per[nama] = {"connected": creds is not None,
                     "email": _stored_email(pid, nama) if creds else "",
                     "scopes": SCOPES_LAYANAN[nama]}
    tersambung = [n for n in LAYANAN if per[n]["connected"]]
    return {
        "client_configured": client_configured(),
        # Dari mana identitas aplikasinya datang. Antarmuka memakainya untuk
        # memutuskan apakah langkah "daftarkan aplikasi" masih perlu ditunjukkan.
        "client_bawaan": client_bawaan_dipakai(),
        "connected": bool(tersambung),
        "email": per[tersambung[0]]["email"] if tersambung else "",
        "redirect_uri": redirect_uri(),
        "scopes": SCOPES,
        "layanan": per,
    }


def begin_authorization(layanan: str = "youtube") -> str:
    """
    Alamat halaman izin Google untuk SATU layanan.

    Satu layanan per permintaan, karena Google menolak izin YouTube dan Drive
    yang diminta bersamaan (lihat SCOPES_LAYANAN).
    """
    if layanan not in SCOPES_LAYANAN:
        raise _fail(f"Layanan Google '{layanan}' tidak dikenal.",
                    code="GOOGLE_SERVICE_UNKNOWN", status=422)
    if not client_configured():
        raise _fail("Pasang dulu berkas OAuth client dari Google Cloud Console.",
                    code="GOOGLE_CLIENT_MISSING")
    from google_auth_oauthlib.flow import Flow

    # `from_client_config`, bukan `from_client_secrets_file`: identitasnya bisa
    # datang dari berkas yang dipasang pemiliknya ATAU dari bawaan aplikasi,
    # dan yang kedua tidak pernah ditulis ke cakram.
    flow = Flow.from_client_config(
        _client_config(), scopes=SCOPES_LAYANAN[layanan],
        redirect_uri=redirect_uri(), autogenerate_code_verifier=True)
    # access_type=offline + prompt=consent memaksa Google mengirim refresh
    # token. Tanpa keduanya, izin kedua dan seterusnya datang tanpa refresh
    # token dan sambungannya putus diam-diam sejam kemudian.
    # Akun yang sudah tersambung untuk LAYANAN LAIN di profil ini. Dipakai dua
    # kali di bawah: memberi tahu Google akun mana yang dimaksud, dan memutuskan
    # apakah pemiliknya masih perlu ditanya "akun yang mana".
    from . import profil as _profil
    pid_kini = _profil.kini()
    sudah = next((_stored_email(pid_kini, n) for n in LAYANAN
                  if n != layanan and _stored_email(pid_kini, n)), "")

    tambahan = {}
    if sudah:
        # Menyambungkan layanan kedua untuk akun yang sama: Google langsung
        # menuju akun itu, jadi yang tersisa cuma satu tekan "izinkan".
        tambahan["login_hint"] = sudah
        aba = "consent"
    else:
        # select_account: tiap profil menyambungkan akun Google-nya sendiri.
        # Tanpa ini Google langsung memakai akun yang sedang masuk di peramban,
        # dan profil kedua diam-diam tersambung ke akun yang sama.
        aba = "select_account consent"

    url, state = flow.authorization_url(
        # include_granted_scopes SENGAJA dimatikan.
        #
        # Nilainya "true" dulu, dan itulah yang membuat "Sambungkan Drive"
        # tetap ditolak walau permintaannya sudah dipisah: dengan nyala, Google
        # MENGGABUNGKAN izin yang sudah pernah diberikan ke dalam permintaan
        # baru. Jadi begitu YouTube tersambung, permintaan Drive berikutnya
        # diam-diam kembali memuat youtube.upload, dan Google menolaknya dengan
        # galat yang sama persis seperti sebelum dipisah. Tiap layanan memang
        # punya tokennya sendiri di sini, jadi penggabungan itu tidak dibutuhkan
        # sama sekali.
        access_type="offline", include_granted_scopes="false",
        prompt=aba, **tambahan)
    from . import profil
    with _lock:
        # Beberapa profil bisa sedang menyambung bersamaan (dua tab); yang
        # lama dibuang setelah 15 menit, bukan setiap kali ada yang baru.
        batas = time.time() - 900
        for k in [k for k, v in _pending.items() if v[2] < batas]:
            _pending.pop(k, None)
        # Profil peminta diingat bersama sesinya: halaman balik dari Google
        # tidak membawa header profil.
        _pending[state] = (flow, profil.kini(), time.time(), layanan)
    return url


def finish_authorization(full_url: str, state: str) -> tuple[str, int]:
    """
    Menukar kode izin jadi token. Mengembalikan (alamat surel, id profil).

    Profilnya ikut dikembalikan karena pemanggilnya perlu tahu akun SIAPA yang
    baru saja tersambung — halaman balik dari Google tidak membawa header
    profil, jadi menebaknya di sana akan selalu menunjuk profil pertama.
    """
    with _lock:
        tunggu = _pending.pop(state, None)
    if tunggu is None:
        raise _fail("Sesi izin sudah kedaluwarsa. Mulai lagi dari Pengaturan.")
    flow, pid, _, layanan = tunggu

    with _izinkan_loopback(redirect_uri()):
        flow.fetch_token(authorization_response=full_url)
    creds = flow.credentials

    email = ""
    try:
        from googleapiclient.discovery import build
        info = build("oauth2", "v2", credentials=creds,
                     cache_discovery=False).userinfo().get().execute()
        email = info.get("email", "")
    except Exception as e:
        log.info("Alamat surel akun tidak terbaca: %s", e)

    payload = json.loads(creds.to_json())
    payload["_omniclip_email"] = email
    tujuan = _token_path(pid, layanan)
    tujuan.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.chmod(tujuan, 0o600)
    return email, pid


def disconnect(pid: Optional[int] = None, layanan: Optional[str] = None) -> None:
    """Memutus satu layanan, atau semuanya bila tidak disebut."""
    for nama in ([layanan] if layanan else LAYANAN):
        _token_path(pid, nama).unlink(missing_ok=True)


# Layanan Google mana yang dipakai tiap API.
_LAYANAN_API = {"youtube": "youtube", "drive": "drive", "oauth2": "youtube"}


def _require_credentials(layanan: str = "youtube"):
    creds = _load_credentials(None, layanan)
    if creds is None:
        nama = "YouTube" if layanan == "youtube" else "Drive"
        raise _fail(f"{nama} belum tersambung. Sambungkan dulu di halaman Akun.",
                    code="GOOGLE_NOT_CONNECTED", status=409)
    return creds


def _service(name: str, version: str):
    from googleapiclient.discovery import build
    layanan = _LAYANAN_API.get(name, "youtube")
    return build(name, version, credentials=_require_credentials(layanan),
                 cache_discovery=False)


def _resumable_upload(request, on_progress: Optional[Callable[[float], None]],
                      should_cancel: Optional[Callable[[], bool]]) -> dict:
    """
    Menjalankan unggahan yang bisa dilanjutkan, sambil melaporkan kemajuannya.

    Bukan `execute()` biasa: berkas klip berukuran puluhan megabita, dan pada
    sambungan rumahan satu unggahan bisa memakan menit. Tanpa potongan, satu
    gangguan jaringan di menit terakhir membatalkan semuanya, dan pengguna
    melihat bilah diam tanpa tahu apa yang sedang terjadi.
    """
    response = None
    while response is None:
        if should_cancel and should_cancel():
            raise _fail("Unggahan dibatalkan.", code="CANCELLED", status=499)
        chunk, response = request.next_chunk()
        if chunk and on_progress:
            on_progress(chunk.progress())
    return response


def _drive_folder_id(service) -> str:
    """Folder OmniClip di Drive, dibuat sekali lalu dipakai ulang."""
    q = ("mimeType='application/vnd.google-apps.folder' and trashed=false and "
         f"name='{DRIVE_FOLDER_NAME}'")
    found = service.files().list(q=q, spaces="drive", fields="files(id)",
                                 pageSize=1).execute().get("files", [])
    if found:
        return found[0]["id"]
    created = service.files().create(
        body={"name": DRIVE_FOLDER_NAME,
              "mimeType": "application/vnd.google-apps.folder"},
        fields="id").execute()
    return created["id"]


def upload_to_drive(path: Path, *, title: str = "",
                    folder_id: str = "",
                    on_progress: Optional[Callable[[float], None]] = None,
                    should_cancel: Optional[Callable[[], bool]] = None) -> dict:
    from googleapiclient.http import MediaFileUpload

    service = _service("drive", "v3")
    parent = folder_id or _drive_folder_id(service)
    media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True,
                            chunksize=4 * 1024 * 1024)
    request = service.files().create(
        body={"name": title or path.name, "parents": [parent]},
        media_body=media, fields="id,webViewLink")
    result = _resumable_upload(request, on_progress, should_cancel)
    return {
        "remote_id": result["id"],
        "remote_url": result.get("webViewLink")
                      or f"https://drive.google.com/file/d/{result['id']}/view",
    }


# YouTube menolak apa pun di luar tiga nilai ini, dengan galat yang tidak
# menyebutkan nilai mana yang salah.
YOUTUBE_PRIVACY = ("private", "unlisted", "public")


def upload_to_youtube(path: Path, *, title: str, description: str = "",
                      tags: Optional[list[str]] = None,
                      privacy: str = "private",
                      on_progress: Optional[Callable[[float], None]] = None,
                      should_cancel: Optional[Callable[[], bool]] = None) -> dict:
    from googleapiclient.http import MediaFileUpload

    if privacy not in YOUTUBE_PRIVACY:
        privacy = "private"

    service = _service("youtube", "v3")
    body = {
        "snippet": {
            # Batas keras YouTube: 100 karakter judul, 5000 deskripsi. Dipotong
            # di sini supaya kegagalannya tidak datang sebagai galat API yang
            # tidak jelas setelah berkasnya selesai terkirim.
            "title": (title or path.stem)[:100],
            "description": description[:5000],
            "tags": [t[:30] for t in (tags or [])][:15],
            "categoryId": "22",          # People & Blogs
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True,
                            chunksize=4 * 1024 * 1024)
    request = service.videos().insert(part="snippet,status", body=body,
                                      media_body=media)
    result = _resumable_upload(request, on_progress, should_cancel)
    vid = result["id"]
    return {"remote_id": vid, "remote_url": f"https://www.youtube.com/watch?v={vid}"}


def explain_error(exc: Exception) -> str:
    """
    Galat pustaka Google -> kalimat yang menyebut jalan keluarnya.

    Tanpa ini pengguna menerima jejak HttpError beserta seluruh badan JSON
    Google, yang tidak memberi tahu bahwa yang perlu dilakukan adalah
    mengaktifkan satu API di Cloud Console.
    """
    text = str(exc)
    low = text.lower()

    if "quotaexceeded" in low.replace(" ", "") or "quota" in low:
        return ("Kuota harian Google untuk akun ini habis. Kuota unggah YouTube "
                "lewat API terbatas per hari dan pulih otomatis besok.")
    if "uploadlimitexceeded" in low.replace(" ", ""):
        return ("YouTube membatasi jumlah unggahan kanal ini untuk hari ini. "
                "Coba lagi besok.")
    if "has not been used in project" in low or "accessnotconfigured" in low.replace(" ", ""):
        return ("API-nya belum diaktifkan di project Google Cloud Anda. Buka "
                "Cloud Console → APIs & Services → Library, lalu aktifkan "
                "YouTube Data API v3 dan Google Drive API.")
    if "insufficient" in low and "scope" in low:
        return ("Izin akun kurang. Putuskan sambungan di Pengaturan lalu "
                "sambungkan ulang, dan centang semua izin yang diminta.")
    if "invalid_grant" in low:
        return ("Izin akun sudah dicabut atau kedaluwarsa. Sambungkan ulang "
                "akun Google di Pengaturan.")
    if "youtubesignuprequired" in low.replace(" ", ""):
        return ("Akun Google ini belum punya kanal YouTube. Buat kanalnya dulu "
                "di youtube.com, lalu coba lagi.")
    return text[:400]
