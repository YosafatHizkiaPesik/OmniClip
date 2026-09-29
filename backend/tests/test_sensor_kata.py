"""
Kata kasar di subtitle ditutup satu huruf di tengahnya.

Diminta pemiliknya 29 September 2026, lengkap dengan contohnya: "anjing"
menjadi "anj*ng". Alasannya praktis: klip yang teksnya memuat umpatan utuh
diturunkan jangkauannya oleh YouTube, TikTok, dan Instagram.

Suaranya tidak disentuh; yang disensor hanya teks yang terbakar di layar.
"""

import re
import unittest
from pathlib import Path

from app.services import sensor
from app.services.subtitles import build_ass

AKAR = Path(__file__).resolve().parents[2]
JS = AKAR / "frontend" / "src" / "lib" / "sensor.js"


class BentuknyaSepertiYangDiminta(unittest.TestCase):
    def test_contoh_dari_pemiliknya(self):
        self.assertEqual(sensor.sensor_teks("anjing"), "anj*ng")

    def test_besar_kecil_huruf_dipertahankan(self):
        self.assertEqual(sensor.sensor_teks("ANJING"), "ANJ*NG")
        self.assertEqual(sensor.sensor_teks("Anjing"), "Anj*ng")

    def test_akhiran_ikut_tertangkap(self):
        self.assertEqual(sensor.sensor_teks("anjingnya"), "anj*ngnya")
        self.assertEqual(sensor.sensor_teks("goblokmu"), "gob*okmu")

    def test_hanya_satu_huruf_yang_ditutup(self):
        for kata in sensor.DAFTAR_KASAR:
            with self.subTest(kata=kata):
                hasil = sensor.sensor_teks(kata)
                self.assertEqual(hasil.count("*"), 1, hasil)
                self.assertEqual(len(hasil), len(kata))
                # Huruf pertama dan terakhir tetap terbaca.
                self.assertEqual(hasil[0], kata[0])
                self.assertEqual(hasil[-1], kata[-1])

    def test_kata_utuhnya_tidak_tersisa(self):
        for kata in sensor.DAFTAR_KASAR:
            with self.subTest(kata=kata):
                self.assertNotIn(kata, sensor.sensor_teks(f"dia bilang {kata} tadi"))


class KataWajarTidakDisentuh(unittest.TestCase):
    """Subtitle yang penuh bintang lebih buruk daripada satu umpatan yang lolos."""

    # Termasuk umpatan RINGAN yang sengaja dibiarkan atas keputusan pemiliknya:
    # "babi", "cok", "cuk", "anjir", "bodoh", "bego", "setan", "gila".
    WAJAR = ("kita main bola", "sianida", "bodoh banget", "setan alas",
             "babi ngepet", "cok ayo berangkat", "anjir serem", "gila sih",
             "kontestan", "taikonaut", "assume", "shitake", "classic",
             "asuransi jiwa", "perekonomian", "pantekan listrik",
             "kolintang", "koleksi baju", "bokeh kamera", "toko kelontong",
             "jalan raya", "kentang goreng", "titik temu", "jembatan",
             "pusat kota", "silitonga")

    def test_tidak_ada_bintang(self):
        for kalimat in self.WAJAR:
            with self.subTest(kalimat=kalimat):
                self.assertEqual(sensor.sensor_teks(kalimat), kalimat)


class TerpakaiSaatMerender(unittest.TestCase):
    BARIS = [{"start": 0.0, "end": 2.0, "text": "dasar anjing goblok",
              "words": [{"w": "dasar", "s": 0.0, "e": 0.5},
                        {"w": "anjing", "s": 0.6, "e": 1.1},
                        {"w": "goblok", "s": 1.2, "e": 1.9}]}]

    def test_bawaannya_menyala(self):
        ass = build_ass(lines=self.BARIS, clip_duration=2.0)
        self.assertIn("ANJ*NG", ass)
        self.assertNotIn("ANJING", ass)
        self.assertIn("GOB*OK", ass)

    def test_bisa_dimatikan(self):
        ass = build_ass(lines=self.BARIS, clip_duration=2.0, sensor=False)
        self.assertIn("ANJING", ass)

    def test_kata_lain_tidak_berubah(self):
        ass = build_ass(lines=self.BARIS, clip_duration=2.0)
        self.assertIn("DASAR", ass)

    def test_dikerjakan_sekali_di_satu_tempat(self):
        """Tiga jalur teks, satu penyensor: itu yang menjaga ketiganya sama."""
        teks = (AKAR / "backend" / "app" / "services" / "subtitles.py").read_text(
            encoding="utf-8")
        self.assertEqual(teks.count("from .sensor import"), 1)


class PratinjauDanRenderMemakaiDaftarYangSama(unittest.TestCase):
    """
    Pratinjau menyensor di peramban, render menyensor di server. Dua salinan
    daftar berarti keduanya bisa bergeser sendiri-sendiri, dan bedanya baru
    ketahuan sesudah merender.
    """

    def test_daftarnya_sama_persis(self):
        js = JS.read_text(encoding="utf-8")
        blok = js.split("export const DAFTAR_KASAR = [")[1].split("];")[0]
        dari_js = tuple(re.findall(r"'([^']+)'", blok))
        self.assertEqual(dari_js, sensor.DAFTAR_KASAR)

    def test_akhirannya_sama(self):
        js = JS.read_text(encoding="utf-8")
        blok = js.split("const AKHIRAN = [")[1].split("];")[0]
        self.assertEqual(tuple(re.findall(r"'([^']+)'", blok)), sensor._AKHIRAN)

    def test_pratinjau_memakainya(self):
        teks = (AKAR / "frontend" / "src" / "features" / "studio"
                / "ClipPreview.jsx").read_text(encoding="utf-8")
        self.assertIn("sensorTeks", teks)


if __name__ == "__main__":
    unittest.main()
