"""
Sisipan: berkas dari luar video sumber, ditempel pada waktunya.

Yang dijaga di sini adalah hal-hal yang rusaknya baru terlihat SESUDAH render,
yaitu paling mahal: petak yang meleset dari yang digambar, panjang yang dipotong
padahal diminta berulang, dan klip lama yang berubah tampilannya sendiri hanya
karena aplikasinya diperbarui.
"""

import unittest

from app.services.render import (POSISI_SISIPAN, build_sisipan_graph,
                                 petak_sisipan, siapkan_sisipan)


def lapis(**kw):
    dasar = {"path": "/tmp/a.png", "jenis": "gambar", "punya_suara": False,
             "t": 0.0, "dur": 2.0, "mulai": 0.0, "volume": 0.0,
             "posisi": "penuh", "rect": None, "isi": "muat", "opasitas": 1.0,
             "fade_masuk": 0.0, "fade_keluar": 0.0, "ulang": False, "redam": False}
    dasar.update(kw)
    return dasar


class PetakSisipan(unittest.TestCase):
    def test_rect_bebas_dipakai_apa_adanya(self):
        x, y, w, h = petak_sisipan({"rect": {"x": 10, "y": 20, "w": 50, "h": 25}},
                                   1080, 1920)
        self.assertEqual((x, y), (108, 384))
        self.assertEqual((w, h), (540, 480))

    def test_preset_lama_masih_berlaku_tanpa_rect(self):
        """
        Klip yang sudah tersimpan sebelum rect ada memakai preset, dan klip yang
        sudah jadi tidak boleh berubah tampilannya sendiri karena pembaruan.
        """
        for nama in POSISI_SISIPAN:
            with self.subTest(nama):
                a = petak_sisipan({"posisi": nama}, 1080, 1920)
                self.assertEqual(len(a), 4)
                self.assertGreater(a[2], 0)
                self.assertGreater(a[3], 0)

    def test_rect_menang_atas_preset(self):
        l = {"posisi": "sudut", "rect": {"x": 0, "y": 0, "w": 100, "h": 100}}
        self.assertEqual(petak_sisipan(l, 1080, 1920), (0, 0, 1080, 1920))

    def test_petak_tidak_pernah_keluar_kanvas(self):
        x, y, w, h = petak_sisipan({"rect": {"x": 90, "y": 95, "w": 60, "h": 60}},
                                   1080, 1920)
        self.assertLessEqual(x + w, 1080)
        self.assertLessEqual(y + h, 1920)

    def test_ukuran_selalu_genap(self):
        """h264 menolak lebar atau tinggi ganjil, dan yang gagal seluruh rendernya."""
        for w_pct in (3, 7, 11, 33, 47, 99):
            _, _, w, h = petak_sisipan({"rect": {"x": 0, "y": 0, "w": w_pct, "h": w_pct}},
                                       1080, 1920)
            self.assertEqual(w % 2, 0, f"lebar ganjil pada {w_pct}%")
            self.assertEqual(h % 2, 0, f"tinggi ganjil pada {w_pct}%")


class GrafSisipan(unittest.TestCase):
    def _graf(self, l):
        _, graf, _, _ = build_sisipan_graph([l], "[0:v]", "[0:a]",
                                            input_awal=1, out_w=1080, out_h=1920)
        return graf

    def test_fade_bekerja_di_saluran_alfa(self):
        """
        Sisipan yang memudar harus memperlihatkan video di bawahnya. Tanpa
        `alpha=1`, `fade` menggelapkan gambarnya sendiri, jadi yang terlihat
        persegi hitam yang tumbuh, bukan sisipan yang muncul.
        """
        graf = self._graf(lapis(fade_masuk=0.4, fade_keluar=0.6))
        self.assertIn("fade=t=in:st=0:d=0.400:alpha=1", graf)
        self.assertIn("fade=t=out:st=1.400:d=0.600:alpha=1", graf)

    def test_ketembusan_dipasang(self):
        self.assertIn("colorchannelmixer=aa=0.400", self._graf(lapis(opasitas=0.4)))

    def test_tanpa_efek_tidak_menambah_filter(self):
        graf = self._graf(lapis())
        for nama in ("fade=", "colorchannelmixer"):
            self.assertNotIn(nama, graf)

    def test_isi_muat_dan_penuh_berbeda(self):
        muat = self._graf(lapis(isi="muat"))
        penuh = self._graf(lapis(isi="penuh"))
        self.assertIn("force_original_aspect_ratio=decrease", muat)
        self.assertIn("force_original_aspect_ratio=increase", penuh)
        self.assertIn("crop=", penuh)

    def test_ulang_memakai_stream_loop_sebelum_input(self):
        """
        `-stream_loop` opsi MASUKAN: ia harus berdiri sebelum `-i`, dan di
        belakangnya salah diam-diam (berlaku untuk masukan berikutnya, atau
        diabaikan sama sekali).
        """
        inputs, _, _, _ = build_sisipan_graph(
            [lapis(jenis="audio", path="/tmp/a.mp3", ulang=True, volume=0.8)],
            "[0:v]", "[0:a]", input_awal=1, out_w=1080, out_h=1920)
        self.assertIn("-stream_loop", inputs)
        self.assertLess(inputs.index("-stream_loop"), inputs.index("-i"))

    def test_afade_untuk_suara(self):
        graf = self._graf(lapis(jenis="audio", path="/tmp/a.mp3", volume=0.8,
                                fade_masuk=0.5, fade_keluar=0.5))
        self.assertIn("afade=t=in:st=0:d=0.500", graf)
        self.assertIn("afade=t=out:st=1.500:d=0.500", graf)


class PanjangSisipan(unittest.TestCase):
    """`siapkan_sisipan` membaca pustaka aset, jadi asetnya dipalsukan."""

    def setUp(self):
        from app.services import aset as aset_svc
        self.asli = (aset_svc.jalur, aset_svc.info)
        aset_svc.jalur = lambda i: "/tmp/a.mp3"
        aset_svc.info = lambda i: {"jenis": "audio", "durasi": 30.0, "punya_suara": True}

    def tearDown(self):
        from app.services import aset as aset_svc
        aset_svc.jalur, aset_svc.info = self.asli

    def test_tanpa_ulang_dipotong_sepanjang_berkasnya(self):
        hasil = siapkan_sisipan([{"aset": "x", "t": 0, "dur": 90}], 120.0)
        self.assertAlmostEqual(hasil[0]["dur"], 30.0)

    def test_dengan_ulang_panjangnya_dihormati(self):
        """Musik satu menit untuk klip dua menit memang dimaksudkan berputar."""
        hasil = siapkan_sisipan([{"aset": "x", "t": 0, "dur": 90, "ulang": True}], 120.0)
        self.assertAlmostEqual(hasil[0]["dur"], 90.0)

    def test_tetap_tidak_melewati_akhir_klip(self):
        hasil = siapkan_sisipan([{"aset": "x", "t": 5, "dur": 90, "ulang": True}], 20.0)
        self.assertAlmostEqual(hasil[0]["dur"], 15.0)

    def test_fade_tidak_pernah_melebihi_separuh_panjangnya(self):
        """Fade masuk dan keluar yang saling melewati akan saling menghapus."""
        hasil = siapkan_sisipan(
            [{"aset": "x", "t": 0, "dur": 4, "fade_masuk": 99, "fade_keluar": 99}], 60.0)
        self.assertLessEqual(hasil[0]["fade_masuk"], 2.0)
        self.assertLessEqual(hasil[0]["fade_keluar"], 2.0)

    def test_nilai_liar_tidak_menggagalkan_render(self):
        hasil = siapkan_sisipan(
            [{"aset": "x", "t": 0, "dur": 4, "opasitas": 9, "isi": "entah"}], 60.0)
        self.assertEqual(hasil[0]["opasitas"], 1.0)
        self.assertEqual(hasil[0]["isi"], "penuh")


if __name__ == "__main__":
    unittest.main()
