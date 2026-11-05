"""Cadangan basis data membawa proyek, versi, bahan, dan pustaka animasi Montase (JOB-4 M6.6)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.db import get_conn, run_migrations
from app.montase import router
from app.repos import montase as repo
from app.services import pemeliharaan, profil

PID = 987_655


def _bersihkan():
    c = get_conn()
    for t in ("montase_proyek", "montase_proyek_versi", "montase_komponen"):
        c.execute(f"DELETE FROM {t} WHERE profil_id = ?", (PID,))


class Cadangan(unittest.TestCase):
    def setUp(self):
        run_migrations()
        _bersihkan()
        self.addCleanup(_bersihkan)
        tanda = profil.setel(PID)
        self.addCleanup(profil.pulihkan, tanda)

    def test_isi_montase_ada_di_cadangan(self):
        p = router.buat_proyek(router.ProyekBaru(nama="Proyek dicadangkan", preset="shorts"))
        repo.catat_versi(PID, p["id"], 1, router.ambil_proyek(p["id"])["dokumen"], alasan="ekspor", paksa=True)
        k = repo.catat_komponen(PID, {"id": None, "nama": "Animasi saya", "asal": "ai",
                                      "sumber_tsx": "export default () => null;", "status": "lolos"})
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(pemeliharaan, "FOLDER_CADANGAN", Path(d)):
            hasil = pemeliharaan.cadangkan()
            c = sqlite3.connect(str(Path(d) / hasil["berkas"]))
            try:
                nama = c.execute("SELECT nama FROM montase_proyek WHERE id = ?", (p["id"],)).fetchone()
                versi = c.execute("SELECT COUNT(*) FROM montase_proyek_versi WHERE proyek_id = ?",
                                  (p["id"],)).fetchone()
                anim = c.execute("SELECT sumber_tsx FROM montase_komponen WHERE id = ?", (k["id"],)).fetchone()
            finally:
                c.close()
        self.assertEqual(nama[0], "Proyek dicadangkan")
        self.assertEqual(versi[0], 1)
        self.assertIn("export default", anim[0])


if __name__ == "__main__":
    unittest.main()
