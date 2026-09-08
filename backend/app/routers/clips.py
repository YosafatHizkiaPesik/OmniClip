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
    # 0 = biarkan sistem menghitungnya dari durasi video. Angka tetap 8 dulu
    # memperlakukan podcast dua jam sama dengan video sepuluh menit.
    max_clips: int = 0
    # short / medium / long — menentukan rentang durasi klip yang dicari.
    clip_length: str = "medium"
    # Perkiraan penutur dari warna suara. Menambah ~15 detik pada video panjang.
    diarize: bool = True
    speakers: Optional[int] = None      # None = tebak sendiri
    use_gemini: bool = True
    # Nama model Gemini pilihan pengguna; kosong = pakai urutan bawaan.
    gemini_model: Optional[str] = None
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
    # Jarak teks dari tepi yang dijadikan jangkar, dalam piksel pada kanvas
    # setinggi 1920. Diisi saat pengguna menyeret subtitle di pratinjau.
    margin_v: Optional[int] = None
    outline_px: Optional[int] = None
    # Warna untuk penutur ke-2 dan seterusnya (penutur pertama pakai `primary`).
    speaker_colors: Optional[List[str]] = None


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
    # Judul di atas video mati secara bawaan: hasilnya lebih bersih, dan hook
    # yang dihasilkan otomatis sering kalah bagus dari klipnya sendiri.
    show_hook: bool = False
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
        if cached:
            if cached["result"].get("has_transcript") is False:
                return {"job_id": None, "cached": True, "result": cached["result"]}
            # Hasil tersimpan hanya dipakai bila jumlah klipnya memang mencukupi
            # permintaan; kalau tidak, analisis diulang. Tanpa syarat ini,
            # meminta 8 klip akan diam-diam mengembalikan 3 klip dari analisis
            # sebelumnya. Untuk permintaan otomatis, targetnya dihitung dari
            # durasi yang tercatat di analisis itu sendiri — sehingga analisis
            # lama yang dipatok 8 klip ikut diperbarui pada video panjang.
            from ..services.heuristics import auto_clip_count
            want = req.max_clips or auto_clip_count(
                float(cached["result"].get("duration") or 0))
            if len(cached["result"].get("clips") or []) >= want:
                return {"job_id": None, "cached": True, "result": cached["result"]}

    job_id, created = queue.enqueue(
        "auto_clip",
        {
            "video_id": video_id,
            "quality": req.quality,
            "whisper_model": req.whisper_model,
            "max_clips": req.max_clips,
            "clip_length": req.clip_length,
            "diarize": req.diarize,
            "speakers": req.speakers,
            "use_gemini": req.use_gemini,
            "gemini_model": req.gemini_model,
        },
        video_id=video_id,
        # Panjang klip ikut ke dalam kunci: meminta klip panjang untuk video
        # yang analisis pendeknya sedang berjalan adalah permintaan berbeda.
        dedupe_key=f"auto_clip:{video_id}:{req.clip_length}:{req.gemini_model or 'auto'}",
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


class ReframePlanRequest(BaseModel):
    video_id: str
    segments: List[SegmentModel]
    aspect_ratio: str = "9:16"


# Perencanaan reframe memakan beberapa detik per klip, sementara editor
# memintanya setiap kali pengguna berpindah klip. Hasilnya disimpan sebentar
# di memori, dikunci oleh susunan segmen yang persis.
_REFRAME_CACHE: dict[tuple, dict] = {}
_REFRAME_CACHE_MAX = 48


@router.post("/clip-reframe")
async def clip_reframe(req: ReframePlanRequest):
    """
    Rencana crop yang mengikuti wajah, untuk digambar di pratinjau editor.

    Tanpa ini pratinjau menampilkan frame 16:9 apa adanya, sehingga pengguna
    tidak punya cara melihat bagaimana hasil 9:16-nya nanti membingkai
    pembicara — satu-satunya cara mengetahuinya adalah dengan merender.
    """
    import asyncio

    video_id = _resolve_video_id(req.video_id)
    segments = [{"start": round(s.start, 3), "end": round(s.end, 3)}
                for s in req.segments if s.end - s.start > 0.2]
    if not segments:
        raise NotFound("Rentang klip tidak valid.")

    key = (video_id, req.aspect_ratio,
           tuple((s["start"], s["end"]) for s in segments))
    if key in _REFRAME_CACHE:
        return _REFRAME_CACHE[key]

    from ..services.paths import find_local_video
    from ..services.reframe import plan_reframe

    source = find_local_video(video_id)
    if source is None:
        raise NotFound("Video sumber belum diunduh.")

    plan = await asyncio.to_thread(plan_reframe, str(source), segments,
                                   aspect_ratio=req.aspect_ratio)
    if plan is None:
        payload = {"available": False, "reason": "unsupported"}
    else:
        payload = {
            "available": plan.usable,
            "reason": None if plan.usable else "low_face_coverage",
            "crop_w": plan.crop_w, "crop_h": plan.crop_h,
            "source_w": plan.source_w, "source_h": plan.source_h,
            "face_coverage": plan.face_coverage,
            "keyframes": plan.keyframes,
        }

    if len(_REFRAME_CACHE) >= _REFRAME_CACHE_MAX:
        _REFRAME_CACHE.clear()
    _REFRAME_CACHE[key] = payload
    return payload


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
            "hook_text": req.hook_text if req.show_hook else "",
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
