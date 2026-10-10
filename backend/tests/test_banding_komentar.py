"""JOB-2 F3-2: klip dengan komentar dibanding yang tanpa."""

import unittest

from app.services import analitik


def k(tayangan, berkomentar):
    return {"tayangan": tayangan, "berkomentar": berkomentar}


class Banding(unittest.TestCase):
    def test_belum_cukup_menyebut_kekurangannya(self):
        h = analitik.banding_komentar([k(100, True), k(50, False), k(70, False)])
        self.assertFalse(h["cukup"])
        self.assertIn("2 klip lagi yang diberi komentar", h["kalimat"])
        self.assertIn("1 klip lagi tanpa komentar", h["kalimat"])

    def test_dengan_komentar_lebih_tinggi(self):
        h = analitik.banding_komentar([k(1000, True), k(1200, True), k(900, True),
                                       k(300, False), k(400, False), k(350, False)])
        self.assertTrue(h["cukup"])
        self.assertEqual((h["median_dengan"], h["median_tanpa"]), (1000, 350))
        self.assertIn("lebih banyak ditonton", h["kalimat"])

    def test_beda_kecil_tidak_dibesar_besarkan(self):
        h = analitik.banding_komentar([k(100, True)] * 3 + [k(95, False)] * 3)
        self.assertIn("Belum terlihat beda", h["kalimat"])

    def test_yang_tidak_diketahui_tidak_dihitung(self):
        h = analitik.banding_komentar([k(100, None), {"tayangan": None, "berkomentar": True}])
        self.assertEqual((h["dengan"], h["tanpa"]), (0, 0))

    def test_berkomentar_dari_sidecar(self):
        self.assertFalse(analitik._berkomentar({"duration": 30}))
        self.assertTrue(analitik._berkomentar({"duration": 30, "komentar": [
            {"d": 3, "bersuara": True}]}))
        self.assertFalse(analitik._berkomentar({"duration": 30, "komentar": [
            {"d": 3, "kartu": True, "merek": True}]}))


if __name__ == "__main__":
    unittest.main()
