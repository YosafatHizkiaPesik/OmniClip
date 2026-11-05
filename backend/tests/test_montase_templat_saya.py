"""Templat milik sendiri (JOB-5 P4)."""

import unittest

from app.db import run_migrations
from app.errors import AppError
from app.montase import router
from app.repos import settings as settings_repo
from app.services import profil

PID = 987_678

KERANGKA = {
    "kanvas": {"lebar": 1080, "tinggi": 1920, "fps": 30}, "detik": 45, "caption": "stiker",
    "isi": [{"jenis": "teks", "teks": "REAKSI", "mulai": 0, "durasi": 3, "gaya": {"font": "Anton"}},
            {"jenis": "animasi", "komponen": "ko_label_nama", "versi": 1, "props": {}, "mulai": 3.5, "durasi": 4}],
    "penanda": [{"t": 0, "label": "Taruh video"}],
}


class TemplatSaya(unittest.TestCase):
    def setUp(self):
        run_migrations()
        tanda = profil.setel(PID)
        self.addCleanup(profil.pulihkan, tanda)
        self.addCleanup(settings_repo.delete, router._kunci_templat(PID))

    def test_simpan_timpa_hapus_per_profil(self):
        r = router.simpan_templat_saya(router.TemplatSaya(nama=" Reaksi kanal ", **KERANGKA))
        self.assertEqual(r["templat"][0]["nama"], "Reaksi kanal")
        self.assertEqual(r["templat"][0]["caption"], "stiker")
        router.simpan_templat_saya(router.TemplatSaya(nama="Lain", **KERANGKA))
        r = router.simpan_templat_saya(router.TemplatSaya(nama="reaksi KANAL", **{**KERANGKA, "caption": "neon"}))
        self.assertEqual([t["nama"] for t in r["templat"]], ["reaksi KANAL", "Lain"])
        self.assertEqual(router.daftar_templat_saya()["templat"][0]["caption"], "neon")
        r = router.hapus_templat_saya(r["templat"][1]["id"])
        self.assertEqual([t["nama"] for t in r["templat"]], ["reaksi KANAL"])
        tanda = profil.setel(PID + 1)
        try:
            self.assertEqual(router.daftar_templat_saya()["templat"], [])
        finally:
            profil.pulihkan(tanda)

    def test_bahan_kosong_dan_raksasa_ditolak(self):
        klip = {**KERANGKA, "isi": [{"jenis": "video", "bahan": "b1", "mulai": 0, "durasi": 3}]}
        with self.assertRaises(AppError):
            router.simpan_templat_saya(router.TemplatSaya(nama="x", **klip))
        with self.assertRaises(AppError):
            router.simpan_templat_saya(router.TemplatSaya(nama="x", isi=[], penanda=[]))
        besar = {**KERANGKA, "isi": [{"jenis": "teks", "teks": "x" * 3000, "mulai": 0, "durasi": 1}] * 100}
        with self.assertRaises(AppError):
            router.simpan_templat_saya(router.TemplatSaya(nama="x", **besar))

    def test_batas_jumlah(self):
        for k in range(router.TEMPLAT_SAYA_MAKS + 3):
            r = router.simpan_templat_saya(router.TemplatSaya(nama=f"T{k}", **KERANGKA))
        self.assertEqual(len(r["templat"]), router.TEMPLAT_SAYA_MAKS)
        self.assertEqual(r["templat"][0]["nama"], f"T{router.TEMPLAT_SAYA_MAKS + 2}")


if __name__ == "__main__":
    unittest.main()
