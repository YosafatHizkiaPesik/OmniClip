"""JOB-2 F2-6: gambar stok Pexels, dipilih orangnya sendiri."""

import unittest
from unittest import mock

from app.db import run_migrations
from app.services import stok


class Jawaban:
    def __init__(self, kode, data):
        self.status_code, self._data = kode, data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class Stok(unittest.TestCase):
    def setUp(self):
        run_migrations()
        stok.setel_kunci("")

    def test_tanpa_kunci_ditolak(self):
        with mock.patch.dict("os.environ", {"PEXELS_API_KEY": ""}):
            with self.assertRaises(PermissionError):
                stok.cari("kapal")

    def test_kunci_aneh_ditolak(self):
        with self.assertRaises(ValueError):
            stok.setel_kunci("bukan kunci!")

    def test_cari_mengirim_kunci_dan_merapikan_hasil(self):
        stok.setel_kunci("a" * 56)
        data = {"photos": [
            {"id": 1, "alt": "Kapal", "photographer": "Budi", "url": "https://www.pexels.com/photo/1",
             "src": {"medium": "https://images.pexels.com/m.jpg", "large2x": "https://images.pexels.com/l.jpg"}},
            {"id": 2, "src": {}},
        ]}
        with mock.patch("requests.get", return_value=Jawaban(200, data)) as g:
            hasil = stok.cari("kapal   nelayan")
        self.assertEqual(g.call_args.kwargs["headers"]["Authorization"], "a" * 56)
        self.assertEqual(g.call_args.kwargs["params"]["query"], "kapal nelayan")
        self.assertEqual([h["id"] for h in hasil], [1])
        self.assertEqual(hasil[0]["fotografer"], "Budi")

    def test_kunci_ditolak_pexels(self):
        stok.setel_kunci("b" * 56)
        with mock.patch("requests.get", return_value=Jawaban(401, {})):
            with self.assertRaises(PermissionError):
                stok.cari("kapal")

    def test_hanya_gambar_pexels_yang_diunduh(self):
        for url in ("https://evil.example/x.jpg", "http://images.pexels.com/x.jpg",
                    "file:///etc/passwd"):
            with self.assertRaises(ValueError):
                stok.ambil(url)


if __name__ == "__main__":
    unittest.main()
