"""JOB-2 F2-5: intro dan outro bermerek per akun."""

import unittest
from pathlib import Path
from unittest import mock

from app.services import komentar as km
from app.services import merek, nilai_tambah


class Siapkan(unittest.TestCase):
    def test_kosong_dan_mati(self):
        self.assertEqual(merek.siapkan({}), {"intro": None, "outro": None, "outro_teks": ""})
        self.assertEqual(merek.siapkan({"aktif": False, "outro_teks": "x"})["outro_teks"], "")

    def test_aset_hilang_diabaikan(self):
        s = merek.siapkan({"intro": "0123456789abcdef", "outro_teks": "  Ikuti   @kanal "})
        self.assertIsNone(s["intro"])
        self.assertEqual(s["outro_teks"], "Ikuti @kanal")

    def test_intro_dibatasi(self):
        info = {"jenis": "video", "durasi": 12.0, "punya_suara": True}
        with mock.patch("app.services.aset.jalur", return_value=Path("/x.mp4")), \
             mock.patch("app.services.aset.info", return_value=info):
            s = merek.siapkan({"intro": "a", "outro": "b"})
        self.assertEqual(s["intro"]["d"], merek.INTRO_MAKS)
        self.assertEqual(s["outro"]["d"], merek.OUTRO_MAKS)

    def test_audio_atau_gambar_ditolak_sebagai_intro(self):
        with mock.patch("app.services.aset.jalur", return_value=Path("/x.mp3")), \
             mock.patch("app.services.aset.info", return_value={"jenis": "audio", "durasi": 2}):
            self.assertIsNone(merek.siapkan({"intro": "a"})["intro"])


class OutroTeks(unittest.TestCase):
    def test_jadi_penutup_bertanda_merek_dan_bukan_nilai_tambah(self):
        items = km.siapkan_render(merek.komentar_outro({"outro_teks": "Ikuti @kanal"}), 10)
        self.assertEqual(items[0]["posisi"], "penutup")
        self.assertTrue(items[0]["merek"])
        meta = {"duration": 10 + items[0]["d"], "komentar": km.ringkas_sidecar(items)}
        self.assertEqual(nilai_tambah.hitung(meta)["detik_komentar"], 0.0)

    def test_tetap_ikut_walau_komentar_penuh(self):
        orang = [{"posisi": "sela", "t": i + 1, "teks": f"k{i}"} for i in range(km.MAKS_KOMENTAR)]
        items = km.siapkan_render(orang + merek.komentar_outro({"outro_teks": "Ikuti"}), 20)
        self.assertTrue(any(k["merek"] for k in items))


class Graf(unittest.TestCase):
    def test_intro_outro_disambung(self):
        siap = {"intro": {"path": Path("/i.png"), "jenis": "gambar", "d": 2.0, "punya_suara": False},
                "outro": {"path": Path("/o.mp4"), "jenis": "video", "d": 3.0, "punya_suara": True}}
        inputs, graf, v, a, tambah = merek.graf_render(
            siap, "[v]", "[a]", input_awal=2, out_w=1080, out_h=1920, fps=30)
        self.assertEqual(tambah, 5.0)
        self.assertIn("-loop", inputs)
        self.assertIn("[2:v]", graf)
        self.assertIn("[3:a]", graf)
        self.assertIn("concat=n=3:v=1:a=1[mrV][mrA]", graf)

    def test_tanpa_berkas_tidak_mengubah(self):
        self.assertEqual(merek.graf_render({"intro": None, "outro": None}, "[v]", "[a]",
                                           input_awal=0, out_w=1, out_h=1, fps=30),
                         ([], "", "[v]", "[a]", 0.0))


if __name__ == "__main__":
    unittest.main()
