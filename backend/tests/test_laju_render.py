"""
Laju bingkai hasil render.

Sampai 5 Oktober 2026 dipatok 30 di tiga tempat terpisah, dan alasannya masuk
akal: sumber 60 fps membawa dua kali bingkai yang dibutuhkan melewati setiap
crop, scale, dan blur, lalu separuhnya dibuang begitu sampai ke pengode.

Yang tidak ikut dihitung: apa yang hilang. Untuk klip gameplay, separuh laju
bingkai adalah kehilangan mutu yang paling kelihatan — jauh lebih terasa
daripada bitrate. Dilaporkan pemiliknya sesudah mengunggah beberapa video:
"kualitasnya jelek meskipun sudah ada tulisan SD dan HD". Terukur pada klip
jadinya: 1080x1920 dan 13,7 Mbps, tapi 30 fps dari sumber 60 fps.
"""

import unittest
from pathlib import Path

from app.services import render

AKAR = Path(__file__).resolve().parents[2]


class LajuRender(unittest.TestCase):
    def setUp(self):
        from app.db import run_migrations
        run_migrations()
        from app.repos import settings as repo
        repo.set_value("render.fps", "")

    def _setel(self, nilai):
        from app.repos import settings as repo
        repo.set_value("render.fps", nilai)

    def test_bawaannya_ikut_sumber(self):
        self.assertEqual(render.laju_render(60), 60)
        self.assertEqual(render.laju_render(30), 30)
        self.assertEqual(render.laju_render(50), 50)

    def test_bisa_dipatok_tiga_puluh(self):
        self._setel("30")
        self.assertEqual(render.laju_render(60), 30)

    def test_sumber_yang_sangat_cepat_dijepit(self):
        """Di atas 60 tidak ada platform video pendek yang peduli."""
        self.assertEqual(render.laju_render(120), render.LAJU_MAKS)

    def test_sumber_yang_sangat_lambat_dinaikkan(self):
        self.assertEqual(render.laju_render(8), render.LAJU_MIN)

    def test_laju_yang_tidak_terbaca_memakai_tiga_puluh(self):
        """
        Menebak terlalu tinggi berarti ffmpeg menggandakan bingkai: berkasnya
        membesar tanpa satu pun gambar baru.
        """
        for v in (None, 0, -5, "entah", float("nan")):
            with self.subTest(v=v):
                self.assertEqual(render.laju_render(v), 30)

    def test_tidak_ada_lagi_tiga_puluh_yang_dipatok(self):
        """
        Tiga tempat dulu menulis 30 masing-masing: pemotongan, linimasa
        bingkai, dan pengode. Satu yang tertinggal berarti hasilnya diam-diam
        kembali ke 30 untuk sebagian klip.
        """
        teks = (AKAR / "backend" / "app" / "services" / "render.py").read_text(
            encoding="utf-8")
        self.assertNotIn("fps=30[v", teks)
        self.assertNotIn('"-r", "30"', teks)
        self.assertIn('f"fps={fps}[v{i}]"', teks)
        self.assertIn('"-r", str(fps_keluar)', teks)

    def test_keyframe_ikut_lajunya(self):
        """`-g` tetap dua detik: keyframe tiap 60 bingkai pada 30 fps itu dua
        detik, pada 60 fps baru satu."""
        teks = (AKAR / "backend" / "app" / "services" / "render.py").read_text(
            encoding="utf-8")
        self.assertIn('"-g", str(fps_keluar * 2)', teks)


if __name__ == "__main__":
    unittest.main()
