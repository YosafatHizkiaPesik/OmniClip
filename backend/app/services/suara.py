"""
Simpanan audio 16 kHz per video sumber.

Mengekstrak audio berarti membaca SELURUH berkas videonya, karena audio dan
gambarnya dijalin sepanjang berkas. Untuk rekaman gameplay 1 jam 48 menit
berukuran 3,9 GB di cakram NTFS itu 49 detik hanya untuk membaca, dan 64 detik
sampai WAV-nya jadi — dan dulu itu dibayar ulang setiap kali pengguna menekan
"Deteksi ulang", lalu WAV-nya dibuang lagi.

WAV mono 16 kHz hanya sekitar 115 MB per jam, jadi disimpan. Namanya diturunkan
dari jalur, ukuran, dan waktu ubah sumbernya (pola yang sama dengan proksi),
sehingga video yang diunduh ulang otomatis mendapat audio baru. Catatan
`.sumber` di sebelahnya membuat simpanan yang videonya sudah dihapus bisa
dikenali dan dibuang.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from ..config import STORAGE_DIR

log = logging.getLogger("omniclip.suara")

SUARA_DIR = STORAGE_DIR / "suara"

_kunci_per_berkas: dict[str, threading.Lock] = {}
_kunci_daftar = threading.Lock()


def _nama(src: Path) -> Path:
    st = src.stat()
    sidik = hashlib.sha1(
        f"{src.resolve()}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()[:16]
    return SUARA_DIR / f"{sidik}.wav"


def _kunci(tujuan: Path) -> threading.Lock:
    with _kunci_daftar:
        return _kunci_per_berkas.setdefault(str(tujuan), threading.Lock())


def tersimpan(src: str | Path) -> Optional[Path]:
    """Audio sumber ini bila sudah tersimpan, tanpa mengekstraknya."""
    try:
        tujuan = _nama(Path(src))
        return tujuan if tujuan.is_file() and tujuan.stat().st_size > 44 else None
    except OSError:
        return None


def ada(src: str | Path) -> bool:
    return tersimpan(src) is not None


def siapkan(src: str | Path) -> Optional[str]:
    """
    Jalur WAV 16 kHz mono untuk `src`, mengekstraknya bila belum ada.

    Dua pekerjaan yang meminta audio yang sama bersamaan tidak mengekstrak dua
    kali: yang kedua menunggu yang pertama lalu memakai hasilnya.
    """
    from .media import extract_audio_wav

    src = Path(src)
    try:
        tujuan = _nama(src)
    except OSError:
        return None
    with _kunci(tujuan):
        if tujuan.is_file() and tujuan.stat().st_size > 44:
            return str(tujuan)
        SUARA_DIR.mkdir(parents=True, exist_ok=True)
        # Ekstensinya tetap .wav supaya ffmpeg tahu formatnya; berkas yang
        # setengah jadi tidak pernah terlihat dengan nama akhirnya.
        sementara = tujuan.with_name(tujuan.stem + ".tmp.wav")
        if not extract_audio_wav(src, sementara):
            sementara.unlink(missing_ok=True)
            return None
        os.replace(sementara, tujuan)
        try:
            tujuan.with_suffix(".sumber").write_text(str(src.resolve()), encoding="utf-8")
        except OSError:
            pass
        log.info("Audio disimpan: %s (%.0f MB)", tujuan.name,
                 tujuan.stat().st_size / 1e6)
        return str(tujuan)


def buang(wav: Path) -> None:
    """Membuang audio tersimpan beserta catatan dan sidik suaranya."""
    for berkas in list(wav.parent.glob(f"{wav.stem}.*")):
        berkas.unlink(missing_ok=True)


def bersihkan_yatim() -> int:
    """Membuang audio yang videonya sudah tidak ada, dan sisa ekstraksi terputus."""
    if not SUARA_DIR.is_dir():
        return 0
    dibuang = 0
    for catatan in SUARA_DIR.glob("*.sumber"):
        try:
            asal = Path(catatan.read_text(encoding="utf-8").strip())
        except OSError:
            continue
        if not asal.is_file():
            buang(catatan.with_suffix(".wav"))
            dibuang += 1
    for sisa in SUARA_DIR.glob("*.tmp.wav"):
        # Hanya sisa proses yang sudah mati; di proses ini kuncinya dipegang.
        if not _kunci(sisa.with_name(sisa.name.replace(".tmp.wav", ".wav"))).locked():
            sisa.unlink(missing_ok=True)
    return dibuang
