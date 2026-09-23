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


@router.get("")
async def daftar():
    ps = await asyncio.to_thread(repo.semua)
    return {"profil": [await asyncio.to_thread(_lengkap, p) for p in ps],
            "aktif": layanan.kini()}


@router.post("")
async def buat(req: ProfilBaru):
    if not _WARNA.match(req.warna):
        raise InvalidInput("Warna harus berbentuk #RRGGBB.")
    pid = await asyncio.to_thread(repo.buat, req.nama.strip(), warna=req.warna,
                                  minat=_rapikan_minat(req.minat))
    # Folder klipnya dibuat SEKARANG dan jalurnya disimpan: mengganti nama
    # profil nanti tidak boleh memindahkan atau memutus folder klip yang ada.
    folder = await asyncio.to_thread(layanan.folder_klip, pid)
    await asyncio.to_thread(repo.ubah, pid, folder_klip=str(folder))
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
    await asyncio.to_thread(repo.ubah, pid, nama=(req.nama or "").strip() or None,
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
