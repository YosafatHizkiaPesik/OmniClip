"""
Daftar klip boleh diurutkan dari nilai tertinggi, tanpa mengubah nomornya.

Diminta pemiliknya 9 Oktober 2026: "saya tidak ingin banyak video klip untuk
satu video jadi saya mengambil klip dengan rating tertinggi... tapi ingat bahwa
default bawaannya masih sama seperti saat ini yang mengurutkan sesuai dengan
timestamp video raw jadi filter ini hanya aktif jika user mau".
"""

import unittest
from pathlib import Path

SUMBER = Path("../frontend/src/features/studio/Editor.jsx")


class UrutanNilai(unittest.TestCase):
    def setUp(self):
        self.src = SUMBER.read_text(encoding="utf-8")

    def test_bawaannya_tetap_urutan_waktu(self):
        """Yang diminta pemiliknya dengan tegas: bawaannya tidak berubah."""
        self.assertIn("const [urutNilai, setUrutNilai] = useState(false)", self.src)

    def test_mengurutkan_dari_tertinggi(self):
        self.assertIn("(Number(b.clip.score) || 0) - (Number(a.clip.score) || 0)", self.src)

    def test_nomor_klip_tidak_ikut_berubah(self):
        """
        Nomor klip ikut urutan waktu, dan nama berkas hasil render memakai
        nomor itu. Kalau nomornya ikut diurutkan, "klip 3" berarti dua klip
        berbeda tergantung sakelarnya.
        """
        self.assertIn("klipTampil.map(({ clip, i })", self.src)
        self.assertIn("clips.map((clip, i) => ({ clip, i }))", self.src)

    def test_sakelarnya_ada_di_layar(self):
        self.assertIn("setUrutNilai((v) => !v)", self.src)


class SkorAdaDiDataKlip(unittest.TestCase):
    """Yang diurutkan harus benar-benar ada di tiap klip."""

    def test_skor_ikut_disimpan(self):
        from app.services.clipmodel import build_clip_payload
        import inspect
        self.assertIn("score", inspect.getsource(build_clip_payload))
