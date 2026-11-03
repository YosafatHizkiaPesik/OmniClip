"""
/api/montase/*

Tahap 0 hanya berisi status mesin, penyiapannya, dan jalur uji. Endpoint
proyek, bahan, dan render sungguhan datang di Tahap 1 (JOB-4.md bagian 18).

Jalur `/api/montase/t/<token>/...` dibaca TANPA sesi masuk (iframe kotak
pasir dan Chrome headless tidak membawa cookie). Gerbang di main.py
melewatkannya karena `auth.OPEN_PREFIXES`; yang menjaganya adalah token di
alamatnya sendiri, diperiksa di setiap handler di bawah.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from ..errors import NotFound
from . import mesin, unduh, uji
from . import token as token_svc

router = APIRouter(prefix="/api/montase", tags=["montase"])


@router.get("/mesin")
def status_mesin():
    return {**mesin.status(), "versi_node_unduhan": unduh.VERSI_NODE}


@router.post("/mesin/siapkan")
def siapkan_mesin():
    from ..services.jobs import queue
    job_id, _ = queue.enqueue("montase_siapkan", {}, lane="net", dedupe_key="montase_siapkan")
    return {"job_id": job_id}


@router.get("/uji")
async def dokumen_uji():
    """Dokumen uji + alamat bertoken untuk pratinjau di peramban."""
    komponen = await run_in_threadpool(uji.siapkan_semua)
    tkn = token_svc.buat(uji.LINGKUP)
    return {
        "dokumen": uji.dokumen(),
        "sumber": uji.sumber("", tkn),
        "komponen": komponen,
        "mesin": mesin.status(),
    }


@router.post("/uji/render")
def render_uji():
    from ..services.jobs import queue
    job_id, _ = queue.enqueue("montase_uji_render", {}, lane="cpu",
                              dedupe_key="montase_uji_render")
    return {"job_id": job_id}


@router.get("/t/{tkn}/uji/{nama}")
async def berkas_uji(tkn: str, nama: str):
    if not token_svc.sah(tkn, uji.LINGKUP):
        raise NotFound("Alamat bahan tidak sah atau sudah kedaluwarsa.")
    jalur = uji.berkas(nama)
    if jalur is None:
        raise NotFound("Berkas uji tidak ada.")
    return FileResponse(jalur, media_type=uji.BERKAS_BOLEH[nama],
                        headers={"Cache-Control": "no-store"})
