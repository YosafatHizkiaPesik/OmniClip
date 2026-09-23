"""
Profil: satu orang atau satu kanal di dalam OmniClip.

Tiap profil boleh menyambungkan SATU akun Google sendiri — Drive-nya sendiri
(15 GB gratis per akun) dan kanal YouTube-nya sendiri — dan membawa folder
klip, riwayat pencarian, minat untuk beranda, serta setelan unggah otomatis
sendiri. Pemiliknya ingin satu akun fokus ke satu jenis konten.

Yang sengaja DIPAKAI BERSAMA: video sumber yang sudah diunduh dan hasil
analisisnya. Video yang sama tidak perlu diunduh dan dianalisis dua kali hanya
karena dua profil ingin mengklipnya; yang terpisah adalah daftar Partitur-nya.

Profil aktif dibawa tiap permintaan lewat header `X-Omniclip-Profil`, bukan
disimpan sekali di server: dua tab (atau laptop dan HP) boleh bekerja di
profil yang berbeda tanpa saling menimpa. Job yang dibuat selama permintaan
mencatat profilnya di payload (lihat JobQueue.enqueue), jadi render dan
unggahan yang berjalan di latar tetap tahu milik siapa mereka.
"""

from __future__ import annotations

import contextvars
import re
import shutil
from pathlib import Path
from typing import Optional

from ..config import CLIPS_DIR, STORAGE_DIR

HEADER = "x-omniclip-profil"
UTAMA = 1

_kini: contextvars.ContextVar[int] = contextvars.ContextVar("profil", default=UTAMA)

# Setelan unggah bawaan profil baru: tidak ada yang keluar dari komputer
# sampai pemiliknya sendiri menyalakannya.
UNGGAH_BAWAAN = {
    "otomatis": False,          # unggah sendiri setelah render selesai
    "youtube": True,
    "drive": False,
    # Tujuan lain, masing-masing perlu akun yang tersambung sendiri
    # (services/sosial.py). Bawaannya mati: menyalakannya berarti klip terbit
    # ke tempat umum tanpa ditinjau lagi.
    # Jarak jam antar unggahan otomatis; 0 = semuanya langsung naik.
    "jadwal_jam": 0,
    "tiktok": False,
    "facebook": False,
    "instagram": False,
    "privasi": "private",       # private | unlisted | public
    "deskripsi": "{judul}\n\n{hashtag}",
    "hashtag": ["#shorts"],
}


def kini() -> int:
    return _kini.get()


def setel(pid: int):
    return _kini.set(pid)


def pulihkan(token) -> None:
    _kini.reset(token)


def dari_header(nilai: Optional[str]) -> int:
    """Nomor profil dari header, atau profil Utama bila kosong/tidak dikenal."""
    try:
        pid = int((nilai or "").strip())
    except ValueError:
        return UTAMA
    from ..repos import profil as repo
    return pid if pid > 0 and repo.ambil(pid) else UTAMA


def _slug(nama: str) -> str:
    s = re.sub(r"[^\w\- ]+", "", nama, flags=re.UNICODE).strip()
    return re.sub(r"\s+", " ", s)[:40] or "Profil"


def folder_klip(pid: int) -> Path:
    """Folder hasil render profil ini. Profil Utama memakai folder klip lama."""
    from ..repos import profil as repo
    p = repo.ambil(pid)
    if p and p.get("folder_klip"):
        d = Path(p["folder_klip"])
    elif pid == UTAMA or not p:
        d = CLIPS_DIR
    else:
        d = CLIPS_DIR / f"{_slug(p['nama'])} ({pid})"
    d.mkdir(parents=True, exist_ok=True)
    return d


def folder_akun(pid: int) -> Path:
    """Tempat token Google profil ini (izin 0600, di luar folder klip)."""
    d = STORAGE_DIR / "akun" / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    # Token lama (sebelum ada profil) menjadi milik profil Utama.
    if pid == UTAMA:
        lama = STORAGE_DIR / "google_token.json"
        baru = d / "google_token.json"
        if lama.is_file() and not baru.exists():
            shutil.move(str(lama), str(baru))
    return d


def unggah(pid: int) -> dict:
    from ..repos import profil as repo
    p = repo.ambil(pid) or {}
    return {**UNGGAH_BAWAAN, **(p.get("unggah") or {})}


def kategori_klip(pid: int) -> str:
    """Kategori media untuk URL klip profil ini (/api/media/<kategori>/<berkas>)."""
    return f"klip_{pid}"
