"""
Unggah klip ke Google Drive dan YouTube.

Satu per satu, tidak pernah berombongan: antreannya berjalan di lane `upload`
yang lebarnya satu, dan untuk YouTube ada jeda tambahan antar unggahan yang
berhasil. Mengirim selusin klip ke satu kanal beruntun adalah persis pola yang
membuat kanal ditandai, dan itu bukan risiko yang boleh diambil aplikasi ini
atas nama penggunanya.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..config import UPLOAD_GAP_SECONDS
from ..errors import AppError
from ..repos import uploads as uploads_repo
from ..services import google_upload as google
from ..services.jobs import queue
from ..services.paths import safe_media_path

log = logging.getLogger("omniclip.uploads")
router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.get("/google/status")
async def google_status():
    st = google.status()
    st["gap_seconds"] = UPLOAD_GAP_SECONDS
    return st


@router.post("/google/client")
async def set_client(payload: str = Body(..., media_type="text/plain")):
    """Menerima isi berkas OAuth client apa adanya, bukan jalur berkasnya."""
    return google.save_client_secret(payload)


@router.post("/google/connect")
async def connect():
    return {"authorization_url": google.begin_authorization()}


@router.get("/google/callback", response_class=HTMLResponse)
async def callback(request: Request, state: str = "", error: str = ""):
    """
    Google mengembalikan pengguna ke sini setelah halaman izin.

    Yang dikirim balik adalah halaman kecil, bukan JSON: yang membacanya adalah
    orang di dalam tab browser, bukan program.
    """
    if error:
        return _page("Izin ditolak", f"Google menjawab: {error}", ok=False)
    try:
        email = google.finish_authorization(str(request.url), state)
    except AppError as e:
        return _page("Gagal menyambungkan", e.message, ok=False)
    except Exception as e:  # noqa: BLE001 — halaman ini tidak boleh 500
        log.exception("Callback OAuth gagal")
        return _page("Gagal menyambungkan", google.explain_error(e), ok=False)
    return _page("Akun tersambung",
                 f"{email or 'Akun Google'} siap dipakai. Tutup tab ini dan "
                 "kembali ke OmniClip.", ok=True)


def _page(title: str, body: str, *, ok: bool) -> HTMLResponse:
    colour = "#07683B" if ok else "#B3182C"
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'>"
        "<title>OmniClip</title>"
        "<body style=\"margin:0;display:grid;place-items:center;min-height:100vh;"
        "font:16px/1.6 system-ui,sans-serif;background:#EDF1F6;color:#0E1420\">"
        f"<div style='max-width:420px;padding:28px;text-align:center'>"
        f"<h1 style='margin:0 0 8px;font-size:1.3rem;color:{colour}'>{title}</h1>"
        f"<p style='margin:0;color:#46536A'>{body}</p></div></body>",
        status_code=200 if ok else 400,
    )


@router.post("/google/disconnect")
async def disconnect():
    google.disconnect()
    return {"status": "ok"}


class UploadRequest(BaseModel):
    clip_name: str
    target: str = Field("drive", pattern="^(drive|youtube)$")
    title: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    privacy: str = Field("private", pattern="^(private|unlisted|public)$")
    folder_id: str = ""


@router.post("", status_code=202)
async def start_upload(req: UploadRequest):
    """
    Mengantrekan satu unggahan.

    Satu klip per permintaan. Tidak ada bentuk jamaknya, dan itu disengaja:
    antarmuka yang menerima daftar akan membuat "unggah semua" terasa seperti
    satu tombol yang wajar, padahal itu justru yang harus dihindari.
    """
    if not google.status()["connected"]:
        raise AppError("Akun Google belum tersambung. Sambungkan dulu di Pengaturan.",
                       code="GOOGLE_NOT_CONNECTED", status=409)

    # Memastikan klipnya ada SEBELUM barisnya dicatat, supaya riwayat tidak
    # terisi baris gagal untuk nama berkas yang salah ketik.
    safe_media_path("edited_clips", req.clip_name)

    # Baris riwayat dibuat LEBIH DULU supaya id-nya sudah ada di dalam muatan
    # saat pekerja mengambilnya. Kalau urutannya dibalik, ada celah di mana job
    # sudah berjalan sementara baris yang harus dituliskannya belum ada.
    upload_id = uploads_repo.create(
        clip_name=req.clip_name, target=req.target,
        title=req.title, privacy=req.privacy, job_id="")

    job_id, created = queue.enqueue(
        "upload",
        {
            "clip_name": req.clip_name,
            "target": req.target,
            "title": req.title,
            "description": req.description,
            "tags": req.tags,
            "privacy": req.privacy,
            "folder_id": req.folder_id,
            "upload_id": upload_id,
        },
        # Satu klip tidak boleh naik dua kali ke tujuan yang sama hanya karena
        # tombolnya tertekan dua kali.
        dedupe_key=f"upload:{req.target}:{req.clip_name}",
    )

    if created:
        uploads_repo.attach_job(upload_id, job_id)
    else:
        # Permintaannya bergabung ke job yang sudah antre; barisnya tidak jadi
        # dipakai dan tidak boleh tertinggal sebagai unggahan yang menggantung.
        uploads_repo.drop(upload_id)

    return {"job_id": job_id, "created": created}


@router.get("")
async def list_uploads(clip_name: Optional[str] = None, limit: int = 60):
    return {"uploads": uploads_repo.list_recent(min(limit, 200), clip_name)}
