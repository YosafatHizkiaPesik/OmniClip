"""
JOB-2 F0-6: kategori YouTube dipilih per klip, bukan dikunci 22.

Sampai 9 Oktober 2026 setiap unggahan masuk People & Blogs (22), termasuk
klip gameplay.
"""

import unittest
from pathlib import Path

from app.services import unggah


class Kategori(unittest.TestCase):
    def setUp(self):
        import app.services.analitik as an
        import app.services.profil as pr
        self.asli = (an._sidecar, pr.unggah)
        self.meta, self.setel = {}, {"kategori": "otomatis"}
        an._sidecar = lambda c, p: self.meta
        pr.unggah = lambda p: self.setel
        self.addCleanup(self._pulihkan)

    def _pulihkan(self):
        import app.services.analitik as an
        import app.services.profil as pr
        an._sidecar, pr.unggah = self.asli

    def test_gameplay_masuk_game(self):
        self.meta = {"frame_mode": "gaming"}
        self.assertEqual(unggah.kategori_youtube("x.mp4", 1), "20")

    def test_selain_gameplay_masuk_hiburan(self):
        self.meta = {"frame_mode": "smart"}
        self.assertEqual(unggah.kategori_youtube("x.mp4", 1), "24")

    def test_tanpa_sidecar_masuk_hiburan(self):
        self.meta = {}
        self.assertEqual(unggah.kategori_youtube("x.mp4", 1), "24")

    def test_pilihan_profil_menang(self):
        self.setel = {"kategori": "23"}
        self.meta = {"frame_mode": "gaming"}
        self.assertEqual(unggah.kategori_youtube("x.mp4", 1), "23")

    def test_pilihan_tak_dikenal_kembali_otomatis(self):
        self.setel = {"kategori": "99"}
        self.meta = {"frame_mode": "gaming"}
        self.assertEqual(unggah.kategori_youtube("x.mp4", 1), "20")


class TidakLagiDikunci(unittest.TestCase):
    def test_bukan_22_yang_dikunci(self):
        from app.services import google_upload
        src = Path(google_upload.__file__).read_text(encoding="utf-8")
        self.assertNotIn('"categoryId": "22"', src)
        self.assertIn('"categoryId": str(category_id or "24")', src)

    def test_diteruskan_dari_antrean_ke_api(self):
        p = Path("app/services/pipeline.py").read_text(encoding="utf-8")
        self.assertIn('category_id=ctx.payload.get("kategori") or "24"', p)
        u = Path(unggah.__file__).read_text(encoding="utf-8")
        self.assertIn('"kategori": kategori_youtube(clip_name, pid)', u)
