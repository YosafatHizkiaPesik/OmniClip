"""
Pemeriksa komponen animasi (JOB-4 M4.4), dipakai jalur AI (API) dan jalur
salin-tempel Claude.ai yang sama persis.

Lima langkah, berhenti di yang pertama gagal:
  1. kompilasi (sucrase) dan
  2. pemeriksaan statis (impor, global, gaya CSS, URL luar): keduanya di
     montase-mesin/src/kompilasi.mjs;
  3. render 5 bingkai contoh dengan `contohProps` lewat komposisi yang sama
     dengan proyek (montase-mesin/src/periksa.mjs);
  4. bingkai kosong atau lima bingkai yang sama persis = animasinya tidak
     bergerak (dinilai di sini dari PNG-nya);
  5. bila koneksi AI bisa melihat gambar, bingkai dinilai terhadap
     permintaannya (motion_ai.nilai_bingkai); kegagalan langkah ini hanya
     peringatan, karena penilai AI bisa salah dan pemiliknya bisa melihat
     sendiri bingkainya.

Pesan masalah ditulis supaya bisa dikirim balik ke AI apa adanya.
"""

from __future__ import annotations

import base64
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..config import PORT, STORAGE_DIR
from . import mesin, teks
from . import token as token_svc

log = logging.getLogger("omniclip.montase.periksa")

# Kotak kecil abu-abu untuk membandingkan bingkai: cukup untuk "kosong" dan
# "tidak bergerak", tidak terpengaruh perbedaan halus huruf.
UKURAN_BANDING = (36, 64)
AMBANG_KOSONG = 1.5      # simpangan baku kecerahan di bawah ini = satu warna
AMBANG_DIAM = 0.6        # selisih rata-rata antar bingkai di bawah ini = sama


def folder_gambar(komponen_id: str, versi: int) -> Path:
    return STORAGE_DIR / "montase" / "komponen" / komponen_id / str(versi)


def _abu(png: Path) -> Optional[bytes]:
    w, h = UKURAN_BANDING
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(png), "-vf", f"scale={w}:{h}",
                        "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, timeout=30)
    return r.stdout if r.returncode == 0 and len(r.stdout) == w * h else None


def _simpangan(b: bytes) -> float:
    n = len(b)
    rata = sum(b) / n
    return (sum((x - rata) ** 2 for x in b) / n) ** 0.5


def _selisih(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def nilai_gerak(berkas: list[Path]) -> list[str]:
    """Masalah dari bingkai contoh: kosong semua, atau semuanya sama."""
    abu = [_abu(p) for p in berkas]
    if any(a is None for a in abu) or not abu:
        return ["Bingkai contoh tidak bisa dibaca."]
    if all(_simpangan(a) < AMBANG_KOSONG for a in abu):
        return ["Kelima bingkai contoh kosong (satu warna saja). Pastikan komponennya menggambar "
                "sesuatu dengan contohProps, dan tidak tersembunyi di luar layar."]
    beda = [_selisih(abu[i], abu[i + 1]) for i in range(len(abu) - 1)]
    if max(beda) < AMBANG_DIAM:
        return ["Kelima bingkai contoh sama persis: animasinya tidak bergerak. Gerak harus "
                "berasal dari useCurrentFrame() (interpolate/spring)."]
    return []


def _jpeg_kecil(png: Path, tujuan: Path) -> bool:
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(png), "-vf", "scale=-2:480",
                        "-q:v", "4", str(tujuan)], capture_output=True, timeout=30)
    return r.returncode == 0


def periksa(sumber: str, *, kanvas: dict, durasi: Optional[int] = None,
            props: Optional[dict] = None, pid: int = 1,
            simpan_ke: Optional[Path] = None) -> dict:
    """
    Menjalankan pemeriksaan 1-4. Mengembalikan
      {"lolos": bool, "tahap", "masalah": [...], "peringatan": [...],
       "js"?, "ekspor"?, "gambar": [jalur jpeg], "durasi"?}
    Gambar bingkai (JPEG 480p) disimpan di `simpan_ke` bila diberikan.
    """
    if len(sumber or "") > 30000:
        return {"lolos": False, "tahap": "kompilasi", "peringatan": [], "gambar": [],
                "masalah": ["Kode lebih dari 30 KB. Pecah atau sederhanakan komponennya."]}
    bundel = mesin.folder_bundel()
    if bundel is None:
        raise mesin.GagalMesin("Bundel komposisi Montase tidak ditemukan.")
    kerja = STORAGE_DIR / "montase" / "periksa"
    kerja.mkdir(parents=True, exist_ok=True)
    sementara = Path(__import__("tempfile").mkdtemp(prefix="periksa_", dir=kerja))
    try:
        tkn = token_svc.buat(f"bahan:{pid}", berlaku_detik=3600)
        dasar = f"http://127.0.0.1:{PORT}"
        font = {f["keluarga"]: f"{dasar}/api/montase/t/{tkn}/font/{f['keluarga'].replace(' ', '%20')}"
                for f in teks.font_bawaan() if teks.jalur_font(f["keluarga"])}
        hasil = mesin.jalankan("periksa", {
            "serve_url": str(bundel), "sumber": sumber, "kanvas": kanvas, "durasi": durasi,
            "props": props, "keluar": str(sementara), "browser": mesin.jalur_browser(), "font": font,
        }, batas_detik=240)
        # Mesin memakai `tahap_gagal`: kunci `tahap` dibaca mesin.py sebagai kabar kemajuan.
        if "tahap_gagal" in hasil:
            hasil["tahap"] = hasil.pop("tahap_gagal")
        hasil.setdefault("masalah", [])
        hasil.setdefault("peringatan", [])
        berkas = [Path(b["berkas"]) for b in hasil.get("bingkai", [])]
        if hasil.get("lolos"):
            masalah = nilai_gerak(berkas)
            if masalah:
                hasil.update(lolos=False, tahap="gerak", masalah=masalah)
        gambar = []
        if simpan_ke is not None and berkas:
            simpan_ke.mkdir(parents=True, exist_ok=True)
            for i, p in enumerate(berkas):
                j = simpan_ke / f"bingkai_{i}.jpg"
                if p.is_file() and _jpeg_kecil(p, j):
                    gambar.append(str(j))
        hasil["gambar"] = gambar
        hasil.pop("bingkai", None)
        return hasil
    finally:
        shutil.rmtree(sementara, ignore_errors=True)


def gambar_base64(jalur: list[str]) -> list[bytes]:
    """Isi JPEG bingkai contoh, untuk penilai AI yang bisa melihat."""
    hasil = []
    for p in jalur:
        try:
            hasil.append(Path(p).read_bytes())
        except OSError:
            pass
    return hasil


def data_url(jalur: str) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(Path(jalur).read_bytes()).decode("ascii")
