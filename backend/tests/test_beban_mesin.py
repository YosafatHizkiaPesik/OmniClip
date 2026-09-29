"""
Mesin orangnya harus tetap bisa dipakai selama OmniClip bekerja.

Dilaporkan pemiliknya 27 September 2026: "sistem saat ini sangat sangat berat
bahkan bisa membuat laptop saya freeze". Diukur di laptop itu juga, Core
i5-8250U (4 inti, 8 utas, 15 watt) dengan RAM 7,6 GB dan swap 2 GB yang sudah
terpakai 1,8 GB: beban rata-rata 14 dari 8.

Sebabnya bukan satu hal yang berat, melainkan beberapa hal yang masing-masing
mengambil seluruh mesin: ffmpeg memakai semua utas untuk mendekode, OpenCV
memakai semua utas lagi untuk mendeteksi, dan di sebelahnya masih ada pembuat
salinan dan Whisper.
"""

import os
import re
import unittest
from pathlib import Path

from app.services import reframe

AKAR = Path(__file__).resolve().parents[2]
SUMBER = AKAR / "backend" / "app" / "services"


class UtasDibatasi(unittest.TestCase):
    def test_menyisakan_utas_untuk_mesinnya(self):
        self.assertLessEqual(reframe.INTI_ANALISIS, max(2, (os.cpu_count() or 4) - 2))
        self.assertGreaterEqual(reframe.INTI_ANALISIS, 2)

    def test_latar_memakai_lebih_sedikit_lagi(self):
        depan = reframe.inti_analisis()
        with reframe.di_latar():
            latar = reframe.inti_analisis()
        self.assertLess(latar, depan, "pekerjaan latar tidak lebih mengalah")
        self.assertGreaterEqual(latar, 1)
        # Kembali seperti semula sesudah bloknya selesai.
        self.assertEqual(reframe.inti_analisis(), depan)

    def test_ffmpeg_pemindai_membawa_batas_utas(self):
        teks = (SUMBER / "reframe.py").read_text(encoding="utf-8")
        badan = teks.split("def _sample_frames")[1].split("\nclass ")[0]
        self.assertIn('"-threads", str(inti_analisis())', badan)
        # Dan di latar ia berjalan dengan prioritas terendah.
        self.assertIn("rendah=_latar.get()", badan)

    def test_opencv_juga_dibatasi(self):
        teks = (SUMBER / "reframe.py").read_text(encoding="utf-8")
        self.assertIn("cv2.setNumThreads(inti_analisis())", teks)

    def test_pemanasan_seluruhnya_pekerjaan_latar(self):
        teks = (SUMBER / "bingkai_awal.py").read_text(encoding="utf-8")
        pembungkus = teks.split("def run_bingkai_awal")[1].split("\ndef ")[0]
        self.assertIn("reframe.di_latar()", pembungkus)
        self.assertIn("_jalankan(ctx)", pembungkus)


class PemanasanBawaannyaMati(unittest.TestCase):
    """
    Diminta pemiliknya: "ubah aturan auto bingkai nonaktif secara default...
    tapi bisa kita aktifkan jika kita mau pada menu bingkai".
    """

    def test_sakelar_bawaannya_mati(self):
        teks = (SUMBER / "pipeline.py").read_text(encoding="utf-8")
        badan = teks.split("def pemanasan_bingkai")[1].split("\ndef ")[0]
        self.assertIn('return nilai == "1"', badan)
        self.assertIn("return False", badan)

    def test_membuka_proyek_tidak_menyalakannya_diam_diam(self):
        teks = (AKAR / "frontend" / "src" / "features" / "studio"
                / "Editor.jsx").read_text(encoding="utf-8")
        self.assertIn("r?.pemanasan_bingkai !== true", teks)

    def test_panel_bingkai_tidak_menebak_menyala(self):
        teks = (AKAR / "frontend" / "src" / "features" / "studio"
                / "FramePanel.jsx").read_text(encoding="utf-8")
        self.assertIn("r?.pemanasan_bingkai === true", teks)
        self.assertNotIn("pemanasan_bingkai !== false", teks)

    def test_tombol_manual_tetap_ada_saat_sakelarnya_mati(self):
        teks = (AKAR / "frontend" / "src" / "features" / "studio"
                / "FramePanel.jsx").read_text(encoding="utf-8")
        self.assertNotIn("{videoId && menyala && (", teks,
                         "tombol siapkan manual hilang saat sakelarnya mati")
        self.assertIn("{videoId && (", teks)

    def test_permintaan_langsung_memaksa(self):
        """Tanpa ini, tombolnya berhenti di klip pertama karena sakelarnya mati."""
        teks = (AKAR / "backend" / "app" / "routers" / "clips.py").read_text(encoding="utf-8")
        badan = teks.split("async def siapkan_bingkai")[1].split("\n@router")[0]
        self.assertIn("paksa=True", badan)
        pekerjaan = (SUMBER / "bingkai_awal.py").read_text(encoding="utf-8")
        self.assertIn("if not (paksa or pemanasan_bingkai())", pekerjaan)


class SalinanAnalisisTidakBerebut(unittest.TestCase):
    def test_pembuat_salinan_memakai_sedikit_inti(self):
        from app.services import proksi
        self.assertLessEqual(proksi.INTI, 2)
        self.assertLessEqual(proksi.INTI_DITUNGGU, max(2, (os.cpu_count() or 4)))


class BingkaiTersimpanSelamanya(unittest.TestCase):
    """
    Bingkai yang sudah dihitung tidak boleh hilang saat aplikasi ditutup.

    Diminta pemiliknya berkali-kali. Terbukti pada 27 September 2026: dihitung
    35,1 detik di satu proses, lalu di proses yang BARU (simpanan memori kosong)
    permintaan yang sama dijawab 0,00 detik dari basis data.
    """

    def test_tanpa_batas_umur(self):
        teks = (AKAR / "backend" / "app" / "routers" / "clips.py").read_text(encoding="utf-8")
        badan = teks.split("def _reframe_tersimpan")[1].split("\ndef ")[0]
        self.assertIn('ttl=float("inf")', badan)

    def test_tidak_ikut_disapu_pembersih(self):
        teks = (AKAR / "backend" / "app" / "repos" / "cache.py").read_text(encoding="utf-8")
        badan = teks.split("def bersihkan")[1]
        for awalan in ("bingkai:", "jenis:", "facecam:", "sutradara:", "tema:"):
            with self.subTest(awalan=awalan):
                self.assertIn(f"NOT LIKE '{awalan}%'", badan)

    def test_disimpan_ke_basis_data_bukan_hanya_memori(self):
        teks = (AKAR / "backend" / "app" / "routers" / "clips.py").read_text(encoding="utf-8")
        badan = teks.split("def _simpan_reframe")[1].split("\ndef ")[0]
        self.assertIn("cache_repo.simpan", badan)
        self.assertIn("_simpan_memori", badan)


if __name__ == "__main__":
    unittest.main()
