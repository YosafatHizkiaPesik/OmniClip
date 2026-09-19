"""
Memeriksa apakah aliran video sebuah berkas BERLUBANG.

Unduhan yang kehilangan potongan tetap bisa dirakit menjadi .mp4 yang tampak
sehat: durasinya benar, audionya utuh, dan pemutar mana pun membukanya tanpa
keluhan. Yang hilang hanya beberapa detik gambar, dan itu baru terlihat di
hasil render sebagai gambar yang membeku.

Pemeriksaannya membaca cap waktu PAKET, tanpa mendekode apa pun, jadi video 40
menit selesai dalam hitungan detik.
"""

import subprocess
from pathlib import Path

CELAH_MIN = 1.0   # detik tanpa satu bingkai pun


def cari_lubang(path: Path, celah_min: float = CELAH_MIN) -> list[dict]:
    """[{mulai, lebar}] dalam detik. Kosong berarti utuh (atau tidak terbaca)."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(path)]
    try:
        keluar = subprocess.run(cmd, capture_output=True, text=True, timeout=300).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    waktu = sorted(float(x) for x in keluar.split() if x.replace(".", "", 1).isdigit())
    return [{"mulai": round(a, 2), "lebar": round(b - a, 2)}
            for a, b in zip(waktu, waktu[1:]) if b - a >= celah_min]
