"""
JOB-2 F0-7: label "konten diubah atau sintetis" saat klip memuat suara TTS.

`status.containsSyntheticMedia` ada di YouTube Data API sejak 30 Oktober 2024
(diperiksa di riwayat revisi API 9 Oktober 2026). Tanpa medan itu API tidak
mengeluh, jadi unggahan lewat API diam-diam tidak pernah berlabel, padahal
OmniClip sudah memakai suara sintetis hari ini: kartu judul bersuara.
"""

import unittest
from pathlib import Path

from app.services import unggah


class Label(unittest.TestCase):
    def setUp(self):
        import app.services.analitik as an
        import app.services.profil as pr
        self.asli = (an._sidecar, pr.unggah)
        self.meta, self.setel = {}, {}
        an._sidecar = lambda c, p: self.meta
        pr.unggah = lambda p: self.setel
        self.addCleanup(self._pulihkan)

    def _pulihkan(self):
        import app.services.analitik as an
        import app.services.profil as pr
        an._sidecar, pr.unggah = self.asli

    def test_suara_sintetis_berlabel(self):
        self.meta = {"suara_sintetis": True}
        self.assertTrue(unggah.label_sintetis("x.mp4", 1))

    def test_tanpa_suara_sintetis_tidak_berlabel(self):
        self.meta = {"suara_sintetis": False}
        self.assertFalse(unggah.label_sintetis("x.mp4", 1))

    def test_klip_lama_tanpa_catatan_tidak_berlabel(self):
        """Klip sebelum F0-7 tidak mencatatnya; yang tidak diketahui tidak dikarang."""
        self.meta = {}
        self.assertFalse(unggah.label_sintetis("x.mp4", 1))

    def test_profil_bisa_mematikan(self):
        self.meta = {"suara_sintetis": True}
        self.setel = {"label_sintetis": False}
        self.assertFalse(unggah.label_sintetis("x.mp4", 1))


class SampaiKeApi(unittest.TestCase):
    def test_medan_api_dikirim(self):
        from app.services import google_upload
        src = Path(google_upload.__file__).read_text(encoding="utf-8")
        self.assertIn('"containsSyntheticMedia": bool(sintetis)', src)

    def test_diteruskan_dari_antrean(self):
        p = Path("app/services/pipeline.py").read_text(encoding="utf-8")
        self.assertIn('sintetis=bool(ctx.payload.get("sintetis"))', p)

    def test_sidecar_mencatat_suara_yang_benar_terbentuk(self):
        """Disetel bukan berarti terbentuk: TTS bisa gagal dan kartu tetap jadi."""
        from app.services import render
        src = Path(render.__file__).read_text(encoding="utf-8")
        self.assertIn('"suara_sintetis": bool(card is not None and card.wav_path)', src)
