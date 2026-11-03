"""
Bahan dan dokumen uji Tahap 0 (JOB-4.md M0.1 sampai M0.6).

Satu dokumen proyek kecil yang menyentuh setiap jalur yang harus dibuktikan:
  - video dari backend, dibaca lewat alamat bertoken (M0.6);
  - teks biasa;
  - animasi bawaan (`ko_hitung_mundur`);
  - animasi buatan AI yang dikompilasi mesin dan dimuat saat berjalan (M0.5).

Videonya dibuat ffmpeg sendiri (pola warna + nada 440 Hz), jadi uji ini tidak
bergantung pada unduhan apa pun dan hasilnya sama di setiap komputer.

Seluruh berkas ini dibuang bersama halaman /montase-uji sesudah Tahap 1
menggantikannya dengan proyek sungguhan.
"""

from __future__ import annotations

import contextlib
import logging
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

from ..config import BUNDLE_DIR, FROZEN, PROJECT_DIR, STORAGE_DIR
from . import mesin
from . import token as token_svc

log = logging.getLogger("omniclip.montase.uji")

LINGKUP = "uji"
NAMA_VIDEO = "uji_video.mp4"
ID_KOMPONEN_AI = "ko_uji_ai"
NAMA_KOMPONEN_AI = f"{ID_KOMPONEN_AI}@1.js"
NAMA_HASIL = "hasil_uji.mp4"
BERKAS_BOLEH = {NAMA_VIDEO: "video/mp4", NAMA_KOMPONEN_AI: "text/javascript", NAMA_HASIL: "video/mp4"}

DURASI_DETIK = 30
FPS = 30
LEBAR, TINGGI = 1080, 1920


def folder() -> Path:
    return STORAGE_DIR / "montase" / "uji"


def berkas(nama: str) -> Optional[Path]:
    """Jalur berkas uji yang boleh disajikan, atau None. Nama lain selalu ditolak."""
    if nama not in BERKAS_BOLEH:
        return None
    jalur = folder() / nama
    return jalur if jalur.is_file() else None


def _sumber_komponen_ai() -> str:
    dasar = (BUNDLE_DIR / "montase_mesin") if FROZEN else (PROJECT_DIR / "montase-mesin")
    return (dasar / "uji" / "komponen_ai.jsx").read_text(encoding="utf-8")


def siapkan_video() -> Path:
    tujuan = folder() / NAMA_VIDEO
    if tujuan.is_file():
        return tujuan
    folder().mkdir(parents=True, exist_ok=True)
    sementara = tujuan.with_suffix(".tmp.mp4")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc2=size={LEBAR}x{TINGGI}:rate={FPS}:duration={DURASI_DETIK}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={DURASI_DETIK}:sample_rate=48000",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-g", str(FPS), "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
        str(sementara),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)
    sementara.replace(tujuan)
    return tujuan


def siapkan_komponen() -> dict:
    """Mengompilasi komponen AI uji. Hasilnya {lolos, masalah|peringatan}."""
    hasil = mesin.kompilasi(_sumber_komponen_ai())
    if hasil.get("lolos"):
        folder().mkdir(parents=True, exist_ok=True)
        (folder() / NAMA_KOMPONEN_AI).write_text(hasil["js"], encoding="utf-8")
    return {k: v for k, v in hasil.items() if k != "js"}


def dokumen(durasi_detik: int = DURASI_DETIK) -> dict:
    """
    Dokumen proyek uji, dalam format JOB-4.md bagian 16. Waktu dalam bingkai.

    Semua item selesai sebelum detik ke-10, jadi uji singkat 10 detik (CI)
    tetap melewati animasi bawaan, teks, dan komponen AI.
    """
    n = min(durasi_detik, DURASI_DETIK) * FPS
    return {
        "versi": 1,
        "id": "mt_uji",
        "nama": "Uji Tahap 0",
        "kanvas": {"lebar": LEBAR, "tinggi": TINGGI, "fps": FPS, "latar": "#000000"},
        "durasi": n,
        "bahan": {"b1": {"jenis": "video", "durasi": DURASI_DETIK, "lebar": LEBAR,
                         "tinggi": TINGGI, "fps": FPS, "ada_suara": True}},
        "lajur": [
            {"id": "L1", "jenis": "video", "nama": "Video 1", "item": [
                {"id": "i1", "jenis": "video", "bahan": "b1", "mulai": 0, "durasi": n,
                 "potong_awal": 0, "isi": "cover"}]},
            {"id": "L2", "jenis": "teks", "nama": "Teks", "item": [
                {"id": "i2", "jenis": "teks", "mulai": 60, "durasi": 120,
                 "teks": "Uji Montase", "gaya": {"letak": "bawah"}}]},
            {"id": "L3", "jenis": "motion", "nama": "Animasi", "item": [
                {"id": "i3", "jenis": "motion", "komponen": "ko_hitung_mundur", "versi": 1,
                 "mulai": 0, "durasi": 60, "asal": "tangan",
                 "props": {"angka": 5, "judul": "Momen paling kacau", "warna": "#FF3355"}},
                {"id": "i4", "jenis": "motion", "komponen": ID_KOMPONEN_AI, "versi": 1,
                 "mulai": 210, "durasi": 75, "asal": "ai",
                 "alasan": "Uji M0.5: komponen buatan AI dimuat saat berjalan",
                 "props": {"teks": "GILA!", "warna": "#FFD400", "serpihan": 18}}]},
        ],
    }


def sumber(dasar_url: str, tkn: str) -> dict:
    """Alamat bahan dan komponen. `dasar_url` kosong = alamat relatif (peramban)."""
    awal = f"{dasar_url.rstrip('/')}/api/montase/t/{tkn}/uji"
    return {
        "bahan": {"b1": f"{awal}/{NAMA_VIDEO}"},
        "komponen": {f"{ID_KOMPONEN_AI}@1": f"{awal}/{NAMA_KOMPONEN_AI}"},
    }


def siapkan_semua() -> dict:
    siapkan_video()
    return siapkan_komponen()


def render(dasar_url: str, *, durasi_detik: int = DURASI_DETIK,
           kabar: Optional[Callable[[dict], None]] = None,
           batal: Optional[Callable[[], bool]] = None) -> dict:
    """Merender dokumen uji lewat Mesin Montase dan mengembalikan angka-angkanya."""
    komponen = siapkan_semua()
    if not komponen.get("lolos"):
        raise mesin.GagalMesin("Komponen AI uji tidak lolos pemeriksaan: "
                               + "; ".join(komponen.get("masalah", [])))
    keluar = folder() / NAMA_HASIL
    durasi = min(durasi_detik, DURASI_DETIK)
    mulai = time.monotonic()
    hasil = mesin.render(dokumen(durasi), sumber(dasar_url, token_svc.buat(LINGKUP)), keluar,
                         kabar=kabar, batal=batal)
    dinding = time.monotonic() - mulai
    return {
        "detik_render": round(float(hasil.get("detik", dinding)), 1),
        "detik_dinding": round(dinding, 1),
        "detik_video": durasi,
        "kali_durasi": round(dinding / durasi, 2),
        "ukuran_mb": round(keluar.stat().st_size / 1e6, 1) if keluar.is_file() else None,
        "bingkai": hasil.get("bingkai"),
        "berkas": NAMA_HASIL,
    }


@contextlib.contextmanager
def server_sementara():
    """
    Server HTTP kecil berisi router Montase saja, di porta acak 127.0.0.1.

    Mesin render membaca bahan lewat HTTP (Range + CORS). Di dalam aplikasi itu
    server OmniClip sendiri; di luar aplikasi (pemeriksaan CI, baris perintah)
    server inilah penggantinya, dengan kode router dan token yang sama.
    """
    import socket
    import threading

    import uvicorn
    from fastapi import FastAPI

    from .cors import CorsBertoken
    from .router import router

    app = FastAPI()
    app.include_router(router)
    app.add_middleware(CorsBertoken)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta,
                                           log_level="warning", lifespan="off"))
    utas = threading.Thread(target=server.run, daemon=True)
    utas.start()
    tenggat = time.monotonic() + 20
    while not server.started:
        if time.monotonic() > tenggat or not utas.is_alive():
            raise mesin.GagalMesin("Server bahan sementara tidak mau menyala.")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{porta}"
    finally:
        server.should_exit = True
        utas.join(timeout=10)


def uji_lengkap(durasi_detik: int = DURASI_DETIK, *, siapkan: bool = True,
                cetak: Callable[[str], None] = print) -> dict:
    """
    Uji ujung ke ujung tanpa server OmniClip: unduh Node dan Chrome bila perlu,
    lalu render. Dipakai `OmniClip --periksa-montase` di CI dan
    `python -m app.montase.uji` di komputer pengembang.
    """
    from . import unduh

    angka: dict = {}
    if siapkan:
        if not mesin.jalur_node():
            cetak("Mengunduh Node portabel…")
            t = time.monotonic()
            unduh.pasang_node()
            angka["detik_unduh_node"] = round(time.monotonic() - t, 1)
        cetak("Menyiapkan Chrome Headless Shell…")
        t = time.monotonic()
        angka["browser"] = mesin.siapkan_browser()
        angka["detik_siapkan_browser"] = round(time.monotonic() - t, 1)
    status = mesin.status()
    angka["mesin"] = status
    if not status["siap"]:
        raise mesin.GagalMesin(f"Mesin belum lengkap: {status}")
    cetak(f"Merender video uji {durasi_detik} detik…")
    with server_sementara() as dasar:
        angka["render"] = render(dasar, durasi_detik=durasi_detik)
    keluar = folder() / NAMA_HASIL
    if not keluar.is_file() or keluar.stat().st_size < 10_000:
        raise mesin.GagalMesin("Render selesai tapi berkasnya tidak ada atau kosong.")
    return angka


if __name__ == "__main__":
    import json
    import sys

    from ..config import use_bundled_ffmpeg

    use_bundled_ffmpeg()
    detik = int(sys.argv[1]) if len(sys.argv) > 1 else DURASI_DETIK
    print(json.dumps(uji_lengkap(detik), indent=2, ensure_ascii=False))
