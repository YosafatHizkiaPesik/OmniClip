"""
Musik latar yang mengalah saat orang bicara.

Dulu ini dikerjakan `sidechaincompress`, yang menebak dari kerasnya audio utama.
Diukur pada satu klip podcast Raditya Dika: musiknya turun 2 dB, dan turun SAMA
RATA baik saat orang bicara maupun saat jeda — beda antara keduanya 0,5 dB.
Artinya fiturnya menurunkan musik tanpa pernah benar-benar mengalah pada
kalimat, yaitu satu-satunya hal yang seharusnya ia lakukan.

Sebabnya audio podcast sudah diratakan `loudnorm` sebelum sampai ke situ. Di
klip yang sama, jeda dan kata sama-sama berada di -17 dB: tidak ada dinamika
yang bisa dideteksi, jadi tidak ada yang bisa memicu kompresornya.

Waktu tiap kata sudah ada di transkrip, jadi redamannya tidak perlu menebak.
Sesudah diganti, terukur 10,4 dB pada MP4 jadinya.
"""

import unittest

from app.services.render import (
    REDAM_DALAM, REDAM_RENTANG_MAKS, rentang_bicara, rumus_redam,
)


def _baris(teks, mulai, akhir, kata=None):
    return {"start": mulai, "end": akhir, "text": teks,
            "words": [{"w": w, "s": s, "e": e} for w, s, e in (kata or [])]}


class RentangBicara(unittest.TestCase):
    def test_celah_antar_suku_kata_dirapatkan(self):
        """
        Celah antar kata bukan kesunyian.

        Tanpa dirapatkan, musik naik-turun puluhan kali dalam satu kalimat, dan
        itu terdengar lebih buruk daripada musik yang tidak mengalah sama sekali.
        """
        b = _baris("satu dua tiga", 0.0, 1.6,
                   [("satu", 0.0, 0.4), ("dua", 0.5, 0.9), ("tiga", 1.0, 1.6)])
        self.assertEqual(rentang_bicara([b]), [(0.0, 1.6)])

    def test_jeda_panjang_tetap_terpisah(self):
        b1 = _baris("halo", 0.0, 1.0, [("halo", 0.0, 1.0)])
        b2 = _baris("lagi", 5.0, 6.0, [("lagi", 5.0, 6.0)])
        self.assertEqual(rentang_bicara([b1, b2]), [(0.0, 1.0), (5.0, 6.0)])

    def test_tanpa_kata_memakai_waktu_barisnya(self):
        """Transkrip lama tidak menyimpan waktu per kata; barisnya tetap terpakai."""
        self.assertEqual(rentang_bicara([{"start": 2.0, "end": 4.0, "text": "halo"}]),
                         [(2.0, 4.0)])

    def test_tanpa_transkrip_kosong(self):
        self.assertEqual(rentang_bicara(None), [])
        self.assertEqual(rentang_bicara([]), [])
        self.assertEqual(rentang_bicara([_baris("", 1.0, 1.0)]), [])

    def test_rentang_dibatasi(self):
        """Rumus lavfi dinilai tiap bingkai audio, jadi panjangnya ada batas."""
        baris = [_baris("x", i * 3.0, i * 3.0 + 0.5,
                        [("x", i * 3.0, i * 3.0 + 0.5)]) for i in range(80)]
        hasil = rentang_bicara(baris)
        self.assertLessEqual(len(hasil), REDAM_RENTANG_MAKS)
        # Menggabung boleh memperluas rentang, tidak boleh kehilangan ujungnya:
        # kata terakhir harus tetap berada di dalam redaman.
        self.assertLessEqual(hasil[0][0], 0.0)
        self.assertGreaterEqual(hasil[-1][1], 79 * 3.0 + 0.5)


class RumusRedam(unittest.TestCase):
    def _nilai(self, rumus: str, t: float) -> float:
        """Menilai rumus lavfi-nya di Python, dengan arti `clip` dan `max` yang sama."""
        def clip(x, a, b):
            return max(a, min(b, x))
        return eval(rumus, {"clip": clip, "max": max, "t": t})  # noqa: S307

    def test_tanpa_bicara_tidak_ada_rumus(self):
        """Klip permainan tanpa kata jatuh ke jalur lama, bukan ke rumus kosong."""
        self.assertIsNone(rumus_redam([]))

    def test_penuh_saat_jeda_dan_turun_saat_bicara(self):
        r = rumus_redam([(5.0, 8.0)])
        self.assertAlmostEqual(self._nilai(r, 0.0), 1.0, places=6)
        self.assertAlmostEqual(self._nilai(r, 6.5), REDAM_DALAM, places=6)
        self.assertAlmostEqual(self._nilai(r, 20.0), 1.0, places=6)

    def test_turun_sebelum_kata_pertama(self):
        """
        Redaman yang baru mulai turun DI kata pertama membuat kata itu tertimpa
        musik yang masih penuh. Turunnya harus sudah selesai saat kata mulai.
        """
        r = rumus_redam([(5.0, 8.0)])
        self.assertAlmostEqual(self._nilai(r, 5.0), REDAM_DALAM, places=6)
        self.assertGreater(self._nilai(r, 4.9), REDAM_DALAM)

    def test_naik_lagi_sesudah_kata_terakhir(self):
        r = rumus_redam([(5.0, 8.0)])
        self.assertAlmostEqual(self._nilai(r, 8.0), REDAM_DALAM, places=6)
        self.assertGreater(self._nilai(r, 8.2), REDAM_DALAM)
        self.assertAlmostEqual(self._nilai(r, 8.5), 1.0, places=6)

    def test_tidak_pernah_di_luar_batas(self):
        r = rumus_redam([(1.0, 2.0), (2.6, 4.0), (9.0, 12.0)])
        for i in range(0, 1500):
            t = i * 0.01
            v = self._nilai(r, t)
            self.assertGreaterEqual(v, REDAM_DALAM - 1e-9, f"t={t}")
            self.assertLessEqual(v, 1.0 + 1e-9, f"t={t}")

    def test_rentang_berdempet_tidak_menaikkan_musik_di_tengahnya(self):
        """
        Dua kalimat yang hanya terpisah sekejap: musik tidak boleh melompat
        kembali ke penuh di antaranya. `max` yang menjaga ini, bukan jumlah.
        """
        r = rumus_redam([(1.0, 3.0), (3.2, 5.0)])
        self.assertAlmostEqual(self._nilai(r, 3.1), REDAM_DALAM, places=6)


if __name__ == "__main__":
    unittest.main()
