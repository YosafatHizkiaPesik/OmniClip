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
for paket in ("ctranslate2", "onnxruntime", "cv2", "av", "piper", "tokenizers",
              # Skrip JS pemecah tantangan YouTube, dimuat sebagai berkas data.
              "yt_dlp_ejs"):
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

# --- Identitas berkas untuk Windows ------------------------------------------
#
# Bukan hiasan. Berkas .exe tanpa tanda tangan DAN tanpa keterangan versi
# adalah bentuk yang paling mirip malware bagi Windows Defender: tidak ada
# nama penerbit, tidak ada nama produk, tidak ada apa pun untuk dibandingkan.
# Mengisinya tidak membuat peringatannya hilang sendiri — hanya tanda tangan
# yang bisa — tapi ia satu dari sedikit hal yang bisa dikerjakan tanpa
# membayar, dan ia juga yang membuat Properties berkasnya masuk akal dibaca.
import sys as _sys

_versi = "1.0.0"
for _baris in (HERE / "app" / "version.py").read_text(encoding="utf-8").splitlines():
    if _baris.startswith("__version__"):
        _versi = _baris.split('"')[1]
        break
_v = tuple(int(x) for x in (_versi.split(".") + ["0", "0", "0"])[:3]) + (0,)

_berkas_versi = None
if _sys.platform == "win32":
    _berkas_versi = HERE / "build" / "versi_windows.txt"
    _berkas_versi.parent.mkdir(parents=True, exist_ok=True)
    _berkas_versi.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={_v}, prodvers={_v}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'OmniClip'),
      StringStruct('FileDescription', 'OmniClip — pemotong klip otomatis'),
      StringStruct('FileVersion', '{_versi}'),
      StringStruct('InternalName', 'OmniClip'),
      StringStruct('OriginalFilename', 'OmniClip.exe'),
      StringStruct('ProductName', 'OmniClip'),
      StringStruct('ProductVersion', '{_versi}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ]
)
""", encoding="utf-8")

_ikon = HERE / "app" / "assets" / "omniclip.ico"

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="OmniClip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX memicu peringatan antivirus di Windows
    # Jendela konsol disembunyikan di Windows: yang dilihat pemiliknya cuma
    # kotak hitam berisi teks yang tidak ia mengerti, muncul bersama
    # aplikasinya dan tidak boleh ditutup. Kemajuan render ada di halamannya
    # sendiri. Di Linux ia dibiarkan — di sana aplikasi memang dijalankan dari
    # terminal, dan tidak ada jendela yang muncul sendiri.
    console=_sys.platform != "win32",
    icon=str(_ikon) if _ikon.is_file() else None,
    version=str(_berkas_versi) if _berkas_versi else None,
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name="OmniClip",
)
