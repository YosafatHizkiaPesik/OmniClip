"""
JOB-2 F0-5: batas unggahan YouTube per hari, sebagai penjadwalan.

Sampai 9 Oktober 2026 tidak ada batas apa pun selain jeda 90 detik antar
unggahan. Kanal baru yang menerbitkan sepuluh video dalam sehari adalah pola
"produksi massal" yang disebut kebijakan konten yang digunakan ulang.
"""

import json
import time
import unittest
import uuid
from datetime import datetime, timedelta

from app.db import run_migrations, tx
from app.services import unggah

PID = 9901


def tanam(status="done", target="youtube", mulai=0.0, dibuat=None, pid=PID):
    """Satu baris job unggah, langsung di tabel, seperti yang ditulis antrean."""
    with tx() as c:
        c.execute(
            "INSERT INTO jobs (id, type, status, lane, payload_json, created_at, mulai_setelah) "
            "VALUES (?, 'upload', ?, 'upload', ?, ?, ?)",
            (f"uji-{uuid.uuid4().hex[:10]}", status,
             json.dumps({"profil_id": pid, "target": target}),
             dibuat if dibuat is not None else time.time(), mulai))


class BatasHarian(unittest.TestCase):
    def setUp(self):
        run_migrations()
        self.addCleanup(self._bersihkan)
        self.kini = datetime.combine(datetime.now().date(), datetime.min.time()).timestamp() + 14 * 3600

    def _bersihkan(self):
        with tx() as c:
            c.execute("DELETE FROM jobs WHERE id LIKE 'uji-%'")

    def test_jatah_masih_ada_tidak_digeser(self):
        tanam(dibuat=self.kini - 600)
        self.assertEqual(unggah.slot_harian(PID, 0.0, 3, sekarang=self.kini), 0.0)

    def test_jatah_habis_pindah_ke_besok_pukul_sepuluh(self):
        for _ in range(3):
            tanam(dibuat=self.kini - 600)
        t = unggah.slot_harian(PID, 0.0, 3, sekarang=self.kini)
        besok = datetime.fromtimestamp(self.kini).date() + timedelta(days=1)
        self.assertEqual(datetime.fromtimestamp(t).date(), besok)
        self.assertEqual(datetime.fromtimestamp(t).hour, unggah.JAM_PINDAH_HARI)

    def test_besok_juga_penuh_pindah_ke_lusa(self):
        for _ in range(3):
            tanam(dibuat=self.kini - 600)
        besok10 = self.kini + 20 * 3600
        for _ in range(3):
            tanam(status="queued", mulai=besok10, dibuat=self.kini - 60)
        t = unggah.slot_harian(PID, 0.0, 3, sekarang=self.kini)
        lusa = datetime.fromtimestamp(self.kini).date() + timedelta(days=2)
        self.assertEqual(datetime.fromtimestamp(t).date(), lusa)

    def test_yang_gagal_dan_dibatalkan_tidak_memakai_jatah(self):
        """Keduanya tidak pernah tayang."""
        tanam(status="failed", dibuat=self.kini - 600)
        tanam(status="cancelled", dibuat=self.kini - 600)
        tanam(status="failed", dibuat=self.kini - 600)
        self.assertEqual(unggah.slot_harian(PID, 0.0, 3, sekarang=self.kini), 0.0)

    def test_drive_tidak_memakai_jatah_youtube(self):
        for _ in range(5):
            tanam(target="drive", dibuat=self.kini - 600)
        self.assertEqual(unggah.slot_harian(PID, 0.0, 3, sekarang=self.kini), 0.0)

    def test_jatah_profil_lain_tidak_terhitung(self):
        for _ in range(5):
            tanam(dibuat=self.kini - 600, pid=9902)
        self.assertEqual(unggah.slot_harian(PID, 0.0, 3, sekarang=self.kini), 0.0)

    def test_nol_berarti_tidak_dibatasi(self):
        for _ in range(10):
            tanam(dibuat=self.kini - 600)
        self.assertEqual(unggah.slot_harian(PID, 0.0, 0, sekarang=self.kini), 0.0)

    def test_jadwal_yang_sudah_diminta_dihormati_bila_harinya_masih_ada_jatah(self):
        """Jarak jam dari profil (`jadwal_jam`) tetap berlaku di dalam jatahnya."""
        nanti = self.kini + 2 * 3600
        self.assertEqual(unggah.slot_harian(PID, nanti, 3, sekarang=self.kini), nanti)

    def test_bawaan_profil_tiga(self):
        from app.services.profil import UNGGAH_BAWAAN
        self.assertEqual(UNGGAH_BAWAAN["batas_harian"], 3)

    def test_berlaku_untuk_unggahan_manual_juga(self):
        """Dipasang di `antrekan`, satu-satunya pintu untuk kedua jalur."""
        from pathlib import Path
        src = Path(unggah.__file__).read_text(encoding="utf-8")
        awal = src.index("def antrekan(")
        badan = src[awal:src.index("def sumber_klip(")]
        self.assertIn("slot_harian(pid, mulai_setelah, batas)", badan)


class SetelanUnggahTidakDibuangDiamDiam(unittest.TestCase):
    """
    Setiap setelan unggah bawaan harus diterima model PATCH profil.

    pydantic membuang medan yang tidak dikenalnya tanpa suara. Itu sebabnya
    pilihan "Berjarak N jam" di layar tidak pernah tersimpan sekali pun:
    `jadwal_jam` ada di UNGGAH_BAWAAN dan di layar, tapi tidak di model. Uji ini
    menangkap setelan baru mana pun yang lupa didaftarkan dengan cara yang sama.
    """

    def test_semua_setelan_bawaan_diterima(self):
        from app.routers.profil import UnggahModel
        from app.services.profil import UNGGAH_BAWAAN
        diterima = set(UnggahModel.model_fields)
        hilang = sorted(set(UNGGAH_BAWAAN) - diterima)
        self.assertEqual(hilang, [], f"setelan dibuang diam-diam oleh PATCH: {hilang}")

    def test_jadwal_jam_tersimpan(self):
        from app.routers.profil import UnggahModel
        m = UnggahModel(jadwal_jam=6, batas_harian=2, kredit=False)
        self.assertEqual(m.model_dump(exclude_none=True),
                         {"jadwal_jam": 6.0, "batas_harian": 2, "kredit": False})
