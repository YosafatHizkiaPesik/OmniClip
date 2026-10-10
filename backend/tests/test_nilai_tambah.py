"""JOB-2 F3-1: skor nilai tambah per klip."""

import unittest

from app.services import nilai_tambah as nt


def komentar(d, **lain):
    return {"posisi": "sela", "t": 1.0, "d": d, "mode": "bekukan", "teks": "x",
            "bersuara": True, "sintetis": False, "kartu": False, **lain}


class Hitung(unittest.TestCase):
    def test_tanpa_apa_pun_nol_dan_tidak_cukup(self):
        h = nt.hitung({"duration": 30})
        self.assertEqual((h["skor"], h["cukup"]), (0.0, False))
        self.assertEqual(nt.hitung(None)["skor"], 0.0)

    def test_komentar_dua_detik_sudah_cukup(self):
        h = nt.hitung({"duration": 40, "komentar": [komentar(2.0)]})
        self.assertTrue(h["cukup"])
        self.assertEqual(h["persen"], 5)

    def test_komentar_tersembunyi_tanpa_suara_tidak_dihitung(self):
        h = nt.hitung({"duration": 40, "komentar": [komentar(5.0, bersuara=False, kartu=False)]})
        self.assertEqual(h["detik_komentar"], 0.0)

    def test_sisipan_setengah_bobot_dan_tumpukan_digabung(self):
        h = nt.hitung({"duration": 20, "media_layers": [
            {"t": 0, "dur": 4}, {"t": 2, "dur": 4}, {"t": 10, "dur": 2}, {"t": 1}]})
        self.assertEqual(h["detik_sisipan"], 8.0)
        self.assertAlmostEqual(h["skor"], 0.2)
        self.assertTrue(h["cukup"])

    def test_skor_dibatasi_satu(self):
        self.assertEqual(nt.hitung({"duration": 5, "komentar": [komentar(30)]})["skor"], 1.0)


if __name__ == "__main__":
    unittest.main()
