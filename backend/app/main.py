"""Aplikasi FastAPI OmniClip: lifespan, middleware, dan pendaftaran router."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import ALLOWED_ORIGINS, require_ffmpeg
from .db import run_migrations
from .errors import register_exception_handlers
from .routers import clips as clips_router
from .routers import jobs as jobs_router
from .routers import media as media_router
from .routers import projects as projects_router
from .routers import settings as settings_router
from .routers import uploads as uploads_router
from .routers import videos as videos_router
from .services.events import broker
from .services.jobs import queue
from .services.pipeline import (
    run_auto_clip, run_diarize, run_download, run_render, run_upload,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("omniclip")


def _demo_job(ctx):
    """Job sintetis untuk memverifikasi antrean, progress, SSE, dan pembatalan."""
    steps = int(ctx.payload.get("steps", 20))
    delay = float(ctx.payload.get("delay", 0.25))
    for i in range(steps):
        ctx.check_cancelled()
        time.sleep(delay)
        ctx.progress((i + 1) / steps, stage="demo",
                     message=f"Langkah {i + 1} dari {steps}")
    return {"steps": steps}


def _log_reframe_status() -> None:
    from .services.reframe import MODEL_PATH
    try:
        import cv2  # noqa: F401
    except ImportError:
        log.warning("Smart reframe nonaktif: opencv-python-headless belum terpasang. "
                    "Klip 9:16 akan memakai bilah kabur.")
        return
    if not MODEL_PATH.is_file():
        log.warning("Smart reframe nonaktif: model YuNet tidak ada di %s. "
                    "Lihat requirements.txt untuk perintah unduhnya.", MODEL_PATH)
        return
    log.info("Smart reframe siap (YuNet)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    require_ffmpeg()
    run_migrations()

    broker.bind_loop(asyncio.get_running_loop())
    queue.register("demo", _demo_job, lane="cpu")
    queue.register("download", run_download, lane="net")
    queue.register("render", run_render, lane="cpu")
    queue.register("auto_clip", run_auto_clip, lane="cpu")
    queue.register("diarize", run_diarize, lane="cpu")
    queue.register("upload", run_upload, lane="upload")
    queue.start()

    # Smart reframe bersifat opsional dan gagal dengan anggun, jadi ketiadaannya
    # tidak akan terlihat sebagai error di mana pun — hanya sebagai klip yang
    # diam-diam selalu memakai bilah kabur. Karena itu statusnya dilaporkan
    # sekali saat startup.
    _log_reframe_status()
    log.info("OmniClip backend siap")

    try:
        yield
    finally:
        queue.stop()
        log.info("OmniClip backend berhenti")


app = FastAPI(
    title="OmniClip AI Backend Engine",
    version="3.2",
    description="Backend lokal untuk pencarian & unduhan YouTube, auto-clipping, dan render FFmpeg",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(jobs_router.router)
app.include_router(settings_router.router)
app.include_router(videos_router.router)
app.include_router(clips_router.router)
app.include_router(media_router.router)
app.include_router(projects_router.router)
app.include_router(uploads_router.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "OmniClip AI Engine v3.2"}
