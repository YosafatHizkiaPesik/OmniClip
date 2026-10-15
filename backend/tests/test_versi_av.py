"""
PyAV dan faster-whisper harus sepakat soal `av.open(metadata_errors=...)`.

PyAV 19 menghapus argumen itu; faster-whisper 1.2.1 masih memakainya untuk
setiap transkrip lokal. Uji ini membaca audio sungguhan lewat jalur yang sama
dengan pipeline, jadi kombinasi versi yang rusak ketahuan sebelum dirilis.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path


class VersiAV(unittest.TestCase):
    def test_requirements_mengunci_av_di_bawah_19(self):
        teks = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text()
        self.assertRegex(teks, r"(?m)^av>=[\d.]+,<19\s*$")

    def test_decode_audio_faster_whisper_jalan(self):
        from faster_whisper.audio import decode_audio
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "a.wav"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                            "sine=frequency=440:duration=1", str(wav)], check=True)
            x = decode_audio(str(wav))
        self.assertGreater(len(x), 15000)


if __name__ == "__main__":
    unittest.main()
