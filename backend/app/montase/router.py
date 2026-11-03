"""
/api/montase/* (JOB-4 bagian 18).

Jalur `/api/montase/t/<token>/...` dibaca TANPA sesi masuk (iframe kotak
pasir dan Chrome headless tidak membawa cookie). Gerbang di main.py
melewatkannya karena `auth.OPEN_PREFIXES`; yang menjaganya adalah token di
alamatnya sendiri, diperiksa di setiap handler di bawah awalan itu.

Semua yang lain dijaga sesi seperti endpoint OmniClip lainnya, dan dibatasi
profil aktif (`profil.kini()`).
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..errors import AppError, InvalidInput, NotFound
from ..repos import montase as repo
from ..repos import settings as settings_repo
from ..services import profil
from . import bahan as bahan_svc
from . import mesin, skema, unduh, uji
from . import token as token_svc

router = APIRouter(prefix="/api/montase", tags=["montase"])

KUNCI_AKTIF = "montase.aktif"


def lingkup_bahan(pid: int) -> str:
    return f"bahan:{pid}"


# --- setelan dan mesin --------------------------------------------------------

class Setelan(BaseModel):
    aktif: bool


@router.get("/setelan")
def ambil_setelan():
    return {"aktif": settings_repo.get(KUNCI_AKTIF, "1") == "1"}


@router.post("/setelan")
def simpan_setelan(b: Setelan):
    settings_repo.set_value(KUNCI_AKTIF, "1" if b.aktif else "0")
    return {"aktif": b.aktif}


@router.get("/mesin")
def status_mesin():
    return {**mesin.status(), "versi_node_unduhan": unduh.VERSI_NODE}


@router.post("/mesin/siapkan")
def siapkan_mesin():
    from ..services.jobs import queue
    job_id, _ = queue.enqueue("montase_siapkan", {}, lane="net", dedupe_key="montase_siapkan")
    return {"job_id": job_id}


@router.get("/token")
def token_bahan():
    """Token untuk membaca bahan profil ini dari iframe kotak pasir (6 jam)."""
    return {"token": token_svc.buat(lingkup_bahan(profil.kini()))}


# --- proyek -------------------------------------------------------------------

class ProyekBaru(BaseModel):
    nama: str = Field("Proyek tanpa judul", min_length=1, max_length=120)
    preset: Optional[str] = None
    lebar: Optional[int] = None
    tinggi: Optional[int] = None
    fps: int = 30


class SimpanProyek(BaseModel):
    dokumen: dict[str, Any]
    revisi: int


def _sampul(dokumen: dict) -> Optional[str]:
    """Bahan gambar/video pertama di linimasa, untuk kartu proyek."""
    for lajur in dokumen.get("lajur", []):
        if lajur.get("jenis") != "video":
            continue
        for item in sorted(lajur.get("item", []), key=lambda i: i.get("mulai", 0)):
            if item.get("bahan"):
                return item["bahan"]
    return None


def _periksa(dokumen: dict) -> dict:
    try:
        return skema.periksa(dokumen)
    except skema.GagalSkema as e:
        raise AppError("Dokumen proyek tidak sah: " + "; ".join(e.pesan[:5]),
                       code="DOKUMEN_TIDAK_SAH", status=422) from e


def _durasi_detik(dokumen: dict) -> float:
    return round(dokumen["durasi"] / dokumen["kanvas"]["fps"], 3)


@router.get("/proyek")
def daftar_proyek():
    return {"proyek": repo.daftar_proyek(profil.kini())}


@router.post("/proyek")
def buat_proyek(b: ProyekBaru):
    if b.preset:
        if b.preset not in skema.PRESET_KANVAS:
            raise InvalidInput(f"Preset kanvas tidak dikenal: {b.preset}")
        lebar, tinggi = skema.PRESET_KANVAS[b.preset]
    else:
        lebar, tinggi = b.lebar or 1080, b.tinggi or 1920
    try:
        dokumen = skema.dokumen_baru(repo.id_baru("mt"), b.nama.strip(),
                                     lebar=lebar, tinggi=tinggi, fps=b.fps)
    except skema.GagalSkema as e:
        raise InvalidInput("; ".join(e.pesan)) from e
    return repo.buat_proyek(profil.kini(), dokumen, durasi_detik=_durasi_detik(dokumen))


@router.get("/proyek/{proyek_id}")
def ambil_proyek(proyek_id: str):
    p = repo.ambil_proyek(profil.kini(), proyek_id)
    if p is None:
        raise NotFound("Proyek tidak ditemukan.")
    return p


@router.put("/proyek/{proyek_id}")
def simpan_proyek(proyek_id: str, b: SimpanProyek):
    pid = profil.kini()
    dokumen = _periksa(b.dokumen)
    if dokumen["id"] != proyek_id:
        raise InvalidInput("Id dokumen tidak sama dengan proyeknya.")
    for bahan_id in dokumen["bahan"]:
        if repo.ambil_bahan(pid, bahan_id) is None:
            raise InvalidInput(f"Bahan {bahan_id} tidak ada di pustaka profil ini.")
    try:
        revisi = repo.simpan_proyek(pid, proyek_id, dokumen, b.revisi,
                                    durasi_detik=_durasi_detik(dokumen), sampul=_sampul(dokumen))
    except KeyError as e:
        raise NotFound("Proyek tidak ditemukan.") from e
    except repo.RevisiBentrok as e:
        raise AppError("Proyek ini sudah diubah di tab atau perangkat lain. Muat ulang untuk "
                       "melihat versi terbarunya.", code="REVISI_BENTROK", status=409,
                       detail=str(e.revisi_kini)) from e
    return {"revisi": revisi, "durasi": dokumen["durasi"]}


@router.delete("/proyek/{proyek_id}")
def hapus_proyek(proyek_id: str):
    if not repo.hapus_proyek(profil.kini(), proyek_id):
        raise NotFound("Proyek tidak ditemukan.")
    return {"ok": True}


@router.post("/proyek/{proyek_id}/gandakan")
def gandakan_proyek(proyek_id: str):
    pid = profil.kini()
    p = repo.ambil_proyek(pid, proyek_id)
    if p is None:
        raise NotFound("Proyek tidak ditemukan.")
    dokumen = {**p["dokumen"], "id": repo.id_baru("mt"),
               "nama": f"{p['nama']} (salinan)"[:120]}
    return repo.buat_proyek(pid, dokumen, durasi_detik=p["durasi_detik"] or 0,
                            sampul=p["sampul"])


@router.post("/proyek/{proyek_id}/ekspor")
def ekspor_proyek(proyek_id: str):
    """Render proyek ke Klip jadi (pekerjaan `montase_render`). Menjawab job_id."""
    from . import ekspor
    try:
        return {"job_id": ekspor.mulai(proyek_id)}
    except KeyError as e:
        raise NotFound("Proyek tidak ditemukan.") from e


# --- bahan --------------------------------------------------------------------

class Rujuk(BaseModel):
    asal: str
    rujukan: str = Field(..., min_length=1, max_length=300)


@router.get("/bahan")
def daftar_bahan():
    return {"bahan": [(b) for b in repo.daftar_bahan(profil.kini())]}


@router.get("/bahan/sumber")
async def sumber_bahan(asal: str):
    try:
        return {"sumber": await run_in_threadpool(bahan_svc.sumber_tersedia, asal)}
    except bahan_svc.BahanTidakSah as e:
        raise InvalidInput(str(e)) from e


@router.post("/bahan/rujuk")
async def rujuk_bahan(b: Rujuk):
    try:
        return await run_in_threadpool(bahan_svc.rujuk, b.asal, b.rujukan)
    except bahan_svc.BahanTidakSah as e:
        raise InvalidInput(str(e)) from e


BATAS_IMPOR = 2 * 1024 ** 3


@router.post("/bahan/impor")
async def impor_bahan(berkas: UploadFile = File(...)):
    """Unggahan masuk pustaka aset (terlihat juga di Studio Klip), lalu jadi bahan."""
    from ..services import aset as aset_svc
    nama = Path(berkas.filename or "berkas").name
    tmp = Path(tempfile.mkstemp(prefix="omni_montase_", suffix=Path(nama).suffix)[1])
    total = 0
    try:
        with open(tmp, "wb") as keluar:
            while True:
                blok = await berkas.read(1 << 20)
                if not blok:
                    break
                total += len(blok)
                if total > BATAS_IMPOR:
                    raise AppError("Berkas terlalu besar (maksimal 2 GB).",
                                   code="BAHAN_TERLALU_BESAR", status=413)
                keluar.write(blok)
        try:
            info = await asyncio.to_thread(aset_svc.simpan_unggahan, tmp, nama)
        except ValueError as e:
            raise InvalidInput(str(e)) from e
        try:
            baris = await run_in_threadpool(bahan_svc.rujuk, "impor", info["id"],
                                            nama=info.get("nama") or Path(nama).stem)
        except bahan_svc.BahanTidakSah as e:
            raise InvalidInput(str(e)) from e
        return baris
    finally:
        tmp.unlink(missing_ok=True)


@router.delete("/bahan/{bahan_id}")
def hapus_bahan(bahan_id: str):
    pid = profil.kini()
    dipakai = bahan_svc.dipakai_proyek(pid, bahan_id)
    if dipakai:
        raise AppError("Bahan ini masih dipakai proyek: " + ", ".join(dipakai[:5]),
                       code="BAHAN_DIPAKAI", status=409)
    if not bahan_svc.hapus(pid, bahan_id):
        raise NotFound("Bahan tidak ditemukan.")
    return {"ok": True}


def _pid_dari_token(tkn: str) -> int:
    lingkup = token_svc.lingkup(tkn) or ""
    if not lingkup.startswith("bahan:"):
        raise NotFound("Alamat bahan tidak sah atau sudah kedaluwarsa.")
    try:
        return int(lingkup.split(":", 1)[1])
    except ValueError as e:
        raise NotFound("Alamat bahan tidak sah.") from e


@router.get("/t/{tkn}/bahan/{bahan_id}")
def berkas_bahan(tkn: str, bahan_id: str, sunting: int = 0):
    """Berkas bahan untuk iframe kotak pasir dan mesin render (token, bukan sesi)."""
    pid = _pid_dari_token(tkn)
    jalur = bahan_svc.jalur_berkas(pid, bahan_id, sunting=bool(sunting))
    if jalur is None:
        raise NotFound("Bahan tidak ditemukan.")
    return FileResponse(jalur, media_type=bahan_svc.jenis_media(jalur),
                        headers={"Cache-Control": "private, max-age=3600"})


_TURUNAN = {"sampul": ("sampul.jpg", "image/jpeg"), "strip": ("strip.jpg", "image/jpeg"),
            "gelombang": ("gelombang.json", "application/json")}


@router.get("/t/{tkn}/bahan/{bahan_id}/{turunan}")
def turunan_bahan(tkn: str, bahan_id: str, turunan: str):
    """
    Sampul, strip, dan gelombang. Lewat token juga, bukan sesi: `<img>` tidak
    membawa header profil, dan tokennya sudah memuat profil pemilik bahan.
    """
    pid = _pid_dari_token(tkn)
    if turunan not in _TURUNAN or repo.ambil_bahan(pid, bahan_id) is None:
        raise NotFound("Bahan tidak ditemukan.")
    nama, jenis = _TURUNAN[turunan]
    jalur = bahan_svc.folder(bahan_id) / nama
    if not jalur.is_file():
        raise NotFound("Belum siap.")
    return FileResponse(jalur, media_type=jenis, headers={"Cache-Control": "no-cache"})


# --- uji Tahap 0 --------------------------------------------------------------

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
