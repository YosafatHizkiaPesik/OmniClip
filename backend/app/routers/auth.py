"""Masuk, keluar, dan memasang kata sandi."""

import logging

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from ..errors import AppError
from ..services import auth, cf_access

log = logging.getLogger("omniclip.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])

MIN_LENGTH = 8


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class PasswordRequest(BaseModel):
    new_password: str = Field(min_length=MIN_LENGTH, max_length=256)
    current_password: str = ""


def client_id(request: Request) -> str:
    """
    Siapa yang dihitung percobaannya.

    Di balik terowongan setiap permintaan datang dari 127.0.0.1, jadi alamat
    peer tidak lagi membedakan siapa pun. Hanya dalam kasus itulah header
    Cloudflare dipercaya — dan hanya untuk menghitung percobaan gagal, tidak
    pernah untuk memberi akses.
    """
    peer = request.client.host if request.client else "?"
    if peer in ("127.0.0.1", "::1", "localhost"):
        forwarded = request.headers.get("cf-connecting-ip") or ""
        if forwarded:
            return f"cf:{forwarded.strip()[:64]}"
    return peer


def _is_https(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    return (proto or request.url.scheme) == "https"


def _set_cookie(response: Response, request: Request) -> None:
    response.set_cookie(
        auth.COOKIE_NAME,
        auth.issue_session(),
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        # Secure hanya bila sambungannya memang https. Memasangnya di http
        # membuat peramban membuang cookie-nya diam-diam, dan gejalanya adalah
        # "kata sandi benar tapi tetap kembali ke layar masuk".
        secure=_is_https(request),
        path="/",
    )


@router.get("/status")
async def status(request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    by_password = auth.valid_session(token)

    # `reason` ada supaya salah setel Cloudflare bisa dibaca, bukan ditebak.
    # Tanpa itu gejalanya hanya "diminta kata sandi terus", yang tidak menunjuk
    # ke mana pun — dan aud yang keliru terlihat persis seperti tim yang keliru.
    email, reason = await cf_access.verify(request)

    return {
        "required": auth.auth_required(),
        "has_password": auth.has_password(),
        "authenticated": not auth.auth_required() or by_password or bool(email),
        "via": "cloudflare" if (email and not by_password) else
               ("password" if by_password else None),
        "mode": auth.auth_mode(),
        "min_length": MIN_LENGTH,
        "cloudflare": {
            "configured": cf_access.configured(),
            "team": cf_access.team(),
            "email": email,
            "reason": reason,
        },
    }


@router.post("/login")
async def login(req: LoginRequest, request: Request, response: Response):
    who = client_id(request)
    remaining = auth.locked_out(who)
    if remaining:
        raise AppError(
            f"Terlalu banyak percobaan. Coba lagi dalam {remaining // 60 + 1} menit.",
            code="AUTH_LOCKED", status=429)

    if not auth.has_password():
        raise AppError("Belum ada kata sandi yang dipasang.",
                       code="AUTH_NO_PASSWORD", status=409)

    if not auth.verify_password(req.password):
        auth.note_failure(who)
        log.warning("Percobaan masuk gagal dari %s", who)
        raise AppError("Kata sandi salah.", code="AUTH_FAILED", status=401)

    auth.note_success(who)
    _set_cookie(response, request)
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.post("/setup")
async def setup(req: PasswordRequest, request: Request, response: Response):
    """
    Memasang kata sandi pertama. Terbuka tanpa sesi — tapi hanya selama belum
    ada kata sandi sama sekali, jadi jendelanya tertutup sendiri setelah sekali
    dipakai.
    """
    if auth.has_password():
        raise AppError("Kata sandi sudah ada. Ubah lewat halaman Catatan main.",
                       code="AUTH_EXISTS", status=409)
    auth.set_password(req.new_password)
    _set_cookie(response, request)
    log.info("Kata sandi pertama dipasang; gerbang aktif.")
    return {"status": "ok"}


@router.post("/password")
async def change_password(req: PasswordRequest, request: Request, response: Response):
    """Mengubah kata sandi. Berada di balik gerbang, jadi pemanggilnya sudah masuk."""
    if auth.has_password() and not auth.verify_password(req.current_password):
        raise AppError("Kata sandi lama salah.", code="AUTH_FAILED", status=401)
    auth.set_password(req.new_password)
    # Mengganti kata sandi mematikan semua sesi, termasuk sesi ini. Terbitkan
    # ulang supaya yang mengganti tidak ikut terlempar keluar.
    _set_cookie(response, request)
    log.info("Kata sandi diganti; seluruh sesi lama dicabut.")
    return {"status": "ok"}


@router.delete("/password")
async def remove_password(request: Request, response: Response):
    """
    Melepas kata sandi — kembali ke mode lokal.

    Ditolak bila gerbangnya sedang dipaksa menyala, karena melepasnya di sana
    berarti membuka aplikasi yang sedang terbit ke internet.
    """
    if auth.auth_mode() == "on":
        raise AppError(
            "Tidak bisa melepas kata sandi selama OMNICLIP_AUTH=on. "
            "Matikan dulu akses jarak jauhnya.",
            code="AUTH_LOCKED_MODE", status=409)
    auth.clear_password()
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    log.warning("Kata sandi dilepas; aplikasi kembali ke mode lokal.")
    return {"status": "ok"}
