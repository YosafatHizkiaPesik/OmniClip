"""
Caption dan tagar siap tempel.

Yang dijaga di sini adalah aturan yang datang dari luar kode dan tidak bisa
ditebak dari membacanya: batas lima tagar TikTok, tagar umum yang justru
merugikan, dan judul video sumber yang tidak boleh jadi caption klip.
"""

import unittest

from app.services import keterangan as kt


def meta(teks="Saya beli rumah pertama umur dua puluh tiga tahun. "
              "Uangnya dari jualan jasa desain waktu kuliah dulu.",
         **kv):
    dasar = {
        "title": "Beli rumah umur 23",
        "video_title": "PODCAST LENGKAP - Bincang Bisnis Anak Muda",
        "channel": "Bincang Bisnis",
        "duration": 58.0,
        "subtitles": [{"start": 0.0, "end": 5.0, "text": teks}],
    }
    return {**dasar, **kv}


class Tagar(unittest.TestCase):
    def test_tagar_umum_dibuang(self):
        # Tidak menaikkan apa pun, dan membuat unggahan terlihat spam.
        hasil = kt._bersih_tagar(["#fyp", "#viral", "#foryou", "#trending", "#properti"],
                                 maks=5)
        self.assertEqual(hasil, ["#properti"])

    def test_tagar_kembar_hanya_sekali(self):
        hasil = kt._bersih_tagar(["#Properti", "properti", "#PROPERTI", "#kpr"], maks=5)
        self.assertEqual(hasil, ["#properti", "#kpr"])

    def test_batas_keras_dihormati(self):
        banyak = [f"#topik{i}" for i in range(20)]
        self.assertEqual(len(kt._bersih_tagar(banyak, maks=5)), 5)
        self.assertEqual(len(kt._bersih_tagar(banyak, maks=3)), 3)

    def test_shorts_hanya_bila_diminta(self):
        # #shorts bukan tagar populer yang ditempel asal: ia menempatkan video
        # di rak Shorts. Tapi hanya di YouTube.
        self.assertIn("#shorts", kt._bersih_tagar(["#a"], maks=3, sertakan_shorts=True))
        self.assertNotIn("#shorts", kt._bersih_tagar(["#a"], maks=3))

    def test_tagar_tanpa_huruf_dibuang(self):
        self.assertEqual(kt._bersih_tagar(["#", "##", "#a", "#!!"], maks=5), [])


class BatasPlatform(unittest.TestCase):
    def test_tiktok_lima_tagar(self):
        # Batas keras sejak Agustus 2025; melebihinya ditolak TikTok.
        self.assertEqual(kt.PLATFORM["tiktok"]["maks_tagar"], 5)

    def test_tiap_platform_punya_alamat_unggah_dan_catatan(self):
        for nama, p in kt.PLATFORM.items():
            self.assertTrue(p["unggah"].startswith("https://"), nama)
            self.assertTrue(p["catatan"], nama)
            self.assertGreaterEqual(p["maks_tagar"], 3, nama)

    def test_hanya_youtube_yang_punya_judul_terpisah(self):
        terpisah = [n for n, p in kt.PLATFORM.items() if p.get("judul_terpisah")]
        self.assertEqual(terpisah, ["shorts"])


class Perakitan(unittest.TestCase):
    INTI = {"hook": "Beli rumah umur 23 dari jualan jasa desain",
            "konteks": "Ceritanya dimulai waktu masih kuliah dan belum punya modal.",
            "tagar": ["#properti", "#kpr", "#bisnisanakmuda", "#freelance",
                      "#desaingrafis", "#fyp", "#viral"]}

    def test_caption_tiga_bagian_berurutan(self):
        p = kt._rakit(self.INTI, meta(), "tiktok")
        baris = p["caption"].split("\n\n")
        self.assertEqual(len(baris), 3)
        self.assertEqual(baris[0], self.INTI["hook"])
        self.assertEqual(baris[1], self.INTI["konteks"])
        self.assertTrue(baris[2].startswith("#"))

    def test_tagar_umum_tidak_lolos_ke_caption(self):
        p = kt._rakit(self.INTI, meta(), "tiktok")
        self.assertNotIn("#fyp", p["caption"])
        self.assertNotIn("#viral", p["caption"])
        self.assertEqual(len(p["tagar"]), 5)

    def test_youtube_mendapat_judul_dari_hooknya(self):
        p = kt._rakit(self.INTI, meta(), "shorts")
        self.assertEqual(p["judul"], self.INTI["hook"])
        self.assertLessEqual(len(p["judul"]), kt.PLATFORM["shorts"]["maks_judul"])
        self.assertIn("#shorts", p["tagar"])

    def test_konteks_yang_mengulang_hook_dibuang(self):
        inti = {**self.INTI, "konteks": self.INTI["hook"]}
        p = kt._rakit(inti, meta(), "tiktok")
        self.assertEqual(p["caption"].count(self.INTI["hook"]), 1)

    def test_klip_panjang_tidak_dapat_shorts(self):
        p = kt._rakit(self.INTI, meta(duration=400.0), "shorts")
        self.assertNotIn("#shorts", p["tagar"])


class TanpaAI(unittest.TestCase):
    def test_judul_video_sumber_tidak_jadi_hook(self):
        # Inilah keluhannya: caption klip yang isinya judul video aslinya.
        m = meta(title="PODCAST LENGKAP - Bincang Bisnis Anak Muda")
        hasil = kt._lokal(m)
        self.assertNotEqual(hasil["hook"].lower(), m["video_title"].lower())
        self.assertTrue(hasil["hook"])

    def test_judul_klip_sendiri_tetap_dipakai(self):
        hasil = kt._lokal(meta())
        self.assertEqual(hasil["hook"], "Beli rumah umur 23")

    def test_gumaman_tidak_ikut(self):
        m = meta("Ee jadi gini, anu, saya mulai jualan jasa desain waktu kuliah.",
                 title="")
        hasil = kt._lokal(m)
        self.assertNotIn(" ee ", f" {hasil['hook'].lower()} ")
        self.assertNotIn("anu", hasil["hook"].lower())

    def test_paket_tanpa_kunci_tetap_lengkap(self):
        hasil = kt.paket(meta(), pakai_ai=False)
        self.assertEqual(hasil["sumber"], "lokal")
        self.assertEqual(len(hasil["platform"]), len(kt.PLATFORM))
        for p in hasil["platform"]:
            self.assertTrue(p["caption"].strip(), p["label"])


class Potong(unittest.TestCase):
    def test_tidak_memotong_di_tengah_kata(self):
        teks = "satu dua tiga empat lima enam tujuh delapan"
        hasil = kt._potong(teks, 20)
        self.assertLessEqual(len(hasil), 20)
        self.assertTrue(teks.startswith(hasil))
        self.assertFalse(hasil.endswith(" "))
        # Yang tersisa harus kata utuh.
        self.assertIn(hasil.split()[-1], teks.split())

    def test_teks_pendek_tidak_disentuh(self):
        self.assertEqual(kt._potong("halo dunia", 50), "halo dunia")


if __name__ == "__main__":
    unittest.main()
