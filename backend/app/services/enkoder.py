"""
Encoder video untuk render: GPU bila ada dan TERBUKTI bekerja, x264 bila tidak.

Diukur 21 September 2026 pada i5-8250U + Intel UHD 620, klip 70 detik
1080x1920:

    x264 veryfast crf 20        45,4 dtk   32 MB
    h264_vaapi qp 22            27,9 dtk   40 MB   SSIM 0,990 terhadap x264

Encoder perangkat keras ada di hampir semua laptop — Intel Quick Sync sejak
2011, NVENC di NVIDIA, AMF di AMD — tapi "ada di daftar ffmpeg" tidak sama
dengan "bekerja di mesin ini": driver bisa tidak terpasang, GPU-nya bisa
terlalu tua untuk 1080x1920. Karena itu setiap calon diuji sungguhan (satu
detik gambar uji, ukuran hasil yang sama) sebelum dipercaya, dan render yang
gagal dengan GPU diulang dengan x264. Hasil terburuknya sama dengan sebelum
modul ini ada.

ffmpeg statis yang dibundel untuk Linux (johnvansickle) tidak memuat satu pun
encoder GPU. ffmpeg bawaan distro (apt) biasanya memuat VA-API, jadi ffmpeg
lain di PATH ikut dicoba — hanya untuk render, dan hanya bila lolos uji.

`OMNICLIP_ENCODER=x264` mematikan semuanya.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
from typing import Optional

log = logging.getLogger("omniclip.enkoder")

X264 = {
    "nama": "x264",
    "ffmpeg": "ffmpeg",
    "global": [],
    "saring": "",
    "video": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
              "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1"],
}

_VAAPI_DEV = "/dev/dri/renderD128"


def _semua_ffmpeg() -> list[str]:
    """ffmpeg yang dipakai aplikasi, lalu ffmpeg lain di PATH (mis. /usr/bin)."""
    nama = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    utama = shutil.which("ffmpeg")
    keluar = [utama] if utama else []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        f = os.path.join(d, nama)
        if os.path.isfile(f) and os.access(f, os.X_OK) and \
                all(not os.path.samefile(f, g) for g in keluar):
            keluar.append(f)
    return keluar


def _calon() -> list[dict]:
    """Encoder GPU yang patut dicoba di sistem ini, untuk tiap ffmpeg yang ada."""
    c: list[dict] = []
    for ff in _semua_ffmpeg():
        for enc in _calon_encoder():
            c.append({**enc, "ffmpeg": ff})
    return c


def _calon_encoder() -> list[dict]:
    """Encoder GPU yang patut dicoba, urut dari yang paling umum."""
    c: list[dict] = []
    if sys.platform.startswith("linux") and os.path.exists(_VAAPI_DEV):
        for lp in ("1", "0"):
            c.append({
                "nama": f"h264_vaapi{' (low power)' if lp == '1' else ''}",
                "global": ["-vaapi_device", _VAAPI_DEV],
                "saring": "format=nv12,hwupload",
                "video": ["-c:v", "h264_vaapi", "-low_power", lp, "-rc_mode", "CQP",
                          "-qp", "22", "-profile:v", "high"],
            })
    c.append({
        "nama": "h264_nvenc", "global": [], "saring": "",
        "video": ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "22",
                  "-b:v", "0", "-pix_fmt", "yuv420p", "-profile:v", "high"],
    })
    c.append({
        "nama": "h264_qsv", "global": [], "saring": "format=nv12",
        "video": ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "22",
                  "-profile:v", "high"],
    })
    if sys.platform == "win32":
        c.append({
            "nama": "h264_amf", "global": [], "saring": "",
            "video": ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp",
                      "-qp_i", "22", "-qp_p", "22", "-pix_fmt", "yuv420p"],
        })
    return c


def _uji(enc: dict) -> bool:
    """Satu detik gambar uji 1080x1920, persis bentuk yang dirender."""
    # Unggahan ke GPU (hwupload) di -vf, bukan di grafik input lavfi: grafik
    # input tidak diberi perangkat, dan ujinya akan selalu gagal.
    cmd = [enc["ffmpeg"], "-hide_banner", "-nostdin", "-loglevel", "error",
           *enc["global"], "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=1",
           "-vf", "format=yuv420p" + ("," + enc["saring"] if enc["saring"] else ""),
           *enc["video"], "-f", "null", "-"]
    try:
        bendera = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        r = subprocess.run(cmd, capture_output=True, timeout=20, creationflags=bendera)
        return r.returncode == 0
    except Exception:
        return False


_kunci = threading.Lock()
_terpilih: Optional[dict] = None
_gagal: set[tuple[str, str]] = set()


def pilih() -> dict:
    """Encoder yang dipakai render. Diuji sekali per jalannya aplikasi."""
    global _terpilih
    with _kunci:
        if _terpilih is not None and (_terpilih["ffmpeg"], _terpilih["nama"]) not in _gagal:
            return _terpilih
        if os.getenv("OMNICLIP_ENCODER", "").strip().lower() == "x264":
            _terpilih = X264
            return _terpilih
        for enc in _calon():
            if (enc["ffmpeg"], enc["nama"]) in _gagal:
                continue
            if _uji(enc):
                log.info("Render memakai encoder GPU: %s (%s)", enc["nama"], enc["ffmpeg"])
                _terpilih = enc
                return enc
        log.info("Tidak ada encoder GPU yang bekerja; render memakai x264.")
        _terpilih = X264
        return _terpilih


def tandai_gagal(enc: dict) -> None:
    """Encoder GPU yang gagal di tengah render tidak dipakai lagi di jalannya ini."""
    global _terpilih
    with _kunci:
        if enc["nama"] != "x264":
            _gagal.add((enc["ffmpeg"], enc["nama"]))
            _terpilih = None
            log.warning("Encoder %s gagal saat render — kembali ke x264", enc["nama"])


def siapkan_di_latar() -> None:
    threading.Thread(target=pilih, name="enkoder", daemon=True).start()
