"""
Proses anak (ffmpeg) yang ikut mati bersama backend.

Terukur 19 September: sepuluh ffmpeg berjalan bersamaan, lima di antaranya
YATIM — induknya, backend yang sudah dimatikan, tidak ada lagi, tapi mereka
terus mendekode video 4K selama lebih dari satu jam. Beban mesin 98 pada
delapan inti, swap penuh, dan setiap halaman aplikasi terasa "loading terus".

Dua pengaman:
  - di Linux, `PR_SET_PDEATHSIG`: kernel sendiri membunuh anaknya begitu
    induknya mati, termasuk saat induknya dibunuh paksa;
  - di semua sistem, daftar proses yang masih hidup dihentikan saat backend
    berhenti dengan wajar.
"""

import atexit
import weakref
import os
import subprocess
import sys
import threading

# WeakSet: proses yang sudah selesai dan tidak dirujuk lagi hilang sendiri
# dari daftar, jadi pemanggil tidak wajib melepasnya.
_hidup: "weakref.WeakSet" = weakref.WeakSet()
_kunci = threading.Lock()


# Windows: nilai bendera yang dipakai di bawah, ditulis di sini supaya tidak
# tersebar sebagai angka ajaib.
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_CONSOLE = 0x00000010
DETACHED_PROCESS = 0x00000008
BELOW_NORMAL = 0x00004000

_konsol_disembunyikan = False


def sembunyikan_konsol_anak() -> None:
    """
    Semua proses anak berjalan tanpa jendela konsol sendiri (Windows saja).

    Dibutuhkan sejak aplikasi dibungkus tanpa konsol. Selama induknya punya
    konsol, anak-anaknya ikut menumpang dan tidak ada jendela baru yang muncul;
    begitu induknya tidak punya, SETIAP pemanggilan ffmpeg memunculkan jendela
    hitam yang berkedip lalu hilang — puluhan kali per render.

    Ini menambal `subprocess.Popen` secara global, bukan menambahkan bendera di
    tiap pemanggilan, dan itu disengaja: yt-dlp, faster-whisper, dan Piper
    memanggil ffmpeg SENDIRI dari dalam pustakanya. Bendera yang dipasang di
    tiap pemanggilan milik kita tidak akan pernah sampai ke sana.

    `CREATE_NEW_CONSOLE` dan `DETACHED_PROCESS` dihormati: Windows mengabaikan
    CREATE_NO_WINDOW bila salah satunya ada, dan penolong pembaruan memang
    sengaja meminta konsolnya sendiri.
    """
    global _konsol_disembunyikan
    if sys.platform != "win32" or _konsol_disembunyikan:
        return
    _konsol_disembunyikan = True

    asli = subprocess.Popen.__init__

    def dengan_bendera(self, *args, **kw):
        bendera = kw.get("creationflags", 0)
        if not bendera & (CREATE_NEW_CONSOLE | DETACHED_PROCESS):
            kw["creationflags"] = bendera | CREATE_NO_WINDOW
        si = kw.get("startupinfo") or subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0            # SW_HIDE
        kw["startupinfo"] = si
        return asli(self, *args, **kw)

    subprocess.Popen.__init__ = dengan_bendera


def _anak_linux(rendah: bool):
    def siapkan():
        try:
            import ctypes
            import signal
            ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGKILL)  # PR_SET_PDEATHSIG
        except Exception:
            pass
        if rendah:
            try:
                os.nice(19)
            except OSError:
                pass
    return siapkan


def popen(cmd: list, *, rendah: bool = False, **kw) -> subprocess.Popen:
    """Seperti subprocess.Popen, tapi anaknya tidak bisa jadi yatim.

    `rendah=True` menjalankannya dengan prioritas terendah: pekerjaan latar yang
    tidak ditunggu siapa pun tidak boleh merebut CPU dari yang sedang ditunggu.
    """
    if sys.platform.startswith("linux"):
        kw.setdefault("preexec_fn", _anak_linux(rendah))
    elif sys.platform == "win32" and rendah:
        kw["creationflags"] = kw.get("creationflags", 0) | BELOW_NORMAL
    proc = subprocess.Popen(cmd, **kw)
    with _kunci:
        _hidup.add(proc)
    return proc


def lepas(proc: subprocess.Popen) -> None:
    with _kunci:
        _hidup.discard(proc)


def jalankan(cmd: list, *, rendah: bool = False, timeout=None, **kw):
    """Seperti subprocess.run(capture_output=True, text=True), lewat popen di atas."""
    proc = popen(cmd, rendah=rendah, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                 text=kw.pop("text", True), **kw)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        raise
    finally:
        lepas(proc)
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def hentikan_semua() -> int:
    with _kunci:
        daftar = list(_hidup)
        _hidup.clear()
    for p in daftar:
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass
    return len(daftar)


atexit.register(hentikan_semua)
