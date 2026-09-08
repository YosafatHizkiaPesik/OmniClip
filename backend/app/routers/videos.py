"""Pencarian YouTube, metadata video, dan unduhan."""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ..errors import AppError, NotFound
from ..repos import media as media_repo
from ..services.jobs import queue
from ..services.paths import extract_youtube_id, find_local_video, safe_media_path
from ..services.ytdlp import (
    YtdlpError,
    get_video_info,
    list_local_downloads,
    search_youtube_videos,
)

router = APIRouter(prefix="/api", tags=["videos"])


def _as_app_error(exc: YtdlpError) -> AppError:
    status = {
        "YTDLP_RATE_LIMIT": 429,
        "YTDLP_UNAVAILABLE": 404,
        "YTDLP_PRIVATE": 404,
    }.get(exc.code, 502)
    return AppError(exc.message, code=exc.code, status=status, detail=exc.original)


class DownloadRequest(BaseModel):
    url: str = Field(..., description="ID atau URL YouTube")
    resolution: str = "720p"


@router.get("/search")
async def search(q: str = Query(..., description="Kata kunci pencarian"), limit: int = 20):
    if not q.strip():
        return []
    try:
        return search_youtube_videos(q, min(limit, 50))
    except YtdlpError as e:
        raise _as_app_error(e) from e


@router.get("/trending")
async def trending(limit: int = 20):
    """Rekomendasi beranda. Fase 7 menggantinya dengan feed bersection."""
    try:
        return search_youtube_videos("podcast indonesia terbaru", min(limit, 50))
    except YtdlpError as e:
        raise _as_app_error(e) from e


@router.get("/video-info")
async def video_info(url: str = Query(...)):
    video_id = extract_youtube_id(url)
    if not video_id:
        raise NotFound("ID video YouTube tidak dikenali.")
    try:
        info = get_video_info(video_id)
    except YtdlpError as e:
        raise _as_app_error(e) from e
    media_repo.upsert_video(info)
    local = find_local_video(video_id)
    info["downloaded"] = local is not None
    info["local_url"] = f"/api/media/local_downloads/{local.name}" if local else None
    return info


@router.post("/download", status_code=202)
async def start_download(req: DownloadRequest):
    """
    Mengantrekan unduhan dan langsung mengembalikan job_id.

    Unduhan bisa berjalan beberapa menit; menahannya di dalam request berarti
    tanpa progress, tanpa pembatalan, dan tanpa cara memulihkan setelah reload.
    """
    video_id = extract_youtube_id(req.url)
    if not video_id:
        raise NotFound("ID video YouTube tidak dikenali.")

    job_id, created = queue.enqueue(
        "download",
        {"video_id": video_id, "resolution": req.resolution},
        video_id=video_id,
        dedupe_key=f"download:{video_id}:{req.resolution}",
    )
    return {"job_id": job_id, "created": created, "video_id": video_id}


@router.get("/downloads")
async def downloads():
    """
    Daftar file di local_downloads/, digabung dengan metadata dari database
    bila ada. File yang diunduh sebelum database ada tetap tampil.
    """
    by_name = {}
    for row in media_repo.list_downloads():
        by_name[row["rel_path"].split("/")[-1]] = row

    files = list_local_downloads()
    for f in files:
        f["web_url"] = f"/api/media/local_downloads/{f['file_name']}"
        meta = by_name.get(f["file_name"])
        if meta:
            f.update({
                "download_id": meta["id"],
                "video_id": meta["video_id"],
                "width": meta["width"],
                "height": meta["height"],
                "resolution": f"{meta['height']}p" if meta["height"] else None,
                "duration": meta["duration"],
            })
    return files


@router.delete("/downloads/{filename}")
async def delete_download(filename: str):
    path = safe_media_path("local_downloads", filename)
    rel = f"local_downloads/{path.name}"
    path.unlink()
    media_repo.delete_download_row(rel)
    return {"success": True, "file_name": path.name}
