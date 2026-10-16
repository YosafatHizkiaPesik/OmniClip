"""Bahasa teks AI (JOB-3 J3-12) dan pengaman terjemahan respons."""
import unittest
from unittest import mock

from app import bahasa
from app.services import bahasa_ai, tts


class BahasaAi(unittest.TestCase):
    def _setelan(self, nilai):
        return mock.patch("app.repos.profil.setelan", return_value={"bahasa_ai": nilai} if nilai else {})

    def test_ikut_antarmuka(self):
        token = bahasa.setel("en")
        try:
            with self._setelan(None):
                self.assertEqual(bahasa_ai.kode(), "en")
        finally:
            bahasa.pulihkan(token)
        with self._setelan(None):
            self.assertEqual(bahasa_ai.kode(), "id")

    def test_pilihan_tetap_menang(self):
        token = bahasa.setel("en")
        try:
            with self._setelan("id"):
                self.assertEqual(bahasa_ai.kode(), "id")
        finally:
            bahasa.pulihkan(token)

    def test_ikut_video(self):
        with self._setelan("video"):
            self.assertEqual(bahasa_ai.kode(video_lang="en-US"), "en")
            self.assertEqual(bahasa_ai.kode(video_lang="id"), "id")
            # Bahasa video lain: jatuh ke bahasa antarmuka.
            self.assertEqual(bahasa_ai.kode(video_lang="ja"), "id")

    def test_sistem_inggris_mengganti_patokan_bahasa(self):
        teks = "Anda editor video berbahasa Indonesia. reason dalam bahasa Indonesia."
        hasil = bahasa_ai.sistem(teks, "en")
        self.assertNotIn("bahasa Indonesia", hasil)
        self.assertIn("BAHASA KELUARAN", hasil)
        self.assertEqual(bahasa_ai.sistem(teks, "id"), teks)


class SuaraBawaan(unittest.TestCase):
    def test_teks_inggris_dibacakan_suara_inggris(self):
        self.assertEqual(tts.bahasa_teks("This is the moment that changed everything for him"), "en")
        self.assertEqual(tts.bahasa_teks("Ini momen yang mengubah segalanya buat dia"), "id")
        with mock.patch.object(tts, "edge_available", return_value=True):
            self.assertEqual(tts.suara_bawaan("What do you think about this, is it true?"),
                             tts.DEFAULT_VOICE_EN)
            self.assertEqual(tts.suara_bawaan("Menurut kalian gimana, setuju nggak?"),
                             tts.DEFAULT_VOICE)


class IsiPenggunaTidakDiterjemahkan(unittest.TestCase):
    def test_kata_transkrip_aman(self):
        data = {"subtitles": [{"text": "belum"}], "words": [{"w": "belum"}],
                "title": "belum", "message": "belum"}
        hasil = bahasa.terjemahkan(data, "en")
        self.assertEqual(hasil["subtitles"][0]["text"], "belum")
        self.assertEqual(hasil["words"][0]["w"], "belum")
        self.assertEqual(hasil["title"], "belum")
        self.assertEqual(hasil["message"], "not yet")

    def test_pesan_gabungan(self):
        s = ("22 klip siap ditinjau (dengan terjemahan), Kuota harian Gemini habis, "
             "jadi dipilih mesin lokal. Coba lagi nanti.")
        self.assertEqual(bahasa.teks(s, "en"),
                         "22 clips ready for review (with translation), The daily Gemini quota "
                         "is used up, so the local engine picked them. Try again later.")


if __name__ == "__main__":
    unittest.main()


class SisipanPenuturAsing(unittest.TestCase):
    def test_kalimat_penutur_jarang_ditandai(self):
        from app.services.heuristics import _asing_kumulatif
        words = [{"w": "a", "sp": 0}] * 300 + [{"w": "b", "sp": 1}] * 300 + [{"w": "c", "sp": 2}] * 20
        sentences = [{"wi": (0, 300)}, {"wi": (300, 600)}, {"wi": (600, 620)}]
        self.assertEqual(_asing_kumulatif(sentences, words), [0, 0, 0, 1])

    def test_tanpa_label_tidak_ada_yang_asing(self):
        from app.services.heuristics import _asing_kumulatif
        self.assertEqual(_asing_kumulatif([{"wi": (0, 2)}], [{"w": "a"}, {"w": "b"}]), [])
