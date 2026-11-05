"""Pemeriksa kemiripan antar video Montase (JOB-5 O3)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.montase import kemiripan as K

F = 30


def dok(nama="Top 5 momen lucu podcast", suara="edge-ardi", komponen="ko_hitung_mundur", n=5, durasi=8,
        musik="bh_musik", pid_proyek="mt_a"):
    v, m, a = [], [], []
    t = 0
    for k in range(n):
        m.append({"id": f"m{k}", "jenis": "motion", "komponen": komponen, "mulai": t, "durasi": 60})
        a.append({"id": f"n{k}", "jenis": "audio", "mulai": t, "durasi": 45, "narasi": {"teks": "x", "suara": suara}})
        t += 60
        v.append({"id": f"v{k}", "jenis": "video", "mulai": t, "durasi": durasi * F})
        t += durasi * F
    a.append({"id": "mus", "jenis": "audio", "bahan": musik, "mulai": 0, "durasi": t})
    return {"id": pid_proyek, "nama": nama, "kanvas": {"fps": F},
            "lajur": [{"id": "V", "jenis": "video", "item": v}, {"id": "M", "jenis": "motion", "item": m},
                      {"id": "A", "jenis": "audio", "item": a}]}


class Sidik(unittest.TestCase):
    def test_struktur_dan_dimensi(self):
        s = K.sidik(dok())
        self.assertEqual(s["struktur"][0], "kartu")
        self.assertEqual(s["struktur"].count("klip"), 5)
        self.assertEqual((s["animasi"], s["suara"], s["musik"]), (["ko_hitung_mundur"], ["edge-ardi"], ["bh_musik"]))
        self.assertEqual(s["irama"], [8] * 5)
        self.assertNotIn("5", s["judul"])

    def test_rekaman_sendiri_berbeda_dari_tts(self):
        d = dok()
        for i in d["lajur"][2]["item"]:
            if i.get("narasi"):
                i["narasi"]["direkam"] = True
        self.assertEqual(K.sidik(d)["suara"], ["sendiri"])


class Banding(unittest.TestCase):
    def test_templat_sama_persis_vs_berbeda(self):
        a = K.sidik(dok())
        b = K.sidik(dok(nama="Top 5 momen lucu podcast minggu ini"))
        r = K.banding(a, b)
        self.assertGreaterEqual(r["skor"], K.AMBANG_MIRIP)
        self.assertIn("suara", r["sama"])
        beda = K.sidik(dok(nama="Kisah nelayan di Maluku", suara="sendiri-x", komponen="ko_label_nama",
                           n=3, durasi=21, musik="bh_lain"))
        self.assertLess(K.banding(a, beda)["skor"], K.AMBANG_MIRIP)
        self.assertFalse(K.banding(a, beda)["templat"])

    def test_top2_dan_top10_bertemplat_sama(self):
        a = K.sidik(dok(n=2, durasi=4, nama="Top 2 kocak"))
        b = K.sidik(dok(n=10, durasi=8, nama="Sepuluh momen kaget"))
        r = K.banding(a, b)
        self.assertGreaterEqual(r["dimensi"]["struktur"], K.AMBANG_DIMENSI)
        self.assertTrue(r["templat"])


class Periksa(unittest.TestCase):
    def test_pola_kanal_dari_ekspor_sebelumnya(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            for i in range(4):
                (folder / f"v{i}.json").write_text(json.dumps({
                    "jenis": "montase", "montase_id": f"mt_{i}", "file_name": f"v{i}.mp4",
                    "title": f"Top 5 momen lucu podcast {i}", "sidik": K.sidik(dok(pid_proyek=f"mt_{i}"))}))
            # ekspor ulang proyek yang sama tidak dihitung
            (folder / "sendiri.json").write_text(json.dumps({
                "jenis": "montase", "montase_id": "mt_kini", "sidik": K.sidik(dok())}))
            (folder / "studio.json").write_text(json.dumps({"title": "klip studio"}))
            with mock.patch.object(K.profil, "folder_klip", return_value=folder):
                r = K.periksa(1, dok(pid_proyek="mt_kini"))
        self.assertEqual((r["jumlah_banding"], r["tingkat"], len(r["mirip"])), (4, "pola", 4))
        self.assertIn("suara", r["sama_sering"])
        self.assertTrue(r["saran"])

    def test_tanpa_ekspor_sebelumnya_aman(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(K.profil, "folder_klip", return_value=Path(d)):
            r = K.periksa(1, dok())
        self.assertEqual((r["tingkat"], r["mirip"]), ("aman", []))


if __name__ == "__main__":
    unittest.main()
