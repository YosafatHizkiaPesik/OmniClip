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
from typing import Optional

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
        return False, ("Dijalankan dari kode sumber, perbarui dengan git pull, "
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


# --- Hasil pemasangan, dibaca sesudah aplikasi hidup lagi ----------------------
#
# Pemasangan selesai di luar aplikasi ini: penolong menukar folder SESUDAH
# prosesnya mati. Akibatnya yang terakhir dilihat pengguna hanyalah sambungan
# yang terputus, dan di layar itu terbaca sebagai "pembaruan gagal" — persis
# yang dilaporkan pemiliknya 7 Oktober 2026: "setiap kali update versi baru di
# windows selalu gagal tapi saat omniclip dibuka kembali versinya sudah
# berubah".
#
# Jadi niatnya dicatat sebelum keluar, dan versi yang hidup berikutnya yang
# menjawab apakah pemasangannya berhasil. Yang gagal membawa serta jalur
# `pasang.log` dan ekornya, supaya sebabnya bisa dibaca alih-alih ditebak.

NIAT_KUNCI = "update.menunggu"
# Berapa baris terakhir `pasang.log` yang ikut dilaporkan saat gagal.
LOG_EKOR = 12


def _simpan(kunci: str, nilai: str) -> None:
    try:
        from ..repos import settings as settings_repo
        settings_repo.set_value(kunci, nilai)
    except Exception as e:                               # noqa: BLE001
        log.info("Niat pembaruan tidak bisa dicatat: %s", str(e)[:120])


def _baca(kunci: str) -> str:
    try:
        from ..repos import settings as settings_repo
        return settings_repo.get(kunci) or ""
    except Exception:                                    # noqa: BLE001
        return ""


def catat_niat(versi: str, log_pasang: Path, dari: str) -> None:
    """Dipanggil tepat sebelum aplikasi menutup diri untuk dipasang."""
    _simpan(NIAT_KUNCI, json.dumps(
        {"versi": versi, "dari": dari, "log": str(log_pasang), "pada": time.time()}))


def hasil_pemasangan(*, bersihkan: bool = True) -> Optional[dict]:
    """
    Apa yang terjadi pada pemasangan terakhir, atau None kalau tidak ada.

    {"berhasil", "versi", "dari", "sekarang", "log", "ekor"}. Dibaca sekali:
    sesudah dilaporkan ke layar, catatannya dihapus supaya kabar lama tidak
    terus muncul tiap kali halaman dibuka.
    """
    mentah = _baca(NIAT_KUNCI)
    if not mentah:
        return None
    try:
        niat = json.loads(mentah)
    except (TypeError, ValueError):
        if bersihkan:
            _simpan(NIAT_KUNCI, "")
        return None

    berhasil = str(niat.get("versi") or "") == __version__
    hasil = {
        "berhasil": berhasil,
        "versi": niat.get("versi") or "",
        "dari": niat.get("dari") or "",
        "sekarang": __version__,
        "log": niat.get("log") or "",
        "ekor": "",
    }
    if not berhasil:
        # Ekor lognya ikut. Inilah satu-satunya keterangan tentang apa yang
        # ditolak Windows, dan tanpa dibawa ke layar ia tinggal di folder
        # sementara yang tidak akan pernah dibuka siapa pun.
        try:
            baris = Path(hasil["log"]).read_text(
                encoding="utf-8", errors="replace").splitlines()
            hasil["ekor"] = "\n".join(b for b in baris[-LOG_EKOR:] if b.strip())
        except OSError:
            hasil["ekor"] = ""
    if berhasil:
        # Versi yang dipasang sudah terbukti berjalan — ini dia yang menjawab.
        # Folder lamanya tidak punya tugas lagi, dan tiap pembaruan
        # meninggalkan satu salinan 300 MB kalau dibiarkan.
        n, besar = buang_cadangan()
        hasil["cadangan_dibuang"] = n
        hasil["ruang_bebas"] = besar
    if bersihkan:
        _simpan(NIAT_KUNCI, "")
    return hasil


# --- Mengecek -----------------------------------------------------------------

# Sisa pemasangan yang gagal, dan kenapa ia harus dibereskan sendiri.
#
# Panggung pembaruan (`.omniclip-pembaruan-<pid>`) dibuat DI SEBELAH folder
# aplikasi, bukan di %TEMP% — `move` di cmd tidak bisa memindahkan direktori
# lintas cakram. Harganya: kalau pemasangan berhenti di tengah, 300 MB hasil
# bongkaran tertinggal di situ, dan tidak ada yang menyapunya seperti %TEMP%
# disapu Windows. Pemiliknya melaporkan pemasangan yang "selalu gagal"
# 7 Oktober 2026; kalau benar gagal berulang kali, di sebelah aplikasinya ada
# beberapa gigabyte yang tidak dipakai siapa pun.
#
# Yang disapu HANYA panggung, dan hanya yang lebih tua dari sehari: panggung
# yang sedang dipakai pemasangan yang berjalan sekarang tidak boleh disentuh.
# Folder cadangan versi lama (`-lama-<waktu>`) TIDAK dihapus di sini — itu
# satu-satunya jalan kembali bila versi barunya bermasalah, dan membuangnya
# tanpa diminta bukan keputusan yang boleh diambil berkas ini.
SISA_UMUR = 24 * 3600


def bersihkan_sisa() -> int:
    """Menyapu panggung pembaruan yang tertinggal. Mengembalikan berapa yang dibuang."""
    folder = folder_aplikasi()
    if folder is None:
        return 0
    dibuang = 0
    sekarang = time.time()
    try:
        tetangga = list(folder.parent.iterdir())
    except OSError:
        return 0
    for d in tetangga:
        if not d.is_dir() or not d.name.startswith(".omniclip-pembaruan-"):
            continue
        try:
            if sekarang - d.stat().st_mtime < SISA_UMUR:
                continue
            shutil.rmtree(d, ignore_errors=True)
            dibuang += 1
        except OSError:
            continue
    if dibuang:
        log.info("Sisa pemasangan yang tertinggal dibuang: %d folder", dibuang)
    return dibuang


def buang_cadangan() -> tuple[int, int]:
    """
    Membuang folder versi LAMA. (berapa folder, berapa byte).

    Dipanggil hanya sesudah pemasangan terbukti berhasil — yaitu versi yang
    sedang berjalan sudah sama dengan yang dipasang. Sebelum bukti itu ada,
    folder lama adalah satu-satunya jalan kembali, dan membuangnya lebih awal
    berarti kegagalan pemasangan meninggalkan komputer tanpa OmniClip sama
    sekali.

    Diminta pemiliknya 7 Oktober 2026: "untuk apa folder omniclip yang lama,
    mengapa tidak kita hapus saja versi sebelumnya dan hanya menggunakan versi
    terbaru". Ia benar bahwa menyimpannya selamanya tidak ada gunanya — tiap
    pembaruan meninggalkan satu salinan 300 MB lagi.
    """
    jumlah = besar = 0
    for c in cadangan_tertinggal():
        try:
            shutil.rmtree(c["jalur"], ignore_errors=True)
        except OSError:
            continue
        if not Path(c["jalur"]).exists():
            jumlah += 1
            besar += int(c.get("ukuran") or 0)
    if jumlah:
        log.info("Folder versi lama dibuang: %d folder, %.0f MB",
                 jumlah, besar / 1e6)
    return jumlah, besar


def cadangan_tertinggal() -> list[dict]:
    """
    Folder versi lama yang masih ada di sebelah aplikasi.

    Dilaporkan apa adanya; yang membuangnya `buang_cadangan`, dan hanya
    sesudah versi barunya terbukti berjalan.
    """
    folder = folder_aplikasi()
    if folder is None:
        return []
    hasil = []
    for d in sorted(folder.parent.glob(folder.name + "-lama-*")):
        if not d.is_dir():
            continue
        try:
            besar = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        except OSError:
            besar = 0
        hasil.append({"jalur": str(d), "ukuran": besar})
    return hasil


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


def _tulis_penolong(temp: Path, pid: int, lama: Path, baru: Path,
                    panggung: Path) -> Path:
    """
    Skrip yang menukar folder setelah aplikasi mati.

    Ia tinggal di folder sementara, bukan di dalam folder yang ditukar maupun
    di panggung — keduanya lenyap di tengah pekerjaannya, dan cmd membaca
    berkas .bat baris demi baris selama dijalankan.

    Segala sesuatunya dicatat ke `pasang.log` di sebelah skrip ini. Tanpa itu,
    kegagalan hanya meninggalkan satu baris di jendela yang lalu tertutup, dan
    satu-satunya yang bisa dilaporkan pengguna adalah "gagal".
    """
    exe = "OmniClip.exe" if sys.platform == "win32" else "OmniClip"
    cadangan = lama.with_name(lama.name + f"-lama-{int(time.time())}")

    if sys.platform == "win32":
        p = temp / "pasang.bat"
        p.write_text(f'''@echo off
rem Penolong pemasangan OmniClip. Menunggu aplikasi mati, menukar folder,
rem lalu menjalankan yang baru. Folder lama hanya DIGANTI NAMA: bila langkah
rem terakhir gagal, yang lama masih utuh di sebelahnya dan dikembalikan.
setlocal
rem Port TIDAK diwariskan. Aplikasi yang sedang berjalan menuliskan port
rem pilihannya ke lingkungan, dan penolong ini mewarisinya. Kalau diteruskan,
rem aplikasi baru dipaksa memakai port yang barangkali belum sempat dilepas
rem sistem - lalu mati saat start, tepat pada saat pengguna paling tidak bisa
rem menebak apa yang terjadi. Dilepas, ia memilih port kosong sendiri.
set OMNICLIP_PORT=
set "LOG=%~dp0pasang.log"
echo === OmniClip: pemasangan %date% %time% >"%LOG%"
echo Lama    : {lama} >>"%LOG%"
echo Baru    : {baru} >>"%LOG%"
echo Cadangan: {cadangan} >>"%LOG%"

echo Menunggu OmniClip menutup...
for /l %%i in (1,1,120) do (
  tasklist /fi "PID eq {pid}" 2>nul | find "{pid}" >nul || goto :tenang
  timeout /t 1 /nobreak >nul
)
echo GAGAL: proses {pid} tidak menutup dalam 120 detik. >>"%LOG%"
rem Tidak ada jendela yang menunggu tombol di sini.
rem
rem Aplikasinya masih hidup, jadi yang dilihat pengguna seharusnya OmniClip,
rem bukan konsol hitam bertuliskan "Press any key". Kegagalannya tetap
rem tercatat, dan versi yang berjalan akan melaporkannya sendiri di kartu
rem Pembaruan - lengkap dengan ekor berkas catatan ini.
exit /b 1

:tenang
rem Hilangnya PID bukan berarti foldernya sudah bebas.
rem
rem ffmpeg.exe dan ffprobe.exe tinggal DI DALAM folder aplikasi, dan keduanya
rem dijalankan sebagai anak dari OmniClip. Proses induk boleh sudah mati
rem sementara anaknya masih menulis sebuah klip - dan Windows menolak
rem memindahkan folder yang salah satu berkasnya sedang dijalankan. Pemindai
rem antivirus juga memegang berkas yang baru saja ditutup, beberapa detik.
echo Menunggu berkas dilepas... >>"%LOG%"
timeout /t 3 /nobreak >nul

rem Hentikan ffmpeg/ffprobe yang berjalan DARI FOLDER INI saja.
rem
rem Keduanya tinggal di dalam folder aplikasi dan dijalankan sebagai anak
rem OmniClip; `os._exit()` tidak mematikan anak, jadi satu render yang belum
rem selesai tetap memegang foldernya. Disaring berdasarkan letak berkasnya,
rem bukan namanya: ffmpeg milik aplikasi lain di komputer ini tidak tersentuh,
rem dan cmd yang sedang menjalankan skrip ini juga tidak.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process -Name ffmpeg,ffprobe -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{lama}\\*' }} | Stop-Process -Force -ErrorAction SilentlyContinue" >>"%LOG%" 2>&1
timeout /t 2 /nobreak >nul

:tukar
echo [1/3] Menyingkirkan versi lama... >>"%LOG%"
set /a coba=0

:coba_singkirkan
move "{lama}" "{cadangan}" >>"%LOG%" 2>&1
if not errorlevel 1 goto :pasang_baru
set /a coba+=1
echo   percobaan %coba% ditolak, menunggu 2 detik... >>"%LOG%"
if %coba% lss 30 (
  timeout /t 2 /nobreak >nul
  goto :coba_singkirkan
)
echo Menukar folder ditolak terus. Mencatat keadaan lalu mencoba cara lain. >>"%LOG%"
tasklist /fi "IMAGENAME eq ffmpeg.exe" >>"%LOG%" 2>&1
tasklist /fi "IMAGENAME eq ffprobe.exe" >>"%LOG%" 2>&1
tasklist /fi "IMAGENAME eq OmniClip.exe" >>"%LOG%" 2>&1

rem Jalan terakhir: pasang DI TEMPAT, tanpa menukar folder sama sekali.
rem
rem Menukar folder lebih disukai karena bisa dibatalkan - yang lama tinggal
rem dikembalikan namanya. Tapi ia menuntut sesuatu yang kadang memang tidak
rem bisa didapat di Windows: hak memindahkan seluruh direktori. Menyalin isi
rem yang baru menimpa yang lama hanya menuntut hak menulis per berkas, dan itu
rem jauh lebih mudah dipenuhi. Tanpa /PURGE: berkas sisa versi lama dibiarkan
rem menganggur, sebab menghapus di sini berarti kegagalan di tengah jalan
rem meninggalkan pemasangan yang tidak utuh dan tanpa cadangan.
echo Memasang di tempat (menyalin menimpa folder lama)... >>"%LOG%"
robocopy "{baru}" "{lama}" /E /IS /R:2 /W:2 /NFL /NDL /NJH /NJS /NP >>"%LOG%" 2>&1
if errorlevel 8 (
  echo GAGAL: memasang di tempat juga ditolak. >>"%LOG%"
  rem Versi lama masih utuh. Dijalankan lagi, dan IA yang memberi tahu
  rem pemiliknya apa yang terjadi, di dalam aplikasi, lengkap dengan ekor
  rem catatan ini. Konsol hitam yang menunggu tombol bukan tempat orang
  rem membaca kabar buruk.
  start "" "{lama}\\{exe}"
  exit /b 1
)
echo Selesai lewat pemasangan di tempat. >>"%LOG%"
rmdir /s /q "{panggung}" >nul 2>&1
start "" "{lama}\\{exe}"
exit /b 0

:pasang_baru

echo [2/3] Memasang versi baru... >>"%LOG%"
move "{baru}" "{lama}" >>"%LOG%" 2>&1
if not errorlevel 1 goto :beres

rem Cadangan bila `move` menolak: paling sering karena berkas yang baru
rem dibongkar masih dipegang pemindai antivirus. Robocopy mencoba ulang
rem alih-alih menyerah pada percobaan pertama.
echo move ditolak; mencoba robocopy... >>"%LOG%"
robocopy "{baru}" "{lama}" /E /MOVE /R:3 /W:2 /NFL /NDL /NJH /NJS /NP >>"%LOG%" 2>&1
if errorlevel 8 (
  echo GAGAL: versi baru tidak bisa dipasang. Mengembalikan yang lama. >>"%LOG%"
  rmdir /s /q "{lama}" >nul 2>&1
  move "{cadangan}" "{lama}" >>"%LOG%" 2>&1
  rem Dikembalikan lalu dijalankan lagi; aplikasinya sendiri yang melaporkan
  rem kegagalan ini kepada pemiliknya.
  start "" "{lama}\\{exe}"
  exit /b 1
)

:beres
echo [3/3] Membersihkan... >>"%LOG%"
rmdir /s /q "{cadangan}" >nul 2>&1
rmdir /s /q "{panggung}" >nul 2>&1
echo Selesai. >>"%LOG%"
start "" "{lama}\\{exe}"
exit /b 0
''', encoding="utf-8")
        return p

    p = temp / "pasang.sh"
    p.write_text(f'''#!/bin/sh
# Penolong pemasangan OmniClip. Lihat catatan di app/services/updater.py.
# Port tidak diwariskan; lihat catatan pada versi Windows di atas.
unset OMNICLIP_PORT
LOG="$(dirname "$0")/pasang.log"
echo "=== OmniClip: pemasangan $(date)" >"$LOG"
echo "Menunggu OmniClip menutup..."
i=0
while kill -0 {pid} 2>/dev/null; do
  i=$((i+1))
  [ "$i" -gt 120 ] && {{ echo "GAGAL: proses {pid} tidak menutup." >>"$LOG"; exit 1; }}
  sleep 1
done
mv "{lama}" "{cadangan}" >>"$LOG" 2>&1 || {{
  echo "GAGAL: folder lama tidak bisa dipindahkan." >>"$LOG"; exit 1; }}
if ! mv "{baru}" "{lama}" >>"$LOG" 2>&1; then
  echo "GAGAL memasang; mengembalikan versi lama." >>"$LOG"
  rm -rf "{lama}"
  mv "{cadangan}" "{lama}"
  exit 1
fi
rm -rf "{cadangan}" "{panggung}"
echo "Selesai." >>"$LOG"
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

    # Panggung dibuat DI SEBELAH folder aplikasi, bukan di %TEMP%.
    #
    # Penolong menukar folder dengan `move`, dan `move` di cmd tidak bisa
    # memindahkan sebuah DIREKTORI ke volume lain — ia gagal dengan "cannot
    # move the file to a different disk drive". Selama panggungnya di %TEMP%
    # (biasanya C:) sedangkan aplikasinya dipasang di D: atau cakram lepasan,
    # pemasangan pasti gagal di langkah terakhir lalu mengembalikan versi lama.
    #
    # Di Linux ini tidak pernah terlihat: `mv` di sana diam-diam menyalin bila
    # lintas berkas-sistem. Karena itu uji ujung-ke-ujung di Linux meloloskannya.
    #
    # Induk folder aplikasi sudah dipastikan bisa ditulis oleh `bisa_memasang()`
    # di atas, jadi panggung di sini aman — dan penukarannya jadi penggantian
    # nama seketika, bukan penyalinan 300 MB.
    lama = folder_aplikasi()
    temp = Path(tempfile.mkdtemp(prefix="omniclip_update_"))   # hanya untuk skrip
    panggung = lama.parent / f".omniclip-pembaruan-{os.getpid()}"
    shutil.rmtree(panggung, ignore_errors=True)
    panggung.mkdir(parents=True)

    arsip = panggung / _nama_aset()
    total = info["ukuran"]

    ctx.progress(0.02, stage="unduh",
                 message=f"Mengunduh OmniClip {info['versi_terbaru']}…")

    try:
        baru = _unduh_dan_bongkar(ctx, info, arsip, panggung, total)
    except BaseException:
        # Panggung ada di sebelah aplikasi, bukan di %TEMP% yang disapu
        # sistem. Gagal tanpa membersihkan berarti 300 MB tertinggal di situ
        # setiap kali seseorang mencoba lalu koneksinya putus.
        shutil.rmtree(panggung, ignore_errors=True)
        shutil.rmtree(temp, ignore_errors=True)
        raise

    ctx.progress(0.95, stage="siap", message="Menyiapkan pemasangan…")
    penolong = _tulis_penolong(temp, os.getpid(), lama, baru, panggung)
    return _jalankan_penolong(ctx, info, temp, penolong)


# Berapa kali unduhan dicoba sebelum menyerah, dan jedanya.
#
# Arsip rilis 260-320 MB. Pada koneksi rumah yang tidak stabil, peluang satu
# unduhan sepanjang itu selesai tanpa satu kali pun terputus tidak besar —
# dan sebelum ini satu putusan berarti mulai dari nol, lalu orangnya menekan
# tombol lagi. Terukur di GitHub pada rilis 1.1.0: masing-masing arsip baru
# SATU kali berhasil diunduh, sementara keluhan "update gagal" sudah masuk.
UNDUH_PERCOBAAN = 5
UNDUH_JEDA = (2, 5, 10, 20)
# Batas satu operasi soket, bukan seluruh unduhan. Dulu 900 detik: sambungan
# yang macet ditunggu lima belas menit sebelum dianggap gagal. Dengan lanjut-
# unduh, gagal cepat lalu melanjutkan jauh lebih baik daripada menunggu lama.
UNDUH_SOKET_TIMEOUT = 60


def _unduh_berlanjut(ctx, url: str, arsip: Path, total: int) -> None:
    """
    Mengunduh `url` ke `arsip`, MELANJUTKAN dari yang sudah ada bila terputus.

    GitHub melayani `Range` (dijawab 206 Partial Content), jadi putusan di
    megabita ke-250 tidak lagi berarti mengulang dari megabita ke-0.
    """
    import http.client
    import urllib.error

    for percobaan in range(1, UNDUH_PERCOBAAN + 1):
        ctx.check_cancelled()
        sudah = arsip.stat().st_size if arsip.exists() else 0
        if total and sudah >= total:
            return
        kepala = {"User-Agent": f"OmniClip/{__version__}"}
        if sudah:
            kepala["Range"] = f"bytes={sudah}-"
        try:
            req = urllib.request.Request(url, headers=kepala)
            with urllib.request.urlopen(req, timeout=UNDUH_SOKET_TIMEOUT) as r:
                if sudah and r.status != 206:
                    # Server mengabaikan Range dan mengirim dari awal: menulis
                    # di ujung berkas akan menyambung dua salinan jadi satu
                    # arsip rusak.
                    log.info("Server tidak melanjutkan unduhan; mulai dari awal")
                    sudah = 0
                with open(arsip, "ab" if sudah else "wb") as f:
                    terunduh = sudah
                    while potong := r.read(1 << 20):
                        ctx.check_cancelled()
                        f.write(potong)
                        terunduh += len(potong)
                        if total:
                            ctx.progress(
                                0.02 + 0.76 * min(1.0, terunduh / total), stage="unduh",
                                message=(f"Mengunduh… {terunduh / 1e6:.0f} dari "
                                         f"{total / 1e6:.0f} MB"
                                         + (f" (percobaan ke-{percobaan})"
                                            if percobaan > 1 else "")))
            if not total or arsip.stat().st_size >= total:
                return
            raise http.client.IncompleteRead(b"", total - arsip.stat().st_size)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError,
                http.client.HTTPException) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 404):
                # Berkasnya tidak ada lagi, atau ditolak. Mencoba lagi tidak
                # mengubah jawaban itu.
                raise RuntimeError(
                    f"Berkas pembaruan tidak bisa diambil (GitHub menjawab {e.code}). "
                    "Rilisnya mungkin sudah ditarik; buka lagi Pengaturan untuk "
                    "memeriksa versi terbaru.") from e
            if percobaan >= UNDUH_PERCOBAAN:
                raise RuntimeError(
                    f"Unduhan terputus {UNDUH_PERCOBAAN} kali. Periksa koneksi "
                    "internet lalu coba lagi; yang sudah terunduh tidak disimpan.") from e
            jeda = UNDUH_JEDA[min(percobaan - 1, len(UNDUH_JEDA) - 1)]
            ada = arsip.stat().st_size if arsip.exists() else 0
            log.warning("Unduhan pembaruan terputus di %.0f MB (%s); dilanjutkan "
                        "dalam %d detik", ada / 1e6, str(e)[:120], jeda)
            ctx.progress(0.02 + 0.76 * (min(1.0, ada / total) if total else 0),
                         stage="unduh",
                         message=f"Koneksi terputus di {ada / 1e6:.0f} MB. "
                                 f"Melanjutkan dalam {jeda} detik…")
            for _ in range(jeda):
                ctx.check_cancelled()
                time.sleep(1)


def _sha256_resmi(url: str) -> str | None:
    """
    Sidik sha256 yang diterbitkan bersama arsipnya, atau None bila tidak ada.

    Berkasnya berformat `sha256sum`: "<64 heksa>  <nama berkas>". Rilis lama
    belum punya berkas ini, dan ketiadaannya bukan alasan menolak pemasangan.
    """
    try:
        req = urllib.request.Request(url + ".sha256",
                                     headers={"User-Agent": f"OmniClip/{__version__}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            teks = r.read(4096).decode("utf-8", "replace").strip()
    except Exception as e:                           # noqa: BLE001
        log.info("Sidik sha256 tidak tersedia: %s", str(e)[:120])
        return None
    kata = teks.split()
    if kata and len(kata[0]) == 64 and all(c in "0123456789abcdefABCDEF" for c in kata[0]):
        return kata[0].lower()
    return None


def _sha256_berkas(berkas: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(berkas, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def _unduh_dan_bongkar(ctx, info: dict, arsip: Path, panggung: Path,
                       total: int) -> Path:
    """Mengunduh arsip rilis lalu membongkarnya; mengembalikan folder baru."""
    _unduh_berlanjut(ctx, info["url_unduh"], arsip, total)

    if total and abs(arsip.stat().st_size - total) > 4096:
        raise RuntimeError("Unduhan tidak lengkap. Coba lagi.")

    # Sidik jari, bukan hanya ukurannya.
    #
    # Berkas `.sha256` sudah diterbitkan bersama setiap arsip sejak 1.0.8, tapi
    # tidak pernah dibaca: yang diperiksa hanya ukuran, dengan kelonggaran 4 KB.
    # Arsip yang ukurannya pas tapi isinya rusak lolos, dan kerusakannya baru
    # ketahuan saat aplikasi baru gagal dibuka — sesudah versi lama sudah
    # ditukar. Lanjut-unduh membuat pemeriksaan ini lebih perlu lagi: dua
    # potongan yang disambung salah tetap bisa berukuran benar.
    ctx.progress(0.79, stage="periksa", message="Memeriksa keaslian berkas…")
    resmi = _sha256_resmi(info["url_unduh"])
    if resmi:
        nyata = _sha256_berkas(arsip)
        if nyata != resmi:
            arsip.unlink(missing_ok=True)
            raise RuntimeError(
                "Berkas pembaruan rusak di perjalanan (sidik sha256 tidak cocok). "
                "Tidak ada yang dipasang; coba lagi.")
        log.info("Sidik sha256 arsip pembaruan cocok: %s…", nyata[:16])

    ctx.progress(0.82, stage="periksa", message="Membongkar berkas…")
    baru = _bongkar(arsip, panggung / "isi")
    arsip.unlink(missing_ok=True)      # 245 MB yang tidak dibutuhkan lagi
    return baru


def _jalankan_penolong(ctx, info: dict, temp: Path, penolong: Path) -> dict:
    """Menyalakan skrip penukar folder, lalu menutup aplikasi ini."""
    log.info("Pembaruan %s siap dipasang; menjalankan penolong %s",
             info["versi_terbaru"], penolong)

    # Dicatat SEBELUM penolongnya menyala: sesudah ini aplikasi tidak punya
    # kesempatan menulis apa pun lagi.
    catat_niat(info["versi_terbaru"], penolong.with_name("pasang.log"), __version__)

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
