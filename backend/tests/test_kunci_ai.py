"""Pengelola kunci Gemini (16 Oktober 2026)."""
import unittest
from unittest import mock

from app.services import kunci_ai


class Galat(Exception):
    def __init__(self, code, teks, details=None):
        super().__init__(teks)
        self.code = code
        self.details = details


class JenisGalat(unittest.TestCase):
    def test_proyek_diblokir(self):
        g = kunci_ai._jenis_galat(Galat(403, "403 PERMISSION_DENIED. Your project has been denied access."))
        self.assertEqual(g["status"], "ditolak")

    def test_limit_nol_bukan_kuota_habis(self):
        g = kunci_ai._jenis_galat(Galat(429, "RESOURCE_EXHAUSTED", {"error": {"message":
            "Quota exceeded for metric: x, limit: 0, model: gemini-3.1-pro", "details": [
                {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"},
                {"retryDelay": "61940s"}]}}))
        self.assertEqual(g["status"], "tanpa_jatah")
        self.assertEqual(g["tunggu"], 61940)

    def test_kuota_harian_habis(self):
        g = kunci_ai._jenis_galat(Galat(429, "RESOURCE_EXHAUSTED", {"error": {"message":
            "limit: 20", "details": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}}))
        self.assertEqual((g["status"], g["batas"]), ("kuota_harian", 20))

    def test_kunci_tidak_sah(self):
        self.assertEqual(kunci_ai._jenis_galat(Galat(400, "API key not valid"))["status"], "tidak_sah")


class Ringkasan(unittest.TestCase):
    def test_satu_ok_berarti_bekerja(self):
        self.assertEqual(kunci_ai._ringkas([{"status": "ditolak"}, {"status": "ok"}], None), "bekerja")

    def test_ditolak_mengalahkan_tanpa_jatah(self):
        self.assertEqual(kunci_ai._ringkas(
            [{"status": "tanpa_jatah"}, {"status": "ditolak"}, {"status": "tidak_ada"}], None), "ditolak")

    def test_semua_kuota(self):
        self.assertEqual(kunci_ai._ringkas([{"status": "kuota_harian"}, {"status": "tanpa_jatah"}], None), "kuota")


class Lewati(unittest.TestCase):
    def test_kunci_ditolak_dilewati_selama_beberapa_jam(self):
        import time
        with mock.patch.object(kunci_ai, "_hasil_uji", return_value={"status": "ditolak", "waktu": time.time()}):
            self.assertFalse(kunci_ai.boleh_dipakai("k"))
        with mock.patch.object(kunci_ai, "_hasil_uji", return_value={"status": "ditolak", "waktu": 0}):
            self.assertTrue(kunci_ai.boleh_dipakai("k"))
        with mock.patch.object(kunci_ai, "_hasil_uji", return_value={"status": "kuota", "waktu": time.time()}):
            self.assertTrue(kunci_ai.boleh_dipakai("k"))


if __name__ == "__main__":
    unittest.main()
