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
from . import mesin, narasi, skema, teks, unduh, uji
from . import token as token_svc

router = APIRouter(prefix="/api/montase", tags=["montase"])

KUNCI_AKTIF = "montase.aktif"


def lingkup_bahan(pid: int) -> str:
    return f"bahan:{pid}"


# --- setelan dan mesin --------------------------------------------------------

class Setelan(BaseModel):
    aktif: Optional[bool] = None
    ai_koneksi: Optional[str] = None


KUNCI_AI = "montase.ai_koneksi"


def _setelan() -> dict:
    from ..services import koneksi_ai
    return {
        "aktif": settings_repo.get(KUNCI_AKTIF, "1") == "1",
        # "" = ikuti urutan koneksi di Pengaturan > AI (K-12).
        "ai_koneksi": settings_repo.get(KUNCI_AI, ""),
        "koneksi": [{"id": k["id"], "nama": k["nama"], "penyedia": k["penyedia"]}
                    for k in koneksi_ai.semua() if k.get("aktif")],
        "versi_paket": _versi_paket(),
    }


def _versi_paket() -> int:
    from . import motion_ai
    return motion_ai.VERSI_KONTRAK


@router.get("/setelan")
def ambil_setelan():
    return _setelan()


@router.post("/setelan")
def simpan_setelan(b: Setelan):
    if b.aktif is not None:
        settings_repo.set_value(KUNCI_AKTIF, "1" if b.aktif else "0")
    if b.ai_koneksi is not None:
        settings_repo.set_value(KUNCI_AI, b.ai_koneksi[:60])
    return _setelan()


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
    repo.catat_versi(pid, proyek_id, revisi, dokumen)
    return {"revisi": revisi, "durasi": dokumen["durasi"]}


@router.post("/proyek/{proyek_id}/pembuka")
def pembuka_proyek(proyek_id: str):
    """Usulan cuplikan pembuka dari momen terkuat (JOB-5 O4), pekerjaan `montase_pembuka`."""
    from . import pembuka
    if repo.ambil_proyek(profil.kini(), proyek_id) is None:
        raise NotFound("Proyek tidak ditemukan.")
    return {"job_id": pembuka.mulai(proyek_id)}


@router.get("/proyek/{proyek_id}/kemiripan")
def kemiripan_proyek(proyek_id: str):
    """Proyek ini lawan ekspor Montase sebelumnya di profil ini (JOB-5 O3)."""
    from . import kemiripan
    pid = profil.kini()
    p = repo.ambil_proyek(pid, proyek_id)
    if p is None:
        raise NotFound("Proyek tidak ditemukan.")
    return kemiripan.periksa(pid, p["dokumen"])


@router.get("/proyek/{proyek_id}/versi")
def daftar_versi(proyek_id: str):
    """Riwayat versi (M6.4): 10 potret terakhir, tanpa isi dokumennya."""
    pid = profil.kini()
    if repo.ambil_proyek(pid, proyek_id) is None:
        raise NotFound("Proyek tidak ditemukan.")
    return {"versi": repo.daftar_versi(pid, proyek_id)}


class Pulihkan(BaseModel):
    revisi: int = Field(..., ge=1)


@router.post("/proyek/{proyek_id}/versi/{versi_id}/pulihkan")
def pulihkan_versi(proyek_id: str, versi_id: int, b: Pulihkan):
    """
    Mengembalikan proyek ke satu versi. Keadaan sekarang dipotret dulu, jadi
    memulihkan pun bisa dibatalkan dengan memulihkan potret itu.
    """
    pid = profil.kini()
    kini = repo.ambil_proyek(pid, proyek_id)
    v = repo.ambil_versi(pid, proyek_id, versi_id)
    if kini is None or v is None:
        raise NotFound("Versi tidak ditemukan.")
    dokumen = _periksa(v["dokumen"])
    hilang = [bid for bid in dokumen["bahan"] if repo.ambil_bahan(pid, bid) is None]
    if hilang:
        raise InvalidInput("Versi ini memakai bahan yang sudah dihapus dari pustaka: " + ", ".join(hilang[:5]))
    repo.catat_versi(pid, proyek_id, kini["revisi"], kini["dokumen"], alasan="sebelum_pulihkan", paksa=True)
    try:
        revisi = repo.simpan_proyek(pid, proyek_id, dokumen, b.revisi,
                                    durasi_detik=_durasi_detik(dokumen), sampul=_sampul(dokumen))
    except repo.RevisiBentrok as e:
        raise AppError("Proyek ini sudah diubah di tab atau perangkat lain. Muat ulang dulu.",
                       code="REVISI_BENTROK", status=409, detail=str(e.revisi_kini)) from e
    return {"revisi": revisi, "dokumen": dokumen}


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


@router.post("/proyek/{proyek_id}/subtitle")
def subtitle_proyek(proyek_id: str):
    """Subtitle otomatis dari suara linimasa (pekerjaan `montase_subtitle`, M3.2)."""
    from . import subtitle
    try:
        return {"job_id": subtitle.mulai(proyek_id)}
    except KeyError as e:
        raise NotFound("Proyek tidak ditemukan.") from e


class Asisten(BaseModel):
    perintah: str = Field(..., min_length=3, max_length=1000)
    bahan: list[str] = Field(..., min_length=1, max_length=20)
    narasi: bool = False
    suara: str = Field("", max_length=80)
    maks_detik: float = Field(20.0, ge=3, le=120)
    pakai_ai: bool = True


@router.post("/proyek/{proyek_id}/asisten")
def asisten_proyek(proyek_id: str, b: Asisten):
    """Asisten penyunting (M5.1): pekerjaan `montase_asisten`, hasilnya daftar operasi usulan."""
    from . import asisten_ai
    if repo.ambil_proyek(profil.kini(), proyek_id) is None:
        raise NotFound("Proyek tidak ditemukan.")
    return {"job_id": asisten_ai.mulai(proyek_id, b.model_dump())}


class Jeda(BaseModel):
    item: str = Field(..., min_length=1, max_length=40)


@router.post("/proyek/{proyek_id}/jeda")
def jeda_proyek(proyek_id: str, b: Jeda):
    """Usulan potongan jeda dan kata isian untuk satu item (M5.4), pekerjaan `montase_jeda`."""
    from . import jeda
    if repo.ambil_proyek(profil.kini(), proyek_id) is None:
        raise NotFound("Proyek tidak ditemukan.")
    return {"job_id": jeda.mulai(proyek_id, b.item)}


@router.post("/proyek/{proyek_id}/bingkai")
def bingkai_proyek(proyek_id: str, b: Jeda):
    """Usulan bingkai ulang 9:16 mengikuti wajah untuk satu item video (M5.5)."""
    from . import bingkai
    if repo.ambil_proyek(profil.kini(), proyek_id) is None:
        raise NotFound("Proyek tidak ditemukan.")
    return {"job_id": bingkai.mulai(proyek_id, b.item)}


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
    # Turunan ditulis sekali saat bahan disiapkan dan tidak berubah lagi, dan
    # alamatnya membawa token: aman disimpan peramban selama token berlaku
    # (M6.3). Dulu `no-cache`, jadi setiap item yang dipasang ulang saat
    # menggulir linimasa memvalidasi ulang sampul dan stripnya.
    return FileResponse(jalur, media_type=jenis, headers={"Cache-Control": "private, max-age=21600"})


class Narasi(BaseModel):
    teks: str = Field(..., min_length=1, max_length=narasi.TEKS_MAKS)
    suara: str = Field(..., min_length=1, max_length=60)
    kecepatan: float = Field(1.0, ge=narasi.KECEPATAN[0], le=narasi.KECEPATAN[1])


@router.get("/suara")
def daftar_suara():
    """Katalog suara narasi (tts.py) dan apakah masing-masing siap dipakai."""
    return {"suara": narasi.daftar_suara()}


@router.post("/narasi")
async def buat_narasi(isi: Narasi):
    """Teks -> suara -> bahan audio (M3.3). Narasi yang persis sama dipakai ulang."""
    try:
        return await run_in_threadpool(narasi.buat_narasi, profil.kini(), isi.teks, isi.suara,
                                       isi.kecepatan)
    except narasi.GagalNarasi as e:
        raise InvalidInput(str(e)) from e


@router.post("/rekam")
async def simpan_rekaman(berkas: UploadFile = File(...)):
    """Rekaman mikrofon dari peramban -> M4A -> bahan audio (M3.3)."""
    tmp = Path(tempfile.mkstemp(prefix="omni_rekam_", suffix=".webm")[1])
    total = 0
    try:
        with open(tmp, "wb") as keluar:
            while True:
                blok = await berkas.read(1 << 20)
                if not blok:
                    break
                total += len(blok)
                if total > BATAS_IMPOR:
                    raise AppError("Rekaman terlalu besar.", code="BAHAN_TERLALU_BESAR", status=413)
                keluar.write(blok)
        nama = Path(berkas.filename or "Rekaman").stem[:120] or "Rekaman"
        try:
            return await run_in_threadpool(narasi.simpan_rekaman, profil.kini(), tmp, nama)
        except narasi.GagalNarasi as e:
            raise InvalidInput(str(e)) from e
    finally:
        tmp.unlink(missing_ok=True)


@router.post("/rekam-video")
async def simpan_rekaman_video(berkas: UploadFile = File(...)):
    """Rekaman reaksi kamera dari peramban -> MP4 -> bahan video `rekam` (JOB-5 O5)."""
    tmp = Path(tempfile.mkstemp(prefix="omni_reaksi_", suffix=".webm")[1])
    total = 0
    try:
        with open(tmp, "wb") as keluar:
            while True:
                blok = await berkas.read(1 << 20)
                if not blok:
                    break
                total += len(blok)
                if total > BATAS_IMPOR:
                    raise AppError("Rekaman terlalu besar.", code="BAHAN_TERLALU_BESAR", status=413)
                keluar.write(blok)
        nama = Path(berkas.filename or "Reaksi").stem[:120] or "Reaksi"
        try:
            return await run_in_threadpool(narasi.simpan_reaksi, profil.kini(), tmp, nama)
        except narasi.GagalNarasi as e:
            raise InvalidInput(str(e)) from e
    finally:
        tmp.unlink(missing_ok=True)


@router.get("/gaya-teks")
def gaya_teks():
    """Tema judul siap pakai dan font bawaan untuk item teks (M3.1)."""
    return {"gaya": teks.daftar_gaya(), "font": teks.font_bawaan()}


@router.get("/t/{tkn}/font/{keluarga}")
def font_bertoken(tkn: str, keluarga: str):
    """Font bawaan untuk iframe kotak pasir dan mesin render."""
    _pid_dari_token(tkn)
    jalur = teks.jalur_font(keluarga)
    if jalur is None:
        raise NotFound("Font tidak ada.")
    return FileResponse(jalur, media_type="font/ttf",
                        headers={"Cache-Control": "public, max-age=86400"})


# --- komponen animasi AI (Tahap 4) -------------------------------------------

class Rentang(BaseModel):
    mulai: int = Field(..., ge=0)
    durasi: int = Field(..., ge=1)


class BuatKomponen(BaseModel):
    permintaan: str = Field(..., min_length=3, max_length=2000)
    proyek_id: Optional[str] = None
    durasi: Optional[int] = Field(None, ge=1, le=36000)
    rentang: Optional[Rentang] = None
    komponen_id: Optional[str] = Field(None, max_length=40)


class TempelKomponen(BaseModel):
    balasan: str = Field(..., min_length=10, max_length=200_000)
    permintaan: str = Field("", max_length=2000)
    proyek_id: Optional[str] = None
    durasi: Optional[int] = Field(None, ge=1, le=36000)
    rentang: Optional[Rentang] = None
    komponen_id: Optional[str] = Field(None, max_length=40)


class SimpanPustaka(BaseModel):
    nama: str = Field(..., min_length=1, max_length=80)


def _versi_publik(v: dict) -> dict:
    from . import komponen as komponen_svc
    return {**v, "gambar": komponen_svc.jumlah_gambar(v)}


@router.post("/komponen/buat")
def buat_komponen(b: BuatKomponen):
    """Animasi baru (atau revisi bila komponen_id) lewat AI: pekerjaan `montase_motion`."""
    from . import komponen as komponen_svc
    return {"job_id": komponen_svc.mulai({"mode": "ai", **b.model_dump()})}


@router.post("/komponen/tempel")
def tempel_komponen(b: TempelKomponen):
    """Balasan dari Claude.ai (salin-tempel) diperiksa dengan pemeriksa yang sama."""
    from . import komponen as komponen_svc
    return {"job_id": komponen_svc.mulai({"mode": "tempel", **b.model_dump()})}


@router.post("/komponen/permintaan-claude")
def permintaan_claude(b: BuatKomponen):
    """Pesan siap salin untuk chat di Project Claude.ai (M4.10)."""
    from . import motion_ai
    pid = profil.kini()
    dokumen = (repo.ambil_proyek(pid, b.proyek_id) or {}).get("dokumen") if b.proyek_id else None
    kanvas = (dokumen or {}).get("kanvas") or {"lebar": 1080, "tinggi": 1920, "fps": 30}
    fakta = None
    if dokumen and b.rentang:
        try:
            fakta = motion_ai.lembar_fakta(pid, dokumen, b.rentang.mulai, b.rentang.durasi)["teks"]
        except Exception:       # noqa: BLE001
            fakta = None
    kode_lama = None
    if b.komponen_id:
        kode_lama = (repo.ambil_komponen(pid, b.komponen_id) or {}).get("sumber_tsx")
    return {"teks": motion_ai.pesan(b.permintaan, kanvas=kanvas, durasi=b.durasi, fakta=fakta,
                                    kode_lama=kode_lama),
            "versi_paket": motion_ai.VERSI_KONTRAK}


@router.get("/komponen/paket-claude")
def paket_claude():
    """Berkas .md untuk Project Claude.ai: instruksi + kontrak + contoh (M4.10)."""
    from fastapi.responses import Response
    from . import motion_ai
    return Response(motion_ai.paket_claude(), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition":
                             f'attachment; filename="omniclip-montase-claude-v{motion_ai.VERSI_KONTRAK}.md"'})


@router.get("/komponen")
def daftar_komponen(pustaka: int = 0, cari: str = ""):
    return {"komponen": [_versi_publik(v) for v in
                         repo.daftar_komponen(profil.kini(), hanya_disimpan=bool(pustaka), cari=cari[:80])]}


@router.get("/komponen/{komponen_id}")
def versi_komponen(komponen_id: str):
    daftar = repo.versi_komponen(profil.kini(), komponen_id)
    if not daftar:
        raise NotFound("Animasi tidak ditemukan.")
    return {"versi": [_versi_publik(v) for v in daftar]}


@router.post("/komponen/{komponen_id}/{versi}/simpan")
def simpan_ke_pustaka(komponen_id: str, versi: int, b: SimpanPustaka):
    """Simpan ke pustaka profil (M4.8). Hanya versi yang lolos pemeriksaan."""
    if not repo.tandai_simpan(profil.kini(), komponen_id, versi, b.nama):
        raise InvalidInput("Hanya animasi yang lolos pemeriksaan yang bisa disimpan ke pustaka.")
    return _versi_publik(repo.ambil_komponen(profil.kini(), komponen_id, versi))


@router.delete("/komponen/{komponen_id}/pustaka")
def keluarkan_dari_pustaka(komponen_id: str):
    repo.hapus_dari_pustaka(profil.kini(), komponen_id)
    return {"ok": True}


@router.get("/t/{tkn}/komponen/{komponen_id}/{versi}/kode.js")
def kode_komponen(tkn: str, komponen_id: str, versi: int):
    """Hasil kompilasi untuk pratinjau dan render. Hanya versi yang lolos."""
    from fastapi.responses import Response
    pid = _pid_dari_token(tkn)
    v = repo.ambil_komponen(pid, komponen_id, versi, dengan_kode=True)
    if v is None or v["status"] != "lolos" or not v.get("hasil_js"):
        raise NotFound("Animasi tidak ada atau belum lolos pemeriksaan.")
    return Response(v["hasil_js"], media_type="text/javascript; charset=utf-8",
                    headers={"Cache-Control": "private, max-age=86400"})


@router.get("/t/{tkn}/komponen/{komponen_id}/{versi}/gambar/{n}")
def gambar_komponen(tkn: str, komponen_id: str, versi: int, n: int):
    from . import periksa as periksa_svc
    pid = _pid_dari_token(tkn)
    if repo.ambil_komponen(pid, komponen_id, versi) is None:
        raise NotFound("Animasi tidak ditemukan.")
    jalur = periksa_svc.folder_gambar(komponen_id, versi) / f"bingkai_{n}.jpg"
    if not jalur.is_file():
        raise NotFound("Gambar tidak ada.")
    return FileResponse(jalur, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


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
