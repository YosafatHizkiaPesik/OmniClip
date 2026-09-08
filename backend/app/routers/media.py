"""Penyajian file media. Menggantikan mount StaticFiles('/storage')."""

import mimetypes

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..config import FONTS_DIR
from ..errors import NotFound
from ..services.paths import safe_media_path
from ..services.subtitles import BUNDLED_FONTS, FONT_FILES

router = APIRouter(prefix="/api", tags=["media"])


@router.get("/fonts")
async def list_fonts():
    """
    Font display yang dibundel bersama aplikasi.

    Dipakai frontend untuk memasang @font-face, sehingga pratinjau memakai font
    yang PERSIS sama dengan yang dibakar libass ke dalam video. Tanpa ini,
    mengganti font tidak mengubah apa pun di layar sampai render selesai.
    """
    return {"fonts": [{**f, "url": f"/api/fonts/{f['file']}"}
                      for f in BUNDLED_FONTS
                      if (FONTS_DIR / f["file"]).is_file()]}


@router.get("/fonts/{filename}")
async def get_font(filename: str):
    """Berkas font. Hanya nama yang ada di daftar bundel yang dilayani."""
    if filename not in FONT_FILES:
        raise NotFound("Font tidak dikenali.")
    path = FONTS_DIR / filename
    if not path.is_file():
        raise NotFound("Berkas font tidak ada.")
    return FileResponse(path=path, media_type="font/ttf",
                        headers={"Cache-Control": "public, max-age=604800"})


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
