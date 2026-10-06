"""
Kata gumam dibuang dari subtitle.

Dilaporkan pemiliknya 5 Oktober 2026: "saya sering menemukan kata ee h dan lain
lain yang mana saya rasa tidak perlu dimasukkan ke dalam subtitle".

Yang diuji bukan hanya apa yang dibuang, melainkan juga apa yang TIDAK — dan
bahwa membuangnya tidak merusak pemecahan barisnya.
"""

import unittest

from app.services.clipmodel import GUMAM, buang_gumam, words_to_caption_lines


def _kata(*teks, jeda=0.4, panjang=0.35):
    return [{"w": w, "s": round(i * jeda, 3), "e": round(i * jeda + panjang, 3)}
            for i, w in enumerate(teks)]


def _teks(words, **kw):
    return [l["text"] for l in words_to_caption_lines(words, buang_gumam_aktif=True, **kw)]


class YangDibuang(unittest.TestCase):
    def test_bunyi_ragu_hilang(self):
        hasil = buang_gumam(_kata("ee", "halo", "h", "dunia", "mmm"))
        self.assertEqual([w["w"] for w in hasil], ["halo", "dunia"])

    def test_tanda_baca_menempel_ikut_dikenali(self):
        hasil = buang_gumam(_kata("Eh,", "tunggu"))
        self.assertEqual([w["w"] for w in hasil], ["tunggu"])

    def test_huruf_besar_kecil_tidak_penting(self):
        self.assertEqual(buang_gumam(_kata("EE", "Hmm", "oke")), 
                         buang_gumam(_kata("ee", "hmm", "oke")))


class YangSENGAJADipertahankan(unittest.TestCase):
    """
    Semuanya terdengar seperti gumam bagi telinga yang tidak terbiasa, tapi di
    bahasa Indonesia semuanya membawa makna. Membuangnya mengubah kalimat, dan
    subtitle yang berubah artinya jauh lebih buruk daripada subtitle yang memuat
    satu "ee".
    """

    def test_kata_bermakna_tidak_ikut_terbuang(self):
        jaga = ["ah", "oh", "nah", "ya", "lah", "dong", "sih", "kok", "deh",
                "kan", "aja", "gitu", "loh", "nih", "tuh"]
        for w in jaga:
            with self.subTest(kata=w):
                self.assertNotIn(w, GUMAM)
                self.assertEqual([x["w"] for x in buang_gumam(_kata(w))], [w])


class CelahWaktuDitutup(unittest.TestCase):
    """
    `words_to_caption_lines` memecah baris pada JEDA BICARA, dan kata yang
    dibuang meninggalkan lubang waktu yang persis terlihat seperti jeda. Di
    suaranya tidak ada jeda sama sekali — lubangnya justru diisi gumamannya.
    """

    def test_baris_tidak_pecah_di_bekas_gumam(self):
        baris = _teks(_kata("Oh", "ee", "tunggu", "h", "sepuluh", "detik"))
        self.assertEqual(len(baris), 1, baris)
        self.assertEqual(baris[0], "Oh tunggu sepuluh detik")

    def test_gumam_di_awal_tidak_meninggalkan_lubang(self):
        baris = _teks(_kata("ee", "halo", "semua"))
        self.assertEqual(baris, ["halo semua"])

    def test_kata_sebelumnya_dipanjangkan_menutupi_gumam(self):
        hasil = buang_gumam(_kata("halo", "eee"))
        self.assertEqual(len(hasil), 1)
        # Berakhir di akhir gumamnya, bukan di akhir "halo".
        self.assertAlmostEqual(hasil[0]["e"], 0.75, places=3)


class SakelarnyaDihormati(unittest.TestCase):
    def test_dimatikan_berarti_semuanya_tetap(self):
        kata = _kata("ee", "halo")
        baris = [l["text"] for l in words_to_caption_lines(kata, buang_gumam_aktif=False)]
        self.assertIn("ee", " ".join(baris))

    def test_bawaannya_nyala(self):
        from app.services.clipmodel import _gumam_dibuang
        self.assertTrue(_gumam_dibuang())


if __name__ == "__main__":
    unittest.main()
