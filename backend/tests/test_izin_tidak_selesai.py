"""
Izin Google yang tidak pernah selesai tidak boleh meninggalkan jejak.

Dilaporkan pemiliknya 27 September 2026, dua keluhan dari satu kejadian:
penukaran kode gagal karena DNS ("Failed to resolve 'oauth2.googleapis.com'"),
dan sesudahnya berdiri akun kosong bernama "Akun baru" yang bahkan menjadi akun
aktif. Yang pertama tampil sebagai jejak urllib3 mentah di layar.
"""

import time
import unittest
from pathlib import Path
from unittest import mock

from app.db import run_migrations
from app.repos import profil as repo
from app.services import google_upload as gu
from app.services import profil as layanan

AKAR = Path(__file__).resolve().parents[2]


def setUpModule():
    # Uji ini menyentuh tabel profil sungguhan, jadi skemanya harus sudah ada.
    run_migrations()


class GalatJaringanDijelaskan(unittest.TestCase):
    def test_dns_gagal_dijelaskan_bukan_dijejakkan(self):
        e = Exception(
            "HTTPSConnectionPool(host='oauth2.googleapis.com', port=443): Max "
            "retries exceeded with url: /token (Caused by NameResolutionError("
            "\"Failed to resolve 'oauth2.googleapis.com' ([Errno -2] Name or "
            "service not known)\"))")
        pesan = gu.explain_error(e)
        self.assertNotIn("HTTPSConnectionPool", pesan)
        self.assertNotIn("Errno", pesan)
        self.assertIn("muat ulang", pesan.lower())

    def test_galat_lain_tidak_disalahartikan(self):
        self.assertIn("kanal", gu.explain_error(Exception("youtubeSignupRequired")).lower())


class PenukaranKodeDicobaLagi(unittest.TestCase):
    def test_kedipan_jaringan_dicoba_lagi(self):
        panggil = []

        class Flow:
            def fetch_token(self, *, authorization_response):
                panggil.append(authorization_response)
                if len(panggil) < 3:
                    raise Exception("Failed to resolve 'oauth2.googleapis.com'")

        with mock.patch.object(gu, "_TUKAR_JEDA", (0.0, 0.0)):
            gu._tukar_kode(Flow(), "http://127.0.0.1:8000/cb?code=x")
        self.assertEqual(len(panggil), 3)

    def test_galat_bukan_jaringan_langsung_dilempar(self):
        panggil = []

        class Flow:
            def fetch_token(self, *, authorization_response):
                panggil.append(1)
                raise ValueError("invalid_grant")

        with self.assertRaises(ValueError):
            gu._tukar_kode(Flow(), "http://127.0.0.1:8000/cb?code=x")
        self.assertEqual(len(panggil), 1, "galat yang tidak sesaat tidak boleh diulang")

    def test_sesi_dikembalikan_supaya_bisa_dicoba_lagi(self):
        """Kode izinnya belum terpakai, jadi memuat ulang halaman harus cukup."""
        with mock.patch.object(gu, "_pending", {"s1": ("flow", 7, time.time(), "youtube")}), \
                mock.patch.object(gu, "_tukar_kode",
                                  side_effect=Exception("Failed to resolve")), \
                mock.patch.object(gu, "_izinkan_loopback", mock.MagicMock()):
            with self.assertRaises(Exception):
                gu.finish_authorization("http://127.0.0.1:8000/cb?code=x", "s1")
            self.assertIn("s1", gu._pending,
                          "sesi izin hilang, jadi percobaan ulang mustahil")


class ProfilSementaraDisapu(unittest.TestCase):
    """Akun wadah yang izinnya tidak pernah selesai tidak boleh menetap."""

    def setUp(self):
        self.dibuat = []

    def tearDown(self):
        for pid in self.dibuat:
            repo.hapus(pid)

    def _buat(self, **kw):
        pid = repo.buat("Akun baru", sementara=True, **kw)
        self.dibuat.append(pid)
        return pid

    def test_yang_masih_baru_tidak_disentuh(self):
        pid = self._buat()
        layanan.sapu_sementara()
        self.assertIsNotNone(repo.ambil(pid), "izin yang masih ditunggu ikut terbuang")

    def test_yang_ditinggalkan_dibuang(self):
        pid = self._buat()
        lama = time.time() - layanan.SEMENTARA_KEDALUWARSA - 60
        with mock.patch.object(repo, "semua",
                               return_value=[{**repo.ambil(pid), "created_at": lama}]):
            layanan.sapu_sementara()
        self.assertIsNone(repo.ambil(pid))

    def test_yang_sudah_punya_google_tidak_dibuang(self):
        pid = self._buat()
        lama = time.time() - layanan.SEMENTARA_KEDALUWARSA - 60
        with mock.patch.object(repo, "semua",
                               return_value=[{**repo.ambil(pid), "created_at": lama}]), \
                mock.patch.object(gu, "tersambung", return_value=True):
            layanan.sapu_sementara()
        self.assertIsNotNone(repo.ambil(pid))
        self.assertFalse(repo.ambil(pid)["sementara"], "akun yang sah tetap bertanda menunggu")

    def test_profil_tanpa_google_yang_disengaja_tidak_pernah_disapu(self):
        """"Buat ruang kerja tanpa akun Google" membuat profil biasa."""
        pid = repo.buat("Ruang kerja")
        self.dibuat.append(pid)
        lama = time.time() - layanan.SEMENTARA_KEDALUWARSA - 600
        with mock.patch.object(repo, "semua",
                               return_value=[{**repo.ambil(pid), "created_at": lama}]):
            layanan.sapu_sementara()
        self.assertIsNotNone(repo.ambil(pid))

    def test_utama_tidak_pernah_disapu(self):
        utama = repo.ambil(layanan.UTAMA)
        lama = time.time() - layanan.SEMENTARA_KEDALUWARSA - 600
        with mock.patch.object(repo, "semua",
                               return_value=[{**utama, "sementara": 1, "created_at": lama}]):
            layanan.sapu_sementara()
        self.assertIsNotNone(repo.ambil(layanan.UTAMA))


class HalamanTidakMenggantung(unittest.TestCase):
    """
    Sesudah izin Google selesai, halaman yang menunggu harus pulang sendiri.

    Dilaporkan pemiliknya 27 September 2026 dengan buktinya di layar: "akun
    sudah tersambung youtube tapi masih saja loading". Tab izin dibuka dengan
    `noopener`, yang menjamin `window.opener` kosong, jadi kabar dari halaman
    balik tidak pernah terkirim dan penantiannya tidak pernah berakhir.
    """

    def _baca(self, nama: str) -> str:
        return (AKAR / "frontend" / "src" / nama).read_text(encoding="utf-8")

    def test_tab_izin_dibuka_tanpa_noopener(self):
        pembuka = self._baca("lib/izinGoogle.js")
        self.assertNotIn("noopener", pembuka.split("export function")[1],
                         "noopener memutus window.opener, kabarnya tidak akan sampai")
        for nama in ("components/TambahAkun.jsx", "components/GoogleAccountCard.jsx"):
            with self.subTest(berkas=nama):
                teks = self._baca(nama)
                self.assertIn("bukaIzinGoogle(", teks)
                self.assertNotIn("'noopener'", teks)

    def test_penantiannya_bertanya_sendiri(self):
        """Pesan antar-tab tidak boleh jadi satu-satunya jalan pulang."""
        for nama in ("components/TambahAkun.jsx", "components/GoogleAccountCard.jsx"):
            with self.subTest(berkas=nama):
                teks = self._baca(nama)
                self.assertIn("setInterval", teks)
                self.assertIn("/uploads/google/status", teks)

    def test_penantiannya_punya_batas_dan_jalan_keluar(self):
        teks = self._baca("components/TambahAkun.jsx")
        self.assertIn("setTimeout", teks)
        self.assertIn("Batalkan", teks)


class StudioMenandaiAkunWadah(unittest.TestCase):
    def test_tombol_masuk_menandai_dan_membersihkan(self):
        teks = (AKAR / "frontend" / "src" / "components" / "TambahAkun.jsx").read_text(
            encoding="utf-8")
        self.assertIn("sementara: true", teks)
        self.assertIn("apiDelete(`/profil/${p.id}`)", teks)


if __name__ == "__main__":
    unittest.main()
