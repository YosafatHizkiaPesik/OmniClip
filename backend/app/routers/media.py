"""Penyajian file media. Menggantikan mount StaticFiles('/storage')."""

import mimetypes

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..services.paths import safe_media_path

router = APIRouter(prefix="/api", tags=["media"])


@router.get("/media/{category}/{filename}")
async def stream_media(category: str, filename: str):
    """
    Pemutaran inline. Starlette FileResponse menangani HTTP Range, jadi seeking
    pada elemen <video> tetap bekerja tanpa perlu mount statis.
    """
    path = safe_media_path(category, filename)
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(path=path, media_type=media_type or "application/octet-stream")


@router.get("/file/{category}/{filename}")
async def download_file(category: str, filename: str):
    """Unduh paksa (Content-Disposition: attachment)."""
    path = safe_media_path(category, filename)
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )
