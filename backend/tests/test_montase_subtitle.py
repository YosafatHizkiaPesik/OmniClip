"""JOB-4 M3.2: subtitle otomatis dari suara linimasa."""

import json
import shutil
import unittest
from unittest import mock

from app.montase import bahan as bahan_svc
from app.montase import subtitle


def kata(*isi):
    return [{"w": w, "s": s, "e": e} for w, s, e in isi]


class Potong(unittest.TestCase):
    def test_peta_ke_linimasa_mengikuti_potong_awal_dan_kecepatan(self):
        k = kata(("satu", 1.0, 1.4), ("dua", 2.0, 2.4), ("tiga", 6.0, 6.5))
        item = {"mulai": 90, "durasi": 60, "potong_awal": 30, "kecepatan": 2}
        # Bahan detik 1-5 dipakai (30 bingkai + 60 x 2). "tiga" di luar.
        hasil = subtitle.ke_linimasa(k, item, 30)
        self.assertEqual([w["w"] for w in hasil], ["satu", "dua"])
        self.assertEqual(hasil[0]["t"], 90)          # detik 1 bahan = awal item
        self.assertEqual(hasil[1]["t"], 105)         # 30 bingkai bahan / 2

    def test_potongan_maksimal_empat_kata_dan_putus_di_jeda_atau_titik(self):
        k = [{"w": w, "t": i * 10, "u": i * 10 + 8} for i, w in enumerate(
            ["ini", "momen", "paling", "kacau", "sepanjang", "musim."])]
        k.append({"w": "Lalu", "t": 300, "u": 310})
        p = subtitle.potong(k, 30)
        self.assertEqual([x["teks"] for x in p], ["ini momen paling kacau", "sepanjang musim.", "Lalu"])
        self.assertEqual(p[0]["kata"][1], {"w": "momen", "t": 10, "d": 8})
        # Potongan pertama bertahan sampai potongan kedua mulai.
        self.assertEqual(p[0]["mulai"] + p[0]["durasi"], p[1]["mulai"])

    def test_lajur_bisu_dan_bingkai_beku_tidak_disalin(self):
        dok = {"kanvas": {"fps": 30}, "bahan": {"b1": {"ada_suara": True}, "b2": {"ada_suara": False}},
               "lajur": [
                   {"jenis": "video", "item": [
                       {"jenis": "video", "bahan": "b1", "mulai": 0, "durasi": 30},
                       {"jenis": "video", "bahan": "b1", "mulai": 30, "durasi": 30, "beku": True},
                       {"jenis": "video", "bahan": "b2", "mulai": 60, "durasi": 30}]},
                   {"jenis": "audio", "bisu": True, "item": [
                       {"jenis": "audio", "bahan": "b1", "mulai": 0, "durasi": 30}]}]}
        self.assertEqual(len(subtitle._bersuara(dok)), 1)


class Prioritas(unittest.TestCase):
    def test_ucapan_bertumpuk_diambil_dari_sumber_utama(self):
        dok = {"kanvas": {"fps": 30},
               "bahan": {"utama": {"ada_suara": True}, "kecil": {"ada_suara": True}},
               "lajur": [
                   {"jenis": "video", "item": [{"jenis": "video", "bahan": "utama", "mulai": 0, "durasi": 90}]},
                   {"jenis": "video", "item": [{"jenis": "video", "bahan": "kecil", "mulai": 0, "durasi": 90}]}]}
        kata_ = {"utama": kata(("satu", 0.1, 0.4), ("dua", 0.5, 0.8)),
                 "kecil": kata(("lain", 0.2, 0.5), ("sendiri", 2.0, 2.3))}
        with mock.patch.object(subtitle, "kata_bahan", side_effect=lambda pid, b, **k: kata_[b]):
            hasil = subtitle.buat(1, dok)
        self.assertEqual(" ".join(p["teks"] for p in hasil["potongan"]), "satu dua sendiri")


class KataBahan(unittest.TestCase):
    def setUp(self):
        self.bahan = "bh_ujisubtitle"
        self.addCleanup(shutil.rmtree, bahan_svc.folder(self.bahan), True)

    def test_simpanan_dipakai_tanpa_whisper(self):
        f = bahan_svc.folder(self.bahan) / "kata.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"kata": kata(("halo", 0.5, 0.9))}), encoding="utf-8")
        with mock.patch.object(subtitle, "_whisper", side_effect=AssertionError("tidak boleh")):
            self.assertEqual(subtitle.kata_bahan(1, self.bahan), kata(("halo", 0.5, 0.9)))

    def test_whisper_hasilnya_disimpan(self):
        b = {"asal": "impor", "rujukan": "x"}
        with mock.patch.object(subtitle.repo, "ambil_bahan", return_value=b), \
             mock.patch.object(subtitle.bahan_svc, "jalur_asli", return_value="/tmp/x.mp4"), \
             mock.patch.object(subtitle, "_whisper", return_value=(kata(("ya", 1, 1.2)), "id")) as w:
            subtitle.kata_bahan(1, self.bahan)
            subtitle.kata_bahan(1, self.bahan)
        self.assertEqual(w.call_count, 1)


if __name__ == "__main__":
    unittest.main()
