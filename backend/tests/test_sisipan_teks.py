"""
Sisipan tulisan, dan janji bahwa bidang wajah tidak keluar facecam.

Dua hal yang diminta pemiliknya 30 September 2026, digabung di sini karena
keduanya lahir dari sesi yang sama:

1. Tulisan yang menempel di atas video, terpisah dari judul klip. Alasannya
   konkret: ada kampanye yang mensyaratkan tulisan tertentu muncul di klip,
   misalnya "@motionklip" berikut logonya.
2. "Bingkai wajahnya terlalu besar melebihi facecam bahkan memotong bingkai
   game." Yang diuji di sini bukan seberapa bagus potongannya, melainkan
   janjinya: potongan bidang wajah TIDAK PERNAH keluar panel facecam.
"""

import unittest

from app.services.render import (_graf_teks, _lolos_teks, _siapkan_teks,
                                 build_sisipan_graph, kotak_reaksi,
                                 siapkan_sisipan)


class TulisanDiterimaTanpaBerkas(unittest.TestCase):
    """Sisipan lain butuh aset di pustaka; tulisan tidak punya berkas apa pun."""

    def test_lapisan_teks_lolos_tanpa_aset(self):
        hasil = siapkan_sisipan([{"jenis": "teks", "teks": "@motionklip",
                                  "t": 0.0, "dur": 5.0}], 10.0)
        self.assertEqual(len(hasil), 1)
        self.assertEqual(hasil[0]["jenis"], "teks")
        self.assertIsNone(hasil[0]["path"])

    def test_tulisan_kosong_dibuang(self):
        for isi in ("", "   ", None):
            with self.subTest(isi=isi):
                self.assertEqual(siapkan_sisipan(
                    [{"jenis": "teks", "teks": isi, "t": 0, "dur": 5}], 10.0), [])

    def test_panjangnya_tidak_melewati_akhir_klip(self):
        hasil = siapkan_sisipan([{"jenis": "teks", "teks": "x",
                                  "t": 8.0, "dur": 99.0}], 10.0)
        self.assertAlmostEqual(hasil[0]["dur"], 2.0, places=3)

    def test_yang_mulai_sesudah_klip_habis_dibuang(self):
        self.assertEqual(siapkan_sisipan(
            [{"jenis": "teks", "teks": "x", "t": 11.0, "dur": 2.0}], 10.0), [])

    def test_tanpa_dur_berlaku_sampai_akhir_klip(self):
        """Syarat kampanye hampir selalu "sepanjang video"."""
        hasil = _siapkan_teks({"teks": "x", "t": 3.0}, 10.0)
        self.assertAlmostEqual(hasil["dur"], 7.0, places=3)


class TulisanTidakMerusakPerintahFfmpeg(unittest.TestCase):
    """
    Teks datang dari pengguna, dan di dalam `drawtext` beberapa tanda punya
    arti bagi ffmpeg. Yang tidak dikawal bukan cuma salah tampil: ia membuat
    seluruh perintah render gagal.
    """

    def test_tanda_berbahaya_dikawal(self):
        for tanda in (":", "'", "%", "\\"):
            with self.subTest(tanda=tanda):
                self.assertIn("\\" + tanda, _lolos_teks(f"a{tanda}b"))

    def test_huruf_biasa_tidak_disentuh(self):
        self.assertEqual(_lolos_teks("@motionklip 2026"), "@motionklip 2026")


class TulisanDigambarLangsung(unittest.TestCase):
    def _graf(self, **ubah):
        l = {"jenis": "teks", "teks": "HALO", "t": 1.0, "dur": 3.0,
             "posisi": "bawah", "ukuran": 5.0, "opasitas": 1.0,
             "fade_masuk": 0.0, "fade_keluar": 0.0, "warna": "#FFFFFF",
             "garis": "#000000", "tebal_garis": 3.0, "latar": "",
             "keluarga": "Archivo Black", "rect": None}
        l.update(ubah)
        bagian = []
        _graf_teks(bagian, l, "[v]", 0, 1080, 1920)
        return bagian[0]

    def test_tanpa_masukan_tambahan(self):
        """Membuatnya jadi gambar dulu berarti satu berkas sementara per tempelan."""
        lap = siapkan_sisipan([{"jenis": "teks", "teks": "x", "t": 0, "dur": 2}], 5.0)
        inputs, _graf, _v, _a = build_sisipan_graph(
            lap, "[0:v]", "[a]", input_awal=1, out_w=1080, out_h=1920)
        self.assertEqual(inputs, [])

    def test_hanya_tampil_pada_rentangnya(self):
        self.assertIn("enable='between(t,1.000,4.000)'", self._graf())

    def test_ketembusan_masuk_ke_alfa(self):
        self.assertIn("alpha='0.500'", self._graf(opasitas=0.5))

    def test_lembut_masuk_dan_keluar_ikut_di_alfa(self):
        g = self._graf(fade_masuk=0.5, fade_keluar=0.5, opasitas=0.8)
        self.assertIn("lt(t,1.500)", g)
        self.assertIn("gt(t,3.500)", g)

    def test_tidak_pernah_keluar_kanvas(self):
        """
        Tulisan bisa lebih lebar daripada petaknya; tanpa kurungan ini ujungnya
        terpotong tepi layar. Terlihat pada render uji 30 September 2026.
        """
        g = self._graf()
        self.assertIn("max(0", g)
        self.assertIn("1080-text_w", g)
        self.assertIn("1920-text_h", g)

    def test_kotak_latar_hanya_bila_diminta(self):
        self.assertNotIn("box=1", self._graf(latar=""))
        self.assertIn("box=1", self._graf(latar="#000000"))

    def test_warna_heksa_diterjemahkan(self):
        self.assertIn("fontcolor=0xFFE600", self._graf(warna="#FFE600"))


class BidangWajahTidakKeluarFacecam(unittest.TestCase):
    """
    Janji yang diminta pemiliknya, dan yang paling sering dilanggar sebelum ini:
    apa pun yang di luar panel facecam isinya permainan, dan permainan tidak
    boleh masuk ke bidang wajah.
    """

    PANEL = {"x": 4.0, "y": 20.0, "w": 18.0, "h": 30.0}

    def _di_dalam(self, r, p):
        return (r["x"] >= p["x"] - 0.01 and r["y"] >= p["y"] - 0.01
                and r["x"] + r["w"] <= p["x"] + p["w"] + 0.01
                and r["y"] + r["h"] <= p["y"] + p["h"] + 0.01)

    def test_kepala_yang_wajar_tetap_di_dalam(self):
        muka = [10.0, 28.0, 16.0, 40.0]
        for rasio in (0.6, 0.8, 1.0, 1.4, 1.8):
            with self.subTest(rasio=rasio):
                r = kotak_reaksi(self.PANEL, muka, rasio, 1920 / 1080)
                self.assertTrue(self._di_dalam(r, self.PANEL), r)

    def test_petak_wajah_yang_MELUAP_pun_tetap_di_dalam(self):
        """
        Petak wajah bisa jauh lebih besar daripada panelnya: `awan_kotak`
        memuat seluruh gerak orangnya selama jendela pemindaian, dan bila POV
        berganti di tengah jendela ia memuat dua letak sekaligus. Terukur satu
        bidikan menuntut 211% tinggi panelnya.
        """
        muka = [0.0, 0.0, 30.0, 70.0]
        for rasio in (0.6, 1.0, 1.8):
            with self.subTest(rasio=rasio):
                r = kotak_reaksi(self.PANEL, muka, rasio, 1920 / 1080)
                self.assertTrue(self._di_dalam(r, self.PANEL), r)

    def test_tanpa_petak_wajah_tetap_di_dalam(self):
        r = kotak_reaksi(self.PANEL, None, 1.4, 1920 / 1080)
        self.assertTrue(self._di_dalam(r, self.PANEL), r)


if __name__ == "__main__":
    unittest.main()
