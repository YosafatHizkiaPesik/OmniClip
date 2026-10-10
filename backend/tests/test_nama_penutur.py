"""JOB-2 F2-2: nama penutur disimpan sekali per video."""

import asyncio
import unittest

from app.db import run_migrations
from app.routers import clips


class NamaPenutur(unittest.TestCase):
    def setUp(self):
        run_migrations()

    def test_simpan_lalu_baca(self):
        req = clips.NamaPenuturModel(nama={"0": "  Windah   Basudara ", "1": "Ilham",
                                           "9": "terlalu besar", "x": "bukan nomor", "2": "  "})
        self.assertEqual(req.nama, {"0": "Windah Basudara", "1": "Ilham"})
        asyncio.run(clips.simpan_nama_penutur("BDjxWMVLqJE", req))
        r = asyncio.run(clips.nama_penutur("BDjxWMVLqJE"))
        self.assertEqual(r["nama"], {"0": "Windah Basudara", "1": "Ilham"})

    def test_video_lain_kosong(self):
        self.assertEqual(asyncio.run(clips.nama_penutur("aaaaaaaaaaa"))["nama"], {})


if __name__ == "__main__":
    unittest.main()
