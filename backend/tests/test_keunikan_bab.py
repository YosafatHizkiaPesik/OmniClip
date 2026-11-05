"""Keunikan judul dan bab di deskripsi (JOB-5 O7)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.montase import ekspor
from app.services import keunikan, unggah


class Bab(unittest.TestCase):
    def test_aturan_youtube(self):
        bab = [{"t": 0, "judul": "Pembuka"}, {"t": 12, "judul": "#3 Kucing"}, {"t": 15, "judul": "terlalu dekat"},
               {"t": 40, "judul": "#2 Mic"}, {"t": 3700, "judul": "#1 Tamu"}]
        self.assertEqual(unggah.teks_bab(bab), "0:00 Pembuka\n0:12 #3 Kucing\n0:40 #2 Mic\n1:01:40 #1 Tamu")
        self.assertEqual(unggah.teks_bab(bab[:2]), "")                       # kurang dari 3
        self.assertEqual(unggah.teks_bab([{"t": 5, "judul": "a"}, {"t": 20, "judul": "b"}, {"t": 40, "judul": "c"}]), "")

    def test_bab_masuk_deskripsi_sebelum_kredit(self):
        d = unggah.deskripsi("", judul="Top 3", hashtag=["lucu"], bab=[
            {"t": 0, "judul": "Pembuka"}, {"t": 12, "judul": "#3"}, {"t": 30, "judul": "#2"}],
            sumber={"judul": "Asli", "kanal": "K", "url": "https://youtu.be/x"})
        self.assertLess(d.index("0:12 #3"), d.index("Sumber:"))

    def test_bab_dari_kartu_hanya_untuk_video_panjang(self):
        def dok(lebar, tinggi, durasi):
            return {"nama": "Top 3", "durasi": durasi, "penanda": [], "kanvas": {"lebar": lebar, "tinggi": tinggi, "fps": 30},
                    "lajur": [{"id": "M", "jenis": "motion", "item": [
                        {"id": f"m{n}", "jenis": "motion", "mulai": 300 + n * 600, "durasi": 60,
                         "props": {"angka": 3 - n, "judul": f"j{n}"}} for n in range(3)]}]}
        b = ekspor.bab(dok(1920, 1080, 2400))
        self.assertEqual([x["judul"] for x in b], ["Top 3", "#3 j0", "#2 j1", "#1 j2"])
        self.assertEqual(ekspor.bab(dok(1080, 1920, 2400)), [])            # Shorts


class Keunikan(unittest.TestCase):
    def test_judul_bertemplat_terdeteksi(self):
        self.assertGreaterEqual(keunikan.mirip("Top 5 Momen Lucu Podcast 3", "TOP 10 momen lucu podcast!"), 0.99)
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            for i, t in enumerate(["Top 5 momen lucu podcast", "Top 3 momen lucu podcast", "Momen lucu podcast terbaik",
                                   "Resep rendang padang"]):
                (folder / f"k{i}.json").write_text(json.dumps({"title": t}))
            with mock.patch("app.services.profil.folder_klip", return_value=folder), \
                 mock.patch("app.repos.uploads.list_recent", return_value=[{"clip_name": "x", "title": "Top 7 momen lucu podcast"}]):
                r = keunikan.periksa("Top 10 momen lucu podcast", clip_name="baru.mp4", profil_id=1)
        self.assertEqual(r["tingkat"], "pola")
        self.assertNotIn("Resep rendang padang", [m["judul"] for m in r["mirip"]])


if __name__ == "__main__":
    unittest.main()
