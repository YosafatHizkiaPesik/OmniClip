"""
Mengunduh ffmpeg dan ffprobe ke backend/bin/, untuk ikut dibungkus.

    cd backend && venv/bin/python ../tools/ambil_ffmpeg.py

ffmpeg di mesin pengembang biasanya hanya ratusan kilobita karena ia menumpang
puluhan pustaka sistem — berguna di sini, tidak berguna sama sekali di mesin
orang lain. Yang dibutuhkan aplikasi terbungkus adalah binari statis.

Sumbernya berbeda per sistem karena ukurannya berbeda jauh:

  Linux  : johnvansickle.com  -> 160 MB sepasang
  Windows: gyan.dev essentials -> unduhan 111 MB

Varian BtbN `gpl` sempat dipakai dan menghasilkan 345 MB untuk pasangan yang
sama, tanpa satu pun fitur tambahan yang dipakai OmniClip. Diukur, bukan
ditebak — lihat PERIKSA di bawah.

Keduanya build GPL, dan itu memang diperlukan: varian LGPL tidak memuat
libx264, dan tanpa x264 tidak ada satu klip pun yang bisa di-encode. OmniClip
memanggil ffmpeg sebagai proses terpisah, bukan menautkannya sebagai pustaka.
"""

import io
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

SUMBER = {
    "win32": ("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", ".exe"),
    "linux": ("https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz", ""),
}

# Yang benar-benar dipakai OmniClip. Kalau satu saja hilang, ada bagian
# aplikasi yang akan gagal diam-diam di mesin pengguna, bukan di sini.
PERIKSA_FILTER = ("ass", "sendcmd", "crop", "loudnorm", "scdet",
                  "silencedetect", "astats")
PERIKSA_ENCODER = ("libx264", "aac")

TUJUAN = Path(__file__).resolve().parent.parent / "backend" / "bin"


def _ambil(url: str) -> bytes:
    print(f"  mengunduh {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "OmniClip-build"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def _keluarkan(data: bytes, url: str, dicari: set[str]) -> int:
    n = 0
    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for info in z.infolist():
                if Path(info.filename).name in dicari:
                    (TUJUAN / Path(info.filename).name).write_bytes(z.read(info))
                    n += 1
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as t:
            for m in t.getmembers():
                if m.isfile() and Path(m.name).name in dicari:
                    f = t.extractfile(m)
                    if f:
                        (TUJUAN / Path(m.name).name).write_bytes(f.read())
                        n += 1
    return n


def _periksa(exe: Path) -> list[str]:
    """
    Menjalankan binernya dan menanyakan kemampuannya.

    Dijalankan di sini, di sistem yang sama dengan yang akan memakainya, supaya
    build Windows diperiksa di Windows dan build Linux di Linux — bukan ditebak
    dari nama berkasnya.
    """
    kurang = []
    filters = subprocess.run([str(exe), "-hide_banner", "-filters"],
                             capture_output=True, text=True).stdout
    for f in PERIKSA_FILTER:
        if not any(line.split()[1:2] == [f]
                   for line in filters.splitlines() if len(line.split()) > 1):
            kurang.append(f"filter {f}")
    encoders = subprocess.run([str(exe), "-hide_banner", "-encoders"],
                              capture_output=True, text=True).stdout
    for e in PERIKSA_ENCODER:
        if not any(line.split()[1:2] == [e]
                   for line in encoders.splitlines() if len(line.split()) > 1):
            kurang.append(f"encoder {e}")
    return kurang


def main() -> int:
    if sys.platform == "darwin":
        print("macOS tidak disediakan di sini. Pasang `brew install ffmpeg`, "
              "lalu salin ffmpeg dan ffprobe ke backend/bin/.")
        return 1

    url, ext = SUMBER["win32" if sys.platform == "win32" else "linux"]
    TUJUAN.mkdir(parents=True, exist_ok=True)

    n = _keluarkan(_ambil(url), url, {f"ffmpeg{ext}", f"ffprobe{ext}"})
    if n != 2:
        print(f"  hanya {n} dari 2 berkas ditemukan di dalam arsip.")
        return 1

    for f in sorted(TUJUAN.iterdir()):
        if f.is_file():
            f.chmod(0o755)
            print(f"  {f.name:14} {f.stat().st_size / 1e6:6.1f} MB")

    kurang = _periksa(TUJUAN / f"ffmpeg{ext}")
    if kurang:
        print("\n  BUILD INI TIDAK LENGKAP — tidak punya: " + ", ".join(kurang))
        print("  Jangan dibungkus: bagian aplikasi yang memakainya akan gagal "
              "di mesin pengguna, bukan di sini.")
        return 1

    print(f"  semua {len(PERIKSA_FILTER)} filter dan "
          f"{len(PERIKSA_ENCODER)} encoder yang dipakai OmniClip tersedia")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
