"""Bilah progres retensi: model permintaan dan graf render."""

import inspect
import unittest

from app.routers.clips import BilahProgresModel, RenderClipRequest
from app.services import render


class Bilah(unittest.TestCase):
    def test_model(self):
        self.assertEqual(BilahProgresModel().posisi, "bawah")
        with self.assertRaises(Exception):
            BilahProgresModel(posisi="kiri")
        with self.assertRaises(Exception):
            BilahProgresModel(warna="kuning")
        r = RenderClipRequest(source_path="abc", bilah_progres={"posisi": "atas"})
        self.assertEqual(r.bilah_progres.posisi, "atas")

    def test_overlay_dievaluasi_per_bingkai(self):
        # drawbox di ffmpeg 6.1 tidak mengevaluasi `t` per bingkai: bilahnya
        # harus overlay yang digeser dengan eval=frame.
        kode = inspect.getsource(render.render_clip)
        self.assertIn("eval=frame", kode)
        self.assertIn("bilah_progres", kode)


if __name__ == "__main__":
    unittest.main()
