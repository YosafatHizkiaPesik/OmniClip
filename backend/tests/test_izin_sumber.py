"""
JOB-2 F0-3: peringatan izin kanal sumber, tanpa memblokir apa pun.

Pemilik menjawab 9 Oktober 2026: belum ada izin dari kreator mana pun yang ia
klip. Yang dibutuhkannya adalah tahu risikonya saat menekan tombol unggah, dan
tempat untuk mencatat izin begitu izin itu didapat.
"""

import unittest
from pathlib import Path

from app.services import izin

MIAWAUG = {"kanal": "MiawAug", "channel_id": "UC3J4Q1grz46bdJ7NJLd4DGw"}
MIAWAUG_LAMA = {"kanal": "MiawAug", "channel_id": ""}     # baris videos sebelum F0-1


class Setelan(unittest.TestCase):
    def setUp(self):
        from app.repos import settings as repo
        self.nilai = {}
        self.asli = (repo.get, repo.set_value)
        repo.get = lambda n, b=None: self.nilai.get(n, b)
        repo.set_value = lambda n, v: self.nilai.__setitem__(n, v)
        self.addCleanup(self._pulihkan)

    def _pulihkan(self):
        from app.repos import settings as repo
        repo.get, repo.set_value = self.asli


class StatusIzin(Setelan):
    def test_bawaannya_belum(self):
        self.assertEqual(izin.status(MIAWAUG), izin.BELUM)

    def test_sumber_tak_dikenal_selalu_belum(self):
        self.assertEqual(izin.status({}), izin.BELUM)
        self.assertEqual(izin.status(None), izin.BELUM)

    def test_dicatat_jadi_diizinkan(self):
        izin.setel(MIAWAUG, True)
        self.assertEqual(izin.status(MIAWAUG), izin.DIIZINKAN)

    def test_izin_terbaca_untuk_baris_lama_tanpa_nomor_kanal(self):
        """
        Baris `videos` sebelum F0-1 tidak punya nomor kanal. Izin yang dicatat
        dari klip baru harus tetap terbaca untuk klip lama dari kanal yang sama.
        """
        izin.setel(MIAWAUG, True)
        self.assertEqual(izin.status(MIAWAUG_LAMA), izin.DIIZINKAN)

    def test_nama_kanal_tidak_peka_huruf_besar(self):
        izin.setel(MIAWAUG, True)
        self.assertEqual(izin.status({"kanal": "miawaug"}), izin.DIIZINKAN)

    def test_izin_bisa_dicabut(self):
        izin.setel(MIAWAUG, True)
        izin.setel(MIAWAUG, False)
        self.assertEqual(izin.status(MIAWAUG), izin.BELUM)

    def test_izin_satu_kanal_tidak_menyeberang(self):
        izin.setel(MIAWAUG, True)
        self.assertEqual(izin.status({"kanal": "Ferry Irwandi"}), izin.BELUM)

    def test_sumber_tak_dikenal_tidak_bisa_dicatat(self):
        with self.assertRaises(ValueError):
            izin.setel({}, True)


class Peringatan(Setelan):
    def test_menyebut_kanal_dan_akibatnya(self):
        p = izin.peringatan(MIAWAUG)
        self.assertIn("MiawAug", p)
        self.assertIn("Content ID", p)

    def test_hilang_begitu_izin_dicatat(self):
        izin.setel(MIAWAUG, True)
        self.assertEqual(izin.peringatan(MIAWAUG), "")


class TidakMemblokir(unittest.TestCase):
    """Janji yang paling penting di sini: peringatan, bukan penghalang."""

    def test_jalur_unggah_tidak_memeriksa_izin(self):
        from app.services import unggah
        src = Path(unggah.__file__).read_text(encoding="utf-8")
        self.assertNotIn("izin.status", src)
        self.assertNotIn("from . import izin", src)

    def test_peringatan_tampil_di_dua_tempat_unggah(self):
        for berkas in ("UploadModal.jsx", "SiapkanTerbit.jsx"):
            src = Path(f"../frontend/src/components/{berkas}").read_text(encoding="utf-8")
            self.assertIn("<PeringatanIzin clipName={clip.file_name} />", src, berkas)
