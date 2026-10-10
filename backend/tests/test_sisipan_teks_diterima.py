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


if __name__ == "__main__":
    unittest.main()
