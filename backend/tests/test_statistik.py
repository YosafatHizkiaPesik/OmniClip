"""
Tayangan klip yang sudah diunggah.

Dibaca dengan KUNCI API, bukan dengan izin akun. Izin unggah yang dipegang
OmniClip tidak bisa membaca statistik — diuji 2 Oktober 2026, jawabannya 403
"insufficient authentication scopes" — dan menambah izin baca ke akun akan
menuntut setiap akun yang sudah tersambung menyambung ulang. Kunci API tidak
menyentuh izin siapa pun; harganya hanya video publik yang terbaca.

Jaringan tidak disentuh di sini. Uji yang gagal saat internet mati tidak
memberi tahu apa pun tentang kode ini.
"""

import unittest
from unittest import mock

from app.services import statistik


JAWABAN = {
    "items": [
        {"id": "aaa", "statistics": {"viewCount": "1234", "likeCount": "56",
                                     "commentCount": "7"}},
        # Kanal yang menyembunyikan jumlah suka: medannya memang tidak ada.
        {"id": "bbb", "statistics": {"viewCount": "89"}},
    ]
}


def _jawab(data=JAWABAN, ok=True, kode=200):
    return mock.Mock(ok=ok, status_code=kode, text="", json=mock.Mock(return_value=data))


class MembacaTayangan(unittest.TestCase):
    def setUp(self):
        from app.db import run_migrations
        run_migrations()
        from app.db import get_conn
        get_conn().execute("DELETE FROM search_cache")

    def _panggil(self, ids, jawaban=None, kunci="KUNCI"):
        modul = mock.Mock()
        modul.get.return_value = jawaban if jawaban is not None else _jawab()
        with mock.patch.dict("sys.modules", {"requests": modul}):
            return statistik.tayangan(ids, kunci=kunci), modul

    def test_angka_dibaca_dan_dijadikan_bilangan(self):
        hasil, _ = self._panggil(["aaa"])
        self.assertEqual(hasil["aaa"], {"tayangan": 1234, "suka": 56, "komentar": 7})

    def test_hitungan_yang_disembunyikan_jadi_none_bukan_nol(self):
        """Nol dan "tidak diberitahu" adalah dua hal yang berbeda."""
        hasil, _ = self._panggil(["bbb"])
        self.assertEqual(hasil["bbb"]["tayangan"], 89)
        self.assertIsNone(hasil["bbb"]["suka"])

    def test_video_yang_tidak_terbaca_tidak_muncul(self):
        """
        Video privat, unlisted, atau terhapus tidak dikembalikan YouTube. Ia
        harus HILANG dari hasilnya, bukan jadi nol tayangan — angka nol pada
        klip yang ditonton ribuan orang langsung dipakai orang untuk mengambil
        keputusan.
        """
        hasil, _ = self._panggil(["aaa", "privat"])
        self.assertIn("aaa", hasil)
        self.assertNotIn("privat", hasil)

    def test_tanpa_kunci_tidak_menyentuh_jaringan(self):
        hasil, modul = self._panggil(["aaa"], kunci="")
        self.assertEqual(hasil, {})
        modul.get.assert_not_called()

    def test_tanpa_id_tidak_menyentuh_jaringan(self):
        hasil, modul = self._panggil([])
        self.assertEqual(hasil, {})
        modul.get.assert_not_called()

    def test_id_kembar_hanya_diminta_sekali(self):
        _, modul = self._panggil(["aaa", "aaa", "bbb"])
        dipakai = modul.get.call_args.kwargs["params"]["id"]
        self.assertEqual(dipakai.count("aaa"), 1)

    def test_jawaban_gagal_tidak_melempar(self):
        """Kuota habis atau kunci salah: yang hilang angkanya, bukan halamannya."""
        hasil, _ = self._panggil(["aaa"], jawaban=_jawab(ok=False, kode=403))
        self.assertEqual(hasil, {})

    def test_jaringan_mati_tidak_melempar(self):
        modul = mock.Mock()
        modul.get.side_effect = OSError("tidak ada rute ke host")
        with mock.patch.dict("sys.modules", {"requests": modul}):
            self.assertEqual(statistik.tayangan(["aaa"], kunci="K"), {})

    def test_jawaban_disimpan_supaya_kuota_tidak_terbakar(self):
        """10.000 unit per hari; membuka halaman sepuluh kali semenit tidak boleh
        menghabiskannya."""
        modul = mock.Mock()
        modul.get.return_value = _jawab()
        with mock.patch.dict("sys.modules", {"requests": modul}):
            statistik.tayangan(["aaa"], kunci="K")
            statistik.tayangan(["aaa"], kunci="K")
        self.assertEqual(modul.get.call_count, 1)

    def test_lebih_dari_lima_puluh_id_dipecah(self):
        modul = mock.Mock()
        modul.get.return_value = _jawab({"items": []})
        with mock.patch.dict("sys.modules", {"requests": modul}):
            statistik.tayangan([f"v{i}" for i in range(120)], kunci="K")
        self.assertEqual(modul.get.call_count, 3)


class KunciDisimpanDiSetelan(unittest.TestCase):
    def setUp(self):
        from app.db import run_migrations
        run_migrations()

    def test_kosong_bila_belum_disetel(self):
        from app.repos import settings as repo
        repo.set_value("youtube.api_key", "")
        self.assertEqual(statistik.kunci_api(), "")

    def test_dibaca_dari_setelan(self):
        from app.repos import settings as repo
        repo.set_value("youtube.api_key", "  ABC  ")
        self.assertEqual(statistik.kunci_api(), "ABC")


if __name__ == "__main__":
    unittest.main()
