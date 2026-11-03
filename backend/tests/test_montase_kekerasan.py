"""JOB-4 M3.9: hasil ekspor diratakan ke -14 LUFS, gambar tidak dikode ulang."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from app.montase import kekerasan


def _buat(jalur: Path, volume: str, suara: bool = True):
    masukan = ["-f", "lavfi", "-i", "color=c=red:s=160x120:r=30:d=4"]
    if suara:
        masukan += ["-f", "lavfi", "-i", f"sine=frequency=440:duration=4,volume={volume}"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *masukan, "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", *(["-c:a", "aac"] if suara else []), "-shortest", str(jalur)],
                   check=True)


def _hash_video(jalur: Path) -> str:
    return subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(jalur), "-map", "0:v",
                           "-c", "copy", "-f", "hash", "-"], capture_output=True, text=True).stdout


class Kekerasan(unittest.TestCase):
    def test_pelan_dinaikkan_ke_minus_14_dan_gambar_utuh(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "a.mp4"
            _buat(v, "0.05")
            gambar = _hash_video(v)
            hasil = kekerasan.ratakan(v)
            self.assertTrue(hasil["diratakan"], hasil)
            self.assertLess(hasil["lufs_awal"], -25)
            akhir = float(kekerasan.ukur(v)["input_i"])
            self.assertAlmostEqual(akhir, -14, delta=1.0)
            self.assertEqual(_hash_video(v), gambar)

    def test_tanpa_suara_dibiarkan(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "b.mp4"
            _buat(v, "1", suara=False)
            self.assertEqual(kekerasan.ratakan(v), {"diratakan": False, "alasan": "tanpa suara"})


if __name__ == "__main__":
    unittest.main()
