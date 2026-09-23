"""
Penyusun teks dan subtitle — bagian yang paling sering rusak diam-diam.

Kenapa justru di sini: cacat pada penyusun subtitle tidak pernah melempar
galat. Ia menghasilkan berkas yang sah, render yang berhasil, dan video yang
baru terlihat salah ketika ditonton — sesudah beberapa menit encode. Dua
cacat sungguhan yang pernah terjadi dan dijaga di berkas ini: kata Jepang
disambung dengan spasi ("あ ぁ 白"), dan dua baris takarir yang waktunya
tumpang tindih digambar bertumpuk di layar.

Dijalankan tanpa memasang apa pun:
    cd backend && ./venv/bin/python -m unittest discover -s tests
"""

import unittest

from app.services.subtitles import _tanpa_tumpang, ke_srt
from app.services.teks import (bobot_kata, cjk, lebar_teks, patah_teks, pecah,
                               sambung, titik_patah)


class TeksCJK(unittest.TestCase):
    def test_spasi_hanya_di_antara_huruf_latin(self):
        self.assertEqual(sambung(["halo", "dunia"]), "halo dunia")
        # Yang membuat subtitle anime terbaca seperti mesin rusak.
        self.assertEqual(sambung(["天", "井", "に"]), "天井に")
        # Batas antara keduanya: spasi hanya hilang bila KEDUA sisinya CJK.
        # Kalimat campuran tetap punya spasi, supaya "Cek 天井 mix" tidak
        # menempel jadi satu kata.
        self.assertEqual(sambung(["天", "OK"]), "天 OK")
        self.assertEqual(sambung(pecah("Cek 天井 mix")), "Cek 天井 mix")

    def test_pecah_kebalikan_dari_sambung(self):
        for teks in ("halo dunia apa kabar", "天井にいたら", "Cek 天井 mix"):
            self.assertEqual(sambung(pecah(teks)), teks.replace(" ", " "))

    def test_pecah_memisah_cjk_per_huruf(self):
        self.assertEqual(pecah("天井に"), ["天", "井", "に"])
        self.assertEqual(pecah("halo dunia"), ["halo", "dunia"])

    def test_huruf_cjk_selebar_dua(self):
        self.assertEqual(lebar_teks(["ab"]), 2)
        self.assertEqual(lebar_teks(["天"]), 2)

    def test_bobot_kata_cjk_sepertiga(self):
        # Tanpa ini, batas "lima kata" jadi baris lima huruf yang berkedip.
        self.assertAlmostEqual(bobot_kata(["天", "井", "に"]), 1.0, places=6)
        self.assertEqual(bobot_kata(["halo", "dunia"]), 2.0)

    def test_cjk_mengenali_kana_dan_han(self):
        self.assertTrue(cjk("天"))
        self.assertTrue(cjk("ハ"))
        self.assertFalse(cjk("a"))
        self.assertFalse(cjk(""))

    def test_patahan_hanya_untuk_teks_tanpa_spasi(self):
        # libass membungkus sendiri teks berspasi; yang tidak berspasi meluber.
        self.assertEqual(titik_patah(list("halo dunia"), 5), frozenset())
        self.assertTrue(titik_patah(list("天井にいたらどのくらい"), 4))

    def test_patah_teks_menyisipkan_ganti_baris_ass(self):
        hasil = patah_teks("天井にいたらどのくらい", 4)
        self.assertIn("\\N", hasil)
        # Isi tetap utuh: yang ditambahkan hanya penanda baris.
        self.assertEqual(hasil.replace("\\N", ""), "天井にいたらどのくらい")


class BarisTakarir(unittest.TestCase):
    def test_baris_tidak_saling_menimpa(self):
        lines = [{"start": 0.0, "end": 3.0, "text": "satu"},
                 {"start": 1.5, "end": 4.0, "text": "dua"}]
        hasil = _tanpa_tumpang(lines)
        self.assertLessEqual(hasil[0]["end"], hasil[1]["start"])

    def test_baris_yang_tidak_bertumpuk_tidak_disentuh(self):
        lines = [{"start": 0.0, "end": 1.0, "text": "satu"},
                 {"start": 2.0, "end": 3.0, "text": "dua"}]
        self.assertEqual([l["end"] for l in _tanpa_tumpang(lines)], [1.0, 3.0])

    def test_kata_yang_jatuh_sesudah_batas_dibuang(self):
        lines = [
            {"start": 0.0, "end": 3.0, "text": "satu dua tiga",
             "words": [{"w": "satu", "s": 0.0, "e": 0.5},
                       {"w": "dua", "s": 1.0, "e": 1.4},
                       {"w": "tiga", "s": 2.4, "e": 2.9}]},
            {"start": 2.0, "end": 4.0, "text": "empat"},
        ]
        hasil = _tanpa_tumpang(lines)
        self.assertEqual(hasil[0]["end"], 2.0)
        self.assertNotIn("tiga", hasil[0]["text"])


class Srt(unittest.TestCase):
    def test_bentuk_berkas_srt(self):
        isi = ke_srt([{"start": 1.5, "end": 2.25, "text": "Halo"}])
        self.assertIn("00:00:01,500 --> 00:00:02,250", isi)
        self.assertTrue(isi.startswith("1\n"))
        self.assertIn("Halo", isi)

    def test_baris_kosong_dilewati(self):
        self.assertEqual(ke_srt([{"start": 0.0, "end": 1.0, "text": "   "}]).strip(), "")

    def test_penomoran_berurutan_tanpa_bolong(self):
        lines = [{"start": i, "end": i + 0.5, "text": f"baris {i}"} for i in range(3)]
        nomor = [b for b in ke_srt(lines).splitlines() if b.strip().isdigit()]
        self.assertEqual(nomor, ["1", "2", "3"])

    def test_waktu_tidak_pernah_mundur(self):
        # Pembulatan milidetik pernah menghasilkan ",1000".
        isi = ke_srt([{"start": 0.9999, "end": 1.9999, "text": "x"}])
        self.assertNotIn(",1000", isi)


if __name__ == "__main__":
    unittest.main()
