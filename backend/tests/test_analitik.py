"""
Laporan performa klip yang sudah diunggah.

Yang diuji di sini bukan angka YouTube melainkan apa yang BOLEH dikatakan dari
angka itu. Dua aturan yang paling penting, dan keduanya soal kejujuran:

  1. Video yang tidak terbaca tidak pernah jadi nol tayangan. Kunci API hanya
     menjawab video publik, dan "0" pada klip yang sebenarnya belum publik
     adalah angka salah yang langsung dipakai orang mengambil keputusan.
  2. Dengan klip terunggah yang masih sedikit, tidak ada perbandingan sama
     sekali. Perbedaan tayangan antara tiga video bisa seluruhnya kebetulan.

Jaringan tidak disentuh: `statistik.tayangan` selalu digantikan.
"""

import unittest
from unittest import mock

from app.services import analitik


def _baris(nama, rid, **extra):
    dasar = {"clip_name": nama, "remote_id": rid, "target": "youtube",
             "status": "done", "title": nama, "privacy": "public",
             "created_at": 1.0, "finished_at": 2.0, "remote_url": ""}
    dasar.update(extra)
    return dasar


def _meta(durasi=30.0, **extra):
    """Sidecar klip yang lolos semua daftar periksa, kecuali yang diubah."""
    dasar = {
        "duration": durasi, "title": "Judul", "hashtags": ["#a", "#b", "#c"],
        "hook_text": "Pendek saja",
        "subtitles": [{"start": 0.2, "end": durasi * 0.8, "text": "ada isinya"}],
    }
    dasar.update(extra)
    return dasar


class Mengumpulkan(unittest.TestCase):
    def _jalankan(self, baris, angka, sidecar):
        with mock.patch("app.repos.uploads.list_recent", return_value=baris), \
             mock.patch("app.services.statistik.tayangan", return_value=angka), \
             mock.patch("app.services.statistik.kunci_api", return_value="AIzaXX"), \
             mock.patch.object(analitik, "_sidecar", side_effect=lambda n, p: sidecar.get(n)):
            return analitik.laporan(1)

    def test_yang_tidak_terbaca_tidak_jadi_nol(self):
        h = self._jalankan(
            [_baris("a.mp4", "A"), _baris("b.mp4", "B", privacy="private")],
            {"A": {"tayangan": 10, "suka": 1, "komentar": 0}},
            {"a.mp4": _meta(), "b.mp4": _meta()})
        tidak = [k for k in h["klip"] if k["remote_id"] == "B"][0]
        self.assertFalse(tidak["terbaca"])
        self.assertIsNone(tidak["tayangan"])
        self.assertEqual(h["terunggah"], 2)
        self.assertEqual(h["terbaca"], 1)
        # Totalnya dihitung dari yang terbaca saja.
        self.assertEqual(h["ringkasan"]["total"], 10)

    def test_satu_baris_per_video_di_kanal(self):
        """
        Klip yang diunggah dua kali jadi DUA video, dan keduanya ikut dihitung.

        Masing-masing punya alamat sendiri dan tayangannya sendiri di kanal
        itu; menggabungkannya jadi satu baris akan menyembunyikan salah satu
        video yang benar-benar ada. Baris riwayat yang kembar untuk satu video
        yang sama tetap diringkas jadi satu.
        """
        h = self._jalankan(
            [_baris("a.mp4", "A2"), _baris("a.mp4", "A1"), _baris("a.mp4", "A1")],
            {"A2": {"tayangan": 5}, "A1": {"tayangan": 99}},
            {"a.mp4": _meta()})
        self.assertEqual(sorted(k["remote_id"] for k in h["klip"]), ["A1", "A2"])
        self.assertEqual(h["ringkasan"]["total"], 104)

    def test_sedikit_klip_tidak_membandingkan(self):
        h = self._jalankan([_baris("a.mp4", "A")], {"A": {"tayangan": 3}},
                           {"a.mp4": _meta(durasi=87.0)})
        self.assertFalse(h["cukup_data"])
        self.assertTrue(h["temuan"])
        for t in h["temuan"]:
            self.assertEqual(t["dasar"], "umum")
            self.assertNotIn("median_kena", t)

    def test_cukup_klip_membandingkan_median(self):
        # Delapan klip: empat panjang dan sepi, empat pas dan ramai.
        baris, angka, sidecar = [], {}, {}
        for i in range(4):
            baris.append(_baris(f"panjang{i}.mp4", f"P{i}"))
            angka[f"P{i}"] = {"tayangan": 10}
            sidecar[f"panjang{i}.mp4"] = _meta(durasi=120.0)
        for i in range(4):
            baris.append(_baris(f"pas{i}.mp4", f"K{i}"))
            angka[f"K{i}"] = {"tayangan": 1000}
            sidecar[f"pas{i}.mp4"] = _meta(durasi=30.0)
        h = self._jalankan(baris, angka, sidecar)
        self.assertTrue(h["cukup_data"])
        kena = {t["kode"]: t for t in h["temuan"]}
        self.assertIn("durasi_panjang", kena)
        t = kena["durasi_panjang"]
        self.assertEqual(t["dasar"], "kanal")
        self.assertEqual(t["median_kena"], 10)
        self.assertEqual(t["median_bersih"], 1000)

    def test_tanpa_unggahan_tidak_meledak(self):
        h = self._jalankan([], {}, {})
        self.assertEqual(h["klip"], [])
        self.assertEqual(h["terunggah"], 0)
        self.assertIsNone(h["ringkasan"]["terbaik"])
        self.assertFalse(h["cukup_data"])

    def test_klip_tanpa_sidecar_tetap_tampil(self):
        h = self._jalankan([_baris("hilang.mp4", "A")], {"A": {"tayangan": 7}}, {})
        self.assertEqual(h["klip"][0]["tayangan"], 7)
        self.assertIsNone(h["klip"][0]["skor"])
        self.assertFalse(h["klip"][0]["ada_catatan_isi"])


class Peringkat(unittest.TestCase):
    def test_terbaca_diurut_dari_tayangan_terbanyak(self):
        klip = [{"tayangan": 1, "judul": "a", "clip_name": "a"},
                {"tayangan": None, "judul": "b", "clip_name": "b"},
                {"tayangan": 50, "judul": "c", "clip_name": "c"}]
        klip.sort(key=lambda k: (k["tayangan"] is None, -(k["tayangan"] or 0)))
        self.assertEqual([k["judul"] for k in klip], ["c", "a", "b"])

    def test_ringkasan_memakai_median_bukan_rerata(self):
        klip = [{"tayangan": n, "judul": str(n), "clip_name": str(n)}
                for n in (1, 2, 3, 4, 10000)]
        r = analitik._ringkasan(klip)
        self.assertEqual(r["median"], 3)
        self.assertEqual(r["terbaik"]["tayangan"], 10000)
        self.assertEqual(r["terendah"]["tayangan"], 1)


if __name__ == "__main__":
    unittest.main()
