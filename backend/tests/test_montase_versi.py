"""Riwayat versi proyek Montase (JOB-4 M6.4)."""

import unittest
from unittest import mock

from app.db import get_conn, run_migrations
from app.errors import AppError
from app.montase import router
from app.repos import montase as repo
from app.services import profil

PID = 987_644


def _bersihkan():
    c = get_conn()
    c.execute("DELETE FROM montase_proyek WHERE profil_id = ?", (PID,))
    c.execute("DELETE FROM montase_proyek_versi WHERE profil_id = ?", (PID,))


class Versi(unittest.TestCase):
    def setUp(self):
        run_migrations()
        _bersihkan()
        self.addCleanup(_bersihkan)
        tanda = profil.setel(PID)
        self.addCleanup(profil.pulihkan, tanda)
        self.p = router.buat_proyek(router.ProyekBaru(nama="Uji versi", preset="shorts"))
        self.jam = [1_000_000.0]
        j = mock.patch("app.repos.montase.now", side_effect=lambda: self.jam[0])
        j.start()
        self.addCleanup(j.stop)

    def _simpan(self, nama, maju=30.0):
        self.jam[0] += maju
        d = router.ambil_proyek(self.p["id"])
        dok = {**d["dokumen"], "nama": nama}
        return router.simpan_proyek(self.p["id"], router.SimpanProyek(dokumen=dok, revisi=d["revisi"]))

    def test_dipotret_paling_sering_dua_menit_sekali_dan_hanya_sepuluh(self):
        for n in range(40):                     # 40 simpanan, 30 detik sekali = 20 menit
            self._simpan(f"v{n}")
        v = router.daftar_versi(self.p["id"])["versi"]
        self.assertEqual(len(v), repo.VERSI_SIMPAN)
        jarak = [a["created_at"] - b["created_at"] for a, b in zip(v, v[1:])]
        self.assertTrue(all(j >= repo.JEDA_VERSI for j in jarak), jarak)

    def test_pulihkan_memotret_keadaan_sekarang_dulu(self):
        self._simpan("pertama")
        self._simpan("kedua", maju=300)
        v = router.daftar_versi(self.p["id"])["versi"]
        lama = next(x for x in v if repo.ambil_versi(PID, self.p["id"], x["id"])["dokumen"]["nama"] == "pertama")
        kini = router.ambil_proyek(self.p["id"])
        r = router.pulihkan_versi(self.p["id"], lama["id"], router.Pulihkan(revisi=kini["revisi"]))
        self.assertEqual(r["dokumen"]["nama"], "pertama")
        self.assertEqual(router.ambil_proyek(self.p["id"])["dokumen"]["nama"], "pertama")
        v2 = router.daftar_versi(self.p["id"])["versi"]
        self.assertEqual(v2[0]["alasan"], "sebelum_pulihkan")
        self.assertEqual(repo.ambil_versi(PID, self.p["id"], v2[0]["id"])["dokumen"]["nama"], "kedua")
        with self.assertRaises(AppError) as e:           # revisi lama: 409
            router.pulihkan_versi(self.p["id"], lama["id"], router.Pulihkan(revisi=kini["revisi"]))
        self.assertEqual(e.exception.status, 409)

    def test_hapus_proyek_menghapus_versinya(self):
        self._simpan("x")
        router.hapus_proyek(self.p["id"])
        self.assertEqual(get_conn().execute("SELECT COUNT(*) FROM montase_proyek_versi WHERE profil_id = ?",
                                            (PID,)).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
