"""
Pengimpor papan suara.

Diminta pemiliknya 30 September 2026 sesudah menolak dua kali usaha membuat
efek suara sendiri: "saya lebih tertarik memasukkan soundboard seperti pada
link ini", menunjuk halaman pencarian Indonesia di myinstants.com.

Yang diuji di sini pembacaan halamannya, bukan pengunduhannya: mengunduh
menuntut internet dan situs pihak ketiga, dan uji yang gagal saat internet mati
tidak memberi tahu apa pun tentang kode ini.
"""

import unittest
from unittest import mock

from app.services import soundboard


# Bentuk markup myinstants, dipotong dari halaman sungguhan 30 September 2026.
HALAMAN = """
<div class="instant">
<button class="small-button" onclick="play('/media/sounds/ajojing.mp3', 'loader-1', 'ajojing-21676')"
  title="Play Ajojing sound" type="button"></button>
<a href="/en/instant/ajojing-21676/" class="instant-link link-secondary">Ajojing</a>
</div>
<div class="instant">
<button class="small-button" onclick="play('/media/sounds/tolong_BPxrsyS.mp3', 'loader-2', 'tolong-9')"
  title="Play Tolong sound" type="button"></button>
<a href="/en/instant/tolong-9/" class="instant-link link-secondary">Tolong</a>
</div>
"""


class TautanLangsungTidakPerluDibaca(unittest.TestCase):
    """Tautan ke berkas suara dikembalikan apa adanya, tanpa menyentuh jaringan."""

    def test_dikenali_dari_ekstensinya(self):
        for u in ("https://x.test/a.mp3", "https://x.test/b.WAV",
                  "https://x.test/c.ogg", "https://x.test/d.m4a"):
            with self.subTest(u=u):
                self.assertTrue(soundboard.tautan_suara(u))

    def test_halaman_biasa_bukan_tautan_suara(self):
        self.assertFalse(soundboard.tautan_suara("https://x.test/cari/?name=indonesia"))

    def test_namanya_diturunkan_dari_nama_berkas(self):
        hasil = soundboard.cari("https://x.test/ngakak-laugh-annoying.mp3")
        self.assertEqual(len(hasil), 1)
        self.assertEqual(hasil[0]["nama"], "Ngakak Laugh Annoying")


class TautanHarusSah(unittest.TestCase):
    def test_bukan_http_ditolak(self):
        for u in ("", "   ", "file:///etc/passwd", "javascript:alert(1)",
                  "www.myinstants.com"):
            with self.subTest(u=u):
                with self.assertRaises(ValueError):
                    soundboard.cari(u)

    def test_ambil_juga_menolak(self):
        with self.assertRaises(ValueError):
            soundboard.ambil("file:///etc/passwd")


class MembacaHalamanPapanSuara(unittest.TestCase):
    def _cari(self, teks: str, kode: int = 200):
        palsu = mock.Mock(status_code=kode, text=teks)
        modul = mock.Mock()
        modul.requests.get.return_value = palsu
        with mock.patch.dict("sys.modules", {"curl_cffi": modul}):
            return soundboard.cari("https://www.myinstants.com/en/search/?name=indonesia")

    def test_nama_diambil_dari_judul_tombol(self):
        """`title="Play X sound"` memberi nama yang benar; nama berkas tidak."""
        hasil = self._cari(HALAMAN)
        self.assertEqual([h["nama"] for h in hasil], ["Ajojing", "Tolong"])

    def test_jalur_relatif_jadi_tautan_penuh(self):
        hasil = self._cari(HALAMAN)
        self.assertEqual(hasil[0]["url"],
                         "https://www.myinstants.com/media/sounds/ajojing.mp3")

    def test_tidak_ada_yang_berulang(self):
        hasil = self._cari(HALAMAN + HALAMAN)
        self.assertEqual(len(hasil), len({h["url"] for h in hasil}))

    def test_suara_tanpa_judul_tetap_terbaca(self):
        hasil = self._cari("<button onclick=\"play('/media/sounds/x.mp3', 'l')\">")
        self.assertEqual(len(hasil), 1)
        self.assertEqual(hasil[0]["nama"], "X")

    def test_halaman_tanpa_suara_memberi_daftar_kosong(self):
        self.assertEqual(self._cari("<html><body>tidak ada apa-apa</body></html>"), [])

    def test_jawaban_bukan_200_dilaporkan(self):
        with self.assertRaises(RuntimeError):
            self._cari("", kode=403)

    def test_jumlahnya_dibatasi(self):
        banyak = "".join(
            f"<button onclick=\"play('/media/sounds/s{i}.mp3', 'l')\">" for i in range(400))
        self.assertLessEqual(len(self._cari(banyak)), soundboard.MAKS_HASIL)


class TidakAdaEfekBawaanLagi(unittest.TestCase):
    """
    Dua percobaan membuat efek suara sendiri, dua penolakan. Yang dicari memang
    bukan suara sintetis, dan membundel rekaman orang lain ke dalam aplikasi
    yang dijual memindahkan masalah hak ciptanya ke pemiliknya.
    """

    def test_pustaka_bawaan_kosong(self):
        from app.services import aset
        self.assertEqual(aset.EFEK, {})
        self.assertEqual(aset.siapkan_efek(), [])


if __name__ == "__main__":
    unittest.main()
