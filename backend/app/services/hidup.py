"""
Mematikan OmniClip dari dalam halamannya sendiri.

Dibutuhkan sejak jendela konsol disembunyikan di Windows. Selama konsolnya ada,
"tutup jendela ini" adalah jawaban yang benar dan jelas; tanpa konsol, satu-
satunya cara mematikan aplikasi adalah lewat Task Manager — dan pengguna yang
harus membuka Task Manager untuk menutup aplikasinya akan menyimpulkan
aplikasinya rusak.

Peluncur mendaftarkan caranya berhenti di sini, dan halaman Pengaturan
memanggilnya. Saat dijalankan dari kode sumber (tanpa peluncur), tidak ada yang
mendaftar — dan sinyal ke diri sendiri dipakai sebagai gantinya, persis seperti
menekan Ctrl-C di terminalnya.
"""

import logging
import os
import signal
import threading
from typing import Callable, Optional

log = logging.getLogger("omniclip.hidup")

_berhenti: Optional[Callable[[], None]] = None


def daftarkan(fn: Callable[[], None]) -> None:
    """Dipanggil peluncur: cara memberi tahu servernya supaya berhenti."""
    global _berhenti
    _berhenti = fn


def berhenti(jeda: float = 0.6) -> None:
    """
    Meminta aplikasi berhenti, sesudah `jeda` detik.

    Jedanya ada supaya jawaban HTTP untuk permintaan ini sempat sampai ke
    peramban lebih dulu. Tanpa itu, halaman yang menekan tombol Keluar
    mendapat sambungan terputus alih-alih jawaban "baik, saya berhenti" —
    dan yang terlihat pengguna adalah galat, bukan pamitan.
    """
    def kerjakan() -> None:
        log.info("Diminta berhenti dari halaman Pengaturan.")
        from .proses import hentikan_semua
        try:
            n = hentikan_semua()
            if n:
                log.info("%d proses anak dihentikan lebih dulu.", n)
        except Exception as e:
            log.warning("Proses anak tidak bisa dihentikan: %s", e)
        if _berhenti is not None:
            _berhenti()
        else:
            # Tanpa peluncur: sama dengan Ctrl-C di terminalnya sendiri.
            os.kill(os.getpid(), getattr(signal, "SIGINT", signal.SIGTERM))

    threading.Timer(max(0.0, jeda), kerjakan).start()
