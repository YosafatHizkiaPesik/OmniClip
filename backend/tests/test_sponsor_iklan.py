"""Segmen bacaan sponsor tidak boleh jadi klip unggulan mesin lokal."""

import unittest

from app.services import heuristics as H


def kal(teks_list, durasi=4.0):
    out, t, w = [], 0.0, 0
    for teks in teks_list:
        n = len(teks.split())
        out.append({"s": t, "e": t + durasi - 0.2, "text": teks, "wi": (w, w + n)})
        t += durasi
        w += n
    return out


class Pola(unittest.TestCase):
    def test_mengenali_bacaan_sponsor(self):
        for t in ["Video ini disponsori oleh aplikasi X", "pakai kode RAKA untuk diskon",
                  "link nya ada di deskripsi ya", "This episode is sponsored by Y",
                  "use code DIARY at checkout", "today's sponsor is Z"]:
            self.assertTrue(H.SPONSOR_POLA.search(t), t)

    def test_obrolan_biasa_tidak_kena(self):
        for t in ["kode etik dokter itu penting", "gue sponsorin lo makan dong",
                  "link up sama temen kampus"]:
            self.assertFalse(H.SPONSOR_POLA.search(t), t)


class Skor(unittest.TestCase):
    def test_kandidat_sponsor_dipotong(self):
        isi = ["kenapa harga rumah naik terus padahal gaji tetap", "karena bunga bank turun dan orang berutang",
               "akhirnya semua orang berebut aset yang sama", "itulah gelembung yang saya lihat dulu"] * 3
        iklan = ["video ini disponsori oleh aplikasi investasi", "pakai kode RAY untuk bonus",
                 "link nya ada di deskripsi", "download aplikasi sekarang juga"] * 3
        c = H.generate_candidates(kal(isi + iklan), [], duration=96.0, max_out=10, dur_min=10, dur_max=40)
        self.assertTrue(c)
        terbaik = max(c, key=lambda x: x.score)
        self.assertLess(terbaik.start, 48.0)
        self.assertTrue(any(x.breakdown.get("iklan") for x in c if x.start >= 48))


if __name__ == "__main__":
    unittest.main()
