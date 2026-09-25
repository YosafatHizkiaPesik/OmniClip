"""
Merapatkan klip: yang dibuang harus jeda, bukan isi.

Yang dijaga di sini adalah dua kesalahan yang sudah pernah terjadi sungguhan:
membuang 40 detik dari klip gameplay karena bagian tanpa kata dianggap bagian
tanpa isi, dan memotong tepat di batas kata sehingga huruf pertamanya hilang.
"""

import unittest

from app.services import rapat

from app.services.rapat import (BANTALAN, GUMAMAN, _iris_sunyi, _potongan_segmen,
                                rapatkan, ringkas)


def kata(*pasangan):
    return [{"w": w, "s": s, "e": e} for w, s, e in pasangan]


class PotonganSegmen(unittest.TestCase):
    def test_jeda_panjang_dipotong_dengan_bantalan(self):
        k = kata(("satu", 0.0, 0.5), ("dua", 3.0, 3.5))
        (a, b, jenis), = _potongan_segmen(0.0, 4.0, k, jeda_min=0.5, gumaman=False)
        self.assertEqual(jenis, "jeda")
        # Bantalan di kedua sisi: memotong tepat di batas kata memakan hurufnya.
        self.assertAlmostEqual(a, 0.5 + BANTALAN, places=6)
        self.assertAlmostEqual(b, 3.0 - BANTALAN, places=6)

    def test_jeda_pendek_dibiarkan(self):
        k = kata(("satu", 0.0, 0.5), ("dua", 0.8, 1.2))
        self.assertEqual(_potongan_segmen(0.0, 1.5, k, jeda_min=0.5, gumaman=False), [])

    def test_diam_di_ujung_dipangkas(self):
        k = kata(("satu", 2.0, 2.5))
        jenis = {j for _a, _b, j in _potongan_segmen(0.0, 5.0, k, jeda_min=0.5, gumaman=False)}
        self.assertEqual(jenis, {"awal", "akhir"})

    def test_gumaman_sendirian_dibuang(self):
        k = kata(("jadi", 0.0, 0.4), ("eee", 0.8, 1.2), ("begitu", 1.6, 2.2))
        jenis = [j for _a, _b, j in _potongan_segmen(0.0, 2.5, k, jeda_min=5.0, gumaman=True)]
        self.assertIn("gumaman", jenis)

    def test_gumaman_yang_menempel_tidak_dibuang(self):
        # Menempel berarti potongannya ikut memakan suku kata tetangganya.
        k = kata(("jadi", 0.0, 0.79), ("eee", 0.8, 1.2), ("begitu", 1.21, 2.0))
        jenis = [j for _a, _b, j in _potongan_segmen(0.0, 2.5, k, jeda_min=5.0, gumaman=True)]
        self.assertNotIn("gumaman", jenis)

    def test_kata_sungguhan_tidak_pernah_masuk_daftar_gumaman(self):
        # "ya", "apa", dan "kan" sering jadi pengisi, tapi ketiganya kata.
        for w in ("ya", "apa", "kan", "nah", "oke"):
            self.assertNotIn(w, GUMAMAN)


class IrisSunyi(unittest.TestCase):
    def test_tanpa_jejak_seluruh_rentang_dipakai(self):
        self.assertEqual(_iris_sunyi(None, 0.0, 1.0, 2.0, -40), (1.0, 2.0))

    def test_hanya_bagian_yang_sunyi_yang_diambil(self):
        # 0,0-1,0 detik: sunyi. 1,0-1,5: tawa. 1,5-3,0: sunyi lagi.
        jejak = [-60.0] * 10 + [-8.0] * 5 + [-60.0] * 15
        iris = _iris_sunyi(jejak, 0.0, 0.0, 3.0, -40.0)
        self.assertIsNotNone(iris)
        a, b = iris
        # Yang diambil deretan sunyi TERPANJANG, yaitu yang kedua.
        self.assertAlmostEqual(a, 1.5, places=2)
        self.assertAlmostEqual(b, 3.0, places=2)

    def test_rentang_yang_seluruhnya_bersuara_ditolak(self):
        self.assertIsNone(_iris_sunyi([-8.0] * 30, 0.0, 0.0, 3.0, -40.0))


class Rapatkan(unittest.TestCase):
    def test_tanpa_kata_segmen_tidak_berubah(self):
        seg = [{"start": 0.0, "end": 10.0}]
        hasil = rapatkan(seg, [])
        self.assertEqual(hasil["segments"], seg)
        self.assertEqual(hasil["dibuang"], 0.0)

    def test_segmen_terpecah_dan_waktunya_masuk_akal(self):
        seg = [{"start": 0.0, "end": 10.0}]
        k = kata(("satu", 0.2, 0.8), ("dua", 4.0, 4.6), ("tiga", 9.0, 9.6))
        hasil = rapatkan(seg, k)
        self.assertGreater(len(hasil["segments"]), 1)
        self.assertGreater(hasil["dibuang"], 0)
        # Tiap segmen maju, tidak saling tumpang, dan tetap di dalam rentangnya.
        akhir = 0.0
        for s in hasil["segments"]:
            self.assertLess(s["start"], s["end"])
            self.assertGreaterEqual(s["start"], akhir - 1e-6)
            self.assertLessEqual(s["end"], 10.0 + 1e-6)
            akhir = s["end"]

    def test_perubahan_terlalu_kecil_dibatalkan(self):
        # Di bawah 0,35 detik, memotong hanya membuat kedipan tanpa manfaat.
        seg = [{"start": 0.0, "end": 2.0}]
        k = kata(("satu", 0.0, 0.5), ("dua", 1.05, 2.0))
        hasil = rapatkan(seg, k)
        self.assertEqual(hasil["segments"], seg)

    def test_kalimat_ringkas_jujur(self):
        self.assertIn("Tidak ada jeda", ringkas({"potongan": 0}, 60.0))
        pesan = ringkas({"potongan": 2, "dibuang": 5.0, "rincian": {"jeda": 2}}, 60.0)
        self.assertIn("5.0 detik", pesan)
        self.assertIn("55 detik", pesan)


if __name__ == "__main__":
    unittest.main()


class TanpaTranskrip(unittest.TestCase):
    """
    Merapatkan klip yang tidak punya transkrip: musik, gameplay tanpa bicara,
    dan video berbahasa asing yang subtitle-nya gagal diambil. Sebelumnya klip
    seperti ini tidak bisa dirapatkan sama sekali, padahal jedanya justru
    sering paling panjang.
    """

    def jejak(self, pola):
        """pola: [(detik, dB), ...] dijadikan jejak per 0,1 detik."""
        keluar = []
        for detik, db in pola:
            keluar += [db] * int(detik / rapat.ENERGI_LANGKAH)
        return keluar

    def test_bagian_sunyi_ditemukan_dari_suara_saja(self):
        jejak = self.jejak([(2.0, -20.0), (3.0, -60.0), (2.0, -20.0)])
        amb = rapat._ambang_tanpa_kata(jejak)
        pot = rapat._potongan_dari_energi(jejak, 0.0, 0.0, 7.0, amb, jeda_min=0.5)
        self.assertEqual(len(pot), 1)
        x, y, _ = pot[0]
        self.assertGreater(x, 2.0)          # bantalan menjaga jarak dari suara
        self.assertLess(y, 5.0)

    def test_sunyi_yang_terlalu_pendek_dilewati(self):
        jejak = self.jejak([(2.0, -20.0), (0.3, -60.0), (2.0, -20.0)])
        amb = rapat._ambang_tanpa_kata(jejak)
        self.assertEqual(
            rapat._potongan_dari_energi(jejak, 0.0, 0.0, 4.3, amb, jeda_min=0.5), [])

    def test_klip_yang_ramai_terus_tidak_dipotong(self):
        jejak = self.jejak([(6.0, -20.0)])
        amb = rapat._ambang_tanpa_kata(jejak)
        self.assertEqual(
            rapat._potongan_dari_energi(jejak, 0.0, 0.0, 6.0, amb, jeda_min=0.5), [])

    def test_ambangnya_memakai_persentil_bukan_nilai_tengah(self):
        # Pada klip yang bagian berisinya lebih banyak daripada bagian sunyinya,
        # nilai tengah ikut terseret naik dan bagian sunyi tidak terdeteksi.
        jejak = self.jejak([(8.0, -20.0), (2.0, -60.0)])
        self.assertGreater(rapat._ambang_tanpa_kata(jejak), -60.0)
        self.assertLess(rapat._ambang_tanpa_kata(jejak), -20.0)

    def test_tanpa_kata_dan_tanpa_berkas_tidak_mengarang(self):
        hasil = rapat.rapatkan([{"start": 0.0, "end": 9.0}], [], sumber=None)
        self.assertEqual(hasil["potongan"], 0)
        self.assertEqual(hasil["segments"], [{"start": 0.0, "end": 9.0}])
