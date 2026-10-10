"""
JOB-2 F1-4/F1-5/F1-6: komentar ikut dirender ke klip.

Render sungguhannya diuji dengan tangan (lihat JOB-2.md). Yang diuji di sini
adalah aturan yang tidak boleh berubah diam-diam: kapan komentar dibuang,
berapa lama ia menahan gambar, dan waktu subtitle sesudahnya.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.services import komentar as km


class Siapkan(unittest.TestCase):
    def test_kartu_tanpa_suara_lamanya_waktu_baca(self):
        out = km.siapkan_render([{"posisi": "pembuka", "teks": "Ini komentar saya."}], 10)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["t"], 0.0)
        self.assertEqual(out[0]["d"], km.detik_baca("Ini komentar saya."))
        self.assertTrue(out[0]["tampil"])
        self.assertEqual(out[0]["mode"], "bekukan")

    def test_kosong_dan_tak_dikenal_dibuang(self):
        out = km.siapkan_render([
            {"posisi": "pembuka", "teks": ""},
            {"posisi": "entah", "teks": "x"},
            {"posisi": "sela", "teks": "tanpa waktu"},
            {"posisi": "penutup", "teks": "disembunyikan", "tampil_teks": False},
            "bukan dict",
        ], 10)
        self.assertEqual(out, [])

    def test_urutan_dan_tempat(self):
        out = km.siapkan_render([
            {"posisi": "penutup", "teks": "akhir"},
            {"posisi": "sela", "t": 99, "teks": "tengah"},
            {"posisi": "pembuka", "teks": "awal"},
        ], 10)
        self.assertEqual([k["posisi"] for k in out], ["pembuka", "sela", "penutup"])
        self.assertEqual(out[1]["t"], 9.9)          # dijepit ke dalam klip
        self.assertEqual(out[2]["t"], 10.0)

    def test_timpa_yang_tidak_muat_jadi_bekukan(self):
        teks = "kata " * 60
        out = km.siapkan_render([{"posisi": "sela", "t": 8, "teks": teks, "mode": "timpa"}], 10)
        self.assertEqual(out[0]["mode"], "bekukan")
        out = km.siapkan_render([{"posisi": "sela", "t": 2, "teks": "pendek", "mode": "timpa"}], 10)
        self.assertEqual(out[0]["mode"], "timpa")

    def test_suara_sintetis_dibaca_dari_server(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(km, "SUARA_DIR", Path(d)):
                (Path(d) / "0123456789abcdef.m4a").write_bytes(b"x")
                (Path(d) / "0123456789abcdef.json").write_text(json.dumps(
                    {"id": "0123456789abcdef", "durasi": 2.0, "sintetis": True}))
                out = km.siapkan_render([{"posisi": "penutup", "suara": "0123456789abcdef",
                                          "teks": "halo", "tampil_teks": False}], 10)
        self.assertTrue(out[0]["sintetis"])
        self.assertAlmostEqual(out[0]["d"], 2.0 + km.JEDA_EKOR)
        self.assertFalse(out[0]["tampil"])

    def test_id_suara_tidak_bisa_keluar_folder(self):
        self.assertIsNone(km.jalur_suara("../../etc/passwd"))
        self.assertIsNone(km.jalur_suara("ABC"))


class Graf(unittest.TestCase):
    def test_bekukan_menambah_waktu(self):
        items = km.siapkan_render([{"posisi": "pembuka", "teks": "awal sekali"},
                                   {"posisi": "penutup", "teks": "akhir"}], 10)
        inputs, graf, v, a, tambah = km.graf_render(
            items, "[v]", "[a]", input_awal=1, fps=30, out_w=1080, out_h=1920, durasi=10)
        self.assertEqual(inputs, [])
        self.assertAlmostEqual(tambah, sum(k["d"] for k in items))
        self.assertIn("concat=n=3:v=1:a=1", graf)
        self.assertIn("tpad=stop_mode=clone", graf)
        self.assertEqual((v, a), ("[kmV]", "[kmA]"))

    def test_tanpa_komentar_tidak_mengubah_apa_pun(self):
        self.assertEqual(km.graf_render([], "[v]", "[a]", input_awal=0, fps=30,
                                        out_w=1080, out_h=1920, durasi=10),
                         ([], "", "[v]", "[a]", 0.0))

    def test_kartu_satu_drawtext_per_baris(self):
        items = km.siapkan_render([{"posisi": "pembuka",
                                    "teks": "kalimat yang cukup panjang untuk dibungkus jadi beberapa baris di layar"}], 10)
        _, graf, *_ = km.graf_render(items, "[v]", "[a]", input_awal=0, fps=30,
                                     out_w=1080, out_h=1920, durasi=10)
        self.assertGreater(graf.count("drawtext="), 1)
        self.assertNotIn("\\\\n", graf)


class GeserSubtitle(unittest.TestCase):
    def test_subtitle_sesudah_titik_beku_bergeser(self):
        items = [{"t": 0.0, "d": 2.0, "mode": "bekukan"},
                 {"t": 5.0, "d": 3.0, "mode": "bekukan"},
                 {"t": 7.0, "d": 9.0, "mode": "timpa"}]
        subs = [{"start": 1.0, "end": 2.0, "text": "a", "words": [{"w": "a", "s": 1.0, "e": 2.0}]},
                {"start": 6.0, "end": 7.0, "text": "b"}]
        out = km.geser_subtitle(subs, items)
        self.assertEqual((out[0]["start"], out[0]["end"]), (3.0, 4.0))
        self.assertEqual(out[0]["words"][0]["s"], 3.0)
        self.assertEqual((out[1]["start"], out[1]["end"]), (11.0, 12.0))



class FypMengenalPembuka(unittest.TestCase):
    def test_pembuka_bukan_awal_sunyi(self):
        from app.services import fyp
        meta = {"duration": 30, "title": "x",
                "subtitles": [{"start": 6.0, "end": 8.0, "text": "kalimat pertama di klip"}]}
        kode = lambda m: {c["kode"] for c in fyp.periksa(m)["catatan"]}
        self.assertIn("awal_sunyi", kode(meta))
        meta["komentar"] = [{"posisi": "pembuka", "teks": "Ini soal kasbon pertama",
                             "bersuara": True, "kartu": False}]
        self.assertNotIn("awal_sunyi", kode(meta))


if __name__ == "__main__":
    unittest.main()
