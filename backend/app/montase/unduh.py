"""
Node portabel untuk Mesin Montase, diunduh saat Montase pertama dipakai.

Pola yang sama dengan Deno di `services/alat_yt.py`: versi dan SHA-256 dipatok
di sini, berkas diperiksa sebelum dibongkar, dan kegagalan tidak menjatuhkan
apa pun di luar Montase.

Kenapa Node diunduh dan tidak dibundel: ±30 MB terkompresi (±100 MB terbongkar)
yang hanya dibutuhkan orang yang memakai Montase. Paket mesin (kode kita +
Remotion renderer) justru ikut di dalam aplikasi, lihat mesin.py.

Versi: v22.23.4, rilis LTS keamanan 20 Oktober 2026. Hash dari
https://nodejs.org/dist/v22.23.4/SHASUMS256.txt. Menaikkan versi berarti
mengganti ketiga angka di bawah sekaligus.
"""

from __future__ import annotations

import hashlib
import logging
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from ..config import STORAGE_DIR

log = logging.getLogger("omniclip.montase.unduh")

VERSI_NODE = "22.23.4"
_DASAR = f"https://nodejs.org/dist/v{VERSI_NODE}/"

# (sistem, mesin) -> (url, sha256, jalur node di dalam arsip)
SUMBER_NODE: dict[tuple[str, str], tuple[str, str, str]] = {
    ("linux", "x86_64"): (
        _DASAR + f"node-v{VERSI_NODE}-linux-x64.tar.xz",
        "1805bcd35e6815559bd2eb97db438d3fdb0eb3a5e6a977b7c1badca76337e9ce",
        f"node-v{VERSI_NODE}-linux-x64/bin/node",
    ),
    ("windows", "amd64"): (
        _DASAR + f"node-v{VERSI_NODE}-win-x64.zip",
        "cbc74b5e0982c9dbb41525fd8fb5dcd32fbee237863f7829072f4639a1ce5f20",
        f"node-v{VERSI_NODE}-win-x64/node.exe",
    ),
}


class GagalUnduh(RuntimeError):
    pass


def folder() -> Path:
    return STORAGE_DIR / "mesin_montase"


def _platform() -> tuple[str, str]:
    sistem = "windows" if sys.platform == "win32" else sys.platform
    mesin = platform.machine().lower()
    if mesin in ("x64", "amd64") and sistem == "linux":
        mesin = "x86_64"
    return sistem, mesin


def _tujuan() -> Optional[Path]:
    sumber = SUMBER_NODE.get(_platform())
    if sumber is None:
        return None
    return folder() / f"node-v{VERSI_NODE}" / sumber[2]


def jalur_node_terunduh() -> Optional[str]:
    tujuan = _tujuan()
    return str(tujuan) if tujuan is not None and tujuan.is_file() else None


def _unduh(url: str, sha: str, ke: Path, kabar: Optional[Callable[[float], None]]) -> None:
    hasher = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=60) as respons, open(ke, "wb") as berkas:
        total = int(respons.headers.get("Content-Length") or 0)
        diterima = 0
        while True:
            potong = respons.read(1 << 20)
            if not potong:
                break
            berkas.write(potong)
            hasher.update(potong)
            diterima += len(potong)
            if kabar is not None and total:
                kabar(diterima / total)
    if hasher.hexdigest() != sha:
        raise GagalUnduh(f"Berkas Node yang diunduh tidak cocok dengan SHA-256 yang dipatok ({url}).")


def _bongkar(arsip: Path, ke: Path) -> None:
    if arsip.name.endswith(".zip"):
        with zipfile.ZipFile(arsip) as z:
            z.extractall(ke)
        return
    with tarfile.open(arsip, "r:xz") as t:
        try:
            t.extractall(ke, filter="data")
        except TypeError:  # Python tanpa filter (< 3.12)
            t.extractall(ke)


def _pangkas(akar: Path) -> None:
    """
    Membuang bagian distribusi Node yang tidak dipakai mesin: npm/npx, berkas
    header C, dan dokumentasi. Terukur pada v22.23.4 Linux: 196 MB -> ±120 MB.
    Mesin hanya menjalankan `node` dengan skrip dan node_modules miliknya sendiri.
    """
    for isi in akar.iterdir():
        for buang in ("include", "share", "lib/node_modules", "node_modules"):
            sasaran = isi / buang
            if sasaran.is_dir():
                shutil.rmtree(sasaran, ignore_errors=True)
        for pola in ("bin/npm", "bin/npx", "bin/corepack", "npm*", "npx*", "corepack*"):
            for berkas in isi.glob(pola):
                if berkas.is_file() or berkas.is_symlink():
                    berkas.unlink(missing_ok=True)


def pasang_node(kabar: Optional[Callable[[float], None]] = None) -> str:
    """Mengunduh, memeriksa, dan membongkar Node. Mengembalikan jalur `node`."""
    sudah = jalur_node_terunduh()
    if sudah:
        return sudah
    sumber = SUMBER_NODE.get(_platform())
    if sumber is None:
        raise GagalUnduh(f"Node portabel belum tersedia untuk {_platform()}.")
    url, sha, _ = sumber
    akhir = folder() / f"node-v{VERSI_NODE}"
    folder().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder(), prefix=".unduh-") as sementara:
        sementara = Path(sementara)
        arsip = sementara / url.rsplit("/", 1)[-1]
        log.info("Mengunduh Node %s untuk Montase", VERSI_NODE)
        _unduh(url, sha, arsip, kabar)
        bongkar = sementara / "isi"
        _bongkar(arsip, bongkar)
        _pangkas(bongkar)
        if akhir.exists():
            shutil.rmtree(akhir)
        bongkar.rename(akhir)
    jalur = jalur_node_terunduh()
    if not jalur:
        raise GagalUnduh("Node sudah dibongkar tapi berkas node tidak ditemukan.")
    return jalur
