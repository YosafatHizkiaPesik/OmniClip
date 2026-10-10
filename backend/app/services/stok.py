"""
Saran gambar stok dari Pexels (JOB-2 F2-6, opsional).

Gambar pendukung (B-roll) adalah modifikasi visual yang disebut kebijakan
YouTube, dan Pexels mengizinkan pemakaian gratis termasuk untuk komersial,
tanpa wajib atribusi. Pixabay tidak dipakai: satu sumber cukup, dan dua kunci
API berarti dua hal yang harus diurus pemiliknya.

Yang TIDAK dilakukan di sini: memasang gambar sendiri. Gambar yang dipilih
mesin dari kata kunci sering salah arti (kata "bola" di obrolan politik), dan
gambar yang salah lebih buruk daripada tidak ada. Studio menampilkan hasil
pencarian, orangnya yang memilih, baru gambar itu diunduh ke pustaka asetnya.

Kunci API Pexels gratis, didaftar sendiri oleh pemilik di pexels.com/api.
Disimpan di setelan global (berlaku untuk semua akun) atau dibaca dari
variabel lingkungan PEXELS_API_KEY.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from ..repos import settings as settings_repo

log = logging.getLogger("omniclip.stok")

KUNCI_SETELAN = "stok.pexels_key"
API = "https://api.pexels.com/v1/search"
HOST_GAMBAR = ("images.pexels.com",)
BATAS_DETIK = 20
BATAS_UNDUH = 15 * 1024 * 1024


def kunci() -> str:
    return (settings_repo.get(KUNCI_SETELAN, "") or os.environ.get("PEXELS_API_KEY", "")).strip()


def setel_kunci(nilai: str) -> None:
    nilai = (nilai or "").strip()
    if nilai and not re.fullmatch(r"[A-Za-z0-9]{20,80}", nilai):
        raise ValueError("Kunci Pexels terlihat tidak sah. Salin utuh dari pexels.com/api.")
    if nilai:
        settings_repo.set_value(KUNCI_SETELAN, nilai)
    else:
        settings_repo.delete(KUNCI_SETELAN)


def cari(kata: str, *, orientasi: str = "portrait", jumlah: int = 12) -> list[dict]:
    import requests

    k = kunci()
    if not k:
        raise PermissionError("Kunci API Pexels belum diisi.")
    kata = " ".join((kata or "").split())[:80]
    if not kata:
        raise ValueError("Tulis dulu kata yang dicari.")
    r = requests.get(API, headers={"Authorization": k}, timeout=BATAS_DETIK,
                     params={"query": kata, "per_page": max(1, min(30, jumlah)),
                             "orientation": orientasi if orientasi in
                             ("portrait", "landscape", "square") else "portrait"})
    if r.status_code in (401, 403):
        raise PermissionError("Kunci API Pexels ditolak. Periksa lagi kuncinya.")
    r.raise_for_status()
    hasil = []
    for f in (r.json() or {}).get("photos") or []:
        src = f.get("src") or {}
        if not src.get("large2x"):
            continue
        hasil.append({
            "id": f.get("id"), "alt": (f.get("alt") or "")[:160],
            "pratinjau": src.get("medium") or src.get("small"),
            "unduh": src.get("large2x"),
            "fotografer": (f.get("photographer") or "")[:80],
            "halaman": f.get("url") or "",
            "lebar": f.get("width"), "tinggi": f.get("height"),
        })
    return hasil


def ambil(url: str, nama: str = "") -> dict:
    """Mengunduh satu gambar Pexels ke pustaka aset pengguna."""
    import requests

    from . import aset as aset_svc

    u = urlparse((url or "").strip())
    if u.scheme != "https" or u.hostname not in HOST_GAMBAR:
        raise ValueError("Hanya gambar dari Pexels yang bisa diambil di sini.")
    with tempfile.TemporaryDirectory() as d:
        tujuan = Path(d) / "stok.jpg"
        with requests.get(url, stream=True, timeout=BATAS_DETIK) as r:
            r.raise_for_status()
            total = 0
            with open(tujuan, "wb") as f:
                for blok in r.iter_content(1 << 16):
                    total += len(blok)
                    if total > BATAS_UNDUH:
                        raise ValueError("Gambarnya terlalu besar.")
                    f.write(blok)
        nama = re.sub(r"[^\w\s-]", "", nama or "")[:60].strip() or "pexels"
        return aset_svc.simpan_unggahan(tujuan, f"{nama}.jpg")
