"""
Pendamping yt-dlp supaya tidak dicap bot: runtime JavaScript dan PO Token.

Diukur 21 September 2026, yt-dlp 2026.08.19, dari IP yang sudah ditandai
YouTube ("Sign in to confirm you're not a bot" untuk 5 dari 6 video):

    polos                          ditolak
    Deno + yt-dlp-ejs              ditolak
    + server PO Token              ditolak (token dibuat & dikirim)
    cookies saja                   "The page needs to be reloaded"
    cookies + Deno                 1080p
    cookies + Deno + PO Token      1080p, unduhan penuh berhasil

Dua pelajaran. Pertama, tanpa runtime JS yt-dlp berjalan di jalur yang sudah
ia sebut usang: tantangan JavaScript YouTube tidak terpecahkan, klien yang
tersisa sedikit, dan cookies pun gagal — itulah sebabnya catatan lama di
services/cookies.py menyimpulkan cookies "memperburuk". Kedua, IP yang sudah
ditandai hanya bisa ditembus dengan sesi login atau IP lain; PO Token
mengurangi peluang DITANDAI, bukan mencabut tanda yang sudah ada.

Deno dan server PO Token (bgutil-pot, Rust, satu berkas) diunduh sekali ke
folder data saat pertama dibutuhkan, dengan versi dan SHA-256 yang dikunci di
sini. Plugin yt-dlp-nya juga diunduh, bukan dibundel: plugin dan servernya
berlisensi GPL-3.0, dan menjalankannya sebagai unduhan terpisah menjaga
OmniClip tidak ikut terikat lisensi itu.

Semua ini gagal dengan anggun. Tanpa jaringan ke GitHub, OmniClip tetap
berjalan persis seperti sebelumnya.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

log = logging.getLogger("omniclip.alat_yt")

VERSI_DENO = "2.9.7"
VERSI_POT = "0.8.1"
_GH_DENO = f"https://github.com/denoland/deno/releases/download/v{VERSI_DENO}/"
_GH_POT = f"https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/releases/download/v{VERSI_POT}/"

# (sistem, mesin) -> {alat: (url, sha256, nama di dalam zip atau None)}
SUMBER: dict[tuple[str, str], dict[str, tuple[str, str, Optional[str]]]] = {
    ("linux", "x86_64"): {
        "deno": (_GH_DENO + "deno-x86_64-unknown-linux-gnu.zip",
                 "c6527f24f4b16031d3ae4fa9f658d5f11534c8d84ce7dc8502420280919c3490", "deno"),
        "pot": (_GH_POT + "bgutil-pot-linux-x86_64",
                "e7c264a574fa2705b6e5dc62283a8a4e80130f27b9d7e9df44e6b09aa6151a87", None),
    },
    ("windows", "x86_64"): {
        "deno": (_GH_DENO + "deno-x86_64-pc-windows-msvc.zip",
                 "a0c3101b4158d1dfb7d6a78a7bf0f3de80c96bb423c152beec8beb22786f2238", "deno.exe"),
        "pot": (_GH_POT + "bgutil-pot-windows-x86_64.exe",
                "25d6b05c79176aa792454c3d1727922ca47e56cf11cb1e866615d751819b14a0", None),
    },
}
PLUGIN = (_GH_POT + "bgutil-ytdlp-pot-provider-rs.zip",
          "99fd83b98fa93b193d6a3b69dc74410d76e7a2b889868c54d16121cac9060344")
# Hanya jalur HTTP. Jalur CLI menjalankan proses baru untuk tiap video dan
# selalu tercatat "unavailable" karena binernya tidak ada di PATH.
PLUGIN_BERKAS = ("yt_dlp_plugins/extractor/getpot_bgutil.py",
                 "yt_dlp_plugins/extractor/getpot_bgutil_http.py")

BATAS_UNDUH = 120 * 1024 * 1024
PORT_BAWAAN = 4416

_kunci = threading.Lock()
_proses: Optional[subprocess.Popen] = None
_url_pot: Optional[str] = None
_status: dict = {"deno": "belum", "pot": "belum", "plugin": "belum", "galat": ""}


def _folder() -> Path:
    from ..config import STORAGE_DIR
    d = Path(STORAGE_DIR) / "alat"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _platform() -> tuple[str, str]:
    sistem = {"win32": "windows", "linux": "linux", "darwin": "macos"}.get(sys.platform, sys.platform)
    mesin = platform.machine().lower()
    mesin = {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}.get(mesin, mesin)
    return sistem, mesin


def _exe(nama: str) -> str:
    return nama + (".exe" if sys.platform == "win32" else "")


def _unduh(url: str, sha: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "OmniClip"})
    with urllib.request.urlopen(req, timeout=300) as r:
        isi = r.read(BATAS_UNDUH + 1)
    if len(isi) > BATAS_UNDUH:
        raise ValueError(f"berkas terlalu besar: {url}")
    nyata = hashlib.sha256(isi).hexdigest()
    if nyata != sha.lower():
        # Berkas yang tidak cocok tidak pernah menyentuh cakram.
        raise ValueError(f"sha256 tidak cocok untuk {url.rsplit('/', 1)[-1]}")
    return isi


def _tulis_exe(tujuan: Path, isi: bytes) -> None:
    sementara = tujuan.with_suffix(tujuan.suffix + ".sedang")
    sementara.write_bytes(isi)
    if sys.platform != "win32":
        sementara.chmod(0o755)
    os.replace(sementara, tujuan)


def _pastikan(alat: str) -> Optional[Path]:
    """Jalur biner `alat` ("deno"/"pot"), diunduh bila belum ada."""
    sumber = SUMBER.get(_platform(), {}).get(alat)
    nama = _exe("deno" if alat == "deno" else "bgutil-pot")
    tujuan = _folder() / f"{alat}-{VERSI_DENO if alat == 'deno' else VERSI_POT}" / nama
    if tujuan.is_file():
        return tujuan
    if sumber is None:
        return None
    url, sha, di_zip = sumber
    log.info("Mengunduh %s untuk yt-dlp (sekali saja)…", alat)
    isi = _unduh(url, sha)
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    if di_zip:
        with zipfile.ZipFile(io.BytesIO(isi)) as z:
            isi = z.read(di_zip)
    _tulis_exe(tujuan, isi)
    return tujuan


def _pastikan_plugin() -> Optional[Path]:
    d = _folder() / f"plugin-{VERSI_POT}"
    if all((d / b).is_file() for b in PLUGIN_BERKAS):
        return d
    isi = _unduh(*PLUGIN)
    sementara = _folder() / f".plugin-{VERSI_POT}.sedang"
    shutil.rmtree(sementara, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(isi)) as z:
        for b in PLUGIN_BERKAS:
            t = sementara / b
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_bytes(z.read(b))
    shutil.rmtree(d, ignore_errors=True)
    os.replace(sementara, d)
    return d


def _muat_plugin(d: Path) -> bool:
    """Mendaftarkan penyedia PO Token ke yt-dlp (terdaftar saat modulnya diimpor)."""
    if str(d) not in sys.path:
        sys.path.append(str(d))
    try:
        import yt_dlp_plugins.extractor.getpot_bgutil_http  # noqa: F401
        return True
    except Exception as e:
        log.warning("Plugin PO Token gagal dimuat: %s", str(e)[:160])
        return False


def _port_bebas(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _ping(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/ping", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _mulai_server(pot: Path) -> Optional[str]:
    global _proses
    port = PORT_BAWAAN
    if not _port_bebas(port):
        # Mungkin server kita sendiri dari jalannya aplikasi sebelumnya, atau
        # server bgutil yang dipasang pengguna — keduanya boleh dipakai.
        if _ping(f"http://127.0.0.1:{port}"):
            return f"http://127.0.0.1:{port}"
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    catatan = open(_folder() / "pot-server.log", "ab")   # noqa: SIM115 — hidup selama prosesnya
    bendera = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    # Hanya di 127.0.0.1: server ini tanpa autentikasi, dan bawaannya
    # mendengarkan di semua antarmuka.
    _proses = subprocess.Popen([str(pot), "server", "--host", "127.0.0.1", "--port", str(port)],
                               stdout=catatan, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, creationflags=bendera)
    for _ in range(40):
        if _ping(url):
            return url
        if _proses.poll() is not None:
            break
        time.sleep(0.25)
    log.warning("Server PO Token tidak menjawab; yt-dlp berjalan tanpa token.")
    hentikan()
    return None


def siapkan() -> dict:
    """Mengunduh (bila perlu) dan menyalakan semuanya. Aman dipanggil berulang."""
    global _url_pot
    with _kunci:
        try:
            _status["deno"] = str(_pastikan("deno") or "tidak tersedia untuk sistem ini")
        except Exception as e:
            _status["deno"] = "gagal"
            _status["galat"] = f"deno: {str(e)[:160]}"
            log.warning("Deno tidak bisa disiapkan: %s", e)
        if _url_pot is None or not _ping(_url_pot):
            try:
                plugin = _pastikan_plugin()
                pot = _pastikan("pot")
                if plugin and pot and _muat_plugin(plugin):
                    _status["plugin"] = "dimuat"
                    _url_pot = _mulai_server(pot)
                    _status["pot"] = _url_pot or "gagal menyala"
                else:
                    _status["pot"] = "tidak tersedia untuk sistem ini"
            except Exception as e:
                _status["pot"] = "gagal"
                _status["galat"] = f"PO Token: {str(e)[:160]}"
                log.warning("PO Token tidak bisa disiapkan: %s", e)
        return dict(_status)


def siapkan_di_latar() -> None:
    threading.Thread(target=siapkan, name="alat-yt", daemon=True).start()


def hentikan() -> None:
    global _proses, _url_pot
    p, _proses, _url_pot = _proses, None, None
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


def _jalur_deno() -> Optional[str]:
    d = _folder() / f"deno-{VERSI_DENO}" / _exe("deno")
    if d.is_file():
        return str(d)
    return shutil.which("deno")


def terapkan(opts: dict) -> dict:
    """Menambahkan runtime JS dan alamat server PO Token ke opsi yt-dlp."""
    deno = _jalur_deno()
    if deno:
        opts["js_runtimes"] = {"deno": {"path": deno}}
    elif shutil.which("node"):
        opts["js_runtimes"] = {"node": {}}
    # Bila yt-dlp memperbarui diri ke versi yang menuntut skrip pemecah
    # tantangan lain dari yang dibundel, ia mengambil yang cocok dari rilis
    # resminya sendiri — bukan diam-diam kehilangan separuh formatnya.
    opts["remote_components"] = {"ejs:github"}
    if _url_pot:
        ea = dict(opts.get("extractor_args") or {})
        ea["youtubepot-bgutilhttp"] = {"base_url": [_url_pot]}
        opts["extractor_args"] = ea
    return opts


def status() -> dict:
    return {**_status, "deno_dipakai": _jalur_deno(), "pot_url": _url_pot}
