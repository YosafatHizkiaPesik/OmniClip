"""
Bingkai pindah ke wajah tanpa luncuran (15 Oktober 2026).

Dilaporkan: "bingkai masih menyorot sepersekian detik ke ruang kosong dan
tidak langsung pindah ke wajah". Tiga sebab, tiga uji.
"""

import unittest

from app.services import reframe as R

W, CROP = 1280, 404


class IsiAwalBidikan(unittest.TestCase):
    def test_bidikan_baru_tidak_mewarisi_posisi_lama(self):
        # Bidikan A di x=300, potongan di sampel 16, wajah bidikan B baru
        # terdeteksi di sampel 19 (x=1000). Tiga sampel di antaranya dulu
        # memakai x=300 dari bidikan A.
        n = 40
        centers = [300.0] * 16 + [None, None, None] + [1000.0] * (n - 19)
        cuts = [False] * n
        cuts[16] = True
        out = R._smooth(centers, cuts, source_w=W, crop_w=CROP)
        for i in (16, 17, 18):
            self.assertGreater(out[i], 900, f"sampel {i}: {out[i]}")


class BatasKeluar(unittest.TestCase):
    def test_batas_diserahkan_ke_pemanggil(self):
        n = 40
        centers = [300.0] * 20 + [1000.0] * 20
        cuts = [False] * n
        cuts[20] = True
        batas = []
        R._smooth(centers, cuts, source_w=W, crop_w=CROP, batas_keluar=batas)
        self.assertIn((20, True), batas)


class PlafonAdaptif(unittest.TestCase):
    def test_wajah_menyeberang_cepat_tetap_di_dalam_kotak(self):
        # Diam 2 dtk, menyeberang 600 px/dtk (75 px per sampel) selama
        # 1,25 dtk, lalu diam. Kode lama: 8 sampel wajah di luar kotak.
        c = [300.0] * 16 + [300.0 + k * 75 for k in range(1, 11)] + [1050.0] * 24
        out = R._smooth(c, [False] * len(c), source_w=W, crop_w=CROP)
        keluar = sum(1 for o, x in zip(out, c) if abs(o - x) > CROP / 2)
        self.assertEqual(keluar, 0)

    def test_gerak_kecil_tetap_halus(self):
        # Goyangan 10 px tidak menggerakkan kamera sama sekali (deadzone).
        c = [600.0 + (10 if i % 2 else 0) for i in range(40)]
        out = R._smooth(c, [False] * len(c), source_w=W, crop_w=CROP)
        self.assertLess(max(out) - min(out), 12)


if __name__ == "__main__":
    unittest.main()
