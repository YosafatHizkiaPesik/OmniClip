"""
Hirarki error aplikasi.

Aturan: klien menerima {code, message} dengan pesan berbahasa Indonesia yang
bisa ditindaklanjuti. Detail mentah (stderr ffmpeg, traceback yt-dlp, path
absolut server) hanya masuk log — versi lama mengirimkan stderr ffmpeg apa
adanya ke browser, lengkap dengan path filesystem server.
"""

import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("omniclip")


class AppError(Exception):
    code = "APP_ERROR"
    status = 400
    message = "Terjadi kesalahan."

    def __init__(self, message: str | None = None, *, code: str | None = None,
                 status: int | None = None, detail: str = ""):
        super().__init__(message or self.message)
        if message:
            self.message = message
        if code:
            self.code = code
        if status:
            self.status = status
        self.detail = detail  # hanya untuk log


class NotFound(AppError):
    code = "NOT_FOUND"
    status = 404
    message = "Data tidak ditemukan."


class InvalidInput(AppError):
    code = "INVALID_INPUT"
    status = 422
    message = "Masukan tidak valid."


class UpstreamError(AppError):
    """Kegagalan dari layanan luar (YouTube, Gemini)."""
    code = "UPSTREAM_ERROR"
    status = 502
    message = "Layanan eksternal sedang bermasalah."


class RateLimited(AppError):
    code = "RATE_LIMITED"
    status = 429
    message = "Terlalu banyak permintaan. Coba lagi beberapa menit lagi."


class RenderError(AppError):
    code = "RENDER_FAILED"
    status = 500
    message = "Gagal merender klip. Cek log server untuk detail."


class JobCancelled(Exception):
    """Dilempar di dalam handler job ketika pembatalan diminta."""


def register_exception_handlers(app) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        if exc.detail:
            log.warning("%s: %s", exc.code, exc.detail[:1000])
        return JSONResponse(status_code=exc.status,
                            content={"code": exc.code, "message": exc.message})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.error("Unhandled error on %s %s\n%s", request.method, request.url.path,
                  traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL", "message": "Terjadi kesalahan internal di server."},
        )
