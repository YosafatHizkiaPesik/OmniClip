"""Unggah video Montase (JOB-4 M6.1-M6.2): kredit banyak sumber, izin, nilai tambah, T-3."""

import unittest
from unittest import mock

from app.services import gerbang, izin, nilai_tambah, unggah

A = {"video_id": "a1", "judul": "Podcast A", "kanal": "Kanal A", "url": "https://youtu.be/a1"}
B = {"video_id": "b2", "judul": "Vlog B", "kanal": "Kanal B", "url": "https://youtu.be/b2"}


def meta(lapisan, sumber=(A, B), durasi=50.0):
    return {"jenis": "montase", "duration": durasi, "sumber_banyak": list(sumber), "lapisan": lapisan,
            "subtitles": [{"start": 0, "end": 3, "text": "halo"}]}


class Kredit(unittest.TestCase):
    def test_sumber_klip_montase_dan_kredit_berbaris(self):
        with mock.patch("app.services.analitik._sidecar", return_value=meta([])):
            s = unggah.sumber_klip("x.mp4", 1)
        self.assertEqual((s["kanal"], len(s["banyak"])), ("Kanal A", 2))
        k = unggah.kredit(s)
        self.assertIn('- "Podcast A" oleh Kanal A', k)
        self.assertIn('- "Vlog B" oleh Kanal B\n  https://youtu.be/b2', k)
        d = unggah.deskripsi("", judul="Top 5", hashtag=["lucu"], sumber=s)
        self.assertIn("Kanal B", d)

    def test_satu_sumber_sama_dengan_klip_biasa(self):
        self.assertEqual(unggah.kredit({**A, "banyak": [A]}), unggah.kredit(A))


class Izin(unittest.TestCase):
    def test_semua_kanal_harus_diizinkan(self):
        with mock.patch.object(izin, "_semua", return_value={"nama:kanal a": {"status": izin.DIIZINKAN}}):
            s = {**A, "banyak": [A, B]}
            self.assertEqual(izin.status(s), izin.BELUM)
            self.assertIn("Kanal B", izin.peringatan(s))
            self.assertNotIn("Kanal A", izin.peringatan(s))
        self.assertEqual(izin.status({"banyak": []}), izin.DIIZINKAN)
        self.assertEqual(izin.peringatan({"banyak": []}), "")


class NilaiTambah(unittest.TestCase):
    def test_narasi_seperti_komentar_teks_setengah(self):
        h = nilai_tambah.hitung(meta([{"t": 0, "d": 3, "jenis": "narasi"}, {"t": 10, "d": 10, "jenis": "animasi"}]))
        self.assertEqual(h["detik_komentar"], 3.0)
        self.assertEqual(h["detik_sisipan"], 10.0)
        self.assertAlmostEqual(h["skor"], (3 + 5) / 50, places=3)
        self.assertTrue(h["cukup"])

    def test_video_orang_lain_wajib_bernarasi(self):
        # Banyak animasi (skor 0,2) tapi tanpa narasi: tidak cukup (T-3).
        h = nilai_tambah.hitung(meta([{"t": 0, "d": 20, "jenis": "animasi"}]))
        self.assertGreaterEqual(h["skor"], nilai_tambah.SKOR_MIN)
        self.assertFalse(h["cukup"])
        # Bahan milik sendiri saja: tidak ada yang digunakan ulang.
        self.assertTrue(nilai_tambah.hitung(meta([], sumber=()))["cukup"])

    def test_gerbang_montase(self):
        with mock.patch("app.services.fyp.periksa", return_value={"catatan": []}):
            r = gerbang.nilai(meta([], sumber=()), sumber={"banyak": []})
            self.assertEqual(r["alasan"], [])           # tanpa sumber: tak perlu kredit, tak wajib narasi
            m = meta([{"t": 0, "d": 20, "jenis": "teks"}])
            r = gerbang.nilai(m, sumber={**A, "banyak": [A, B]})
            self.assertFalse(r["lolos"])
            self.assertTrue(any("wajib bernarasi" in a for a in r["alasan"]))
            m["lapisan"].append({"t": 0, "d": 4, "jenis": "narasi"})
            self.assertTrue(gerbang.nilai(m, sumber={**A, "banyak": [A, B]})["lolos"])


if __name__ == "__main__":
    unittest.main()
