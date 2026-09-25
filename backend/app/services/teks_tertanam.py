"""
Menemukan subtitle yang SUDAH TERBAKAR di dalam gambar sumber.

Video fansub, potongan berita, dan unduhan berbahasa asing sering datang dengan
teksnya sendiri di bagian bawah. OmniClip menggambar subtitlenya di tempat yang
sama, jadi keduanya bertumpuk dan dua-duanya jadi tidak terbaca. Sampai sekarang
jalan keluarnya adalah pemiliknya menyadari sendiri lalu menaikkan subtitlenya
dengan tangan, satu klip demi satu klip.

Cara mengenalinya, dan kenapa begitu:

- Teks dicari dari TEPINYA, bukan dari terangnya. Subtitle terbakar hampir
  selalu punya garis luar gelap di sekeliling huruf terang, dan pasangan itu
  menghasilkan tepi yang sangat rapat. Mengandalkan "piksel terang" saja akan
  ikut menandai langit, lampu, dan kaos putih.
- Yang membedakannya dari gambar biasa adalah PERBANDINGAN, bukan angka
  mutlak. Diukur pada dua video sungguhan: pita subtitle anime fansub punya
  keramaian tepi 0,096, sementara seluruh bagian gambar lainnya 0,048 -- dua
  kali lipat. Pada wawancara bersih yang penuh gerak, pita bawahnya 0,049
  sementara sisanya 0,026, dan angka mutlaknya tidak pernah sampai setengah
  milik anime. Jadi dipakai dua syarat sekaligus: cukup ramai secara mutlak,
  DAN jauh lebih ramai daripada bagian gambar di atasnya.
- Yang dilaporkan adalah BATAS ATAS pita teksnya, dalam persen tinggi gambar.
  Pemanggil menaikkan subtitlenya sendiri sampai di atas garis itu.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("omniclip.tertanam")

# Bagian bawah gambar yang diperiksa. Subtitle terbakar di atas seperempat
# bawah praktis tidak ada, dan memeriksa lebih tinggi berarti menandai kerah
# baju, meja, dan papan nama di belakang orang.
DASAR_PERIKSA = 0.72
LEBAR = 480                 # cukup untuk melihat huruf, cukup murah untuk dibaca
SAMPEL = 12                 # bingkai yang diperiksa per klip
# Kedua angka diukur, bukan ditebak. Lihat penjelasan di kepala berkas.
TEPI_MIN = 0.070            # keramaian tepi mutlak sebuah baris dianggap teks
LIPAT_MIN = 1.7             # dan sekian kali lebih ramai daripada bagian atasnya
BARIS_MIN = 5               # pita setipis ini bukan baris teks


def _bingkai(src: Path, mulai: float, durasi: float, n: int):
    """`n` bingkai abu-abu, tersebar rata sepanjang rentang."""
    import numpy as np

    from .reframe import _sample_frames

    # `_sample_frames` menghasilkan bita BGR mentah, bukan larik: bentuknya
    # disusun di sini supaya modul itu tidak perlu tahu siapa pemakainya.
    tinggi = int(LEBAR * 9 / 16)
    if tinggi % 2:
        tinggi += 1
    jeda = max(0.5, durasi / max(1, n))
    keluar = []
    for i in range(n):
        t = mulai + i * jeda
        if t >= mulai + durasi:
            break
        for buf in _sample_frames(src, t, 0.05, LEBAR, tinggi):
            bgr = np.frombuffer(buf, dtype=np.uint8).reshape(tinggi, LEBAR, 3)
            keluar.append(bgr.mean(axis=2))
            break
    return keluar


def _keramaian(abu) -> "list[float]":
    """Berapa ramai tepi di tiap baris piksel, 0 sampai 1."""
    import numpy as np

    beda = np.abs(np.diff(abu, axis=1))
    return (beda > 40).mean(axis=1).tolist()


def batas_atas(src, mulai: float, durasi: float) -> Optional[float]:
    """
    Batas ATAS pita teks terbakar, dalam persen tinggi gambar; None bila bersih.

    Contoh: 82.0 berarti teksnya menempati 18% bagian bawah, jadi subtitle
    OmniClip harus berakhir di atas garis 82%.
    """
    try:
        import numpy as np
    except ImportError:
        return None
    try:
        bingkai = _bingkai(Path(src), mulai, durasi, SAMPEL)
    except Exception as e:                  # deteksi bukan alasan render gagal
        log.warning("Teks tertanam tidak bisa diperiksa: %s", str(e)[:160])
        return None
    if len(bingkai) < 4:
        return None

    tinggi = bingkai[0].shape[0]
    ramai = np.array([_keramaian(b) for b in bingkai])        # sampel x baris
    rata = ramai.mean(axis=0)

    y0 = int(tinggi * DASAR_PERIKSA)
    # Pembanding diambil dari gambar itu sendiri, bukan dari nilai tetap:
    # animasi datar dan rekaman kamera punya keramaian dasar yang jauh berbeda,
    # dan yang menandakan teks adalah LONJAKANNYA di pita bawah.
    dasar = float(np.median(rata[:y0])) if y0 > 4 else 0.0
    ambang = max(TEPI_MIN, dasar * LIPAT_MIN)

    teks = rata[y0:] > ambang
    if not teks.any():
        return None
    baris = np.flatnonzero(teks)
    if len(baris) < BARIS_MIN:
        return None

    persen = (y0 + int(baris[0])) / tinggi * 100.0
    log.info("Teks tertanam terdeteksi mulai %.0f%% tinggi gambar "
             "(tepi %.3f, dasar gambar %.3f)",
             persen, float(rata[y0 + int(baris[0])]), dasar)
    return round(persen, 1)
