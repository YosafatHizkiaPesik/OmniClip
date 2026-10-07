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
    # Kabar dari pemasangan sebelumnya, bila ada. Hanya versi yang HIDUP
    # SEKARANG yang bisa menjawab apakah penukaran foldernya berhasil, karena
    # yang mengerjakannya sudah mati sebelum selesai.
    hasil = await asyncio.to_thread(updater.hasil_pemasangan)
    # Pemasangan yang berhenti di tengah meninggalkan hasil bongkarannya di
    # sebelah aplikasi, dan tidak ada yang menyapunya seperti %TEMP% disapu
    # Windows. Dibereskan di sini, sekalian saat halaman ini dibuka.
    await asyncio.to_thread(updater.bersihkan_sisa)
    return {**info, "bisa_pasang_sendiri": bisa, "alasan_tidak_bisa": alasan,
            "pemasangan_terakhir": hasil,
            # Folder versi lama dibuang sendiri begitu pemasangan terbukti
            # berhasil (`hasil_pemasangan`). Yang masih tersisa di sini berarti
            # pemasangan yang belum terbukti, dan itu dilaporkan apa adanya.
            "cadangan_tertinggal": await asyncio.to_thread(updater.cadangan_tertinggal)}


@router.post("/pasang", status_code=202)
async def pasang():
    """
    Mengunduh dan memasang versi terbaru.

    Aplikasi akan menutup sendiri setelah berkasnya siap, lalu terbuka kembali
    pada versi baru — penukaran foldernya dikerjakan proses penolong, karena
    sebuah .exe yang sedang berjalan tidak bisa menimpa dirinya sendiri.
    """
    import asyncio

    bisa, alasan = updater.bisa_memasang()
    if not bisa:
        raise AppError(alasan, code="UPDATE_TIDAK_BISA", status=409)

    # Di utas terpisah: ini menghubungi GitHub dengan batas 20 detik, dan
    # memanggilnya langsung di sini membekukan seluruh server selama itu.
    info = await asyncio.to_thread(updater.cek, True)
    if not info["ada_pembaruan"]:
        raise AppError(f"Sudah memakai versi terbaru ({__version__}).",
                       code="UPDATE_SUDAH_TERBARU", status=409)

    job_id, dibuat = queue.enqueue("update", {}, dedupe_key="update:pasang")
    return {"job_id": job_id, "created": dibuat, "versi": info["versi_terbaru"]}
