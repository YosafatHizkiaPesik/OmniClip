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
from pathlib import Path
from typing import Any, Callable, Optional

from ..config import STORAGE_DIR
from ..errors import AppError

log = logging.getLogger("omniclip.upload")

CLIENT_SECRET_PATH = STORAGE_DIR / "google_client_secret.json"
TOKEN_PATH = STORAGE_DIR / "google_token.json"

# Cakupan sekecil mungkin yang masih menyelesaikan pekerjaannya.
#
# drive.file memberi akses HANYA ke berkas yang dibuat aplikasi ini sendiri —
# bukan ke seluruh Drive. youtube.upload hanya bisa mengunggah, tidak bisa
# membaca atau menghapus video yang sudah ada di kanal.
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/youtube.upload",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

REDIRECT_URI = "http://127.0.0.1:8000/api/uploads/google/callback"

# Nama folder yang dibuat sendiri di Drive bila pengguna tidak memilih tujuan.
DRIVE_FOLDER_NAME = "OmniClip"

_lock = threading.Lock()
# Sesi izin yang sedang berjalan: state -> Flow. Umurnya sepanjang satu
# kunjungan ke halaman izin Google, jadi ia tidak perlu bertahan lintas restart.
_pending: dict[str, Any] = {}


def _fail(message: str, code: str = "GOOGLE_UPLOAD", status: int = 400) -> AppError:
    return AppError(message, code=code, status=status)


def client_configured() -> bool:
    return CLIENT_SECRET_PATH.is_file()


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


def _load_credentials():
    """Token tersimpan, disegarkan bila sudah kedaluwarsa."""
    if not TOKEN_PATH.is_file():
        return None
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    except Exception:
        return None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _write_token(creds)
        except Exception as e:
            log.warning("Menyegarkan token Google gagal: %s", e)
            return None
    return creds if creds and creds.valid else None


def _write_token(creds) -> None:
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    os.chmod(TOKEN_PATH, 0o600)


def _stored_email() -> str:
    try:
        return json.loads(TOKEN_PATH.read_text(encoding="utf-8")).get("_omniclip_email", "")
    except Exception:
        return ""


def status() -> dict:
    creds = _load_credentials()
    return {
        "client_configured": client_configured(),
        "connected": creds is not None,
        "email": _stored_email() if creds else "",
        "redirect_uri": REDIRECT_URI,
        "scopes": SCOPES,
    }


def begin_authorization() -> str:
    """Mengembalikan alamat halaman izin Google untuk dibuka pengguna."""
    if not client_configured():
        raise _fail("Pasang dulu berkas OAuth client dari Google Cloud Console.",
                    code="GOOGLE_CLIENT_MISSING")
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH), scopes=SCOPES, redirect_uri=REDIRECT_URI)
    # access_type=offline + prompt=consent memaksa Google mengirim refresh
    # token. Tanpa keduanya, izin kedua dan seterusnya datang tanpa refresh
    # token dan sambungannya putus diam-diam sejam kemudian.
    url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent")
    with _lock:
        _pending.clear()
        _pending[state] = flow
    return url


def finish_authorization(full_url: str, state: str) -> str:
    """Menukar kode izin jadi token. Mengembalikan alamat surel akunnya."""
    with _lock:
        flow = _pending.pop(state, None)
    if flow is None:
        raise _fail("Sesi izin sudah kedaluwarsa. Mulai lagi dari Pengaturan.")

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
    TOKEN_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.chmod(TOKEN_PATH, 0o600)
    return email


def disconnect() -> None:
    TOKEN_PATH.unlink(missing_ok=True)


def _require_credentials():
    creds = _load_credentials()
    if creds is None:
        raise _fail("Akun Google belum tersambung. Sambungkan dulu di Pengaturan.",
                    code="GOOGLE_NOT_CONNECTED", status=409)
    return creds


def _service(name: str, version: str):
    from googleapiclient.discovery import build
    return build(name, version, credentials=_require_credentials(),
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
