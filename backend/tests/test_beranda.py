"""
Isi beranda: saringan mutunya, dan cara dua sumber disusun jadi satu daftar.

Diuji di sini karena dua keluhan pemiliknya lahir dari berkas ini: beranda yang
isinya tidak layak diklip (vlog 23 detik, 3 tayangan), dan beranda yang tidak
pernah selesai memuat. Yang kedua cacat saya sendiri: putaran penyusunnya bisa
berputar tanpa memasang apa pun saat salah satu sumber habis lebih dulu, dan
karena ia berjalan di gelung peristiwa, SELURUH server ikut berhenti menjawab.
Uji `test_sumber_habis_tidak_menggantung` ada supaya itu tidak terulang.

Jaringan tidak disentuh.
"""

import unittest
from unittest import mock

from app.services import beranda


def _v(i, *, views=50_000, durasi=600, kanal=None, sebab="cari"):
    return {"id": f"v{i}", "title": f"Video {i}", "views": views,
            "duration": durasi, "channel": kanal or f"kanal{i}", "sebab": sebab}


class Saringan(unittest.TestCase):
    def test_video_pendek_selalu_dibuang(self):
        pendek = _v(1, durasi=23, views=3)
        self.assertFalse(beranda.layak(pendek, 0))
        # Bahkan saat ambang tayangan sudah longgar sepenuhnya.
        self.assertEqual(beranda.saring([pendek], cukup=10), [])

    def test_siaran_berjam_jam_dibuang(self):
        self.assertFalse(beranda.layak(_v(1, durasi=9 * 3600), 0))

    def test_ambang_mengalah_sebelum_beranda_kosong(self):
        sepi = [_v(i, views=300) for i in range(5)]
        # Ambang paling ketat tidak meloloskan satu pun, tapi hasilnya tidak
        # boleh kosong: lebih baik video yang kurang ramai daripada layar kosong.
        self.assertEqual(len(beranda.saring(sepi, cukup=5)), 5)

    def test_yang_ramai_tetap_disaring_lebih_dulu(self):
        campur = [_v(i, views=50_000) for i in range(10)] + [_v(99, views=5)]
        lolos = beranda.saring(campur, cukup=5)
        self.assertEqual(len(lolos), 10)
        self.assertNotIn("v99", [v["id"] for v in lolos])


class Penyusun(unittest.TestCase):
    def test_ramai_disisipkan_di_antara_hasil_cari(self):
        ramai = [_v(f"r{i}", sebab="ramai") for i in range(5)]
        cari = [_v(f"c{i}") for i in range(20)]
        hasil = beranda.gabung(ramai, cari, want=12)
        self.assertEqual(len(hasil), 12)
        sebab = [v["sebab"] for v in hasil]
        self.assertEqual(sebab[0], "cari")
        self.assertEqual(sebab[1], "ramai")
        # Sepertiga dari daftar, bukan separuh: yang dicari sendiri tetap isi
        # utamanya.
        self.assertEqual(sebab.count("ramai"), 4)

    def test_sumber_habis_tidak_menggantung(self):
        # Ramai habis lebih dulu, lalu cari habis lebih dulu. Keduanya harus
        # selesai, bukan berputar selamanya.
        self.assertEqual(len(beranda.gabung([_v("r0", sebab="ramai")],
                                            [_v(f"c{i}") for i in range(9)],
                                            want=50)), 10)
        self.assertEqual(len(beranda.gabung([_v(f"r{i}", sebab="ramai")
                                             for i in range(9)],
                                            [_v("c0")], want=50)), 10)
        self.assertEqual(beranda.gabung([], [], want=20), [])

    def test_satu_kanal_tidak_memenuhi_layar(self):
        banyak = [_v(i, kanal="kanal yang sama") for i in range(20)]
        self.assertEqual(len(beranda.gabung([], banyak, want=20)), 3)

    def test_video_yang_sama_dari_dua_sumber_hanya_sekali(self):
        sama = _v(1, sebab="ramai")
        hasil = beranda.gabung([sama], [dict(sama, sebab="cari")], want=10)
        self.assertEqual(len(hasil), 1)


class DaftarRamai(unittest.TestCase):
    def test_tanpa_kunci_tidak_menyentuh_jaringan(self):
        with mock.patch("app.services.statistik.kunci_api", return_value=""), \
             mock.patch.object(beranda, "_minta") as minta:
            self.assertEqual(beranda.ramai(), [])
            minta.assert_not_called()

    def test_klip_musik_dan_siaran_langsung_tidak_ikut(self):
        self.assertIsNone(beranda._kartu({
            "id": "a", "snippet": {"categoryId": "10", "title": "Lagu"},
            "contentDetails": {"duration": "PT4M"}}))
        self.assertIsNone(beranda._kartu({
            "id": "b", "snippet": {"categoryId": "20", "title": "Live",
                                   "liveBroadcastContent": "live"},
            "contentDetails": {"duration": "PT9H"}}))

    def test_bentuk_kartu_sama_dengan_hasil_pencarian(self):
        k = beranda._kartu({
            "id": "abc", "snippet": {"categoryId": "20", "title": "Main game",
                                     "channelTitle": "Kanal",
                                     "publishedAt": "2026-10-05T10:00:00Z",
                                     "thumbnails": {"high": {"url": "http://x/y.jpg"}}},
            "statistics": {"viewCount": "12345"},
            "contentDetails": {"duration": "PT1H2M3S"}})
        self.assertEqual(k["duration"], 3723)
        self.assertEqual(k["views"], 12345)
        self.assertEqual(k["upload_date"], "20261005")
        self.assertEqual(k["sebab"], "ramai")
        self.assertEqual(k["url"], "https://www.youtube.com/watch?v=abc")


if __name__ == "__main__":
    unittest.main()


class UrutDekat(unittest.TestCase):
    """
    Daftar ramai didahulukan yang dekat dengan yang dicari, tanpa membuang.

    Pemiliknya mengklip podcast dan permainan; daftar populer Indonesia tiap
    hari juga berisi hal lain. Yang tidak nyambung turun, bukan hilang.
    """

    def test_yang_nyambung_naik_yang_lain_tetap_ada(self):
        videos = [
            {"title": "Trailer sinetron episode 183", "channel": "MNC"},
            {"title": "Podcast ngobrol santai bareng gamer", "channel": "Kanal"},
            {"title": "Lagu daerah", "channel": "Topic"},
        ]
        hasil = beranda.urut_dekat(videos, ["podcast indonesia", "gameplay horor"])
        self.assertEqual(hasil[0]["title"], "Podcast ngobrol santai bareng gamer")
        self.assertEqual(len(hasil), 3)

    def test_tanpa_minat_urutannya_tidak_diubah(self):
        videos = [{"title": "A", "channel": "x"}, {"title": "B", "channel": "y"}]
        self.assertEqual([v["title"] for v in beranda.urut_dekat(videos, [])],
                         ["A", "B"])


class TanpaMusik(unittest.TestCase):
    """
    Video musik tidak bisa diklip aplikasi yang mencari orang berbicara.

    Kategori Musik sudah dibuang di sisi daftar ramai, tapi klip musik dan
    kompilasi lagu sering diunggah ke kategori Hiburan, dan pencarian pun
    membawanya. Terlihat pada beranda sungguhan: "Best of Gibran Alcocer
    (Beautiful Piano Mix)" dan "Tipe-x - Kumpulan Lagu-lagu Pilihan".
    """

    def test_ciri_musik_dibuang_dari_kedua_sumber(self):
        for judul in ("Lagu Baru (Official Music Video)",
                      "Kumpulan Lagu-lagu Pilihan Terbaik",
                      "Beautiful Piano Mix", "Judul Lagu | Lirik"):
            self.assertFalse(beranda.layak(
                {"title": judul, "duration": 900, "views": 10_000_000,
                 "channel": "Kanal"}, 0), judul)

    def test_kanal_topic_buatan_youtube_dibuang(self):
        self.assertFalse(beranda.layak(
            {"title": "Apa saja", "duration": 900, "views": 500_000,
             "channel": "Sadewok - Topic"}, 0))

    def test_podcast_dengan_kata_cover_tetap_lolos_bila_bukan_kata_utuh(self):
        self.assertTrue(beranda.layak(
            {"title": "Ngobrol soal undercover journalism", "duration": 1800,
             "views": 50_000, "channel": "Kanal"}, 0))
