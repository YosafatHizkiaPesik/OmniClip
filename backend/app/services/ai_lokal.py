"""
AI lokal OmniClip: model bahasa kecil yang berjalan di komputer ini.

Diminta pemilik 17 Oktober 2026, sesudah semua proyek Gemini-nya berstatus
"Restricted": OmniClip tidak boleh bergantung sepenuhnya pada API milik orang
lain. Ini jalan keluarnya, dengan batas yang dikatakan terus terang: model yang
muat di laptop 8 GB jauh lebih kecil daripada Gemini, jadi tugasnya dibuat
sempit. Ia tidak membaca seluruh transkrip; ia menilai kandidat klip yang sudah
disaring mesin lokal, lalu menulis judul, tagar, dan alasannya
(lihat gemini.refine_lokal).

Mesinnya llama.cpp (`llama-server`, lisensi MIT), build yang DIPATOK beserta
sha256-nya dari GitHub, diunduh sekali ke folder alat. Modelnya GGUF dari
Hugging Face, juga dipatok sha256-nya. Keduanya hanya diunduh bila pemiliknya
menekan Pasang.

Supaya laptopnya tidak tercekik:
  * server dinyalakan HANYA saat ada pekerjaan, dan dimatikan sendiri sesudah
    MENGANGGUR_DETIK tanpa permintaan, jadi memorinya kembali;
  * sebelum menyala, RAM bebas diperiksa; bila kurang, ia menolak dengan
    alasan yang jelas alih-alih membuat sistem swap;
  * berjalan dengan prioritas rendah (nice 10) dan separuh inti CPU;
  * satu permintaan sekaligus (`-np 1`), cache KV dikuantisasi ke q8_0.
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("omniclip.ai_lokal")

BUILD = "b11390"          # llama.cpp, 4 Oktober 2026
_RILIS = f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD}/"
# (sistem, mesin) -> (nama berkas, sha256)
MESIN = {
    ("linux", "x86_64"): (f"llama-{BUILD}-bin-ubuntu-x64.tar.gz",
                          "e533bc71f5d680f9f9ba80a3d7291ea9d7f878a6821213449756bb4850c8836a"),
    ("linux", "aarch64"): (f"llama-{BUILD}-bin-ubuntu-arm64.tar.gz",
                           "d360c0d102409702f89a5dbb5b5704dcdba8989df4dbf48728ae5d356148a9ad"),
    ("windows", "x86_64"): (f"llama-{BUILD}-bin-win-cpu-x64.zip",
                            "071e95e15271ec8424a76caa3559f5353080635289b073b5b83067c13d035fc3"),
    ("macos", "aarch64"): (f"llama-{BUILD}-bin-macos-arm64.tar.gz",
                           "58f9636642b33f2929ee3a70da2a1b658f84312c85a1da56fd715f83b83d9228"),
    ("macos", "x86_64"): (f"llama-{BUILD}-bin-macos-x64.tar.gz",
                          "a7633e9729612b69844527f8ef36cabd50c12673c9a1b84cea3abc161bb0cd93"),
}

# Model yang ditawarkan. Diuji 17 Oktober 2026 pada wawancara 78 menit
# (12 kandidat, 8 pilihan): Qwen3 4B menulis judul spesifik dan beragam dengan
# skor yang dibedakan, ±8 menit di laptop 8 GB; Qwen2.5 3B lebih cepat (±4
# menit) tapi judulnya seragam dan sering memilih terlalu sedikit. Karena itu
# 4B yang disarankan. Ukuran dan sha256 dibaca dari Hugging Face
# (x-linked-size / x-linked-etag) 17 Oktober 2026. `ram_mb` = perkiraan
# memori saat berjalan dengan konteks KONTEKS dan cache KV q8_0.
MODEL = {
    "qwen3-4b": {
        "nama": "Qwen3 4B Instruct",
        "url": "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/"
               "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        "sha256": "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597",
        "bita": 2497281120, "ram_mb": 3300,
    },
    "qwen2.5-3b": {
        "nama": "Qwen2.5 3B Instruct",
        "url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/"
               "qwen2.5-3b-instruct-q4_k_m.gguf",
        "sha256": "626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d",
        "bita": 2104932768, "ram_mb": 2600,
    },
    "qwen2.5-1.5b": {
        "nama": "Qwen2.5 1.5B Instruct",
        "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
               "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "sha256": "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e",
        "bita": 1117320736, "ram_mb": 1500,
    },
}
MODEL_BAWAAN = "qwen3-4b"

KONTEKS = 8192
MENGANGGUR_DETIK = 90
CADANGAN_RAM_MB = 400          # yang harus tetap bebas untuk sistem


# --- Tempat ---------------------------------------------------------------------

def _platform() -> tuple[str, str]:
    sistem = {"win32": "windows", "linux": "linux", "darwin": "macos"}.get(sys.platform, sys.platform)
    mesin = platform.machine().lower()
    mesin = {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}.get(mesin, mesin)
    return sistem, mesin


def _folder() -> Path:
    from ..config import STORAGE_DIR
    d = Path(STORAGE_DIR) / "alat" / "ai_lokal"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _folder_model() -> Path:
    d = _folder() / "model"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _berkas_model(kunci: str) -> Path:
    return _folder_model() / MODEL[kunci]["url"].rsplit("/", 1)[-1]


def _server() -> Optional[Path]:
    nama = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    for p in (_folder() / BUILD).rglob(nama):
        if p.is_file():
            return p
    return None


def ram_bebas_mb() -> int:
    """RAM yang masih bisa dipakai, lintas sistem; 0 bila tidak terbaca."""
    if sys.platform == "win32":
        try:
            import ctypes

            class _M(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = _M()
            m.dwLength = ctypes.sizeof(_M)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return int(m.ullAvailPhys // (1024 * 1024))
        except Exception:                                 # noqa: BLE001
            return 0
    try:
        with open("/proc/meminfo") as f:
            for baris in f:
                if baris.startswith("MemAvailable:"):
                    return int(baris.split()[1]) // 1024
    except OSError:
        pass
    if sys.platform == "darwin":
        try:
            keluar = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
            halaman = 4096
            bebas = sum(int(b.split(":")[1].strip().rstrip("."))
                        for b in keluar.splitlines()
                        if b.startswith(("Pages free", "Pages inactive")))
            return bebas * halaman // (1024 * 1024)
        except Exception:                                 # noqa: BLE001
            return 0
    return 0


# --- Status ---------------------------------------------------------------------

def status() -> dict:
    sistem, mesin = _platform()
    model = []
    for kunci, m in MODEL.items():
        p = _berkas_model(kunci)
        model.append({"id": kunci, "nama": m["nama"], "ukuran_mb": round(m["bita"] / 1e6),
                      "ram_mb": m["ram_mb"], "terpasang": p.is_file() and p.stat().st_size == m["bita"]})
    return {
        "didukung": (sistem, mesin) in MESIN,
        "mesin_terpasang": _server() is not None,
        "model": model,
        "bawaan": MODEL_BAWAAN,
        "ram_bebas_mb": ram_bebas_mb(),
        "berjalan": _proses is not None and _proses.poll() is None,
        "model_jalan": _model_jalan,
    }


# --- Pasang ---------------------------------------------------------------------

def _unduh_ke(url: str, tujuan: Path, sha: str, ukuran: int,
              kabar: Optional[Callable[[float, str], None]] = None,
              batal: Optional[Callable[[], None]] = None) -> None:
    """Unduh mengalir ke berkas .part (bisa dilanjutkan), lalu verifikasi sha256."""
    sementara = tujuan.with_suffix(tujuan.suffix + ".part")
    sudah = sementara.stat().st_size if sementara.exists() else 0
    if ukuran and sudah > ukuran:
        sementara.unlink()
        sudah = 0
    if not ukuran or sudah < ukuran:
        kepala = {"User-Agent": "OmniClip"}
        if sudah:
            kepala["Range"] = f"bytes={sudah}-"
        req = urllib.request.Request(url, headers=kepala)
        with urllib.request.urlopen(req, timeout=60) as r:
            if sudah and r.status != 206:
                sudah = 0                 # server tidak mendukung lanjutan
            mode = "ab" if sudah else "wb"
            total = ukuran or (sudah + int(r.headers.get("Content-Length") or 0))
            terakhir = 0.0
            with open(sementara, mode) as f:
                while True:
                    if batal is not None:
                        batal()
                    potong = r.read(1 << 20)
                    if not potong:
                        break
                    f.write(potong)
                    sudah += len(potong)
                    if kabar is not None and time.monotonic() - terakhir > 0.7:
                        terakhir = time.monotonic()
                        kabar(sudah / total if total else 0.0,
                              f"Mengunduh {tujuan.name}: {sudah / 1e6:.0f} dari {total / 1e6:.0f} MB")
    if kabar is not None:
        kabar(1.0, "Memeriksa keaslian berkas…")
    h = hashlib.sha256()
    with open(sementara, "rb") as f:
        for potong in iter(lambda: f.read(1 << 20), b""):
            h.update(potong)
    if h.hexdigest() != sha.lower():
        sementara.unlink(missing_ok=True)
        raise ValueError("Berkas unduhan rusak (sha256 tidak cocok). Coba pasang lagi.")
    os.replace(sementara, tujuan)


def pasang(model: str = MODEL_BAWAAN, kabar=None, batal=None) -> dict:
    """Mengunduh mesin llama.cpp (sekali) dan satu model."""
    if model not in MODEL:
        raise ValueError("Model AI lokal tidak dikenal.")
    sistem, mesin = _platform()
    if (sistem, mesin) not in MESIN:
        raise ValueError("AI lokal belum tersedia untuk sistem ini.")
    m = MODEL[model]
    bebas_disk = shutil.disk_usage(_folder()).free
    if bebas_disk < m["bita"] + 300_000_000:
        raise ValueError(f"Ruang cakram tidak cukup: butuh sekitar {m['bita'] / 1e9:.1f} GB.")

    if _server() is None:
        nama, sha = MESIN[(sistem, mesin)]
        arsip = _folder() / nama
        _unduh_ke(_RILIS + nama, arsip, sha, 0,
                  kabar=(lambda f, p: kabar(0.05 * f, p)) if kabar else None, batal=batal)
        tujuan = _folder() / BUILD
        tujuan.mkdir(exist_ok=True)
        if nama.endswith(".zip"):
            with zipfile.ZipFile(arsip) as z:
                z.extractall(tujuan)
        else:
            with tarfile.open(arsip) as t:
                t.extractall(tujuan, filter="data")
        arsip.unlink(missing_ok=True)
        srv = _server()
        if srv is None:
            raise ValueError("Arsip llama.cpp tidak memuat llama-server.")
        if sys.platform != "win32":
            for p in srv.parent.iterdir():
                if p.is_file() and not p.suffix:
                    p.chmod(0o755)

    berkas = _berkas_model(model)
    if not (berkas.is_file() and berkas.stat().st_size == m["bita"]):
        _unduh_ke(m["url"], berkas, m["sha256"], m["bita"],
                  kabar=(lambda f, p: kabar(0.05 + 0.95 * f, p)) if kabar else None, batal=batal)
    return status()


def hapus_model(model: str) -> None:
    if model not in MODEL:
        raise ValueError("Model AI lokal tidak dikenal.")
    if _model_jalan == model:
        hentikan()
    _berkas_model(model).unlink(missing_ok=True)
    _berkas_model(model).with_suffix(".gguf.part").unlink(missing_ok=True)


# --- Menjalankan ---------------------------------------------------------------

_kunci = threading.Lock()
_proses: Optional[subprocess.Popen] = None
_port = 0
_model_jalan: Optional[str] = None
_terakhir = 0.0
_pengawas: Optional[threading.Thread] = None
# Permintaan yang sedang berjalan. Server tidak dimatikan selama ini > 0:
# membaca prompt 2.300 token saja butuh ±80 detik di CPU, lebih lama daripada
# batas menganggur (terukur 17 Oktober 2026, server mati di tengah jawaban).
_sedang = 0


def _port_bebas() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _siap(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return r.status == 200
    except Exception:                                     # noqa: BLE001
        return False


def _awasi() -> None:
    """Mematikan server sesudah menganggur, supaya memorinya kembali."""
    while True:
        time.sleep(10)
        with _kunci:
            if _proses is None or _proses.poll() is not None:
                return
            if _sedang == 0 and time.monotonic() - _terakhir > MENGANGGUR_DETIK:
                log.info("AI lokal menganggur %d dtk, dimatikan", MENGANGGUR_DETIK)
                _matikan()
                return


def _matikan() -> None:
    global _proses, _model_jalan
    if _proses is not None and _proses.poll() is None:
        _proses.terminate()
        try:
            _proses.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _proses.kill()
    _proses = None
    _model_jalan = None


def hentikan() -> None:
    with _kunci:
        _matikan()


def _bersihkan_sisa() -> None:
    """Mematikan llama-server yang tertinggal dari OmniClip sebelumnya (pid tersimpan)."""
    berkas = _folder() / "server.pid"
    try:
        pid = int(berkas.read_text().strip())
    except (OSError, ValueError):
        return
    berkas.unlink(missing_ok=True)
    if _proses is not None and _proses.pid == pid:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=10)
        else:
            nama = Path(f"/proc/{pid}/comm")
            if nama.exists() and "llama-server" not in nama.read_text():
                return
            os.kill(pid, 15)
        log.info("llama-server sisa (pid %d) dimatikan", pid)
    except Exception:                                     # noqa: BLE001
        pass


def _anak_rendah() -> None:
    """Dijalankan di proses anak sebelum llama-server mulai (Linux/macOS)."""
    os.nice(10)
    if sys.platform.startswith("linux"):
        # Server ikut mati bila OmniClip mati mendadak; tanpa ini ia tertinggal
        # memegang 3 GB RAM (terjadi saat uji 17 Oktober 2026).
        try:
            import ctypes
            import signal
            ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG
        except Exception:                                 # noqa: BLE001
            pass


import atexit as _atexit  # noqa: E402

_atexit.register(hentikan)


def alamat(model: str = MODEL_BAWAAN) -> str:
    """Alamat API bergaya OpenAI dari server yang menyala (dinyalakan bila perlu)."""
    global _proses, _port, _model_jalan, _terakhir, _pengawas
    if model not in MODEL:
        model = MODEL_BAWAAN
    with _kunci:
        _terakhir = time.monotonic()
        if _proses is not None and _proses.poll() is None and _model_jalan == model:
            return f"http://127.0.0.1:{_port}/v1"
        _matikan()
        srv = _server()
        berkas = _berkas_model(model)
        if srv is None or not berkas.is_file():
            raise RuntimeError("AI lokal belum dipasang. Pasang dulu di Pengaturan > Mesin AI.")
        perlu = MODEL[model]["ram_mb"] + CADANGAN_RAM_MB
        bebas = ram_bebas_mb()
        if bebas and bebas < perlu:
            raise RuntimeError(
                f"RAM bebas tinggal {bebas} MB, AI lokal butuh sekitar {perlu} MB. "
                "Tutup aplikasi atau tab peramban lain, atau pilih model yang lebih kecil.")
        port = _port_bebas()
        utas = max(2, (os.cpu_count() or 4) // 2)
        perintah = [str(srv), "-m", str(berkas), "--host", "127.0.0.1", "--port", str(port),
                    "-c", str(KONTEKS), "-t", str(utas), "-np", "1",
                    "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "--jinja"]
        env = dict(os.environ)
        if sys.platform != "win32":
            env["LD_LIBRARY_PATH"] = str(srv.parent) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        catatan = open(_folder() / "server.log", "ab")
        kw: dict = {"cwd": str(srv.parent), "env": env, "stdout": catatan,
                    "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
        if sys.platform == "win32":
            kw["creationflags"] = 0x00004000 | 0x08000000   # BELOW_NORMAL, NO_WINDOW
        else:
            kw["preexec_fn"] = _anak_rendah
        log.info("Menyalakan AI lokal %s (%d utas, konteks %d)", model, utas, KONTEKS)
        _bersihkan_sisa()
        _proses = subprocess.Popen(perintah, **kw)
        _port, _model_jalan = port, model
        try:
            (_folder() / "server.pid").write_text(str(_proses.pid))
        except OSError:
            pass
        tenggat = time.monotonic() + 240
        while time.monotonic() < tenggat:
            if _proses.poll() is not None:
                _proses = None
                _model_jalan = None
                raise RuntimeError("AI lokal berhenti saat dinyalakan. Lihat alat/ai_lokal/server.log.")
            if _siap(port):
                break
            time.sleep(1)
        else:
            _matikan()
            raise RuntimeError("AI lokal tidak siap dalam 4 menit.")
        _terakhir = time.monotonic()
        if _pengawas is None or not _pengawas.is_alive():
            _pengawas = threading.Thread(target=_awasi, name="ai-lokal-pengawas", daemon=True)
            _pengawas.start()
        return f"http://127.0.0.1:{port}/v1"


def sentuh() -> None:
    """Menandai server masih dipakai (menunda mati karena menganggur)."""
    global _terakhir
    _terakhir = time.monotonic()


def mulai_pakai() -> None:
    global _sedang, _terakhir
    with _kunci:
        _sedang += 1
        _terakhir = time.monotonic()


def selesai_pakai() -> None:
    global _sedang, _terakhir
    with _kunci:
        _sedang = max(0, _sedang - 1)
        _terakhir = time.monotonic()


def run_pasang(ctx) -> dict:
    """Pekerjaan antrean: memasang mesin dan model AI lokal, dengan kemajuan."""
    model = (ctx.payload or {}).get("model") or MODEL_BAWAAN
    ctx.progress(0.01, stage="unduh", message="Menyiapkan AI lokal…")
    hasil = pasang(model, kabar=lambda f, pesan: ctx.progress(min(0.99, f), stage="unduh",
                                                              message=pesan),
                   batal=ctx.check_cancelled)
    ctx.progress(1.0, stage="done", message="AI lokal siap dipakai.")
    return hasil
