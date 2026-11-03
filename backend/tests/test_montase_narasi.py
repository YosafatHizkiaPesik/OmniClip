"""JOB-4 M3.3: narasi TTS dan rekaman mikrofon menjadi bahan audio."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.db import get_conn, run_migrations
from app.montase import bahan as bahan_svc
from app.montase import narasi
from app.services import profil, tts

PID = 987_621


def _bersihkan():
    c = get_conn()
    for (rel,) in c.execute("SELECT rel_path FROM montase_bahan WHERE profil_id = ?", (PID,)).fetchall():
        p = narasi.media_repo.abs_from_storage(rel)
        if p.is_relative_to(narasi.folder()):
            p.unlink(missing_ok=True)
    c.execute("DELETE FROM montase_bahan WHERE profil_id = ?", (PID,))


def _bunyi(teks, jalur, rate=1.0, voice=None):
    """Pengganti tts.synthesize: nada 1 detik, tanpa jaringan dan model."""
    jalur.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=1", str(jalur)], check=True)
    return 1.0


class Narasi(unittest.TestCase):
    def setUp(self):
        run_migrations()
        _bersihkan()
        self.addCleanup(_bersihkan)
        tanda = profil.setel(PID)
        self.addCleanup(profil.pulihkan, tanda)
        p = mock.patch.object(bahan_svc, "_jadwalkan_persiapan")
        p.start()
        self.addCleanup(p.stop)

    def test_narasi_jadi_bahan_audio_dan_dipakai_ulang(self):
        with mock.patch.object(tts, "edge_available", return_value=True), \
             mock.patch.object(tts, "synthesize", side_effect=_bunyi) as s:
            a = narasi.buat_narasi(PID, "Ini  momen nomor lima.", "edge-ardi")
            b = narasi.buat_narasi(PID, "Ini momen nomor lima.", "edge-ardi")
            c = narasi.buat_narasi(PID, "Ini momen nomor empat.", "edge-ardi")
        self.assertEqual(s.call_count, 2)
        self.assertEqual(a["id"], b["id"])
        self.assertNotEqual(a["id"], c["id"])
        self.assertEqual((a["asal"], a["jenis"], a["ada_suara"]), ("tts", "audio", True))
        self.assertAlmostEqual(a["durasi"], 1.0, delta=0.1)

    def test_teks_kosong_dan_suara_belum_terpasang_ditolak_dengan_alasan(self):
        with self.assertRaisesRegex(narasi.GagalNarasi, "kosong"):
            narasi.buat_narasi(PID, "   ", "edge-ardi")
        with mock.patch.object(tts, "available", return_value=False):
            with self.assertRaisesRegex(narasi.GagalNarasi, "belum terpasang"):
                narasi.buat_narasi(PID, "halo", "piper-news")

    def test_rekaman_jadi_m4a_dan_terhapus_bersama_bahannya(self):
        with tempfile.TemporaryDirectory() as d:
            webm = Path(d) / "r.webm"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            "sine=frequency=300:duration=1.5", "-c:a", "libopus", str(webm)], check=True)
            b = narasi.simpan_rekaman(PID, webm, "Rekaman 1")
        jalur = bahan_svc.jalur_asli(PID, b["id"])
        self.assertEqual(jalur.suffix, ".m4a")
        self.assertEqual(b["asal"], "rekam")
        bahan_svc.hapus(PID, b["id"])
        self.assertFalse(jalur.exists())


if __name__ == "__main__":
    unittest.main()
