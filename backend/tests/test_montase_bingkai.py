"""Bingkai ulang 9:16 dari jejak subjek (JOB-4 M5.5)."""

import unittest

from app.montase import bingkai


class KeyframeX(unittest.TestCase):
    def test_skala_menutup_tinggi_dan_x_dijepit(self):
        skala, lebar = bingkai.ukuran_tampak(1920, 1080, 1080, 1920)
        self.assertAlmostEqual(skala, 1920 / (1080 * 1080 / 1920), places=3)
        self.assertAlmostEqual(lebar, 1920 * 1920 / 1080, places=1)
        # Subjek di tengah -> 0; di tepi kiri bahan -> geser kanan, dijepit supaya tidak ada tepi kosong.
        _s, kf = bingkai.keyframe_x([(0.0, 960), (1.0, 0)], sw=1920, sh=1080, W=1080, H=1920, fps=30)
        maks = (lebar - 1080) / 2
        self.assertEqual(kf[0]["v"], 0)
        self.assertAlmostEqual(kf[-1]["v"], round(maks, 1), places=1)
        self.assertEqual(kf[-1]["t"], 30)

    def test_titik_rapat_diringkas(self):
        # Gerak lurus 3 detik pada 10 sampel/detik: cukup dua titik.
        centers = [(i / 10, 600 + i * 10) for i in range(31)]
        _s, kf = bingkai.keyframe_x(centers, sw=1920, sh=1080, W=1080, H=1920, fps=30)
        self.assertEqual([k["t"] for k in kf], [0, 90])
        # Berbelok di tengah: titik beloknya dipertahankan.
        belok = [(i / 10, 600 + (i if i <= 15 else 30 - i) * 20) for i in range(31)]
        _s, kf = bingkai.keyframe_x(belok, sw=1920, sh=1080, W=1080, H=1920, fps=30)
        self.assertIn(45, [k["t"] for k in kf])

    def test_kecepatan_memendekkan_waktu_item(self):
        _s, kf = bingkai.keyframe_x([(0.0, 900), (2.0, 1100)], sw=1920, sh=1080, W=1080, H=1920,
                                    fps=30, kecepatan=2)
        self.assertEqual(kf[-1]["t"], 30)


if __name__ == "__main__":
    unittest.main()
