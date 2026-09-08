"""Analisis auto-clip dan render klip."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..errors import NotFound
from ..repos import analyses as analyses_repo
from ..services.jobs import queue
from ..services.paths import (
    extract_id_from_filename,
    extract_youtube_id,
    safe_media_path,
)
from ..services.render import list_local_clips

router = APIRouter(prefix="/api", tags=["clips"])


class AutoClipRequest(BaseModel):
    video_id: str = Field(..., description="ID atau URL YouTube")
    quality: str = "720p"
    whisper_model: str = "base"
    max_clips: int = 8
    use_gemini: bool = True
    force: bool = False  # abaikan hasil analisis yang sudah tersimpan


class SegmentModel(BaseModel):
    start: float
    end: float


class CaptionStyleModel(BaseModel):
    """Gaya teks dari UI. Semua nilai di sini benar-benar sampai ke ffmpeg."""
    size: Optional[int] = None
    primary: Optional[str] = None
    highlight: Optional[str] = None
    position: Optional[str] = None
    uppercase: Optional[bool] = None
    animation: Optional[str] = None
    font: Optional[str] = None


class RenderClipRequest(BaseModel):
    # Referensi video, bukan path filesystem: klien tidak menentukan file mana
    # yang dibuka server.
    source_path: str
    # Klip bisa terdiri dari beberapa potongan yang disambung — misalnya menit 10
    # digabung dengan menit 50. Bila kosong, start/end dipakai sebagai satu segmen.
    segments: Optional[List[SegmentModel]] = None
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    subtitles: Optional[List[Dict[str, Any]]] = None
    aspect_ratio: str = "9:16"
    font_color: str = "yellow"
    font_size: int = 24
    position: str = "bottom"
    hook_text: str = ""
    watermark: str = ""
    video_filter: str = "normal"
    # smart = ikuti wajah pembicara, blur = bilah kabur, center = crop tengah.
    frame_mode: str = "smart"
    caption_style: Optional[CaptionStyleModel] = None


def _resolve_video_id(reference: str) -> str:
    vid = extract_youtube_id(reference) or extract_id_from_filename(reference)
    if not vid:
        raise NotFound("Video sumber tidak dikenali.")
    return vid


@router.post("/auto-clip", status_code=202)
async def start_auto_clip(req: AutoClipRequest):
    """
    Mengantrekan pipeline auto-clip lengkap dan mengembalikan job_id.

    Frontend mengikuti progres lewat SSE di /api/jobs/{id}/events. Seluruh teks
    tahapan datang dari server — tidak ada progres yang disimulasikan di klien.
    """
    video_id = _resolve_video_id(req.video_id)

    if not req.force:
        cached = analyses_repo.latest_for_video(video_id)
        # Hasil tersimpan hanya dipakai bila jumlah klipnya memang mencukupi
        # permintaan; kalau tidak, analisis diulang. Tanpa syarat ini, meminta
        # 8 klip akan diam-diam mengembalikan 3 klip dari analisis sebelumnya.
        if cached and len(cached["result"].get("clips") or []) >= req.max_clips:
            return {"job_id": None, "cached": True, "result": cached["result"]}
        if cached and cached["result"].get("has_transcript") is False:
            return {"job_id": None, "cached": True, "result": cached["result"]}

    job_id, created = queue.enqueue(
        "auto_clip",
        {
            "video_id": video_id,
            "quality": req.quality,
            "whisper_model": req.whisper_model,
            "max_clips": req.max_clips,
            "use_gemini": req.use_gemini,
        },
        video_id=video_id,
        dedupe_key=f"auto_clip:{video_id}",
    )
    return {"job_id": job_id, "created": created, "cached": False, "video_id": video_id}


@router.get("/analysis/{video_id}")
async def get_analysis(video_id: str):
    cached = analyses_repo.latest_for_video(_resolve_video_id(video_id))
    if not cached:
        raise NotFound("Belum ada analisis untuk video ini.")
    return cached["result"]


class ClipPreviewRequest(BaseModel):
    video_id: str
    segments: List[SegmentModel]


@router.post("/clip-preview")
async def clip_preview(req: ClipPreviewRequest):
    """
    Menghitung ulang subtitle setelah pengguna menggeser batas klip atau
    menggabungkan potongan dari menit lain.

    Perhitungannya hanya ada di satu tempat (backend) supaya subtitle yang
    dilihat di preview persis sama dengan yang nanti dibakar ke video.
    """
    from ..repos import transcripts as tx_repo
    from ..services.clipmodel import rebuild_subtitles_for_segments

    video_id = _resolve_video_id(req.video_id)
    stored = tx_repo.get_best(video_id)
    if not stored:
        raise NotFound("Video ini belum punya transkrip.")

    segments = [{"start": s.start, "end": s.end} for s in req.segments
                if s.end - s.start > 0.2]
    if not segments:
        raise NotFound("Rentang klip tidak valid.")

    subtitles, words = rebuild_subtitles_for_segments(segments, stored["words"])
    return {
        "segments": segments,
        "duration": round(sum(s["end"] - s["start"] for s in segments), 3),
        "subtitles": subtitles,
        "words": words,
    }


@router.post("/render-clip", status_code=202)
async def render_clip(req: RenderClipRequest):
    """Mengantrekan render dan mengembalikan job_id untuk dipantau lewat SSE."""
    video_id = _resolve_video_id(req.source_path)

    segments = (
        [{"start": s.start, "end": s.end} for s in req.segments]
        if req.segments
        else [{"start": req.start_seconds, "end": req.end_seconds}]
    )
    segments = [s for s in segments if s["end"] - s["start"] > 0.2]
    if not segments:
        raise NotFound("Rentang klip tidak valid.")

    job_id, created = queue.enqueue(
        "render",
        {
            "video_id": video_id,
            "segments": segments,
            "subtitles": req.subtitles,
            "aspect_ratio": req.aspect_ratio,
            "font_color": req.font_color,
            "font_size": req.font_size,
            "position": req.position,
            "hook_text": req.hook_text,
            "watermark": req.watermark,
            "video_filter": req.video_filter,
            "frame_mode": req.frame_mode,
            "caption_style": (req.caption_style.model_dump(exclude_none=True)
                              if req.caption_style else None),
        },
        video_id=video_id,
    )
    return {"job_id": job_id, "created": created, "video_id": video_id}


@router.get("/clips")
async def get_clips():
    clips = list_local_clips()
    for c in clips:
        c["web_url"] = f"/api/media/edited_clips/{c['file_name']}"
    return {"local_clips": clips}


@router.delete("/clips/{filename}")
async def delete_clip(filename: str):
    path = safe_media_path("edited_clips", filename)
    path.unlink()
    sidecar = path.with_suffix(".json")
    if sidecar.exists():
        sidecar.unlink()
    return {"success": True, "file_name": path.name}
