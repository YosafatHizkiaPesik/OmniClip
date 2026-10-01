"""
Dua cacat bingkai yang dilaporkan pemiliknya 27 September 2026, diukur pada
videonya sendiri.

1. Sebagian klip jatuh ke bilah kabur walau wajahnya jelas sepanjang klip.
   Bukan "wajah tidak terbaca": perencananya MELEMPAR GALAT, dan galat itu
   ditangkap jauh di atas sebagai "tidak ada rencana".

2. Video multi-POV (LaperGang: banyak POV YouTuber lain, masing-masing menaruh
   facecam-nya sendiri) dibingkai mengikuti wajah, bukan permainannya. Dan
   ketika sudah jadi bingkai game, kotak kameranya berdiri di tempat kosong.
"""

import unittest

from app.services import reframe as R
from app.services import sutradara_ai as SA


class PerencanaTidakMelemparGalat(unittest.TestCase):
    """
    `_tahan_saat_sepi` dulu menghitung `people[q][i] - acuan` dengan `acuan`
    yang bisa None, dan `float - None` melempar TypeError. Terjadi pada klip
    podcast 171 detik milik pemiliknya; yang terlihat olehnya adalah klip yang
    jatuh ke bilah kabur.
    """

    @staticmethod
    def _sepi_tanpa_acuan():
        """
        Keadaan yang meledak: orang yang sedang ditahan menghilang dari layar,
        dua orang lain terlihat, dan belum ada satu pun titik bingkai
        sebelumnya yang bisa jadi acuan.
        """
        n = 4
        centers = [None] * n
        subject = [0, None, None, None]
        people = [[100.0, None, None, None], [500.0] * n, [900.0] * n]
        seen = [[True, False, False, False], [True] * n, [True] * n]
        return centers, subject, people, seen

    def test_klip_tanpa_acuan_tidak_meledak(self):
        out, subj = R._tahan_saat_sepi(*self._sepi_tanpa_acuan())
        self.assertEqual(len(out), 4)
        # Tanpa acuan: wajah paling kiri di antara yang terlihat.
        self.assertEqual(out[1:], [500.0, 500.0, 500.0], out)
        self.assertEqual(subj[1:], [1, 1, 1], subj)

    def test_pilihannya_tetap_sama_tiap_kali_dihitung(self):
        a = R._tahan_saat_sepi(*self._sepi_tanpa_acuan())
        b = R._tahan_saat_sepi(*self._sepi_tanpa_acuan())
        self.assertEqual(a, b)

    def test_acuan_dipakai_bila_ada(self):
        n = 3
        centers = [500.0, None, None]
        subject = [1, None, None]
        people = [[100.0] * n, [500.0] * n]
        seen = [[True] * n, [False] * n]     # orang 1 hilang dari layar
        out, _ = R._tahan_saat_sepi(centers, subject, people, seen)
        # Hanya satu wajah yang terlihat, jadi tidak ada yang perlu ditahan.
        self.assertEqual(out[0], 500.0)


class FacecamDiTepiTengahTerbaca(unittest.TestCase):
    """
    Aturan lama menuntut wajah dekat tepi mendatar DAN tepi tegak. Facecam
    LaperGang ada di x 11,5% tapi y 50,2%, tepat di celah yang ditolak.
    Terukur: porsi "game" 12% sebelum, 94% sesudah.
    """

    SW, SH = 1920, 1080

    def pojok(self, fx, fy, fw):
        return SA._wajah_pojok(fx * self.SW, fy * self.SH, fw * self.SW, self.SW, self.SH)

    def test_facecam_kiri_tengah_terbaca(self):
        self.assertTrue(self.pojok(0.115, 0.502, 0.062))

    def test_facecam_kanan_bawah_tetap_terbaca(self):
        self.assertTrue(self.pojok(0.770, 0.674, 0.064))

    def test_facecam_pojok_lama_tidak_berubah(self):
        self.assertTrue(self.pojok(0.885, 0.862, 0.067))

    def test_wajah_podcast_di_tengah_tetap_bukan_facecam(self):
        for fx, fy, fw in ((0.304, 0.298, 0.072), (0.676, 0.389, 0.053),
                           (0.315, 0.287, 0.057), (0.717, 0.328, 0.054)):
            with self.subTest(x=fx):
                self.assertFalse(self.pojok(fx, fy, fw))

    def test_wajah_besar_di_tepi_bukan_facecam(self):
        """Tamu yang duduk di tepi layar wajahnya jauh lebih besar."""
        self.assertFalse(self.pojok(0.10, 0.50, 0.20))
        self.assertFalse(self.pojok(0.10, 0.50, 0.12))   # masih di atas 9%


class PanelDikelompokkan(unittest.TestCase):
    """
    Dua facecam yang terlihat bersamaan dulu digabung jadi satu awan selebar
    layar, lalu seluruh jendelanya ditolak. Terukur pada klip LaperGang:
    8 dari 11 jendela tidak terbaca sama sekali.
    """

    def test_jendela_cukup_pendek_supaya_panel_tidak_basi(self):
        """
        Sebuah panel berlaku mulai dari awal jendela tempat ia ditemukan, jadi
        panjang jendela ADALAH batas atas seberapa basi panel itu bisa jadi.
        Pada video multi-POV yang facecam-nya berpindah tiap beberapa detik,
        panel basi tidak meleset sedikit — ia menunjuk bagian layar yang sama
        sekali lain.

        Versi uji ini dulu juga menuntut MINIMAL 12 sampel per jendela, dengan
        alasan "jangan sampai kehilangan dasar". Pengukuran 30 September 2026
        membantah alasan itu, jadi tuntutannya dicabut: pada empat klip
        LaperGang, 1.456 sampel berwajah,

            jendela 2,0 dtk (16 sampel) -> 75,1% tepat, 363 meleset
            jendela 1,0 dtk ( 8 sampel) -> 85,2% tepat, 215 meleset
            jendela 0,5 dtk ( 4 sampel) -> 88,7% tepat, 164 meleset

        Empat sampel memang dasar yang lebih tipis, dan `_tepi_panel` bahkan
        tidak pernah jalan di jendela sependek itu. Panel yang selalu SEGAR
        tetap lebih berharga daripada panel yang tepinya lebih rapi tapi
        terlambat setengah detik.
        """
        self.assertLessEqual(R.FACECAM_JENDELA, 1.0)
        # Satu sampel saja bukan jendela; harus ada beberapa untuk memastikan
        # panelnya diam, bukan wajah yang kebetulan lewat satu bingkai.
        self.assertGreaterEqual(R.FACECAM_JENDELA * R.SAMPLE_FPS, 3)

    def test_panel_yang_sama_diukur_dari_tumpang_tindih(self):
        with open(R.__file__, encoding="utf-8") as f:
            teks = f.read()
        self.assertIn("FACECAM_TINDIH_MIN", teks)
        # Jarak pusat sendirian tidak cukup; ia goyah saat kotaknya berubah bentuk.
        self.assertNotIn("FACECAM_PINDAH", teks)

    def test_kiri_dan_kanan_tidak_pernah_dianggap_sama(self):
        """Dua panel di sisi berlawanan tidak bertindih sama sekali."""
        kiri = {"x": 0.0, "y": 34.5, "w": 21.1, "h": 34.2}
        kanan = {"x": 82.4, "y": 64.4, "w": 17.5, "h": 30.0}
        x1, y1 = max(kiri["x"], kanan["x"]), max(kiri["y"], kanan["y"])
        x2 = min(kiri["x"] + kiri["w"], kanan["x"] + kanan["w"])
        y2 = min(kiri["y"] + kiri["h"], kanan["y"] + kanan["h"])
        tindih = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        self.assertEqual(tindih, 0.0)

    def test_panel_sama_yang_bergeser_sedikit_tidak_dihitung_pindah(self):
        a = {"x": 0.0, "y": 34.5, "w": 21.1, "h": 34.2}
        b = {"x": 3.4, "y": 34.5, "w": 17.7, "h": 34.2}
        x1, y1 = max(a["x"], b["x"]), max(a["y"], b["y"])
        x2 = min(a["x"] + a["w"], b["x"] + b["w"])
        y2 = min(a["y"] + a["h"], b["y"] + b["h"])
        tindih = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        gabung = a["w"] * a["h"] + b["w"] * b["h"] - tindih
        self.assertGreaterEqual(tindih / gabung, R.FACECAM_TINDIH_MIN)

    def test_ambang_gugus_masuk_akal(self):
        # Cukup longgar untuk satu panel, cukup ketat untuk memisahkan dua
        # panel di sudut yang berlawanan.
        self.assertGreater(R.FACECAM_GUGUS, 0.05)
        self.assertLess(R.FACECAM_GUGUS, 0.35)

    def test_perpindahan_kuat_tidak_perlu_saksi(self):
        sumber = (R.__file__)
        with open(sumber, encoding="utf-8") as f:
            teks = f.read()
        self.assertIn("FACECAM_SENDIRI_MIN", teks)
        badan = teks.split("def deteksi_facecam_waktu")[1]
        self.assertIn("kuat", badan)

    def test_kehadiran_dihitung_per_sampel(self):
        with open(R.__file__, encoding="utf-8") as f:
            teks = f.read()
        badan = teks.split("def _facecam_dari_bingkai")[1].split("\ndef ")[0]
        self.assertIn('"kehadiran": len({q[0] for q in pilih})', badan)
        # Awan tunggal yang lama tidak boleh kembali diam-diam.
        self.assertIn("gugus", badan)


if __name__ == "__main__":
    unittest.main()
