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
    # Dibuat untuk menampung izin Google yang sedang diminta. Bila izinnya tidak
    # pernah selesai, profil ini disapu kembali; lihat profil.sapu_sementara.
    sementara: bool = False


class ProfilUbah(BaseModel):
    nama: Optional[str] = Field(None, min_length=1, max_length=40)
    warna: Optional[str] = None
    minat: Optional[List[str]] = None
    unggah: Optional[UnggahModel] = None


# Akun yang fotonya sudah pernah dicoba diambil pada proses ini. Pengambilan
# yang gagal (jaringan mati, Google sedang menolak) tidak boleh diulang pada
# tiap pemuatan halaman Akun.
_foto_dicoba: set[int] = set()


def _foto(p: dict, tersambung: bool) -> str:
    """
    Alamat foto akun Google, diambil sekali lalu disimpan di profilnya.

    Diambil DI SINI, bukan hanya saat izin selesai: akun yang sudah tersambung
    sejak sebelum kolom `foto` ada tidak akan pernah menyambung ulang, dan
    tanpa pengambilan susulan ia selamanya tinggal berlencana huruf.
    """
    ada = (p.get("foto") or "").strip()
    if ada or not tersambung or p["id"] in _foto_dicoba:
        return ada
    _foto_dicoba.add(p["id"])
    from ..services import google_upload
    return google_upload.simpan_foto(p["id"])


def _lengkap(p: dict) -> dict:
    from ..services import google_upload
    st = google_upload.status(p["id"])
    return {
        **p,
        "foto": _foto(p, st["connected"]),
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
    # Akun yang izin Google-nya tidak pernah selesai dibuang di sini, bukan di
    # latar belakang: daftar inilah satu-satunya tempat ia akan terlihat, dan
    # membuangnya tepat sebelum daftar disusun berarti ia tidak pernah sempat
    # muncul sebagai "Akun baru" yang kosong.
    await asyncio.to_thread(layanan.sapu_sementara)
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


@router.get("/setelan")
async def lihat_setelan():
    """
    Setelan milik akun yang sedang aktif, per kelompok.

    Kenapa di server dan bukan cukup di peramban: setelan seperti tanda air
    adalah nama kanal, jadi ia milik AKUN. Sampai 9 Oktober 2026 semuanya
    tersimpan di localStorage dengan satu kunci untuk semua akun, dan
    dilaporkan "saat beralih akun dan mencoba klip pada akun tersebut watermark
    tersebut settingannya masih ada". Kunci peramban per akun akan menutup
    kebocoran itu, tapi localStorage terikat pada origin dan origin memuat
    nomor port yang bisa berpindah sendiri, dan itu sudah pernah menghapus
    ingatan peramban di sini.
    """
    from ..services import profil as profil_svc

    pid = profil_svc.kini()
    return {"profil_id": pid,
            "setelan": await asyncio.to_thread(repo.setelan, pid),
            "kelompok": list(repo.KELOMPOK)}


class SetelanModel(BaseModel):
    kelompok: str = Field(..., min_length=1, max_length=32)
    nilai: Dict[str, Any] = Field(default_factory=dict)


@router.put("/setelan")
async def simpan_setelan(req: SetelanModel):
    """Menyimpan satu kelompok setelan akun aktif. Kunci yang tidak dikirim dibiarkan."""
    from ..services import profil as profil_svc

    if req.kelompok not in repo.KELOMPOK:
        raise InvalidInput(
            f"Kelompok setelan '{req.kelompok}' tidak dikenal. "
            f"Yang ada: {', '.join(repo.KELOMPOK)}.")
    pid = profil_svc.kini()
    if not await asyncio.to_thread(repo.ambil, pid):
        raise NotFound("Profil tidak ditemukan.")
    nilai = await asyncio.to_thread(repo.simpan_setelan, pid, req.kelompok, req.nilai)
    return {"profil_id": pid, "kelompok": req.kelompok, "nilai": nilai}


@router.post("")
async def buat(req: ProfilBaru):
    if not _WARNA.match(req.warna):
        raise InvalidInput("Warna harus berbentuk #RRGGBB.")
    pid = await asyncio.to_thread(repo.buat, req.nama.strip(), warna=req.warna,
                                  minat=_rapikan_minat(req.minat),
                                  sementara=req.sementara)
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
