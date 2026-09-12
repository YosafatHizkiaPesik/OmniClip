# -*- mode: python ; coding: utf-8 -*-
"""
Resep pembungkusan OmniClip.

    venv/bin/pyinstaller omniclip.spec --noconfirm

Hasilnya `dist/OmniClip/` — satu folder berisi aplikasi lengkap. Bentuk
satu-folder dipilih, bukan satu-berkas: satu-berkas membongkar ± 700 MB ke
folder sementara SETIAP KALI dijalankan, yang berarti menunggu belasan detik
sebelum apa pun terjadi, dan menyalin 700 MB ke diska setiap kali dibuka.

Tiga hal yang harus ikut dan tidak ditemukan PyInstaller sendiri:

  * pustaka biner ctranslate2, onnxruntime, cv2, av — semuanya memuat `.so`
    atau `.dll` saat berjalan, bukan lewat impor Python yang bisa dilacak;
  * berkas VAD milik faster-whisper, yang adalah data, bukan kode;
  * frontend hasil build dan font subtitle.

Font subtitle bukan hiasan: tanpa berkasnya, libass jatuh ke font teks badan
lewat fontconfig, dan hasil render berhenti cocok dengan pratinjau.
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

HERE = Path(SPECPATH).resolve()
PROJECT = HERE.parent

binaries = []
datas = []
hiddenimports = []

# Paket yang membawa pustaka biner atau data yang tidak terlihat sebagai impor.
for paket in ("ctranslate2", "onnxruntime", "cv2", "av", "piper", "tokenizers"):
    d, b, h = collect_all(paket)
    datas += d
    binaries += b
    hiddenimports += h

# faster-whisper membawa model VAD Silero sebagai berkas data.
datas += collect_data_files("faster_whisper")

# Aset aplikasi. Tujuannya ditulis persis seperti yang dicari app/config.py
# saat FROZEN.
datas += [
    (str(HERE / "app" / "assets"), "app/assets"),
    (str(PROJECT / "frontend" / "dist"), "frontend_dist"),
]

# Model yang cukup kecil untuk ikut. YuNet 232 KB adalah syarat bingkai
# otomatis bekerja sama sekali; sisanya (SFace 37 MB, CAM++ 27 MB, Whisper,
# Piper) diunduh saat pertama dipakai supaya unduhan awalnya tidak membengkak.
_yunet = HERE / "models" / "face_detection_yunet_2023mar.onnx"
if _yunet.is_file():
    datas += [(str(_yunet), "models")]

# ffmpeg dan ffprobe statis, bila sudah disiapkan di backend/bin/. Skrip
# tools/ambil_ffmpeg.py yang mengunduhnya. Tanpa keduanya aplikasi tetap
# terbangun, tapi mesin penggunanya harus sudah punya ffmpeg sendiri.
_bin = HERE / "bin"
if _bin.is_dir():
    for f in _bin.iterdir():
        if f.is_file():
            binaries += [(str(f), "bin")]

hiddenimports += [
    # uvicorn memuat implementasi protokolnya lewat nama string saat berjalan.
    "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    # Ekstraktor yt-dlp juga diimpor lewat nama.
    "yt_dlp.extractor",
]

a = Analysis(
    ["omniclip_app.py"],
    pathex=[str(HERE)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Dibuang dengan sengaja: unggah YouTube memakai googleapiclient (136 MB),
    # dan ia memuat seluruh deskripsi SETIAP layanan Google. Lihat catatan di
    # PANDUAN-MEMBUNGKUS.md sebelum mengubah daftar ini.
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "setuptools",
              "PIL", "PyQt5", "PyQt6", "notebook"],
    noarchive=False,
)

# googleapiclient membawa deskripsi SETIAP layanan Google: 586 berkas, 99 MB.
# OmniClip memakai dua di antaranya. Sisanya dibuang di sini, bukan lewat
# `excludes`, karena paketnya sendiri memang dibutuhkan — yang tidak dibutuhkan
# hanya 584 berkas datanya.
def _buang_discovery_tak_terpakai(datas):
    dipakai = ("youtube", "drive")
    hasil, dibuang, bita = [], 0, 0
    for entry in datas:
        tujuan = str(entry[0]).replace("\\", "/")
        if "googleapiclient/discovery_cache/documents/" in tujuan:
            if not tujuan.rsplit("/", 1)[-1].startswith(dipakai):
                try:
                    bita += os.path.getsize(entry[1])
                except OSError:
                    pass
                dibuang += 1
                continue
        hasil.append(entry)
    if dibuang:
        print(f"  spec: {dibuang} dokumen discovery dibuang "
              f"({bita / 1e6:.0f} MB)")
    return hasil


a.datas = _buang_discovery_tak_terpakai(a.datas)

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="OmniClip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX memicu peringatan antivirus di Windows
    console=True,       # render bisa bermenit-menit; kemajuannya harus terlihat
    icon=None,
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name="OmniClip",
)
