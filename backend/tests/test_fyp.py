"""
Daftar periksa sebelum unggah.

Diminta pemiliknya 5 Oktober 2026 sesudah mengunggah banyak video dan hanya
satu-dua yang ditonton: "racikkan formula video konten saya agar tembus fyp".

Yang diuji di sini termasuk hal yang TIDAK dijanjikan. Tidak ada yang bisa
menjamin FYP, dan menjual jaminan itu kepada orang yang memakainya untuk
mencari nafkah adalah hal paling buruk yang bisa dilakukan berkas ini. Jadi
jawabannya harus mengatakan dirinya daftar periksa, bukan ramalan.
"""

import unittest

from app.services.fyp import periksa


def _klip(**ubah):
    dasar = {
        "duration": 25.0,
        "title": "Momen paling sial di Minecraft",
        "hashtags": ["#minecraft", "#gaming", "#fyp"],
        "hook_text": "Dia nggak nyangka ini bakal kejadian",
        "subtitles": [
            {"start": 0.2, "end": 6.0, "text": "Ini kenapa bisa begini sih?"},
            {"start": 6.0, "end": 14.0, "text": "Gue beneran nggak nyangka."},
            {"start": 14.0, "end": 24.0, "text": "Lihat bagian ini pelan-pelan."},
        ],
    }
    dasar.update(ubah)
    return dasar


def _judul(hasil):
    return " | ".join(c["judul"] for c in hasil["catatan"])


class KlipYangSehat(unittest.TestCase):
    def test_klip_wajar_skornya_tinggi(self):
        h = periksa(_klip())
        self.assertGreaterEqual(h["skor"], 85, _judul(h))

    def test_jawabannya_mengaku_bukan_ramalan(self):
        h = periksa(_klip())
        self.assertIn("bukan ramalan", h["catatan_kaki"].lower())
        self.assertIn("tidak ada yang bisa menjamin", h["catatan_kaki"].lower())


class YangDitandai(unittest.TestCase):
    def test_terlalu_pendek(self):
        self.assertIn("pendek", _judul(periksa(_klip(duration=5.0))).lower())

    def test_terlalu_panjang(self):
        self.assertIn("panjang", _judul(periksa(_klip(duration=150.0))).lower())

    def test_tiga_detik_pertama_sunyi(self):
        h = periksa(_klip(subtitles=[
            {"start": 5.0, "end": 12.0, "text": "Baru mulai bicara di sini."}]))
        self.assertIn("tiga detik pertama", _judul(h).lower())

    def test_dibuka_dengan_sapaan(self):
        h = periksa(_klip(subtitles=[
            {"start": 0.1, "end": 6.0, "text": "Halo semuanya balik lagi di channel gue"},
            {"start": 6.0, "end": 24.0, "text": "Oke jadi hari ini kita main."}]))
        self.assertIn("basa-basi", _judul(h).lower())

    def test_tanpa_subtitle(self):
        h = periksa(_klip(subtitles=[]))
        self.assertIn("subtitle", _judul(h).lower())

    def test_subtitle_jarang(self):
        h = periksa(_klip(subtitles=[{"start": 0.2, "end": 3.0, "text": "Sebentar saja."}]))
        self.assertIn("bertulisan", _judul(h).lower())

    def test_hook_kepanjangan(self):
        h = periksa(_klip(hook_text="ini adalah momen yang sangat sangat tidak "
                                    "pernah saya duga akan terjadi pada hari ini"))
        self.assertIn("hook", _judul(h).lower())

    def test_tagar_kurang(self):
        self.assertIn("tagar", _judul(periksa(_klip(hashtags=["#satu"]))).lower())

    def test_tanpa_judul(self):
        self.assertIn("judul", _judul(periksa(_klip(title=""))).lower())


class TiapCatatanBisaDikerjakan(unittest.TestCase):
    def test_semua_catatan_punya_saran(self):
        """
        Catatan tanpa saran hanya membuat orang merasa salah tanpa tahu apa yang
        harus diubah.
        """
        h = periksa(_klip(duration=200.0, subtitles=[], title="", hashtags=[]))
        self.assertTrue(h["catatan"])
        for c in h["catatan"]:
            with self.subTest(judul=c["judul"]):
                self.assertTrue(c["saran"].strip())
                self.assertIn(c["berat"], ("berat", "sedang", "ringan"))

    def test_skor_tidak_pernah_negatif(self):
        h = periksa({"duration": 300.0})
        self.assertGreaterEqual(h["skor"], 0)

    def test_klip_kosong_tidak_melempar(self):
        self.assertIsInstance(periksa({})["skor"], int)


if __name__ == "__main__":
    unittest.main()
