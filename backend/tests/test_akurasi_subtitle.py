"""
Model Whisper untuk bahasa Indonesia.

Pemiliknya melapor 5 Oktober 2026 bahwa ia "sering harus edit manual subtitle".
Sebabnya diukur, bukan ditebak: 45 detik audio gameplay miliknya sendiri,
model dimuat lebih dulu supaya waktunya adil.

  base  beam 1   7,9 dtk   "Oh eh, tunggu sebuah dia tikai ke lu mati loh..."
  small beam 1   6,2 dtk   "oh eh tunggu 10 detik lagi ya... oke 8 7 6 5 4..."
  small beam 5   7,4 dtk   sama, tanpa pengulangan "anjing anjing anjing"

Yang diucapkan memang hitungan mundur sepuluh detik, dan hanya `small` yang
mendengarnya. Dan ia LEBIH CEPAT: `base` yang salah dengar jatuh ke
pengulangan dan mendekode jauh lebih banyak token untuk audio yang sama.
"""

import unittest
from unittest import mock

from app.services import whisper as w


class ModelUntukBahasa(unittest.TestCase):
    def test_indonesia_dinaikkan_ke_small(self):
        with mock.patch.object(w, "available_ram_mb", return_value=8000):
            model, alasan = w.model_untuk("id", "base")
        self.assertEqual(model, "small")
        self.assertTrue(alasan)

    def test_bahasa_serumpun_ikut(self):
        with mock.patch.object(w, "available_ram_mb", return_value=8000):
            for b in ("ms", "jv", "su", "id-ID"):
                with self.subTest(b=b):
                    self.assertEqual(w.model_untuk(b, "base")[0], "small")

    def test_aksara_sulit_tetap_dinaikkan(self):
        """Aturan lama tidak boleh hilang saat yang baru ditambahkan."""
        with mock.patch.object(w, "available_ram_mb", return_value=8000):
            self.assertEqual(w.model_untuk("ja", "base")[0], "small")

    def test_inggris_tidak_dinaikkan(self):
        """Yang tidak terbukti bermasalah tidak membayar ongkosnya."""
        with mock.patch.object(w, "available_ram_mb", return_value=8000):
            self.assertEqual(w.model_untuk("en", "base")[0], "base")

    def test_pilihan_yang_lebih_besar_dihormati(self):
        with mock.patch.object(w, "available_ram_mb", return_value=8000):
            self.assertEqual(w.model_untuk("id", "medium")[0], "medium")

    def test_ram_tipis_tidak_dinaikkan(self):
        """Mati kehabisan memori jauh lebih buruk daripada transkrip kurang tepat."""
        with mock.patch.object(w, "available_ram_mb", return_value=1000):
            model, alasan = w.model_untuk("id", "base")
        self.assertEqual(model, "base")
        self.assertIn("RAM", alasan)


class BeamIkutUkuranModel(unittest.TestCase):
    def test_beam_dipilih_dari_ukuran_model(self):
        """
        Beam 5 pada `base` JUSTRU lebih buruk: terukur, ia jatuh ke pengulangan
        "di jodh, di jodh, di jodh" selama belasan detik. Model yang salah
        dengar diberi lebih banyak jalan hanya menemukan lebih banyak jalan
        yang salah.
        """
        from pathlib import Path
        teks = (Path(w.__file__)).read_text(encoding="utf-8")
        self.assertIn('beam = 5 if _MODEL_SIZE in ("small", "medium", "large") else 1',
                      teks)
        self.assertIn("beam_size=beam", teks)
        self.assertNotIn("beam_size=1,\n        word_timestamps", teks)


if __name__ == "__main__":
    unittest.main()
