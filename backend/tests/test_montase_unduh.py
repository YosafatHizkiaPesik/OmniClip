"""
JOB-4 M0.4: Node portabel diunduh, diperiksa SHA-256-nya, lalu dibongkar.

Tidak menyentuh jaringan: `urlopen` diganti arsip buatan sendiri.
"""

import hashlib
import io
import re
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.montase import unduh


def _arsip_node(isi: bytes = b"#!/bin/sh\necho v22.23.4\n") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:xz") as t:
        info = tarfile.TarInfo(f"node-v{unduh.VERSI_NODE}-linux-x64/bin/node")
        info.size = len(isi)
        info.mode = 0o755
        t.addfile(info, io.BytesIO(isi))
    return buf.getvalue()


class _Respons(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Sumber(unittest.TestCase):
    def test_versi_dan_hash_dipatok(self):
        for (sistem, _), (url, sha, dalam) in unduh.SUMBER_NODE.items():
            self.assertIn(f"v{unduh.VERSI_NODE}/", url)
            self.assertIn(unduh.VERSI_NODE, dalam)
            self.assertRegex(sha, r"^[0-9a-f]{64}$")
            self.assertTrue(url.startswith("https://nodejs.org/dist/"))
        self.assertEqual({s for s, _ in unduh.SUMBER_NODE}, {"linux", "windows"})


class Pasang(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data = _arsip_node()
        sha = hashlib.sha256(self.data).hexdigest()
        url = f"https://nodejs.org/dist/v{unduh.VERSI_NODE}/node-v{unduh.VERSI_NODE}-linux-x64.tar.xz"
        self._p = [
            mock.patch.object(unduh, "folder", return_value=Path(self._tmp.name)),
            mock.patch.object(unduh, "_platform", return_value=("linux", "x86_64")),
            mock.patch.dict(unduh.SUMBER_NODE, {("linux", "x86_64"): (
                url, sha, f"node-v{unduh.VERSI_NODE}-linux-x64/bin/node")}),
        ]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()
        self._tmp.cleanup()

    def test_terpasang_dan_kemajuan_dilaporkan(self):
        kabar = []
        with mock.patch("urllib.request.urlopen", return_value=_Respons(self.data)):
            jalur = unduh.pasang_node(kabar.append)
        self.assertTrue(Path(jalur).is_file())
        self.assertEqual(jalur, unduh.jalur_node_terunduh())
        self.assertAlmostEqual(kabar[-1], 1.0)
        # Tidak ada sisa folder sementara.
        self.assertEqual([p.name for p in Path(self._tmp.name).iterdir()],
                         [f"node-v{unduh.VERSI_NODE}"])

    def test_hash_tidak_cocok_ditolak_tanpa_sisa(self):
        with mock.patch("urllib.request.urlopen", return_value=_Respons(_arsip_node(b"lain"))):
            with self.assertRaisesRegex(unduh.GagalUnduh, "SHA-256"):
                unduh.pasang_node()
        self.assertIsNone(unduh.jalur_node_terunduh())
        self.assertEqual(list(Path(self._tmp.name).iterdir()), [])

    def test_sudah_ada_tidak_diunduh_lagi(self):
        with mock.patch("urllib.request.urlopen", return_value=_Respons(self.data)):
            unduh.pasang_node()
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("diunduh lagi")):
            self.assertTrue(unduh.pasang_node())


class PlatformTakDikenal(unittest.TestCase):
    def test_pesan_jelas(self):
        with mock.patch.object(unduh, "_platform", return_value=("darwin", "arm64")):
            self.assertIsNone(unduh.jalur_node_terunduh())
            with self.assertRaisesRegex(unduh.GagalUnduh, "belum tersedia"):
                unduh.pasang_node()


if __name__ == "__main__":
    unittest.main()
