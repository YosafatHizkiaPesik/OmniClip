"""Aplikasi FastAPI OmniClip: lifespan, middleware, dan pendaftaran router."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from .config import ALLOWED_ORIGINS, FRONTEND_DIST, HOST, require_ffmpeg
from .db import run_migrations
from .errors import NotFound, register_exception_handlers
from .routers import auth as auth_router
from .routers import clips as clips_router
from .routers import jobs as jobs_router
from .routers import media as media_router
from .routers import projects as projects_router
from .routers import settings as settings_router
from .routers import uploads as uploads_router
from .routers import videos as videos_router
from .services import auth
from .services.events import broker
from .services.jobs import queue
from .services.pipeline import (
    run_auto_clip, run_diarize, run_download, run_render, run_retitle,
    run_tts_voice, run_upload,
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
    from .services.reframe import SFACE_PATH
    if SFACE_PATH.is_file():
        log.info("Smart reframe siap (YuNet + pengenal wajah SFace)")
    else:
        # Bukan peringatan: tanpa pengenal, penomoran orang jatuh ke tempat
        # duduk — lebih buruk di bidikan dekat, tapi tetap bekerja.
        log.info("Smart reframe siap (YuNet). Pengenal wajah belum diunduh, "
                 "nomor orang memakai tempat duduk. Lihat requirements.txt.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    require_ffmpeg()
    run_migrations()
    auth.check_startup_policy()

    broker.bind_loop(asyncio.get_running_loop())
    queue.register("demo", _demo_job, lane="cpu")
    queue.register("download", run_download, lane="net")
    queue.register("render", run_render, lane="cpu")
    queue.register("auto_clip", run_auto_clip, lane="cpu")
    queue.register("diarize", run_diarize, lane="cpu")
    queue.register("upload", run_upload, lane="upload")
    queue.register("tts_voice", run_tts_voice, lane="net")
    queue.register("retitle", run_retitle, lane="net")
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

app.include_router(auth_router.router)
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


# --- Gerbang -------------------------------------------------------------------

@app.middleware("http")
async def gerbang(request: Request, call_next):
    """
    Satu pemeriksaan di depan seluruh API.

    Sengaja middleware, bukan `Depends` per-router: dependency yang harus
    diingat untuk dipasang di setiap router baru adalah dependency yang suatu
    hari lupa dipasang, dan router yang terlupa itu persis router yang membuka
    segalanya. Di sini bawaannya tertutup — jalur yang terbuka harus disebut
    namanya satu per satu di auth.OPEN_PATHS.

    Berkas frontend (HTML/JS/CSS) tidak ikut dijaga: isinya sama untuk semua
    orang dan tidak memuat data apa pun. Yang dijaga adalah /api, dan tanpa itu
    aplikasinya hanya menampilkan layar masuk.
    """
    path = request.url.path
    if (path.startswith("/api/")
            and path not in auth.OPEN_PATHS
            and auth.auth_required()
            and not auth.valid_session(request.cookies.get(auth.COOKIE_NAME))):
        return JSONResponse(
            status_code=401,
            content={"code": "AUTH_REQUIRED",
                     "message": "Sesi berakhir. Masuk lagi dengan kata sandi."},
        )

    response = await call_next(request)
    # Aplikasi ini tidak pernah pantas muncul di hasil pencarian, dan begitu ia
    # punya alamat publik, tidak diindeks adalah bagian dari tidak ditemukan.
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


# --- Frontend hasil build ------------------------------------------------------
#
# Bila `frontend/dist` ada, seluruh aplikasi hidup di satu port: satu asal, satu
# terowongan, dan CORS tidak lagi ikut bermain. Bila tidak ada, backend tetap
# berjalan seperti biasa dan UI dilayani Vite di port 5173 seperti selama ini.

if FRONTEND_DIST.is_dir():
    _INDEX = FRONTEND_DIST / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            raise NotFound("Endpoint tidak dikenali.")
        if full_path:
            candidate = (FRONTEND_DIST / full_path).resolve()
            # Tanpa pemeriksaan ini, "../../backend/.env" adalah jalur yang sah
            # menuju API key.
            if (candidate.is_file()
                    and candidate.is_relative_to(FRONTEND_DIST.resolve())):
                cache = ("public, max-age=31536000, immutable"
                         if full_path.startswith("assets/") else "no-cache")
                return FileResponse(candidate, headers={"Cache-Control": cache})
        # Rute React (/studio/xxx, /watch/xxx) bukan berkas: kembalikan shell-nya
        # dan biarkan router di peramban yang memutuskan.
        return FileResponse(_INDEX, headers={"Cache-Control": "no-cache"})

    log.info("Frontend hasil build disajikan dari %s", FRONTEND_DIST)
else:
    log.info("frontend/dist belum ada: UI dilayani Vite (npm run dev). "
             "Untuk akses jarak jauh, jalankan `npm run build` lebih dulu.")

if HOST not in ("127.0.0.1", "::1", "localhost"):
    log.warning("Backend mendengar di %s — bukan hanya komputer ini. "
                "Pastikan kata sandi sudah dipasang.", HOST)
