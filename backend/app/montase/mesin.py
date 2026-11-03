"""
Menemukan dan menjalankan Mesin Montase (JOB-4.md bagian 19).

Mesinnya program Node (`montase-mesin/`) yang dijalankan sekali per perintah,
bukan proses yang hidup terus: render, kompilasi komponen, menyiapkan browser.
Antarmukanya satu objek JSON di stdin dan satu objek JSON per baris di stdout
(lihat montase-mesin/src/alat.mjs).

Di mana bagian-bagiannya berada:

  bagian            pengembangan                       aplikasi terbungkus
  ---------------   --------------------------------   ------------------------------
  Node              `node` di PATH (versi >= 22)        diunduh ke folder data (unduh.py)
  paket mesin       montase-mesin/ (npm ci)             ikut di dalam aplikasi
  bundel komposisi  montase-mesin/dist/bundel           ikut di dalam aplikasi
  Chrome headless   diunduh Remotion ke node_modules    diunduh Remotion saat siapkan

Paket mesin ikut di dalam aplikasi (K-16), bukan diunduh: build uji dari
`workflow_dispatch` tidak punya rilis untuk diunduhi, dan dengan begitu versi
mesin selalu sama dengan versi komposisi di aplikasinya.

Dua variabel lingkungan untuk pengembangan dan uji:
  OMNICLIP_NODE              jalur `node` tertentu
  OMNICLIP_MONTASE_BROWSER   jalur Chrome/Chromium headless tertentu (dipakai
                             di container yang jaringannya tidak bisa
                             mengunduh Chrome Headless Shell)
"""

from __future__ import annotations

import collections
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from ..config import BUNDLE_DIR, FROZEN, PROJECT_DIR, STORAGE_DIR
from ..services.proses import lepas, popen

log = logging.getLogger("omniclip.montase.mesin")

NODE_MIN_MAYOR = 22
# Tenggat sesudah SIGTERM sebelum seluruh pohon proses dimatikan paksa.
TENGGAT_BERHENTI = 10.0


class GagalMesin(RuntimeError):
    """Mesin tidak ada, atau perintahnya berakhir tanpa hasil."""


class Dibatalkan(RuntimeError):
    """Perintah dihentikan karena diminta."""


def folder_paket() -> Optional[Path]:
    """Folder berisi package.json + src/ + node_modules/ mesin, bila lengkap."""
    folder = (BUNDLE_DIR / "montase_mesin") if FROZEN else (PROJECT_DIR / "montase-mesin")
    if (folder / "src" / "render.mjs").is_file() and \
            (folder / "node_modules" / "@remotion" / "renderer").is_dir():
        return folder
    return None


def folder_kerja() -> Path:
    """
    Folder kerja (cwd) setiap perintah mesin, di folder data OmniClip.

    Remotion menaruh Chrome Headless Shell di `node_modules/.remotion` milik
    `package.json` terdekat DARI CWD (getDownloadsCacheDir). Tanpa folder ini,
    cwd-nya folder paket mesin, dan di aplikasi terbungkus itu berarti Chrome
    terunduh ke DALAM folder aplikasi: gagal bila folder itu tidak bisa
    ditulis, dan hilang setiap kali pembaruan mengganti aplikasinya. Terlihat
    di build CI pertama (3 Nov 2026): `_internal/montase_mesin/node_modules/.remotion`.

    `package.json` kecil di sini menghentikan pencarian ke atas, jadi Chrome
    selalu ke `<data>/mesin_montase/kerja/node_modules/.remotion`, dan perintah
    render menemukannya di tempat yang sama.
    """
    folder = STORAGE_DIR / "mesin_montase" / "kerja"
    penanda = folder / "package.json"
    if not penanda.is_file():
        folder.mkdir(parents=True, exist_ok=True)
        penanda.write_text('{"name": "omniclip-montase-kerja", "private": true}\n',
                           encoding="utf-8")
    return folder


def _browser_terunduh() -> Optional[str]:
    akar = STORAGE_DIR / "mesin_montase" / "kerja" / "node_modules" / ".remotion"
    if not akar.is_dir():
        return None
    for nama in ("chrome-headless-shell.exe", "chrome-headless-shell"):
        for jalur in akar.rglob(nama):
            if jalur.is_file():
                return str(jalur)
    return None


def folder_bundel() -> Optional[Path]:
    folder = (BUNDLE_DIR / "montase_mesin" / "dist" / "bundel") if FROZEN \
        else (PROJECT_DIR / "montase-mesin" / "dist" / "bundel")
    return folder if (folder / "index.html").is_file() else None


def _versi_node(jalur: str) -> Optional[str]:
    try:
        keluar = subprocess.run([jalur, "--version"], capture_output=True, text=True,
                                timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return keluar.lstrip("v") or None


def _cukup_baru(versi: Optional[str]) -> bool:
    try:
        return int((versi or "0").split(".")[0]) >= NODE_MIN_MAYOR
    except ValueError:
        return False


def jalur_node() -> Optional[str]:
    """Node yang dipakai: pilihan lingkungan, hasil unduhan, lalu PATH (pengembangan)."""
    from . import unduh

    calon = [os.environ.get("OMNICLIP_NODE"), unduh.jalur_node_terunduh()]
    if not FROZEN:
        calon.append(shutil.which("node"))
    for jalur in calon:
        if jalur and Path(jalur).is_file() and _cukup_baru(_versi_node(jalur)):
            return str(jalur)
    return None


def jalur_browser() -> Optional[str]:
    jalur = os.environ.get("OMNICLIP_MONTASE_BROWSER")
    return jalur if jalur and Path(jalur).is_file() else None


def status() -> dict:
    """Keadaan mesin untuk halaman uji dan menu Montase."""
    node = jalur_node()
    paket = folder_paket()
    bundel = folder_bundel()
    return {
        "node": node,
        "versi_node": _versi_node(node) if node else None,
        "paket": str(paket) if paket else None,
        "bundel": str(bundel) if bundel else None,
        # Pilihan lingkungan, atau Chrome yang sudah diunduh ke folder kerja.
        # None berarti render pertama akan mengunduhnya sendiri.
        "browser": jalur_browser() or _browser_terunduh(),
        "siap": bool(node and paket and bundel),
    }


def _hentikan_pohon(proc: subprocess.Popen) -> None:
    """SIGTERM ke seluruh grup proses (Node + Chrome), lalu paksa bila perlu."""
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           capture_output=True, timeout=30)
            return
        os.killpg(proc.pid, signal.SIGTERM)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.wait(timeout=TENGGAT_BERHENTI)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()


_IZIN_DIPERIKSA = False


def _pulihkan_izin_eksekusi(paket: Path) -> None:
    """
    Berkas biner compositor Remotion (`remotion`, `ffmpeg`, `ffprobe`) harus bisa
    dijalankan. Pembungkus aplikasi menyalinnya sebagai berkas data, dan di
    Linux bit eksekusinya bisa hilang di jalan; gejalanya baru muncul sebagai
    `EACCES` di tengah render pertama. Diperiksa sekali per proses.
    """
    global _IZIN_DIPERIKSA
    if _IZIN_DIPERIKSA or sys.platform == "win32":
        return
    _IZIN_DIPERIKSA = True
    for folder in (paket / "node_modules" / "@remotion").glob("compositor-*"):
        for nama in ("remotion", "ffmpeg", "ffprobe"):
            berkas = folder / nama
            try:
                if berkas.is_file() and not os.access(berkas, os.X_OK):
                    berkas.chmod(berkas.stat().st_mode | 0o755)
            except OSError as e:
                log.warning("Izin eksekusi %s tidak bisa dipulihkan: %s", berkas, e)


def jalankan(perintah: str, masukan: dict, *,
             kabar: Optional[Callable[[dict], None]] = None,
             batal: Optional[Callable[[], bool]] = None,
             batas_detik: Optional[float] = None) -> dict:
    """
    Menjalankan `montase-mesin/src/<perintah>.mjs` dan mengembalikan hasil akhirnya.

    `kabar` menerima setiap baris JSON (kemajuan). Hasil akhir adalah baris
    terakhir yang bukan kemajuan; baris `{"galat": ...}` atau kode keluar bukan
    nol menjadi GagalMesin berisi pesan itu dan ekor stderr.
    """
    node = jalur_node()
    paket = folder_paket()
    if not node or not paket:
        raise GagalMesin("Mesin Montase belum terpasang.")
    _pulihkan_izin_eksekusi(paket)

    env = dict(os.environ)
    # Node 22 tidak membaca HTTPS_PROXY sendiri; tanpa ini unduhan Chrome
    # gagal di jaringan yang wajib lewat proxy.
    if env.get("HTTPS_PROXY") or env.get("https_proxy"):
        env["NODE_USE_ENV_PROXY"] = "1"
    env.setdefault("NODE_NO_WARNINGS", "1")

    kw: dict = {"cwd": str(folder_kerja()), "env": env, "stdin": subprocess.PIPE,
                "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
                "text": True, "encoding": "utf-8", "errors": "replace", "bufsize": 1}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        # Grup proses sendiri, supaya pembatalan ikut mematikan Chrome anaknya.
        kw["start_new_session"] = True

    proc = popen([node, str(paket / "src" / f"{perintah}.mjs")], **kw)
    ekor_stderr: collections.deque = collections.deque(maxlen=40)
    alasan_henti: list[str] = []

    def baca_stderr():
        for baris in proc.stderr:
            ekor_stderr.append(baris.rstrip())

    def penjaga():
        tenggat = time.monotonic() + batas_detik if batas_detik else None
        while proc.poll() is None:
            if batal is not None and batal():
                alasan_henti.append("batal")
                _hentikan_pohon(proc)
                return
            if tenggat is not None and time.monotonic() > tenggat:
                alasan_henti.append("waktu")
                _hentikan_pohon(proc)
                return
            time.sleep(0.25)

    pembaca = threading.Thread(target=baca_stderr, daemon=True)
    pembaca.start()
    threading.Thread(target=penjaga, daemon=True).start()

    hasil: Optional[dict] = None
    galat: Optional[str] = None
    try:
        proc.stdin.write(json.dumps(masukan, ensure_ascii=False))
        proc.stdin.close()
        for baris in proc.stdout:
            baris = baris.strip()
            if not baris:
                continue
            try:
                objek = json.loads(baris)
            except ValueError:
                ekor_stderr.append(baris)
                continue
            if "galat" in objek:
                galat = str(objek["galat"])
            elif any(k in objek for k in ("kemajuan", "tahap", "unduh")):
                if kabar is not None:
                    kabar(objek)
            else:
                hasil = objek
        proc.wait()
    finally:
        if proc.poll() is None:
            _hentikan_pohon(proc)
        pembaca.join(timeout=5)
        for pipa in (proc.stdout, proc.stderr):
            try:
                pipa.close()
            except OSError:
                pass
        lepas(proc)

    if "batal" in alasan_henti:
        raise Dibatalkan(f"Perintah {perintah} dibatalkan.")
    if "waktu" in alasan_henti:
        raise GagalMesin(f"Perintah {perintah} melewati batas {batas_detik:.0f} detik.")
    if galat or proc.returncode != 0 or hasil is None:
        ekor = "\n".join(list(ekor_stderr)[-8:])
        pesan = galat or f"Mesin berhenti dengan kode {proc.returncode}."
        log.warning("Mesin Montase %s gagal: %s\n%s", perintah, pesan, ekor)
        raise GagalMesin(f"{pesan}\n{ekor}".strip())
    return hasil


def kompilasi(sumber: str) -> dict:
    """Komponen animasi -> {lolos, js | masalah, peringatan} (kompilasi.mjs)."""
    return jalankan("kompilasi", {"sumber": sumber}, batas_detik=60)


def render(dokumen: dict, sumber: dict, keluar: Path, *,
           kabar: Optional[Callable[[dict], None]] = None,
           batal: Optional[Callable[[], bool]] = None,
           crf: int = 18, concurrency: Optional[int] = None) -> dict:
    bundel = folder_bundel()
    if not bundel:
        raise GagalMesin("Bundel komposisi Montase tidak ditemukan.")
    keluar.parent.mkdir(parents=True, exist_ok=True)
    return jalankan("render", {
        "serve_url": str(bundel),
        "dokumen": dokumen,
        "sumber": sumber,
        "keluar": str(keluar),
        "crf": crf,
        "concurrency": concurrency,
        "browser": jalur_browser(),
    }, kabar=kabar, batal=batal)


def siapkan_browser(kabar: Optional[Callable[[dict], None]] = None) -> dict:
    """Memastikan Chrome Headless Shell ada (diunduh Remotion bila belum)."""
    return jalankan("siapkan", {"browser": jalur_browser()}, kabar=kabar, batas_detik=1800)
