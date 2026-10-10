"""
Suara komentar pemilik kanal (JOB-2 F1-4): rekaman mikrofon dari Studio, atau
TTS sebagai cadangan. Drafnya ada di /api/clip-komentar (routers/clips.py).
"""

import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..errors import AppError, NotFound
from ..services import komentar as km

router = APIRouter(prefix="/api/komentar", tags=["komentar"])

# Satu menit rekaman opus dari peramban kira-kira 0,5 MB; 25 MB berarti
# sesuatu yang bukan rekaman komentar.
BATAS_UKURAN = 25 * 1024 * 1024


@router.post("/rekaman")
async def simpan_rekaman(berkas: UploadFile = File(...)):
    akhiran = Path(berkas.filename or "rekaman.webm").suffix or ".webm"
    tmp = Path(tempfile.mkstemp(prefix="omni_rekam_", suffix=akhiran)[1])
    total = 0
    try:
        with open(tmp, "wb") as keluar:
            while True:
                blok = await berkas.read(1 << 20)
                if not blok:
                    break
                total += len(blok)
                if total > BATAS_UKURAN:
                    raise AppError("Rekaman terlalu besar (maksimal 25 MB).",
                                   code="REKAMAN_TERLALU_BESAR", status=413)
                keluar.write(blok)
        return await asyncio.to_thread(km.simpan_rekaman, tmp)
    except ValueError as e:
        raise AppError(str(e), code="REKAMAN_TIDAK_SAH", status=422) from e
    finally:
        tmp.unlink(missing_ok=True)


class TtsRequest(BaseModel):
    teks: str = Field(..., min_length=1, max_length=600)
    suara: str = Field("", max_length=40)


@router.post("/tts")
async def buat_tts(req: TtsRequest):
    try:
        return await asyncio.to_thread(km.buat_tts, req.teks, req.suara)
    except (ValueError, KeyError) as e:
        raise AppError(str(e) or "Suara itu tidak dikenal.", status=422) from e
    except RuntimeError as e:
        raise AppError(str(e), code="TTS_TIDAK_ADA", status=503) from e


@router.get("/suara-tts")
async def daftar_suara_tts():
    from ..services import tts
    return {"suara": tts.catalogue(), "bawaan": tts.DEFAULT_VOICE}


@router.get("/suara/{sidik}")
async def berkas_suara(sidik: str):
    p = km.jalur_suara(sidik)
    if p is None:
        raise NotFound("Suara komentar ini tidak ditemukan.")
    return FileResponse(p, media_type="audio/mp4")


@router.get("/suara/{sidik}/info")
async def info_suara(sidik: str):
    data = km.info_suara(sidik)
    if data is None:
        raise NotFound("Suara komentar ini tidak ditemukan.")
    return data
