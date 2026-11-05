"""Cuplikan pembuka (JOB-5 O4)."""

import unittest
from unittest import mock

from app.montase import pembuka as P

F = 30
DOK = {"kanvas": {"fps": F}, "bahan": {"b2": {"jenis": "video", "durasi": 15}}, "lajur": [
    {"id": "V", "jenis": "video", "item": [
        {"id": "v1", "jenis": "video", "bahan": "b1", "mulai": 60, "durasi": 240, "potong_awal": 30},
        {"id": "v2", "jenis": "video", "bahan": "b2", "mulai": 360, "durasi": 240, "potong_awal": 90},
    ]},
    {"id": "M", "jenis": "motion", "item": []},
]}


class Pembuka(unittest.TestCase):
    def test_momen_terkuat_di_rentang_yang_dipakai(self):
        # t dalam detik BAHAN (seluruh bahan dianalisis); yang di luar rentang dipakai dibuang.
        hasil = {"b1": [{"t": 2.0, "jenis": ["tawa"], "kuat": 0.6}],
                 "b2": [{"t": 8.0, "jenis": ["kejut"], "kuat": 0.9}, {"t": 1.0, "jenis": ["x"], "kuat": 1.0}]}
        jalur = {"b1": "/b1.mp4", "b2": "/b2.mp4"}
        with mock.patch("app.montase.bahan.jalur_asli", side_effect=lambda pid, b: jalur[b]), \
             mock.patch.object(P.repo, "ambil_bahan", return_value={"durasi": 15}), \
             mock.patch("app.services.momen.cari_momen",
                        side_effect=lambda j, seg, dengar: hasil["b1" if "b1" in str(j) else "b2"]):
            m = P.pilih_momen(1, DOK)
        self.assertEqual((m["item"]["id"], m["detik_bahan"]), ("v2", 8.0))

    def test_operasi_geser_klip_teks(self):
        m = {"item": DOK["lajur"][0]["item"][1], "detik_bahan": 8.0, "kuat": 0.9, "jenis": ["kejut"]}
        ops = P.susun_operasi(DOK, m, bahan_info={}, bahasa="en")
        self.assertEqual([o["jenis"] for o in ops], ["geser_semua", "klip", "teks"])
        self.assertEqual(ops[0]["delta"], 60)
        self.assertEqual((ops[1]["mulai"], ops[1]["potong_awal"], ops[1]["durasi"]), (0, round(7.3 * F), 60))
        self.assertEqual(ops[2]["teks"], "Wait for this moment!")
        self.assertEqual(ops[1]["bahan_info"]["durasi"], 15)

    def test_tanpa_momen_dari_klip_terakhir(self):
        ops = P.susun_operasi(DOK, None, bahan_info={}, bahasa="id")
        self.assertEqual((ops[1]["bahan"], ops[1]["potong_awal"]), ("b2", 90))


if __name__ == "__main__":
    unittest.main()
