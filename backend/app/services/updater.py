"""
Pembaruan aplikasi: mengecek, mengunduh, memasang.

Bentuknya mengikuti kendala yang tidak bisa ditawar di Windows: **sebuah .exe
yang sedang berjalan tidak bisa menimpa dirinya sendiri**, dan folder yang
memuatnya tidak bisa diganti nama selama prosesnya hidup. Jadi pemasangan tidak
mungkin dikerjakan oleh aplikasi itu sendiri.

Yang dilakukan: aplikasi mengunduh dan membongkar versi baru ke folder
sementara, menulis satu skrip penolong, lalu menyalakan penolong itu dan keluar.
Penolong menunggu proses aplikasi benar-benar mati, baru menukar foldernya, lalu
menjalankan yang baru. Penolong tinggal di luar folder yang ditukar — kalau ia
di dalam, ia sedang menggergaji dahan tempatnya berdiri.

Tiga hal yang sengaja dikerjakan sebelum apa pun disentuh:

  * folder aplikasi diuji apakah benar-benar bisa ditulis. Dipasang di Program
    Files, penukaran akan gagal di tengah jalan — dan gagal di tengah jalan
    jauh lebih buruk daripada tidak mulai sama sekali;
  * arsip yang diunduh diperiksa keutuhannya DAN diperiksa apakah benar memuat
    aplikasi, sebelum satu berkas lama pun disentuh;
  * folder lama tidak dihapus, hanya diganti nama. Kalau langkah terakhir
    gagal, yang lama masih utuh di sebelahnya.

Saat dijalankan dari sumber, seluruh modul ini menolak bekerja: menukar folder
git dengan hasil build adalah hal yang tidak akan pernah diinginkan siapa pun.
"""

import json
import logging
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from ..config import FROZEN
from ..version import __version__, sebagai_tuple

log = logging.getLogger("omniclip.updater")

REPO = os.getenv("OMNICLIP_REPO", "YosafatHizkiaPesik/OmniClip")
API_RILIS = f"https://api.github.com/repos/{REPO}/releases/latest"

# GitHub membatasi 60 permintaan per jam untuk pemanggil tanpa akun. Mengecek
# sekali tiap enam jam jauh di bawah itu, dan tetap berarti pembaruan ketahuan
# di hari yang sama.
CACHE_DETIK = 6 * 3600
UNDUH_TIMEOUT = 900

_cache: dict | None = None
_cache_pada = 0.0


def _nama_aset() -> str:
    return "OmniClip-windows.zip" if sys.platform == "win32" else "OmniClip-linux.tar.gz"


def folder_aplikasi() -> Path | None:
    """Folder yang memuat aplikasi terbungkus, atau None bila dari sumber."""
    if not FROZEN:
        return None
    return Path(sys.executable).resolve().parent


def bisa_memasang() -> tuple[bool, str]:
    """
    Apakah pemasangan sendiri mungkin di sini. (bisa, alasan).

    Diperiksa sebelum tombolnya ditampilkan, bukan setelah ditekan.
    """
    if not FROZEN:
        return False, ("Dijalankan dari kode sumber — perbarui dengan git pull, "
                       "bukan lewat sini.")
    folder = folder_aplikasi()
    if folder is None:
        return False, "Folder aplikasi tidak dikenali."
    induk = folder.parent
    try:
        # Menukar folder berarti menulis di INDUKNYA, bukan di dalamnya.
        uji = induk / f".omniclip-uji-tulis-{os.getpid()}"
        uji.mkdir()
        uji.rmdir()
    except OSError as e:
        return False, (f"Folder {induk} tidak bisa ditulis ({e.strerror}). "
                       "Pindahkan OmniClip ke folder milik Anda sendiri, "
                       "misalnya Documents, lalu coba lagi.")
    return True, ""


# --- Mengecek -----------------------------------------------------------------

def cek(paksa: bool = False) -> dict:
    """
    Versi terbaru menurut GitHub Releases.

    Tidak pernah melempar: aplikasi yang gagal membuka halaman Pengaturan hanya
    karena internet mati adalah pertukaran yang buruk untuk fitur yang sifatnya
    tambahan.
    """
    global _cache, _cache_pada

    if _cache is not None and not paksa and (time.time() - _cache_pada) < CACHE_DETIK:
        return _cache

    hasil = {
        "versi_sekarang": __version__,
        "versi_terbaru": None,
        "ada_pembaruan": False,
        "catatan": "",
        "halaman": f"https://github.com/{REPO}/releases/latest",
        "url_unduh": None,
        "ukuran": 0,
        "terbit": "",
        "galat": "",
    }

    try:
        req = urllib.request.Request(
            API_RILIS,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": f"OmniClip/{__version__}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Terhubung, dijawab, dan jawabannya "belum ada rilis". Bukan
            # kegagalan jaringan, dan menyebutnya begitu mengirim orang mencari
            # masalah di tempat yang salah.
            hasil["galat"] = "Belum ada versi yang dirilis untuk dibandingkan."
        elif e.code == 403:
            hasil["galat"] = ("GitHub sedang membatasi permintaan. Coba lagi "
                              "sebentar lagi.")
        else:
            hasil["galat"] = f"GitHub menjawab {e.code}."
        return hasil
    except Exception as e:
        hasil["galat"] = f"Tidak bisa menghubungi GitHub: {str(e)[:120]}"
        return hasil

    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        hasil["galat"] = "Rilis terbaru tidak punya nomor versi."
        return hasil

    hasil["versi_terbaru"] = tag.lstrip("vV")
    hasil["catatan"] = (data.get("body") or "").strip()[:4000]
    hasil["terbit"] = data.get("published_at") or ""
    hasil["halaman"] = data.get("html_url") or hasil["halaman"]
    hasil["ada_pembaruan"] = sebagai_tuple(tag) > sebagai_tuple(__version__)

    nama = _nama_aset()
    for aset in data.get("assets") or []:
        if aset.get("name") == nama:
            hasil["url_unduh"] = aset.get("browser_download_url")
            hasil["ukuran"] = int(aset.get("size") or 0)
            break

    if hasil["ada_pembaruan"] and not hasil["url_unduh"]:
        hasil["galat"] = (f"Rilis {tag} ada, tapi tidak memuat {nama} untuk "
                          f"{platform.system()}.")

    _cache, _cache_pada = hasil, time.time()
    return hasil


# --- Mengunduh dan memasang ---------------------------------------------------

def _bongkar(arsip: Path, tujuan: Path) -> Path:
    """Membongkar arsip, mengembalikan folder OmniClip di dalamnya."""
    if arsip.suffix == ".zip":
        with zipfile.ZipFile(arsip) as z:
            rusak = z.testzip()
            if rusak:
                raise ValueError(f"arsip rusak pada {rusak}")
            z.extractall(tujuan)
    else:
        with tarfile.open(arsip, "r:gz") as t:
            t.extractall(tujuan)

    folder = tujuan / "OmniClip"
    if not folder.is_dir():
        raise ValueError("arsip tidak memuat folder OmniClip")
    exe = folder / ("OmniClip.exe" if sys.platform == "win32" else "OmniClip")
    if not exe.is_file():
        raise ValueError(f"arsip tidak memuat {exe.name}")
    if sys.platform != "win32":
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return folder


def _tulis_penolong(temp: Path, pid: int, lama: Path, baru: Path) -> Path:
    """
    Skrip yang menukar folder setelah aplikasi mati.

    Ia tinggal di folder sementara, bukan di dalam folder yang ditukar.
    """
    exe = "OmniClip.exe" if sys.platform == "win32" else "OmniClip"
    cadangan = lama.with_name(lama.name + f"-lama-{int(time.time())}")

    if sys.platform == "win32":
        p = temp / "pasang.bat"
        p.write_text(f'''@echo off
rem Penolong pemasangan OmniClip. Menunggu aplikasi mati, menukar folder,
rem lalu menjalankan yang baru. Folder lama hanya DIGANTI NAMA: bila langkah
rem terakhir gagal, yang lama masih utuh di sebelahnya.
setlocal
rem Port TIDAK diwariskan. Aplikasi yang sedang berjalan menuliskan port
rem pilihannya ke lingkungan, dan penolong ini mewarisinya. Kalau diteruskan,
rem aplikasi baru dipaksa memakai port yang barangkali belum sempat dilepas
rem sistem - lalu mati saat start, tepat pada saat pengguna paling tidak bisa
rem menebak apa yang terjadi. Dilepas, ia memilih port kosong sendiri.
set OMNICLIP_PORT=
echo Menunggu OmniClip menutup...
for /l %%i in (1,1,120) do (
  tasklist /fi "PID eq {pid}" 2>nul | find "{pid}" >nul || goto :tukar
  timeout /t 1 /nobreak >nul
)
echo OmniClip tidak menutup. Pemasangan dibatalkan.
pause
exit /b 1

:tukar
move "{lama}" "{cadangan}" >nul 2>&1
if errorlevel 1 (
  echo Tidak bisa memindahkan folder lama. Pemasangan dibatalkan.
  pause
  exit /b 1
)
move "{baru}" "{lama}" >nul 2>&1
if errorlevel 1 (
  echo Pemasangan gagal. Mengembalikan versi lama...
  move "{cadangan}" "{lama}" >nul 2>&1
  pause
  exit /b 1
)
rmdir /s /q "{cadangan}" >nul 2>&1
start "" "{lama}\\{exe}"
exit /b 0
''', encoding="utf-8")
        return p

    p = temp / "pasang.sh"
    p.write_text(f'''#!/bin/sh
# Penolong pemasangan OmniClip. Lihat catatan di app/services/updater.py.
# Port tidak diwariskan; lihat catatan pada versi Windows di atas.
unset OMNICLIP_PORT
echo "Menunggu OmniClip menutup..."
i=0
while kill -0 {pid} 2>/dev/null; do
  i=$((i+1))
  [ "$i" -gt 120 ] && {{ echo "OmniClip tidak menutup. Dibatalkan."; exit 1; }}
  sleep 1
done
mv "{lama}" "{cadangan}" || {{ echo "Tidak bisa memindahkan folder lama."; exit 1; }}
if ! mv "{baru}" "{lama}"; then
  echo "Pemasangan gagal. Mengembalikan versi lama..."
  mv "{cadangan}" "{lama}"
  exit 1
fi
rm -rf "{cadangan}"
exec "{lama}/{exe}"
''', encoding="utf-8")
    p.chmod(0o755)
    return p


def pasang(ctx) -> dict:
    """
    Job `update`: unduh, periksa, siapkan, lalu keluar supaya penolong bekerja.

    Berjalan di lane `net`.
    """
    bisa, alasan = bisa_memasang()
    if not bisa:
        raise RuntimeError(alasan)

    info = cek(paksa=True)
    if not info["ada_pembaruan"]:
        return {"status": "sudah_terbaru", "versi": info["versi_sekarang"]}
    if not info["url_unduh"]:
        raise RuntimeError(info["galat"] or "Rilis terbaru tidak punya berkas untuk sistem ini.")

    temp = Path(tempfile.mkdtemp(prefix="omniclip_update_"))
    arsip = temp / _nama_aset()
    total = info["ukuran"]

    ctx.progress(0.02, stage="unduh",
                 message=f"Mengunduh OmniClip {info['versi_terbaru']}…")

    req = urllib.request.Request(
        info["url_unduh"], headers={"User-Agent": f"OmniClip/{__version__}"})
    with urllib.request.urlopen(req, timeout=UNDUH_TIMEOUT) as r, open(arsip, "wb") as f:
        terunduh = 0
        while potong := r.read(1 << 20):
            ctx.check_cancelled()
            f.write(potong)
            terunduh += len(potong)
            if total:
                ctx.progress(0.02 + 0.78 * min(1.0, terunduh / total), stage="unduh",
                             message=f"Mengunduh… {terunduh / 1e6:.0f} dari "
                                     f"{total / 1e6:.0f} MB")

    if total and abs(arsip.stat().st_size - total) > 4096:
        raise RuntimeError("Unduhan tidak lengkap. Coba lagi.")

    ctx.progress(0.82, stage="periksa", message="Memeriksa berkas…")
    baru = _bongkar(arsip, temp / "isi")

    ctx.progress(0.95, stage="siap", message="Menyiapkan pemasangan…")
    lama = folder_aplikasi()
    penolong = _tulis_penolong(temp, os.getpid(), lama, baru)

    log.info("Pembaruan %s siap dipasang; menjalankan penolong %s",
             info["versi_terbaru"], penolong)

    if sys.platform == "win32":
        subprocess.Popen(["cmd", "/c", "start", "", str(penolong)],
                         cwd=str(temp), close_fds=True,
                         creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    else:
        subprocess.Popen(["/bin/sh", str(penolong)], cwd=str(temp),
                         start_new_session=True, close_fds=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ctx.progress(1.0, stage="selesai",
                 message=f"OmniClip {info['versi_terbaru']} siap. Aplikasi akan "
                         "menutup dan membuka kembali dengan sendirinya.")

    # Diberi jeda supaya pesan terakhir sempat sampai ke layar lewat SSE sebelum
    # servernya hilang. Tanpa ini, yang dilihat pengguna adalah jendela yang
    # menghilang begitu saja tanpa penjelasan.
    def _tutup() -> None:
        time.sleep(2.5)
        log.info("Menutup untuk pemasangan.")
        os._exit(0)

    import threading
    threading.Thread(target=_tutup, daemon=True).start()

    return {"status": "memasang", "versi": info["versi_terbaru"]}
