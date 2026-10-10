"""JOB-2 F2-1: punch-in zoom di momen yang keras."""

import unittest

from app.services import punch


def jejak(detik, lonjak=()):
    """Energi per 50 ms: obrolan -30 dB, lonjakan -8 dB selama 0,3 detik."""
    n = int(detik / punch.LANGKAH)
    e = [-30.0 + (i % 7) * 0.5 for i in range(n)]
    for t in lonjak:
        i = int(t / punch.LANGKAH)
        for j in range(i, min(n, i + 6)):
            e[j] = -8.0
    return e


class Cari(unittest.TestCase):
    def test_menemukan_lonjakan(self):
        hasil = punch.cari(jejak(40, lonjak=(10, 25)))
        self.assertEqual(len(hasil), 2)
        self.assertAlmostEqual(hasil[0]["t"], 10 - punch.MENDAHULUI, delta=0.1)

    def test_obrolan_datar_tanpa_titik(self):
        self.assertEqual(punch.cari(jejak(40)), [])

    def test_berdekatan_hanya_satu(self):
        self.assertEqual(len(punch.cari(jejak(40, lonjak=(10, 12)))), 1)

    def test_dibatasi_panjang_klip(self):
        hasil = punch.cari(jejak(16, lonjak=(2, 8, 14)))
        self.assertLessEqual(len(hasil), max(1, int(16 * punch.PER_DETIK)))


class Siapkan(unittest.TestCase):
    def test_dijepit_dan_diurut(self):
        out = punch.siapkan([{"t": 8, "skala": 3}, {"t": 2, "dur": 9}, {"t": 50}, "x"], 10)
        self.assertEqual([p["t"] for p in out], [2, 8])
        self.assertEqual(out[1]["skala"], punch.SKALA_MAKS)
        self.assertEqual(out[0]["dur"], 4.0)
        self.assertEqual(out[1]["dur"], 1.0)

    def test_graf(self):
        g = punch.graf(punch.siapkan([{"t": 2}], 10), "[v]", out_w=1080, out_h=1920, fps=30)
        self.assertIn("zoompan=z='1+", g)
        self.assertIn("s=1080x1920:fps=30[vpunch]", g)
        self.assertEqual(punch.graf([], "[v]", out_w=1, out_h=1, fps=30), "")


if __name__ == "__main__":
    unittest.main()
