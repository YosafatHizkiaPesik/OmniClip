"""
Beranda yang disiapkan di latar (15 Oktober 2026).

Dilaporkan pemiliknya: memuat beranda lama. Halaman kini meminta benih yang
berandanya sudah jadi di singgahan, dan kolam kuerinya deterministik per benih
supaya singgahan itu benar-benar kena.
"""

import asyncio
import random
import unittest
from unittest import mock


class KolamDeterministik(unittest.TestCase):
    def kolam(self, benih):
        from app.routers.videos import _kolam_beranda
        with mock.patch("app.repos.profil.ambil", return_value={"minat": ["horor"]}), \
             mock.patch("app.repos.profil.kueri_sering", return_value=[]), \
             mock.patch("app.repos.profil.riwayat_cari", return_value=[]), \
             mock.patch("app.services.profil.kini", return_value=1):
            return _kolam_beranda(random.Random(f"kolam:{benih}"))

    def test_benih_sama_kolam_sama(self):
        """Tanpa ini kunci singgahan beranda berubah di tiap permintaan."""
        self.assertEqual(self.kolam(42), self.kolam(42))


class BenihSiap(unittest.TestCase):
    def jalankan(self, simpanan):
        from app.routers import videos
        tersimpan = {}

        async def siapkan(pid, tunda=0.0, wilayah="ID"):
            return None

        with mock.patch.object(videos.cache_repo, "ambil", return_value=simpanan), \
             mock.patch.object(videos.cache_repo, "simpan",
                               side_effect=lambda k, v: tersimpan.__setitem__(k, v)), \
             mock.patch.object(videos, "_siapkan_beranda", siapkan), \
             mock.patch("app.services.profil.kini", return_value=1):
            hasil = asyncio.run(videos.benih_beranda())
        return hasil, tersimpan

    def test_benih_yang_siap_dipakai_lebih_dulu(self):
        hasil, tersimpan = self.jalankan([5, 7])
        self.assertEqual(hasil, {"benih": 5, "siap": True})
        self.assertEqual(tersimpan.get("beranda.benih:1"), [7])

    def test_tanpa_benih_siap_tetap_memberi_benih(self):
        hasil, _ = self.jalankan(None)
        self.assertFalse(hasil["siap"])
        self.assertIsInstance(hasil["benih"], int)


if __name__ == "__main__":
    unittest.main()
