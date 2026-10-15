"""Topik resmi YouTube, tautan situs lain, alasan Gemini, id channel (15 Oktober 2026)."""
import unittest
from unittest import mock

from app.services import beranda


class TopikResmi(unittest.TestCase):
    def test_tanpa_kunci_jatuh_ke_cadangan(self):
        with mock.patch("app.services.statistik.kunci_api", return_value=""), \
             mock.patch.object(beranda, "_minta") as minta:
            self.assertIsNone(beranda.topik("gaming", "US", 20))
            minta.assert_not_called()

    def test_kategori_dan_negara_diteruskan(self):
        kartu = [{"id": f"v{i}", "title": "x", "channel": "c"} for i in range(3)]
        with mock.patch("app.repos.cache.ambil", return_value=None), \
             mock.patch("app.repos.cache.simpan"), \
             mock.patch.object(beranda, "_minta", return_value=(kartu, None)) as minta:
            hasil = beranda.topik("gaming", "gb", 20, kunci="k")
        self.assertEqual(len(hasil), 3)
        args = minta.call_args[0]
        self.assertEqual(args[1], "20")
        self.assertEqual(args[3], "GB")
        self.assertEqual(minta.call_args[1]["buang_musik"], True)

    def test_topik_musik_tidak_membuang_musik(self):
        with mock.patch("app.repos.cache.ambil", return_value=None), \
             mock.patch("app.repos.cache.simpan"), \
             mock.patch.object(beranda, "_minta", return_value=([], None)) as minta:
            beranda.topik("musik", "ID", 20, kunci="k")
        self.assertEqual(minta.call_args[1]["buang_musik"], False)

    def test_wilayah_tidak_sah_jadi_id(self):
        self.assertEqual(beranda.wilayah_sah("x1"), "ID")
        self.assertEqual(beranda.wilayah_sah("us"), "US")

    def test_topik_tidak_memakai_kategori_yang_ditolak_youtube(self):
        # Pendidikan (27) dan Wisata (19) menjawab 404 untuk chart mostPopular.
        self.assertNotIn("27", beranda.TOPIK.values())
        self.assertNotIn("19", beranda.TOPIK.values())


class PencarianTanpaCookies(unittest.TestCase):
    def test_pencarian_tidak_memasang_cookies(self):
        from app.services import ytdlp
        with mock.patch.object(ytdlp.cookies_svc, "terapkan") as pasang:
            ytdlp._base_opts(cookies=False)
            pasang.assert_not_called()
            ytdlp._base_opts()
            pasang.assert_called_once()


class AlasanGemini(unittest.TestCase):
    def test_alasan_dibedakan(self):
        from app.services.pipeline import alasan_gemini
        kuota = "429 RESOURCE_EXHAUSTED. You exceeded your current quota"
        tolak = "403 PERMISSION_DENIED. Your project has been denied access."
        self.assertEqual(alasan_gemini([kuota]), "Kuota harian Gemini habis")
        self.assertEqual(alasan_gemini([tolak]), "Kunci Gemini ditolak Google (proyeknya diblokir)")
        self.assertEqual(alasan_gemini([kuota, tolak]),
                         "Kuota Gemini habis dan kunci lainnya ditolak Google")
        self.assertEqual(alasan_gemini(["503 UNAVAILABLE"]), "Gemini sedang sibuk atau tidak menjawab")
        self.assertEqual(alasan_gemini(["entah"]), "Gemini gagal")


class Tautan(unittest.TestCase):
    def test_tautan_youtube_dikenali(self):
        from app.services.ytdlp import adalah_tautan_youtube
        self.assertTrue(adalah_tautan_youtube("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(adalah_tautan_youtube("https://youtu.be/abc"))
        self.assertFalse(adalah_tautan_youtube("https://www.tiktok.com/@a/video/1"))


class IdChannel(unittest.TestCase):
    def test_kartu_tanpa_id_diisi_dari_kartu_sejenis_dan_kolaborasi(self):
        from app.routers import videos
        daftar = [
            {"id": "a", "channel": "Windah Basudara", "channel_id": "UCw"},
            {"id": "b", "channel": "Windah Basudara", "channel_id": None},
            {"id": "c", "channel": "Windah Basudara and Glen", "channel_id": ""},
        ]
        with mock.patch.object(videos.cache_repo, "ambil", return_value=None):
            videos._lengkapi_kanal(daftar)
        self.assertEqual([v["channel_id"] for v in daftar], ["UCw", "UCw", "UCw"])


if __name__ == "__main__":
    unittest.main()
