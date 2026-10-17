"""Koneksi AI universal dan AI lokal (17 Oktober 2026)."""
import json
import unittest
from unittest import mock

from app.services import koneksi_ai


class _Settings:
    def __init__(self):
        self.d = {}

    def get(self, k, default=""):
        return self.d.get(k, default)

    def set_value(self, k, v):
        self.d[k] = v

    def delete(self, k):
        self.d.pop(k, None)


class Daftar(unittest.TestCase):
    def setUp(self):
        self.s = _Settings()
        self.p = [mock.patch.object(koneksi_ai, "_settings", return_value=self.s),
                  mock.patch("app.services.kunci_ai._settings", return_value=self.s),
                  mock.patch.object(koneksi_ai, "_env_kunci", return_value={}),
                  mock.patch.object(koneksi_ai, "_hasil_uji", return_value=None),
                  mock.patch.object(koneksi_ai, "_simpan_uji")]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_migrasi_dari_kunci_lama(self):
        self.s.d["ai.api_key"] = "AIzaSATU\nAIzaDUA"
        self.s.d["ai.openrouter_key"] = "sk-or-xyz"
        d = koneksi_ai.semua()
        self.assertEqual([k["penyedia"] for k in d], ["gemini", "gemini", "openrouter"])
        self.assertTrue(json.loads(self.s.d[koneksi_ai.SIMPAN]))

    def test_tambah_urut_utama_hapus(self):
        with mock.patch.object(koneksi_ai, "uji_koneksi", return_value={"status": "bekerja"}):
            a = koneksi_ai.tambah("groq", "gsk_a", nama="Groq")["id"]
            b = koneksi_ai.tambah("lokal", nama="Lokal")["id"]
        pub = koneksi_ai.daftar_publik()
        self.assertEqual([k["id"] for k in pub], [a, b])
        self.assertTrue(pub[0]["utama"])
        self.assertNotIn("kunci", pub[0])
        koneksi_ai.jadikan_utama(b)
        self.assertEqual(koneksi_ai.rantai()[0]["id"], b)
        koneksi_ai.ubah(b, aktif=False)
        self.assertEqual([k["id"] for k in koneksi_ai.rantai()], [a])
        koneksi_ai.hapus(a)
        self.assertEqual([k["id"] for k in koneksi_ai.semua()], [b])

    def test_kunci_ditolak_tidak_ditambahkan(self):
        with mock.patch.object(koneksi_ai, "uji_koneksi", return_value={"status": "tidak_sah"}):
            with self.assertRaises(ValueError):
                koneksi_ai.tambah("openai", "sk-salah")
        self.assertEqual(koneksi_ai.semua(), [])

    def test_kunci_gemini_dicerminkan_untuk_pembaca_lama(self):
        with mock.patch.object(koneksi_ai, "uji_koneksi", return_value={"status": "bekerja"}):
            koneksi_ai.tambah("gemini", "AIzaBARU")
        self.assertEqual(self.s.d.get("ai.api_key"), "AIzaBARU")
        self.assertEqual(koneksi_ai.kunci_gemini(), ["AIzaBARU"])

    def test_rantai_gambar_melewati_yang_buta(self):
        with mock.patch.object(koneksi_ai, "uji_koneksi", return_value={"status": "bekerja"}):
            koneksi_ai.tambah("lokal", nama="Lokal")
            koneksi_ai.tambah("anthropic", "sk-ant-x")
        self.assertEqual([k["penyedia"] for k in koneksi_ai.rantai(butuh_gambar=True)], ["anthropic"])


class AlasanAi(unittest.TestCase):
    def test_ram_kurang_disebut(self):
        from app.services.pipeline import alasan_ai
        self.assertTrue(alasan_ai([], ["RAM bebas tinggal 900 MB, AI lokal butuh sekitar 3000 MB. Tutup"]).startswith("RAM bebas"))
        self.assertEqual(alasan_ai(["429 RESOURCE_EXHAUSTED"], []), "Kuota harian Gemini habis")


class AiLokal(unittest.TestCase):
    def test_model_dipatok_sha256(self):
        from app.services import ai_lokal
        for m in ai_lokal.MODEL.values():
            self.assertEqual(len(m["sha256"]), 64)
            self.assertTrue(m["url"].startswith("https://huggingface.co/"))
        for nama, sha in ai_lokal.MESIN.values():
            self.assertIn(ai_lokal.BUILD, nama)
            self.assertEqual(len(sha), 64)

    def test_ram_kurang_ditolak(self):
        from app.services import ai_lokal
        with mock.patch.object(ai_lokal, "_server", return_value=mock.Mock()), \
             mock.patch.object(ai_lokal, "_berkas_model") as bm, \
             mock.patch.object(ai_lokal, "ram_bebas_mb", return_value=500):
            bm.return_value.is_file.return_value = True
            with self.assertRaises(RuntimeError) as c:
                ai_lokal.alamat("qwen2.5-3b")
        self.assertIn("RAM bebas", str(c.exception))


if __name__ == "__main__":
    unittest.main()
