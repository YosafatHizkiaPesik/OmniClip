"""JOB-3 J3-7: filter jenis pencarian, kode sama dengan youtube.com."""

import base64
import unittest
from urllib.parse import unquote

from app.services.ytdlp import sp_pencarian


def bait(sp):
    return base64.b64decode(unquote(sp))


class Jenis(unittest.TestCase):
    def test_shorts_sama_dengan_youtube(self):
        self.assertEqual(unquote(sp_pencarian(jenis="shorts")), "EgIQCQ==")

    def test_live_memuat_fitur_siaran(self):
        self.assertIn(bytes([0x40, 0x01]), bait(sp_pencarian(jenis="live")))

    def test_digabung_dengan_durasi_dan_urutan(self):
        b = bait(sp_pencarian(sort="terbaru", durasi="pendek", jenis="shorts"))
        self.assertTrue(b.startswith(bytes([0x08, 0x02])))
        self.assertIn(bytes([0x10, 0x09]), b)
        self.assertIn(bytes([0x18, 0x01]), b)
        self.assertNotIn(bytes([0x10, 0x01]), b)

    def test_tanpa_saring_tetap_kosong(self):
        self.assertIsNone(sp_pencarian())


if __name__ == "__main__":
    unittest.main()
