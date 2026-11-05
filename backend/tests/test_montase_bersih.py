"""Sampah Montase (JOB-4 M6.5): hanya yang bisa dibuktikan tidak berguna."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from app.montase import bersih


def _tua(p: Path):
    t = time.time() - 2 * bersih.DIAM
    os.utime(p, (t, t))


class Bersih(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.akar = Path(self.tmp.name) / "montase"
        for d in ("render", "periksa", "bahan", "suara", "komponen"):
            (self.akar / d).mkdir(parents=True)
        self.sumber = Path(self.tmp.name) / "klip.mp4"
        self.sumber.write_bytes(b"x")
        self.bahan = [
            {"id": "bh_ada", "profil_id": 1, "asal": "klip_jadi", "rel_path": str(self.sumber)},
            {"id": "bh_hilang", "profil_id": 1, "asal": "klip_jadi", "rel_path": str(Path(self.tmp.name) / "hilang.mp4")},
            {"id": "bh_hilang_dipakai", "profil_id": 1, "asal": "unduhan", "rel_path": "/tidak/ada.mp4"},
            {"id": "bh_tts", "profil_id": 1, "asal": "tts", "rel_path": "montase/suara/narasi_a.wav"},
        ]
        for i in ("bh_ada", "bh_hilang", "bh_hilang_dipakai", "bh_dihapus"):
            (self.akar / "bahan" / i).mkdir()
            (self.akar / "bahan" / i / "strip.jpg").write_bytes(b"12345")
        for n in ("narasi_a.wav", "narasi_b.wav"):
            f = self.akar / "suara" / n
            f.write_bytes(b"w")
            _tua(f)
        for n in ("km_ada", "km_hapus"):
            (self.akar / "komponen" / n).mkdir()
        mulai = self.akar / "render" / "mt_lama.mp4"
        mulai.write_bytes(b"r")
        _tua(mulai)
        (self.akar / "render" / "mt_jalan.mp4").write_bytes(b"r")
        kerja = self.akar / "periksa" / "periksa_abc"
        kerja.mkdir()
        _tua(kerja)
        for nama, nilai in (("semua_bahan_ringkas", self.bahan), ("bahan_dipakai_semua", {"bh_hilang_dipakai"}),
                            ("semua_id_komponen", {"km_ada"})):
            q = mock.patch.object(bersih.repo, nama, return_value=nilai)
            q.start()
            self.addCleanup(q.stop)
        q = mock.patch("app.repos.media.abs_from_storage", side_effect=lambda r: Path(r))
        q.start()
        self.addCleanup(q.stop)

    def test_sementara_hanya_yang_diam(self):
        self.assertEqual(sorted(t["nama"] for t in bersih.sementara(self.akar)), ["mt_lama.mp4", "periksa_abc"])

    def test_yatim(self):
        nama = sorted(t["nama"] for t in bersih.yatim(self.akar))
        # bh_ada (berkas masih ada) dan bh_hilang_dipakai (masih dipakai proyek) tidak disentuh;
        # narasi_a.wav masih dirujuk bahan tts.
        self.assertEqual(nama, ["bh_dihapus", "bh_hilang", "km_hapus", "narasi_b.wav"])
        self.assertTrue(all(t["ukuran"] >= 0 for t in bersih.yatim(self.akar)))

    def test_rapikan_membuang_baris_bahan_yang_sumbernya_hilang(self):
        hapus = []
        c = mock.MagicMock()
        c.execute.side_effect = lambda sql, arg: hapus.append(arg[0])
        tx = mock.MagicMock()
        tx.return_value.__enter__.return_value = c
        with mock.patch("app.db.tx", tx):
            n = bersih.rapikan([str(self.akar / "bahan" / "bh_hilang"), str(self.akar / "bahan" / "bh_ada")], self.akar)
        self.assertEqual((n, hapus), (1, ["bh_hilang"]))


if __name__ == "__main__":
    unittest.main()
