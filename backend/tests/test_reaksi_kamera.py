"""Reaksi kamera pemilik kanal: rekaman, peredaman suara klip, nilai tambah."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.services import komentar as km
from app.services import nilai_tambah as nt
from app.services.render import build_sisipan_graph


class Simpan(unittest.TestCase):
    def test_webm_jadi_aset_mp4(self):
        with tempfile.TemporaryDirectory() as d:
            webm = Path(d) / "r.webm"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                            "testsrc=s=640x480:d=2:r=15", "-f", "lavfi", "-i", "sine=d=2",
                            "-c:v", "libvpx", "-c:a", "libopus", "-shortest", str(webm)], check=True)
            asetdir = Path(d) / "aset"
            with mock.patch("app.services.aset.ASET_DIR", asetdir), \
                 mock.patch.object(km, "SUARA_DIR", Path(d) / "suara"):
                a = km.simpan_reaksi(webm)
        self.assertEqual(a["jenis"], "video")
        self.assertTrue(a["punya_suara"])
        self.assertAlmostEqual(a["durasi"], 2.0, delta=0.3)
        self.assertTrue(a["berkas"].endswith(".mp4"))


class Redam(unittest.TestCase):
    def lapis(self, **lain):
        return {"jenis": "video", "path": Path("/x.mp4"), "punya_suara": True, "t": 2.0,
                "dur": 3.0, "mulai": 0.0, "volume": 1.0, "posisi": "sudut", "rect": None,
                "isi": "penuh", "opasitas": 1.0, "fade_masuk": 0, "fade_keluar": 0,
                "ulang": False, "redam": False, **lain}

    def test_suara_klip_diredam_selama_reaksi(self):
        _, graf, _, _ = build_sisipan_graph([self.lapis(redam_utama=True)], "[v]", "[a]",
                                            input_awal=1, out_w=1080, out_h=1920)
        self.assertIn("[sutama0]volume=volume=", graf)

    def test_tanpa_tanda_tidak_diredam(self):
        _, graf, _, _ = build_sisipan_graph([self.lapis()], "[v]", "[a]",
                                            input_awal=1, out_w=1080, out_h=1920)
        self.assertNotIn("[sutamaR]", graf)


class NilaiTambah(unittest.TestCase):
    def test_reaksi_dihitung_seperti_komentar(self):
        h = nt.hitung({"duration": 30, "media_layers": [
            {"t": 0, "dur": 6, "asal": "reaksi"}, {"t": 10, "dur": 4, "asal": "pengguna"}]})
        self.assertEqual(h["detik_komentar"], 6.0)
        self.assertEqual(h["detik_sisipan"], 4.0)
        self.assertTrue(h["cukup"])
        self.assertIn("reaksi kamera 6.0 detik", h["rincian"])


if __name__ == "__main__":
    unittest.main()
