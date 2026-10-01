"""
Potongan wajah yang wajahnya MEMENUHI layar tidak boleh ditelan.

Diminta pemiliknya 30 September 2026, dengan contohnya sendiri: "disini
dominan wajah jadi mengapa tidak beralih ke mengikuti wajah". Ia benar, dan
penggolongnya sebenarnya SUDAH menandai momen itu sebagai wajah — yang
menelannya adalah batas empat detik yang ada untuk menahan kedipan.

Batas itu masuk akal selama kedua pilihannya sama-sama wajar. Tapi saat wajah
orangnya memenuhi layar, bingkai game bukan pilihan yang kurang bagus
melainkan SALAH: ia memotong kotak sebesar facecam dari wajah yang sedang
besar-besarnya, lalu menaruh balok permainan di bidang bawah.
"""

import unittest

from app.services.sutradara_ai import (POTONGAN_DASAR_MIN, POTONGAN_WAJAH_BESAR_MIN,
                                       WAJAH_BESAR_MIN, _rapikan_potongan)


class BatasSendiriUntukWajahBesar(unittest.TestCase):
    # Potongan wajah 2,4 detik di tengah dua potongan game yang panjang: bentuk
    # yang persis terjadi pada klip LaperGang detik 32,5-34,9.
    RUNS = [["game", 0.0, 32.5], ["wajah", 32.5, 34.9], ["game", 34.9, 43.7]]

    def test_tanpa_batas_sendiri_potongan_itu_ditelan(self):
        hasil = _rapikan_potongan([r[:] for r in self.RUNS])
        self.assertEqual([r[0] for r in hasil], ["game"])

    def test_dengan_batas_sendiri_potongan_itu_bertahan(self):
        hasil = _rapikan_potongan(
            [r[:] for r in self.RUNS],
            minimum={("wajah", 32.5): POTONGAN_WAJAH_BESAR_MIN})
        self.assertEqual([r[0] for r in hasil], ["game", "wajah", "game"])

    def test_yang_lebih_pendek_dari_batasnya_sendiri_tetap_ditelan(self):
        """Batasnya dilonggarkan, bukan dihapus: kedipan tetap harus tertahan."""
        runs = [["game", 0.0, 32.5], ["wajah", 32.5, 33.1], ["game", 33.1, 43.7]]
        hasil = _rapikan_potongan(
            runs, minimum={("wajah", 32.5): POTONGAN_WAJAH_BESAR_MIN})
        self.assertEqual([r[0] for r in hasil], ["game"])

    def test_batasnya_memang_lebih_longgar(self):
        self.assertLess(POTONGAN_WAJAH_BESAR_MIN, POTONGAN_DASAR_MIN)


class AmbangnyaMemisahkanYangTerukur(unittest.TestCase):
    """
    Angkanya diukur pada klip LaperGang, bukan ditebak. Lebar wajah TENGAH tiap
    potongan memisah dengan bersih, dan ambangnya duduk di tengah jurang itu.
    """

    GAME = (0.036, 0.036, 0.040, 0.044, 0.054, 0.059, 0.083)
    WAJAH = (0.103, 0.116, 0.134, 0.141)

    def test_tidak_satu_pun_potongan_game_ikut_terpilih(self):
        for v in self.GAME:
            self.assertLess(v, WAJAH_BESAR_MIN, v)

    def test_semua_potongan_wajah_terpilih(self):
        for v in self.WAJAH:
            self.assertGreaterEqual(v, WAJAH_BESAR_MIN, v)

    def test_ambangnya_punya_jarak_ke_kedua_sisi(self):
        """Ambang yang menempel di salah satu sisi akan goyah di video lain."""
        self.assertGreater(WAJAH_BESAR_MIN - max(self.GAME), 0.01)
        self.assertGreater(min(self.WAJAH) - WAJAH_BESAR_MIN, 0.001)


if __name__ == "__main__":
    unittest.main()
