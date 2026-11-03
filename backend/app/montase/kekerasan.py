"""
Penyamaan kekerasan suara hasil ekspor Montase (JOB-4 M3.9).

Remotion mencampur suara apa adanya: klip yang pelan tetap pelan, narasi yang
keras tetap keras. YouTube menurunkan video di atas -14 LUFS dan membiarkan
yang lebih pelan tetap pelan, jadi hasil ekspor diratakan ke -14 LUFS dengan
`loudnorm` DUA lintasan: lintasan pertama mengukur, lintasan kedua memakai
angka itu dengan `linear=true`, sehingga keseluruhan video dinaikkan atau
diturunkan sebagai satu kesatuan (tanpa "memompa" seperti satu lintasan).

Gambar disalin tanpa dikode ulang (`-c:v copy`); hanya suaranya yang ditulis
ulang. Video tanpa suara, atau yang suaranya senyap, dibiarkan apa adanya.
Kegagalan di sini tidak menggagalkan ekspor: berkas aslinya tetap dipakai.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger("omniclip.montase.kekerasan")

TARGET_I = -14.0
TARGET_TP = -1.5
TARGET_LRA = 11.0
_FILTER = f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}"


def _ada_suara(jalur: Path) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                        "stream=index", "-of", "csv=p=0", str(jalur)],
                       capture_output=True, text=True, timeout=60)
    return bool(r.stdout.strip())


def ukur(jalur: Path, timeout: float = 1800) -> Optional[dict]:
    """Lintasan pertama: angka loudnorm (JSON di stderr), atau None."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(jalur), "-vn",
                        "-af", f"{_FILTER}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=timeout)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr or "", re.S)
    if r.returncode != 0 or not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def ratakan(jalur: Path, *, timeout: float = 1800) -> dict:
    """
    Meratakan berkas di tempat. Mengembalikan {"diratakan": bool, "lufs_awal",
    "lufs_akhir"?, "alasan"?}.
    """
    if not _ada_suara(jalur):
        return {"diratakan": False, "alasan": "tanpa suara"}
    a = ukur(jalur, timeout)
    if a is None:
        return {"diratakan": False, "alasan": "pengukuran gagal"}
    try:
        masuk = float(a["input_i"])
    except (KeyError, ValueError):
        return {"diratakan": False, "alasan": "pengukuran gagal"}
    if masuk == float("-inf") or masuk < -70:
        return {"diratakan": False, "alasan": "senyap", "lufs_awal": masuk}
    nilai = (f"{_FILTER}:measured_I={a['input_i']}:measured_TP={a['input_tp']}"
             f":measured_LRA={a['input_lra']}:measured_thresh={a['input_thresh']}"
             f":offset={a['target_offset']}:linear=true,aresample=48000")
    sementara = jalur.with_name(jalur.stem + ".rata" + jalur.suffix)
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-nostdin", "-loglevel", "error",
                        "-i", str(jalur), "-map", "0:v?", "-map", "0:a:0", "-c:v", "copy",
                        "-af", nilai, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                        str(sementara)], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 or not sementara.is_file() or sementara.stat().st_size == 0:
        sementara.unlink(missing_ok=True)
        log.warning("loudnorm gagal, berkas asli dipakai: %s", (r.stderr or "")[-300:])
        return {"diratakan": False, "alasan": "ffmpeg gagal", "lufs_awal": masuk}
    sementara.replace(jalur)
    return {"diratakan": True, "lufs_awal": round(masuk, 1)}
