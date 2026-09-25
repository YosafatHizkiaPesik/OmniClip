"""
Subtitle yang sudah terbakar di gambar sumber.

Video fansub dan potongan berita datang dengan teksnya sendiri di bagian bawah.
OmniClip menggambar subtitlenya di tempat yang sama, jadi keduanya bertumpuk dan
dua-duanya tidak terbaca.

Yang paling penting dijaga di sini BUKAN "teksnya ketemu", melainkan "gambar
bersih tidak ditandai". Menaikkan subtitle pada video yang sebenarnya bersih
merusak klip yang tadinya baik-baik saja, dan pemiliknya tidak punya cara
menebak kenapa.
"""

import unittest

import numpy as np

from app.services import teks_tertanam as tt


def gambar(tinggi=270, lebar=480, dasar=0.04, pita=None, ramai=0.10):
    """
    Bingkai buatan dengan keramaian tepi yang bisa diatur.

    `pita` = (y0, y1) baris yang dibuat seramai `ramai`. Nilainya diambil dari
    pengukuran pada video sungguhan: pita subtitle anime 0,096 dengan dasar
    gambar 0,048; wawancara bersih 0,049 dengan dasar 0,026.
    """
    rng = np.random.default_rng(7)
    g = np.zeros((tinggi, lebar), dtype=float)
    for y in range(tinggi):
        p = ramai if (pita and pita[0] <= y < pita[1]) else dasar
        lompat = rng.random(lebar) < p
        g[y] = np.cumsum(np.where(lompat, 80.0, 0.0)) % 200
    return g


class Deteksi(unittest.TestCase):
    def jalankan(self, bingkai):
        """Meniru `batas_atas` tanpa menyentuh ffmpeg."""
        asli = tt._bingkai
        tt._bingkai = lambda *a, **kv: bingkai
        try:
            return tt.batas_atas("/tmp/x.mp4", 0.0, 30.0)
        finally:
            tt._bingkai = asli

    def test_gambar_bersih_tidak_ditandai(self):
        self.assertIsNone(self.jalankan([gambar() for _ in range(12)]))

    def test_gambar_bersih_yang_ramai_juga_tidak(self):
        # Rekaman kamera penuh gerak: dasarnya tinggi, tapi merata.
        self.assertIsNone(self.jalankan([gambar(dasar=0.05) for _ in range(12)]))

    def test_pita_teks_di_bawah_ditemukan(self):
        hasil = self.jalankan([gambar(pita=(225, 250), ramai=0.14) for _ in range(12)])
        self.assertIsNotNone(hasil)
        self.assertGreater(hasil, 72.0)
        self.assertLess(hasil, 95.0)

    def test_pita_setipis_satu_baris_diabaikan(self):
        # Garis tepi atau bingkai gambar, bukan baris teks.
        self.assertIsNone(self.jalankan(
            [gambar(pita=(240, 242), ramai=0.20) for _ in range(12)]))

    def test_teks_di_tengah_gambar_tidak_menaikkan_subtitle(self):
        # Papan nama dan tulisan di kaos ada di mana-mana; yang diperiksa hanya
        # seperempat bawah.
        self.assertIsNone(self.jalankan(
            [gambar(pita=(100, 140), ramai=0.20) for _ in range(12)]))

    def test_sampel_terlalu_sedikit_menjawab_tidak_tahu(self):
        self.assertIsNone(self.jalankan([gambar(pita=(230, 255), ramai=0.2)] * 2))


class Ambang(unittest.TestCase):
    def test_angkanya_diukur_bukan_ditebak(self):
        # Anime 0,096 vs wawancara bersih 0,049: ambangnya harus di antara
        # keduanya, kalau tidak salah satunya pasti salah dinilai.
        self.assertGreater(tt.TEPI_MIN, 0.049)
        self.assertLess(tt.TEPI_MIN, 0.096)

    def test_hanya_seperempat_bawah_yang_diperiksa(self):
        self.assertGreaterEqual(tt.DASAR_PERIKSA, 0.70)

    def test_perbandingan_ikut_menentukan(self):
        # Angka mutlak saja tidak cukup: animasi datar dan rekaman kamera punya
        # keramaian dasar yang jauh berbeda.
        self.assertGreater(tt.LIPAT_MIN, 1.0)


if __name__ == "__main__":
    unittest.main()
