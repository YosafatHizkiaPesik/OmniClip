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
        kw.setdefault("creationflags", 0x00004000)   # BELOW_NORMAL_PRIORITY_CLASS
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
