"""
Project klip: daftar video yang sedang atau sudah diproses, plus data timeline.

Halaman Studio menampilkan ini sebagai kartu. Pengguna bisa menekan "Clip" pada
beberapa video berturut-turut lalu kembali menonton; pekerjaannya berjalan di
antrean, dan kartunya menunjukkan kemajuan masing-masing.
"""

import asyncio

from fastapi import APIRouter, Query

from ..errors import AppError, NotFound
from ..repos import analyses as analyses_repo
from ..repos import projects as projects_repo
from ..services.paths import extract_youtube_id, find_local_video

router = APIRouter(prefix="/api", tags=["projects"])


def _resolve(video_id: str) -> str:
    vid = extract_youtube_id(video_id) or (video_id if len(video_id) == 11 else "")
    if not vid:
        raise NotFound("Video tidak dikenali.")
    return vid


@router.get("/projects")
async def list_projects(limit: int = Query(60, le=200)):
    return await asyncio.to_thread(projects_repo.list_projects, limit)


@router.get("/projects/{video_id}")
async def get_project(video_id: str):
    """Semua yang dibutuhkan halaman editor dalam satu permintaan."""
    vid = _resolve(video_id)
    cached = await asyncio.to_thread(analyses_repo.latest_for_video, vid)
    if not cached:
        raise NotFound("Belum ada analisis untuk video ini.")

    result = cached["result"]

    # Penanda non-ucapan ("[Musik]", "[Tertawa]") dibersihkan saat dibaca, bukan
    # hanya saat analisis baru dibuat, supaya project yang sudah tersimpan ikut
    # membaik tanpa perlu dianalisis ulang.
    from ..services.clipmodel import sanitize_caption_lines
    result = {**result, "clips": [
        {**c, "subtitles": sanitize_caption_lines(c.get("subtitles") or [])}
        for c in (result.get("clips") or [])
    ]}

    local = find_local_video(vid)
    return {
        "video_id": vid,
        "analysis_id": cached["id"],
        "created_at": cached["created_at"],
        # local_url ikut dihitung ulang di sini, bukan hanya dibaca dari hasil
        # tersimpan: file bisa saja sudah dihapus sejak analisis dibuat.
        "local_url": f"/api/media/local_downloads/{local.name}" if local else None,
        "downloaded": local is not None,
        **result,
    }


@router.delete("/projects/{video_id}")
async def delete_project(video_id: str):
    vid = _resolve(video_id)
    await asyncio.to_thread(analyses_repo.delete_for_video, vid)
    return {"success": True, "video_id": vid}


@router.get("/videos/{video_id}/waveform")
async def waveform(video_id: str, bins: int = Query(1200, ge=100, le=4000)):
    """
    Puncak amplitudo untuk digambar di timeline.

    Dihitung sekali lalu di-cache: satu pass ffmpeg atas podcast 75 menit
    memakan beberapa detik, dan timeline memintanya setiap kali editor dibuka.
    """
    vid = _resolve(video_id)
    cached = await asyncio.to_thread(projects_repo.get_waveform, vid, bins)
    if cached:
        return {"video_id": vid, "bins": len(cached), "peaks": cached, "cached": True}

    source = find_local_video(vid)
    if source is None:
        raise AppError("Video belum diunduh, gelombang suara belum bisa dibuat.",
                       code="SOURCE_NOT_DOWNLOADED", status=409)

    from ..services.media import probe, waveform_peaks

    info = await asyncio.to_thread(probe, source)
    duration = float(info.get("duration") or 0)
    peaks = await asyncio.to_thread(waveform_peaks, source, bins=bins, duration=duration)
    if peaks:
        await asyncio.to_thread(projects_repo.save_waveform, vid, bins, peaks, duration)
    return {"video_id": vid, "bins": len(peaks), "peaks": peaks,
            "duration": duration, "cached": False}
