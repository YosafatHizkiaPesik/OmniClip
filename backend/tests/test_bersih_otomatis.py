"""
Pembersihan otomatis video mentah dan klip jadi (diminta 28 Oktober 2026).
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HARI = 86400


class AturanPembersihan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.unduh = Path(self.tmp.name) / "unduh"
        self.unduh.mkdir()
        self.kini = 1_800_000_000.0
        self.simpan = {}
        from app.services import bersih_otomatis as bo
        self.bo = bo
        self.tambal = [
            mock.patch("app.config.DOWNLOAD_DIR", self.unduh),
            mock.patch("app.repos.settings.get", side_effect=lambda k, d="": self.simpan.get(k, d)),
            mock.patch("app.repos.settings.set_value", side_effect=lambda k, v: self.simpan.__setitem__(k, v)),
            mock.patch.object(bo, "_unggahan_tertunda", return_value=set()),
            mock.patch("app.services.proksi._nama", side_effect=lambda p: p.with_suffix(".proksi")),
        ]
        for t in self.tambal:
            t.start()

    def tearDown(self):
        for t in self.tambal:
            t.stop()
        self.tmp.cleanup()

    def _video(self, vid, umur_hari):
        f = self.unduh / f"Judul_{vid}.mp4"
        f.write_bytes(b"x" * 1000)
        t = self.kini - umur_hari * HARI
        os.utime(f, (t, t))
        return f

    def _rencana(self, akhir=None, sibuk=(), klip=()):
        with mock.patch.object(self.bo, "_aktivitas", return_value=(dict(akhir or {}), set(sibuk))), \
             mock.patch.object(self.bo, "_klip_semua_profil", return_value=list(klip)):
            return self.bo.rencana(self.kini)

    def test_diam_30_hari_dibuang(self):
        self._video("aaaaaaaaaaa", 40)
        r = self._rencana()
        self.assertEqual([s["alasan"] for s in r["sumber"]], ["diam"])

    def test_baru_tidak_dibuang(self):
        self._video("bbbbbbbbbbb", 3)
        self.assertEqual(self._rencana()["sumber"], [])

    def test_aktivitas_suntingan_menyelamatkan(self):
        self._video("ccccccccccc", 60)
        r = self._rencana(akhir={"ccccccccccc": self.kini - 2 * HARI})
        self.assertEqual(r["sumber"], [])

    def test_proyek_selesai_dibuang_lebih_cepat(self):
        self._video("ddddddddddd", 10)
        klip = [{"path": Path("/x/k.mp4"), "berkas": "k.mp4", "video_id": "ddddddddddd",
                 "ukuran": 5, "waktu": self.kini - 10 * HARI, "profil": "A"}]
        r = self._rencana(klip=klip)
        self.assertEqual([s["alasan"] for s in r["sumber"]], ["selesai"])
        self.assertEqual(r["klip"], [])        # klipnya sendiri baru 10 hari

    def test_sedang_dikerjakan_tidak_disentuh(self):
        self._video("eeeeeeeeeee", 90)
        self.assertEqual(self._rencana(sibuk={"eeeeeeeeeee"})["sumber"], [])

    def test_klip_diam_dibuang(self):
        klip = [{"path": Path("/x/k.mp4"), "berkas": "k.mp4", "video_id": "fffffffffff",
                 "ukuran": 5, "waktu": self.kini - 45 * HARI, "profil": "A"}]
        self.assertEqual(len(self._rencana(klip=klip)["klip"]), 1)

    def test_putaran_otomatis_menunggu_persetujuan(self):
        f = self._video("ggggggggggg", 40)
        with mock.patch.object(self.bo, "_aktivitas", return_value=({}, set())), \
             mock.patch.object(self.bo, "_klip_semua_profil", return_value=[]):
            h = self.bo.jalankan(self.kini)
            self.assertTrue(h["lewat"])
            self.assertTrue(f.exists())
            h = self.bo.jalankan(self.kini, paksa=True)
        self.assertEqual(h["dibuang"], 1)
        self.assertFalse(f.exists())
        self.assertEqual(self.simpan.get("bersih.disetujui"), "1")

    def test_mati_tidak_membuang(self):
        self._video("hhhhhhhhhhh", 40)
        self.simpan["bersih.sumber"] = "0"
        self.assertEqual(self._rencana()["sumber"], [])


if __name__ == "__main__":
    unittest.main()
