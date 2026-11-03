"""JOB-4 M3.1: tema teks Montase berasal dari tema_judul.py, font lewat token."""

import unittest

from app.errors import NotFound
from app.montase import router, teks
from app.montase import token as token_svc
from app.services import tema_judul


class GayaTeks(unittest.TestCase):
    def test_setiap_tema_judul_jadi_gaya_dengan_font_bawaan(self):
        daftar = teks.daftar_gaya()
        self.assertEqual([g["id"] for g in daftar], list(tema_judul.TEMA))
        for g in daftar:
            gaya = g["gaya"]
            self.assertIn(gaya["latar"], teks.LATAR, g["id"])
            self.assertIn(gaya["gerak"], teks.GERAK, g["id"])
            self.assertIsNotNone(teks.jalur_font(gaya["font"]), gaya["font"])

    def test_besar_tema_dikalikan_ke_ukuran(self):
        pita = tema_judul.TEMA["pita-hitam"]
        self.assertEqual(teks.gaya_dari_tema(pita)["ukuran"], round(teks.UKURAN_DASAR * pita.besar))

    def test_font_dipakai_hanya_font_bawaan_item_teks(self):
        dok = {"lajur": [{"item": [
            {"jenis": "teks", "gaya": {"font": "Anton"}},
            {"jenis": "teks", "gaya": {"font": "Comic Sans"}},
            {"jenis": "video", "gaya": {"font": "Oswald"}},
            {"jenis": "teks", "gaya": {"font": "Anton"}},
        ]}]}
        self.assertEqual(teks.font_dipakai(dok), ["Anton"])

    def test_rute_font_menolak_token_salah_dan_font_asing(self):
        with self.assertRaises(NotFound):
            router.font_bertoken("palsu", "Anton")
        tkn = token_svc.buat("bahan:1")
        self.assertTrue(str(router.font_bertoken(tkn, "Bebas Neue").path).endswith("BebasNeue-Regular.ttf"))
        with self.assertRaises(NotFound):
            router.font_bertoken(tkn, "../../etc/passwd")


if __name__ == "__main__":
    unittest.main()
