"""Preset teks milik sendiri (JOB-5 P2)."""

import unittest

from app.db import run_migrations
from app.errors import AppError
from app.montase import router
from app.repos import settings as settings_repo
from app.services import profil

PID = 987_677


class PresetTeks(unittest.TestCase):
    def setUp(self):
        run_migrations()
        tanda = profil.setel(PID)
        self.addCleanup(profil.pulihkan, tanda)
        self.addCleanup(settings_repo.delete, router._kunci_preset(PID))

    def test_simpan_timpa_hapus_per_profil(self):
        g = {"font": "Anton", "warna": "#FFE500", "ukuran": 120, "tema": "neon"}
        r = router.simpan_preset_teks(router.PresetTeks(nama="Judul kanal", gaya=g))
        self.assertEqual(len(r["preset"]), 1)
        self.assertNotIn("tema", r["preset"][0]["gaya"])
        router.simpan_preset_teks(router.PresetTeks(nama="Lain", gaya={"font": "Oswald"}))
        r = router.simpan_preset_teks(router.PresetTeks(nama="judul KANAL", gaya={"font": "Teko"}))
        self.assertEqual([p["nama"] for p in r["preset"]], ["judul KANAL", "Lain"])
        r = router.hapus_preset_teks(r["preset"][1]["id"])
        self.assertEqual([p["nama"] for p in r["preset"]], ["judul KANAL"])
        tanda = profil.setel(PID + 1)
        try:
            self.assertEqual(router.daftar_preset_teks()["preset"], [])
        finally:
            profil.pulihkan(tanda)

    def test_gaya_raksasa_ditolak(self):
        with self.assertRaises(AppError):
            router.simpan_preset_teks(router.PresetTeks(nama="x", gaya={"a": "x" * 5000}))


if __name__ == "__main__":
    unittest.main()
