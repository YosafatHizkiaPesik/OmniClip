"""Rekam reaksi kamera (JOB-5 O5): WebM -> MP4 bahan rekam, dihitung seperti komentar."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.db import get_conn, run_migrations
from app.montase import narasi
from app.services import nilai_tambah, profil

PID = 987_666


class Reaksi(unittest.TestCase):
    def setUp(self):
        run_migrations()
        self.addCleanup(lambda: get_conn().execute("DELETE FROM montase_bahan WHERE profil_id = ?", (PID,)))
        tanda = profil.setel(PID)
        self.addCleanup(profil.pulihkan, tanda)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(narasi, "folder", return_value=Path(self.tmp.name) / "suara")
        p.start()
        self.addCleanup(p.stop)
        q = mock.patch("app.montase.bahan._jadwalkan_persiapan")
        q.start()
        self.addCleanup(q.stop)

    def test_webm_jadi_bahan_video_rekam(self):
        webm = Path(self.tmp.name) / "r.webm"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=2",
                        "-f", "lavfi", "-i", "sine=d=2", "-c:v", "libvpx", "-b:v", "300k", "-c:a", "libopus",
                        "-shortest", str(webm)], check=True)
        with mock.patch("app.services.media.rel_to_storage" if False else "app.repos.media.rel_to_storage",
                        side_effect=lambda p: str(p)):
            b = narasi.simpan_reaksi(PID, webm, "Reaksi saya")
        self.assertEqual((b["asal"], b["jenis"], b["lebar"], b["ada_suara"]), ("rekam", "video", 640, True))
        self.assertAlmostEqual(b["durasi"], 2.0, delta=0.2)

    def test_berkas_rusak_ditolak(self):
        rusak = Path(self.tmp.name) / "x.webm"
        rusak.write_bytes(b"bukan video")
        with self.assertRaises(narasi.GagalNarasi):
            narasi.simpan_reaksi(PID, rusak, "x")

    def test_reaksi_dihitung_penuh_dan_memenuhi_wajib_narasi(self):
        h = nilai_tambah.hitung({"jenis": "montase", "duration": 30, "sumber_banyak": [{"judul": "a"}],
                                 "lapisan": [{"t": 0, "d": 6, "jenis": "reaksi"}]})
        self.assertEqual((h["detik_komentar"], h["cukup"]), (6.0, True))


if __name__ == "__main__":
    unittest.main()
