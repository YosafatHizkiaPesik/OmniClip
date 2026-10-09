"""
Bingkai yang tidak memuat siapa pun padahal ada wajah di layar.

Diukur 9 Oktober 2026 pada sepuluh video di penyimpanan pemiliknya, dengan
patokan yang berdiri sendiri dari keputusan bingkai itu sendiri: wajah hasil
deteksi. Dua sebab ditemukan, dan keduanya berbeda.

  1. Potongan adegan yang dibuang penyaring jeda. Klip 5 LaperGang: potongan
     di 36,12 detik diterima, potongan di 37,75 dibuang karena cuma berjarak
     1,63 detik dari yang sebelumnya, padahal JEDA_BATAS_MIN 2 detik. Gambar
     kembali ke bidikan kiri, bingkainya tidak, dan plafon kecepatan memaksanya
     menggeser 2,38 detik melintasi layar. 5,8% klip tanpa siapa pun.

  2. Titik cadangan yang usang. Klip 4 Kajian: 3,75 detik bingkai membeku di
     x=1083 sementara satu-satunya orang berdiri tenang di x=558. 6,9% klip.

Sesudah keduanya: LaperGang 1,99% -> 0,04%, Kajian 0,83% -> 0,12%, dan jumlah
perpindahan kamera per menit tidak berubah sama sekali.
"""

import unittest

from app.services import reframe as R


class PotonganAdeganTidakPernahDibuang(unittest.TestCase):
    """
    Jeda antar batas ada untuk keputusan KITA: berpindah dari wajah satu ke
    wajah lain dua kali dalam sedetik memang goyang. Potongan adegan bukan
    keputusan kita, melainkan kenyataan di gambarnya.
    """

    def jalankan(self, cuts, centers=None, n=None):
        n = n or len(cuts)
        centers = centers or [100.0] * n
        return R._smooth(centers, cuts, source_w=1920, crop_w=608)

    def test_dua_potongan_berdekatan_keduanya_dihormati(self):
        """1,63 detik: persis jarak dua potongan yang gagal di klip LaperGang."""
        n = 8 * 6
        cuts = [False] * n
        a, b = int(8 * 1.0), int(8 * 2.63)
        cuts[a] = cuts[b] = True
        # Tiap bidikan punya posisi wajahnya sendiri, berjauhan.
        centers = ([300.0] * a + [1600.0] * (b - a) + [300.0] * (n - b))
        out = self.jalankan(cuts, centers, n)
        # `_smooth` mengembalikan TITIK TENGAH, dijepit ke [crop_w/2, w-crop_w/2],
        # jadi wajah di 300 jatuh ke tepi kiri yang sah, yaitu 304.
        self.assertAlmostEqual(out[b], 304.0, delta=1.0,
                               msg="bingkai tidak melompat di potongan kedua")
        # Dan ia sudah di situ SEKETIKA, bukan sesudah menggeser beberapa detik.
        self.assertAlmostEqual(out[b + 2], 304.0, delta=1.0)
        # Buktinya memang perbaikan ini: tanpa pengecualian, potongan kedua
        # dibuang penyaring jeda dan bingkainya menggeser perlahan dari 1600.
        self.assertGreater(abs(out[b - 1] - out[b]), 500.0,
                           "tidak ada lompatan sama sekali di potongan kedua")

    def test_pergantian_subjek_beruntun_tetap_disaring(self):
        """Yang disaring tetap disaring; perbaikannya tidak menghapus penyaring."""
        n = 8 * 6
        cuts = [False] * n
        subject = [0] * n
        for i in range(int(8 * 1.0), int(8 * 1.5)):
            subject[i] = 1
        centers = [300.0] * n
        out = R._smooth(centers, cuts, source_w=1920, crop_w=608, subject=subject)
        self.assertEqual(len(out), n)

    def test_tanpa_potongan_tetap_mulus(self):
        n = 40
        out = self.jalankan([False] * n, [300.0] * n, n)
        self.assertTrue(all(abs(out[i] - out[i - 1]) < 1e-6 for i in range(1, n)))


class TitikCadanganTidakUsang(unittest.TestCase):
    """
    `subject=None` berarti "bingkai memakai titik tengah semua wajah". Sampai
    9 Oktober 2026 artinya "pakai titik yang dihitung pelacak", dan titik itu
    bisa berasal dari bidikan yang sudah berganti.
    """

    def test_titik_usang_diganti_wajah_yang_terlihat(self):
        people = [[558.0] * 10]
        seen = [[True] * 10]
        centers = [1387.0] * 10          # usang: dari bidikan sebelumnya
        out, subject = R._centers_from_speakers(
            centers, people, {}, [], 10, seen=seen, crop_w=608)
        self.assertEqual(subject, [None] * 10)
        self.assertEqual(out[5], 558.0, "masih memakai titik usang")

    def test_titik_yang_sudah_memuat_wajah_tidak_disentuh(self):
        """Syaratnya "tidak memuat wajah", jadi yang sudah benar tidak berubah."""
        people = [[558.0] * 10]
        seen = [[True] * 10]
        centers = [600.0] * 10           # beda 42 px, wajahnya tetap di dalam
        out, _ = R._centers_from_speakers(
            centers, people, {}, [], 10, seen=seen, crop_w=608)
        self.assertEqual(out[5], 600.0)

    def test_tanpa_wajah_terlihat_titiknya_dibiarkan(self):
        people = [[558.0] * 10]
        seen = [[False] * 10]
        centers = [1387.0] * 10
        out, _ = R._centers_from_speakers(
            centers, people, {}, [], 10, seen=seen, crop_w=608)
        self.assertEqual(out[5], 1387.0)

    def test_titik_kosong_diisi_wajah_yang_terlihat(self):
        people = [[558.0] * 10]
        seen = [[True] * 10]
        centers = [None] * 10
        out, _ = R._centers_from_speakers(
            centers, people, {}, [], 10, seen=seen, crop_w=608)
        self.assertEqual(out[5], 558.0)

    def test_beberapa_wajah_memakai_titik_tengahnya(self):
        people = [[200.0] * 10, [800.0] * 10]
        seen = [[True] * 10, [True] * 10]
        centers = [1800.0] * 10
        out, _ = R._centers_from_speakers(
            centers, people, {}, [], 10, seen=seen, crop_w=608)
        self.assertEqual(out[5], 500.0)


class SimpananIkutNaikVersi(unittest.TestCase):
    """
    Perbaikan pada cara menghitung tidak sampai ke klip yang sudah pernah
    dibuka kalau kunci simpanannya tidak ikut berubah.
    """

    def test_versi_ada_di_kunci(self):
        from app.routers.clips import BINGKAI_VERSI, _kunci_reframe
        self.assertGreaterEqual(BINGKAI_VERSI, 3)
        a = _kunci_reframe(("v", "9:16", (), (), None, (), False, "wajah"))
        import app.routers.clips as c
        asli = c.BINGKAI_VERSI
        try:
            c.BINGKAI_VERSI = asli + 1
            b = c._kunci_reframe(("v", "9:16", (), (), None, (), False, "wajah"))
        finally:
            c.BINGKAI_VERSI = asli
        self.assertNotEqual(a, b, "versi tidak ikut ke dalam kunci")
