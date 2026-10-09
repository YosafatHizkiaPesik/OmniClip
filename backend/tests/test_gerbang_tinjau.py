"""
JOB-2 F0-4: gerbang tinjau sebelum sebuah klip naik PUBLIK.

Sampai 9 Oktober 2026 render yang dimulai orang langsung diunggah publik oleh
`unggah.setelah_render`, tanpa `fyp.periksa`, tanpa kredit, tanpa batas. Itu
persis "zero-touch generation" yang ditolak kebijakan YouTube untuk konten
yang digunakan ulang.
"""

import unittest
from pathlib import Path

from app.services import gerbang

SUMBER = {"judul": "Video Asli", "kanal": "Kanal", "url": "https://youtu.be/x"}


def klip_sehat(**lain):
    meta = {
        "duration": 30.0, "title": "Judul klip", "hook_text": "Kenapa dia marah",
        "hashtags": ["#a", "#b", "#c"],
        "subtitles": [{"start": 0.2, "end": 29.5, "text": "pertanyaan yang aneh",
                       "words": [{"w": "pertanyaan", "s": 0.2, "e": 0.8}]}],
    }
    meta.update(lain)
    return meta


class Nilai(unittest.TestCase):
    def test_klip_sehat_dengan_kredit_lolos(self):
        h = gerbang.nilai(klip_sehat(), sumber=SUMBER)
        self.assertTrue(h["lolos"], h["alasan"])

    def test_tanpa_kredit_tidak_lolos(self):
        h = gerbang.nilai(klip_sehat(), sumber={})
        self.assertFalse(h["lolos"])
        self.assertTrue(any("sumber" in a for a in h["alasan"]))

    def test_kredit_dimatikan_tidak_lolos(self):
        h = gerbang.nilai(klip_sehat(), sumber=SUMBER, pakai_kredit=False)
        self.assertFalse(h["lolos"])

    def test_temuan_berat_tidak_lolos(self):
        """Terlalu pendek: salah satu temuan BERAT dari fyp.periksa."""
        h = gerbang.nilai(klip_sehat(duration=4.0), sumber=SUMBER)
        self.assertFalse(h["lolos"])

    def test_tanpa_sidecar_tidak_lolos(self):
        h = gerbang.nilai(None, sumber=SUMBER)
        self.assertFalse(h["lolos"])

    def test_alasannya_bisa_dibaca_orang(self):
        h = gerbang.nilai(klip_sehat(duration=4.0), sumber={})
        for a in h["alasan"]:
            self.assertTrue(a.endswith("."), a)
            self.assertNotIn("_", a, "kode internal bocor ke kalimat untuk orang")


class TidakDibuangHanyaDiturunkan(unittest.TestCase):
    """Yang tidak lolos tetap naik, sebagai private, dengan alasannya."""

    def test_unggah_otomatis_menurunkan_ke_private(self):
        from app.services import unggah
        src = Path(unggah.__file__).read_text(encoding="utf-8")
        awal = src.index('if target == "youtube" and privasi == "public":')
        blok = src[awal:awal + 900]
        self.assertIn('privasi = "private"', blok)
        self.assertIn("catatan_gerbang = g[\"alasan\"]", blok)
        self.assertIn("privacy=privasi", src)

    def test_hanya_publik_yang_digerbangi(self):
        """Private dan unlisted tidak pernah tayang di beranda siapa pun."""
        from app.services import unggah
        src = Path(unggah.__file__).read_text(encoding="utf-8")
        self.assertIn('privasi == "public"', src)

    def test_penurunan_dikatakan_di_layar(self):
        src = Path("app/services/pipeline.py").read_text(encoding="utf-8")
        self.assertIn("Diunggah sebagai PRIVATE, belum lolos tinjau", src)
        editor = Path("../frontend/src/features/studio/Editor.jsx").read_text(encoding="utf-8")
        self.assertIn("sebagai PRIVATE, belum lolos tinjau", editor)

    def test_formulir_manual_tidak_mengubah_pilihan_orang(self):
        """Orang yang menekan tombolnya sedang meninjau; ia hanya diberi alasan."""
        src = Path("../frontend/src/components/UploadModal.jsx").read_text(encoding="utf-8")
        self.assertIn("Di sini Anda tetap bisa menerbitkannya publik.", src)
        self.assertNotIn("setPrivacy('private')", src)
