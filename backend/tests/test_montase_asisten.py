"""Asisten penyunting Montase (JOB-4 M5.1-M5.3): rencana lokal/AI dan operasinya."""

import unittest
from unittest import mock

from app.montase import asisten_ai as A


def _r(bid, durasi, momen=(), hook="", judul=""):
    return {"id": bid, "nama": f"klip {bid}", "durasi": durasi, "judul": judul, "hook": hook,
            "kata": [{"w": "halo", "s": 0.1, "e": 0.4}], "transkrip": "[0.1] halo",
            "momen": [{"t": t, "jenis": list(j), "kuat": k} for t, j, k in momen],
            "info": {"jenis": "video", "nama": f"klip {bid}", "durasi": durasi, "lebar": 1080,
                     "tinggi": 1920, "fps": 30, "ada_suara": True}}


RINGKAS = [
    _r("b1", 12.0, [(3.0, ("tawa",), 0.5)], hook="Kucing jatuh dari meja"),
    _r("b2", 40.0, [(30.0, ("tawa", "tanpa_kata"), 0.9), (5.0, ("kejut",), 0.6)]),
    _r("b3", 8.0),
    _r("b4", 15.0, [(2.0, ("kejut",), 0.8)]),
    _r("b5", 10.0, [(1.0, ("tawa",), 0.3)]),
]
DOK = {"kanvas": {"lebar": 1080, "tinggi": 1920, "fps": 30},
       "lajur": [{"id": "v1", "jenis": "video", "item": [{"id": "i1", "mulai": 0, "durasi": 90}]}]}


class Perintah(unittest.TestCase):
    def test_jumlah_dan_minat(self):
        self.assertEqual(A.jumlah_diminta("susun Top 5 momen paling lucu"), 5)
        self.assertEqual(A.jumlah_diminta("3 momen terbaik"), 3)
        self.assertIsNone(A.jumlah_diminta("gabungkan semua klip"))
        self.assertIn("tawa", A.minat("yang paling lucu"))
        self.assertIn("kejut", A.minat("momen paling kaget"))


class RencanaLokal(unittest.TestCase):
    def test_top3_lucu_hitung_mundur_dari_skor_momen(self):
        r = A.rencana_lokal("Top 3 momen paling lucu", RINGKAS, maks=20, bahasa="id")
        urut = r["urutan"]
        self.assertEqual([s["peringkat"] for s in urut], [3, 2, 1])
        # Tawa dibobot dua kali: b2 (1,8 + 0,6) > b1 (1,0) > b4 (0,8) > b5 (0,6).
        self.assertEqual([s["bahan"] for s in urut], ["b4", "b1", "b2"])
        b2 = urut[-1]
        self.assertAlmostEqual(b2["sampai"] - b2["dari"], 20.0)
        self.assertLessEqual(b2["dari"], 30.0)
        self.assertGreaterEqual(b2["sampai"], 30.0)
        self.assertEqual(urut[1]["judul"], "Kucing jatuh dari meja")
        self.assertTrue(urut[0]["narasi"].startswith("Nomor 3."))
        self.assertIn("tawa", b2["alasan"])

    def test_tanpa_peringkat_mengikuti_urutan(self):
        r = A.rencana_lokal("gabungkan klip ini", RINGKAS[:3], maks=20, bahasa="en")
        self.assertEqual([s["peringkat"] for s in r["urutan"]], [None, None, None])


class BersihkanRencana(unittest.TestCase):
    def test_bahan_asing_ganda_dan_rentang_dibuang_atau_dipangkas(self):
        r = A.bersihkan_rencana({"judul": "x", "urutan": [
            {"bahan": "zzz", "dari": 0, "sampai": 5, "judul": "a", "alasan": ""},
            {"bahan": "b2", "dari": 10, "sampai": 99, "peringkat": 1, "judul": "b", "alasan": "c"},
            {"bahan": "b2", "dari": 0, "sampai": 5, "judul": "lagi", "alasan": ""},
            {"bahan": "b3", "dari": 7.5, "sampai": 8, "judul": "pendek", "alasan": ""},
        ]}, RINGKAS, maks=20)
        self.assertEqual(len(r["urutan"]), 1)
        self.assertEqual((r["urutan"][0]["dari"], r["urutan"][0]["sampai"]), (10.0, 30.0))


class SusunOperasi(unittest.TestCase):
    def test_kartu_narasi_klip_berurutan_sesudah_isi_lama(self):
        rencana = A.rencana_lokal("Top 2 lucu", RINGKAS[:2], maks=20, bahasa="id")
        nar = {0: {"id": "bn1", "jenis": "audio", "nama": "n", "durasi": 3.0, "ada_suara": True}}
        ops = A.susun_operasi(DOK, rencana, RINGKAS, narasi_bahan=nar, suara="edge:ardi")
        jenis = [(o["jenis"], o["kelompok"]) for o in ops]
        self.assertEqual(jenis, [("animasi", "#2"), ("audio", "#2"), ("klip", "#2"),
                                 ("animasi", "#1"), ("klip", "#1")])
        self.assertEqual(ops[0]["mulai"], 90)                 # sesudah item lama
        self.assertEqual(ops[0]["durasi"], round(3.4 * 30))   # narasi 3 dtk + jeda
        self.assertEqual(ops[2]["mulai"], 90 + 102)
        self.assertEqual(ops[3]["mulai"], ops[2]["mulai"] + ops[2]["durasi"])
        self.assertEqual(ops[3]["durasi"], 60)                # kartu tanpa narasi: 2 dtk
        self.assertEqual(ops[4]["potong_awal"], round(ops[4]["potong_awal"]))
        self.assertEqual(ops[1]["narasi"]["suara"], "edge:ardi")
        self.assertEqual(len({o["id"] for o in ops}), len(ops))


class Pekerjaan(unittest.TestCase):
    def _jalankan(self, ai=None, payload=None):
        ctx = mock.Mock(cancelled=False, payload={"proyek_id": "mt_x", "profil_id": 1,
                                                  "perintah": "Top 3 momen paling lucu",
                                                  "bahan": [r["id"] for r in RINGKAS], **(payload or {})})
        with mock.patch.object(A.repo, "ambil_proyek", return_value={"dokumen": DOK}), \
             mock.patch.object(A, "ringkas_bahan", return_value=RINGKAS), \
             mock.patch("app.services.penyedia_ai.ada_ai", return_value=ai is not None), \
             mock.patch("app.services.bahasa_ai.kode", return_value="id"), \
             mock.patch.object(A, "rencana_ai", side_effect=ai or AssertionError):
            return A.run_asisten(ctx)

    def test_tanpa_ai_susunan_lokal(self):
        h = self._jalankan()
        self.assertEqual(h["sumber"], "lokal")
        self.assertEqual(sum(o["jenis"] == "klip" for o in h["operasi"]), 3)

    def test_ai_gagal_jatuh_ke_lokal_dengan_peringatan(self):
        h = self._jalankan(ai=RuntimeError("habis kuota"))
        self.assertEqual(h["sumber"], "lokal")
        self.assertTrue(any("lokal" in p for p in h["peringatan"]))

    def test_rencana_ai_dipakai(self):
        rencana = {"judul": "x", "penutup": "Ikuti untuk lagi", "urutan": [
            {"bahan": "b3", "dari": 0, "sampai": 8, "peringkat": 1, "judul": "Paling lucu",
             "narasi": "", "alasan": "tertawa di detik 2"}]}
        h = self._jalankan(ai=lambda *a, **k: (rencana, "tiruan"))
        self.assertEqual((h["sumber"], h["model"]), ("ai", "tiruan"))
        self.assertEqual([o["jenis"] for o in h["operasi"]], ["animasi", "klip", "animasi"])
        self.assertEqual(h["operasi"][-1]["komponen"], "ko_ajakan_langganan")


if __name__ == "__main__":
    unittest.main()
