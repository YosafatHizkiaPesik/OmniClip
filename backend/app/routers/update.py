"""Pembaruan aplikasi."""

import logging

from fastapi import APIRouter

from ..errors import AppError
from ..services import updater
from ..services.jobs import queue
from ..version import __version__

log = logging.getLogger("omniclip.update")
router = APIRouter(prefix="/api/update", tags=["update"])


@router.get("")
async def status(paksa: bool = False):
    """
    Keadaan pembaruan. Tidak pernah gagal — kegagalan jaringan dilaporkan
    sebagai `galat` di dalam jawaban, bukan sebagai permintaan yang gagal,
    supaya halaman Pengaturan tetap terbuka saat internet mati.
    """
    import asyncio

    info = await asyncio.to_thread(updater.cek, paksa)
    bisa, alasan = updater.bisa_memasang()
    return {**info, "bisa_pasang_sendiri": bisa, "alasan_tidak_bisa": alasan}


@router.post("/pasang", status_code=202)
async def pasang():
    """
    Mengunduh dan memasang versi terbaru.

    Aplikasi akan menutup sendiri setelah berkasnya siap, lalu terbuka kembali
    pada versi baru — penukaran foldernya dikerjakan proses penolong, karena
    sebuah .exe yang sedang berjalan tidak bisa menimpa dirinya sendiri.
    """
    bisa, alasan = updater.bisa_memasang()
    if not bisa:
        raise AppError(alasan, code="UPDATE_TIDAK_BISA", status=409)

    info = updater.cek(paksa=True)
    if not info["ada_pembaruan"]:
        raise AppError(f"Sudah memakai versi terbaru ({__version__}).",
                       code="UPDATE_SUDAH_TERBARU", status=409)

    job_id = queue.enqueue("update", {}, dedupe_key="update:pasang")
    return {"job_id": job_id, "versi": info["versi_terbaru"]}
