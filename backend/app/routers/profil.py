"""Profil: daftar, buat, ubah, hapus. Lihat services/profil.py."""

import asyncio
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from ..errors import InvalidInput, NotFound
from ..repos import profil as repo
from ..services import profil as layanan

router = APIRouter(prefix="/api/profil", tags=["profil"])

_WARNA = re.compile(r"^#[0-9A-Fa-f]{6}$")
PRIVASI = ("private", "unlisted", "public")


def _rapikan_minat(v: Optional[List[str]]) -> Optional[List[str]]:
    if v is None:
        return None
    keluar = []
    for m in v:
        m = (m or "").strip()[:80]
        if m and m.lower() not in {x.lower() for x in keluar}:
            keluar.append(m)
    return keluar[:20]


class UnggahModel(BaseModel):
    otomatis: Optional[bool] = None
    youtube: Optional[bool] = None
    drive: Optional[bool] = None
    privasi: Optional[str] = None
    deskripsi: Optional[str] = Field(None, max_length=4000)
    hashtag: Optional[List[str]] = None

    @field_validator("privasi")
    @classmethod
    def _cek_privasi(cls, v):
        if v is not None and v not in PRIVASI:
            raise ValueError("privasi harus private, unlisted, atau public")
        return v

    @field_validator("hashtag")
    @classmethod
    def _cek_tagar(cls, v):
        if v is None:
            return None
        return [("#" + t.strip().lstrip("#"))[:40] for t in v if t and t.strip().lstrip("#")][:15]


class ProfilBaru(BaseModel):
    nama: str = Field(..., min_length=1, max_length=40)
    warna: str = "#E0473A"
    minat: List[str] = Field(default_factory=list)


class ProfilUbah(BaseModel):
    nama: Optional[str] = Field(None, min_length=1, max_length=40)
    warna: Optional[str] = None
    minat: Optional[List[str]] = None
    unggah: Optional[UnggahModel] = None


def _lengkap(p: dict) -> dict:
    from ..services import google_upload
    st = google_upload.status(p["id"])
    return {
        **p,
        "folder_klip": str(layanan.folder_klip(p["id"])),
        "unggah": layanan.unggah(p["id"]),
        "google": {"connected": st["connected"], "email": st["email"]},
    }


# Kunci setelan tempat profil terakhir diingat.
TERAKHIR = "profil.terakhir"


def _terakhir() -> int:
    from ..repos import settings as settings_repo
    try:
        n = int((settings_repo.get(TERAKHIR) or "").strip() or 0)
    except ValueError:
        return layanan.UTAMA
    return n if n > 0 and repo.ambil(n) else layanan.UTAMA


@router.get("")
async def daftar():
    ps = await asyncio.to_thread(repo.semua)
    return {"profil": [await asyncio.to_thread(_lengkap, p) for p in ps],
            "aktif": layanan.kini(),
            # Profil yang terakhir dipakai, diingat DI SERVER.
            #
            # Peramban mengingatnya juga, tapi `localStorage` terikat pada
            # origin — dan origin itu memuat NOMOR PORT. Aplikasi memilih port
            # pertama yang kosong mulai 8000, jadi begitu 8000 dipakai program
            # lain ia pindah ke 8001, dan seluruh ingatan peramban ikut hilang.
            # Terlapor pemiliknya: membuka aplikasi selalu masuk ke "Utama",
            # bukan akun yang terakhir dipakai.
            "terakhir": await asyncio.to_thread(_terakhir)}


@router.post("/terakhir/{pid}")
async def ingat_terakhir(pid: int):
    """Mengingat profil yang barusan dipilih, supaya sesi berikutnya memakainya."""
    from ..repos import settings as settings_repo
    if not await asyncio.to_thread(repo.ambil, pid):
        raise NotFound("Profil tidak ditemukan.")
    await asyncio.to_thread(settings_repo.set_value, TERAKHIR, str(pid))
    return {"status": "ok", "terakhir": pid}


@router.post("")
async def buat(req: ProfilBaru):
    if not _WARNA.match(req.warna):
        raise InvalidInput("Warna harus berbentuk #RRGGBB.")
    pid = await asyncio.to_thread(repo.buat, req.nama.strip(), warna=req.warna,
                                  minat=_rapikan_minat(req.minat))
    # Foldernya SENGAJA belum dipatok di sini.
    #
    # Dulu dipatok, dengan alasan yang masuk akal waktu itu: mengganti nama
    # profil tidak boleh memutus folder klip yang sudah ada. Tapi saat profil
    # dibuat, akun Googlenya belum diketahui, jadi yang dipatok selalu bernama
    # "Akun baru (6)" — dan itu nama yang menempel selamanya. Sekarang folder
    # dipilih saat akun Googlenya tersambung, dari surelnya (lihat
    # services/profil.folder_untuk_akun), sehingga masuk lagi dengan akun yang
    # sama kembali ke folder yang sama.
    return await asyncio.to_thread(_lengkap, repo.ambil(pid))


@router.patch("/{pid}")
async def ubah(pid: int, req: ProfilUbah):
    lama = await asyncio.to_thread(repo.ambil, pid)
    if not lama:
        raise NotFound("Profil tidak ditemukan.")
    if req.warna is not None and not _WARNA.match(req.warna):
        raise InvalidInput("Warna harus berbentuk #RRGGBB.")
    unggah: Optional[Dict[str, Any]] = None
    if req.unggah is not None:
        unggah = {**(lama.get("unggah") or {}), **req.unggah.model_dump(exclude_none=True)}
    nama_baru = (req.nama or "").strip() or None
    # Folder klip mengikuti nama akunnya. Dikerjakan SEBELUM namanya berubah di
    # basis data, karena nama folder lama diturunkan dari nama yang lama.
    if nama_baru and nama_baru != lama.get("nama"):
        await asyncio.to_thread(layanan.ikutkan_nama_folder, pid, nama_baru)
    await asyncio.to_thread(repo.ubah, pid, nama=nama_baru,
                            warna=req.warna, minat=_rapikan_minat(req.minat), unggah=unggah)
    return await asyncio.to_thread(_lengkap, repo.ambil(pid))


@router.delete("/{pid}")
async def hapus(pid: int):
    """
    Menghapus profil — bukan berkasnya. Klip yang sudah dirender tetap di
    foldernya, dan video sumber tetap bisa dipakai profil lain. Token Google
    profil ini dibuang, jadi OmniClip tidak lagi bisa mengunggah atas namanya.
    """
    if pid == layanan.UTAMA:
        raise InvalidInput("Profil Utama tidak bisa dihapus.")
    if not await asyncio.to_thread(repo.ambil, pid):
        raise NotFound("Profil tidak ditemukan.")
    from ..services import google_upload
    folder = str(await asyncio.to_thread(layanan.folder_klip, pid))
    await asyncio.to_thread(google_upload.disconnect, pid)
    await asyncio.to_thread(repo.hapus, pid)
    return {"success": True, "folder_klip_tetap": folder}
