"""
Aset sisipan: berkas yang diimpor pengguna ke Studio, plus efek suara bawaan.

Berkas diterima SEPOTONG-SEPOTONG ke berkas sementara, bukan dibaca utuh ke
memori: cuplikan pertandingan bisa ratusan megabita, dan `await berkas.read()`
pada ukuran itu adalah cara tercepat menghabiskan RAM mesin 8 GB ini.
"""

import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse

from ..errors import AppError, NotFound
from ..services import aset as aset_svc

router = APIRouter(prefix="/api/aset", tags=["aset"])

BATAS_UKURAN = 2 * 1024 * 1024 * 1024    # 2 GB


@router.get("")
async def daftar_aset():
    return {"aset": await asyncio.to_thread(aset_svc.daftar)}


@router.post("")
async def unggah_aset(berkas: UploadFile = File(...)):
    nama = Path(berkas.filename or "berkas").name
    tmp = Path(tempfile.mkstemp(prefix="omni_aset_", suffix=Path(nama).suffix)[1])
    total = 0
    try:
        with open(tmp, "wb") as keluar:
            while True:
                blok = await berkas.read(1 << 20)
                if not blok:
                    break
                total += len(blok)
                if total > BATAS_UKURAN:
                    raise AppError("Berkas terlalu besar (maksimal 2 GB).",
                                   code="ASET_TERLALU_BESAR", status=413)
                keluar.write(blok)
        return await asyncio.to_thread(aset_svc.simpan_unggahan, tmp, nama)
    except ValueError as e:
        raise AppError(str(e), code="ASET_TIDAK_SAH", status=422) from e
    finally:
        tmp.unlink(missing_ok=True)


@router.get("/{aset_id}/berkas")
async def berkas_aset(aset_id: str):
    """Untuk pratinjau di Studio. FileResponse mendukung Range, jadi bisa di-seek."""
    p = await asyncio.to_thread(aset_svc.jalur, aset_id)
    if p is None:
        raise NotFound("Aset tidak ditemukan.")
    return FileResponse(p)


class RakModel(BaseModel):
    kategori: str = Field(..., max_length=16)


@router.patch("/{aset_id}/rak")
async def pindah_rak(aset_id: str, body: RakModel):
    """Memindahkan aset ke rak Musik, Efek suara, atau Media."""
    data = await asyncio.to_thread(aset_svc.setel_kategori, aset_id, body.kategori)
    if data is None:
        raise NotFound("Aset tidak ditemukan, raknya tidak dikenal, "
                       "atau ini aset bawaan yang raknya tetap.")
    return data


@router.delete("/{aset_id}")
async def hapus_aset(aset_id: str):
    if not await asyncio.to_thread(aset_svc.hapus, aset_id):
        raise NotFound("Aset tidak ditemukan, atau aset bawaan yang tidak bisa dihapus.")
    return {"status": "ok"}
