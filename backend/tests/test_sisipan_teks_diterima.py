"""
Sisipan TEKS ("Tulisan") sampai ke render.

Sampai 10 Oktober 2026 `MediaLayerModel` mewajibkan `aset` dan tidak punya
medan teks, jadi setiap klip bersisipan Tulisan ditolak 422 saat dirender.
"""

import unittest

from app.routers.clips import MediaLayerModel
from app.services.render import siapkan_sisipan

TULISAN = {"jenis": "teks", "nama": "Tulisan", "teks": "@namakanal", "t": 0.5,
           "dur": 3, "posisi": "sudut", "ukuran": 4.5, "warna": "#FFFFFF",
           "garis": "#000000", "tebal_garis": 3, "keluarga": "Archivo Black",
           "opasitas": 0.85, "volume": 0, "asal": "pengguna", "latar": "#000000"}


class SisipanTeks(unittest.TestCase):
    def test_diterima_dan_tulisannya_tidak_dibuang(self):
        data = MediaLayerModel(**TULISAN).model_dump(exclude_none=True)
        for k in ("teks", "ukuran", "warna", "garis", "tebal_garis", "keluarga", "latar"):
            self.assertIn(k, data)
        siap = siapkan_sisipan([data], 10.0)
        self.assertEqual(len(siap), 1)
        self.assertEqual(siap[0]["jenis"], "teks")
        self.assertEqual(siap[0]["teks"], "@namakanal")

    def test_tanpa_aset_dan_tanpa_tulisan_ditolak(self):
        with self.assertRaises(Exception):
            MediaLayerModel(jenis="teks", teks="   ")
        with self.assertRaises(Exception):
            MediaLayerModel()

    def test_sisipan_berkas_tetap_seperti_dulu(self):
        self.assertEqual(MediaLayerModel(aset="0123456789abcdef").aset, "0123456789abcdef")



class Bungkus(unittest.TestCase):
    def test_teks_panjang_dipecah_per_kata(self):
        from app.services.render import bungkus_teks
        b = bungkus_teks("Kai Cenat shows Tota around the States", 20)
        self.assertEqual(b, ["Kai Cenat shows Tota", "around the States"])
        self.assertEqual(bungkus_teks("@namakanal", 20), ["@namakanal"])
        self.assertEqual(len(bungkus_teks("a " * 100, 10, maks_baris=3)), 3)

    def test_graf_satu_drawtext_per_baris(self):
        l = siapkan_sisipan([dict(TULISAN, teks="Kai Cenat shows Tota around the States",
                                  posisi="atas", ukuran=3.2, rect=None)], 10.0)
        from app.services.render import build_sisipan_graph
        _, graf, v, _ = build_sisipan_graph(l, "[0:v]", "[0:a]", input_awal=1,
                                            out_w=1080, out_h=1920)
        self.assertEqual(graf.count("drawtext="), 2)
        self.assertEqual(v, "[svt0]")


if __name__ == "__main__":
    unittest.main()
