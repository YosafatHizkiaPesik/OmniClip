"""Pesan server mengikuti bahasa antarmuka (JOB-3 J3-11)."""

import unittest

from app import bahasa


class Terjemahan(unittest.TestCase):
    def test_kalimat_tetap(self):
        self.assertEqual(bahasa.teks("Job tidak ditemukan.", "en"), "Job not found.")

    def test_templat_dengan_angka(self):
        self.assertEqual(bahasa.teks("Merender klip… 45%", "en"), "Rendering clip… 45%")
        self.assertEqual(bahasa.teks("Mengunduh «Kai Cenat»…", "en"), "Downloading «Kai Cenat»…")

    def test_isian_ikut_diterjemahkan(self):
        self.assertEqual(bahasa.teks("Gemini gagal, memakai mesin lokal.", "en"),
                         "Gemini failed, using the local engine.")

    def test_data_pengguna_tidak_berubah(self):
        """Judul video dan teks lain yang tidak ada di katalog dibiarkan."""
        self.assertEqual(bahasa.teks("Podcast seru tentang AI", "en"), "Podcast seru tentang AI")

    def test_bahasa_indonesia_tidak_disentuh(self):
        self.assertEqual(bahasa.teks("Job tidak ditemukan.", "id"), "Job tidak ditemukan.")

    def test_struktur_json(self):
        hasil = bahasa.terjemahkan({"message": "Pekerjaan gagal.", "judul": "X",
                                    "baris": [{"nama": "Kunci AI"}]}, "en")
        self.assertEqual(hasil, {"message": "The job failed.", "judul": "X",
                                 "baris": [{"nama": "AI key"}]})

    def test_bahasa_dari_permintaan(self):
        self.assertEqual(bahasa.dari_permintaan(None, "en-US,en;q=0.9"), "en")
        self.assertEqual(bahasa.dari_permintaan("id", "en-US"), "id")
        self.assertEqual(bahasa.dari_permintaan(None, "fr-FR"), "id")
        self.assertEqual(bahasa.dari_permintaan(None, None), "id")


class LewatServer(unittest.TestCase):
    def test_galat_api_dalam_bahasa_inggris(self):
        from fastapi.testclient import TestClient

        from app.main import app
        with TestClient(app) as c:
            r = c.get("/api/jobs/tidak-ada", headers={"Accept-Language": "en"})
            self.assertEqual(r.status_code, 404)
            self.assertIn("Job not found.", r.text)
            r = c.get("/api/jobs/tidak-ada", headers={"Accept-Language": "id"})
            self.assertIn("Job tidak ditemukan.", r.text)


if __name__ == "__main__":
    unittest.main()
