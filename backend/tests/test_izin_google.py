"""
Izin Google, dan kenapa YouTube dan Drive tidak boleh diminta bersamaan.

Terjadi sungguhan 24 September 2026, saat pemiliknya mencoba login pertama kali:

    Access blocked: Authorization Error
    This request contains scopes that cannot be requested together:
    [https://www.googleapis.com/auth/drive.file,
     https://www.googleapis.com/auth/youtube.upload]
    Error 400: invalid_request

Semua setelan di Google Cloud Console sudah benar; yang salah permintaannya.
Uji di sini menjaga supaya keduanya tidak pernah bersatu lagi dalam satu
permintaan izin.
"""

import unittest

from app.services import google_upload as gu


class IzinDipisah(unittest.TestCase):
    YOUTUBE = "https://www.googleapis.com/auth/youtube.upload"
    DRIVE = "https://www.googleapis.com/auth/drive.file"

    def test_tidak_ada_satu_layanan_pun_yang_meminta_keduanya(self):
        for nama, izin in gu.SCOPES_LAYANAN.items():
            punya = {self.YOUTUBE in izin, self.DRIVE in izin}
            self.assertNotEqual(punya, {True}, f"{nama} meminta YouTube DAN Drive")

    def test_tiap_layanan_meminta_izin_intinya(self):
        self.assertIn(self.YOUTUBE, gu.SCOPES_LAYANAN["youtube"])
        self.assertIn(self.DRIVE, gu.SCOPES_LAYANAN["drive"])

    def test_keduanya_ikut_meminta_identitas(self):
        # Dipakai untuk memberi nama akun yang tersambung.
        for izin in gu.SCOPES_LAYANAN.values():
            self.assertIn("https://www.googleapis.com/auth/userinfo.email", izin)

    def test_izinnya_tetap_sekecil_mungkin(self):
        semua = {s for v in gu.SCOPES_LAYANAN.values() for s in v}
        for berbahaya in ("https://www.googleapis.com/auth/drive",
                          "https://www.googleapis.com/auth/youtube.force-ssl",
                          "https://www.googleapis.com/auth/youtubepartner"):
            self.assertNotIn(berbahaya, semua)


class TokenTerpisah(unittest.TestCase):
    """
    Dua izin berarti dua token. Satu berkas untuk keduanya akan membuat
    menyambungkan Drive menimpa sambungan YouTube.
    """

    def test_tiap_layanan_punya_berkasnya_sendiri(self):
        jalur = {n: gu._token_path(1, n) for n in gu.LAYANAN}
        self.assertEqual(len(set(jalur.values())), len(gu.LAYANAN))

    def test_youtube_memakai_nama_berkas_lama(self):
        # Supaya sambungan yang sudah ada tidak putus saat versi ini dipasang.
        self.assertEqual(gu._token_path(1, "youtube").name, "google_token.json")

    def test_api_diarahkan_ke_token_yang_benar(self):
        self.assertEqual(gu._LAYANAN_API["drive"], "drive")
        self.assertEqual(gu._LAYANAN_API["youtube"], "youtube")
        # Pembacaan alamat surel memakai token YouTube, yang selalu ada lebih
        # dulu karena itu tombol pertama.
        self.assertEqual(gu._LAYANAN_API["oauth2"], "youtube")


class Penolakan(unittest.TestCase):
    def test_layanan_tak_dikenal_ditolak_jelas(self):
        from app.errors import AppError
        with self.assertRaises(AppError) as e:
            gu.begin_authorization("dropbox")
        self.assertIn("dropbox", str(e.exception))


class Antarmuka(unittest.TestCase):
    def test_antarmuka_menyebut_layanan_yang_sama(self):
        import re
        from pathlib import Path
        akar = Path(__file__).resolve().parents[2]
        jsx = (akar / "frontend" / "src" / "components"
               / "GoogleAccountCard.jsx").read_text(encoding="utf-8")
        m = re.search(r"const LAYANAN = \[([^\]]+)\]", jsx)
        self.assertIsNotNone(m)
        daftar = re.findall(r"'([a-z]+)'", m.group(1))
        self.assertEqual(sorted(daftar), sorted(gu.LAYANAN))


if __name__ == "__main__":
    unittest.main()


class AlamatBalikLoopback(unittest.TestCase):
    """
    oauthlib menolak menukar kode izin lewat `http://`:

        (insecure_transport) OAuth 2 MUST utilize https.

    Aturan itu benar untuk aplikasi web dan salah untuk aplikasi yang dipasang
    di komputer orang: RFC 8252 justru MEWAJIBKAN alamat balik loopback memakai
    http, karena tidak ada otoritas sertifikat yang bisa menerbitkan sertifikat
    sah untuk 127.0.0.1.

    Yang dijaga: pelonggarannya tidak pernah bocor ke alamat lain, dan tidak
    pernah tertinggal menyala sesudah penukaran selesai.
    """

    NAMA = "OAUTHLIB_INSECURE_TRANSPORT"

    def setUp(self):
        import os
        self.asli = os.environ.pop(self.NAMA, None)

    def tearDown(self):
        import os
        os.environ.pop(self.NAMA, None)
        if self.asli is not None:
            os.environ[self.NAMA] = self.asli

    def test_alamat_loopback_dikenali(self):
        for a in ("http://127.0.0.1:8000/x", "http://localhost:9000/x",
                  "http://[::1]:8000/x"):
            self.assertTrue(gu._loopback(a), a)

    def test_alamat_luar_tidak(self):
        for a in ("https://omniclip.contoh.com/x", "http://192.168.1.5:8000/x",
                  "https://127.0.0.1.jahat.com/x"):
            self.assertFalse(gu._loopback(a), a)

    def test_dilonggarkan_hanya_untuk_loopback(self):
        import os
        with gu._izinkan_loopback("http://127.0.0.1:8000/x"):
            self.assertEqual(os.environ.get(self.NAMA), "1")
        with gu._izinkan_loopback("https://contoh.com/x"):
            self.assertIsNone(os.environ.get(self.NAMA))

    def test_dikembalikan_sesudahnya(self):
        import os
        with gu._izinkan_loopback("http://127.0.0.1:8000/x"):
            pass
        self.assertIsNone(os.environ.get(self.NAMA))

    def test_nilai_sebelumnya_tidak_dirusak(self):
        import os
        os.environ[self.NAMA] = "sudah-ada"
        with gu._izinkan_loopback("http://127.0.0.1:8000/x"):
            self.assertEqual(os.environ.get(self.NAMA), "1")
        self.assertEqual(os.environ.get(self.NAMA), "sudah-ada")

    def test_dikembalikan_walau_penukarannya_gagal(self):
        import os
        with self.assertRaises(RuntimeError):
            with gu._izinkan_loopback("http://127.0.0.1:8000/x"):
                raise RuntimeError("penukaran gagal")
        self.assertIsNone(os.environ.get(self.NAMA))

    def test_alamat_balik_bawaan_memang_loopback(self):
        self.assertTrue(gu._loopback(gu.redirect_uri()))


class IzinBertahap(unittest.TestCase):
    """
    `include_granted_scopes` dan kenapa ia harus mati.

    Dengan nyala, Google MENGGABUNGKAN izin yang sudah pernah diberikan ke dalam
    permintaan baru. Itulah yang membuat "Sambungkan Drive" tetap ditolak walau
    permintaannya sudah dipisah: begitu YouTube tersambung, permintaan Drive
    berikutnya diam-diam kembali memuat youtube.upload, dan Google menolaknya
    dengan galat yang sama persis seperti sebelum dipisah.
    """

    def test_penggabungan_izin_dimatikan(self):
        from pathlib import Path
        akar = Path(__file__).resolve().parents[1]
        kode = (akar / "app" / "services" / "google_upload.py").read_text(encoding="utf-8")
        self.assertIn('include_granted_scopes="false"', kode)
        self.assertNotIn('include_granted_scopes="true"', kode)

    def test_tiap_layanan_punya_tokennya_sendiri(self):
        # Karena itu penggabungan di atas memang tidak dibutuhkan.
        self.assertEqual(len({gu._token_path(1, n) for n in gu.LAYANAN}), len(gu.LAYANAN))


class HalamanBalik(unittest.TestCase):
    """
    Tab izin Google mengabarkan dirinya selesai lalu menutup sendiri, supaya
    tidak ada tombol "Saya sudah selesai" yang harus ditekan orang.
    """

    def halaman(self, ok: bool) -> str:
        from app.routers.uploads import _page
        return _page("Judul", "Isi", ok=ok).body.decode()

    def test_berhasil_mengabarkan_dan_menutup(self):
        h = self.halaman(True)
        self.assertIn("omniclip:google-tersambung", h)
        self.assertIn("window.close()", h)

    def test_kabarnya_dipagari_ke_asal_yang_sama(self):
        # postMessage tanpa pagar asal mengirim isinya ke situs mana pun yang
        # kebetulan membuka tab ini.
        self.assertIn("window.location.origin", self.halaman(True))

    def test_halaman_gagal_tidak_menutup_sendiri(self):
        # Yang gagal justru harus bisa dibaca.
        h = self.halaman(False)
        self.assertNotIn("window.close()", h)
        self.assertNotIn("omniclip:google-tersambung", h)

    def test_antarmuka_mendengarkan_kabar_yang_sama(self):
        from pathlib import Path
        akar = Path(__file__).resolve().parents[2]
        for berkas in ("TambahAkun.jsx", "GoogleAccountCard.jsx"):
            jsx = (akar / "frontend" / "src" / "components"
                   / berkas).read_text(encoding="utf-8")
            self.assertIn("omniclip:google-tersambung", jsx, berkas)
            self.assertIn("e.origin", jsx, berkas)


class IdentitasBawaan(unittest.TestCase):
    """
    Identitas aplikasi Google yang ikut di dalam OmniClip.

    Tanpa ini, tiap orang yang memasang OmniClip harus membuat project Google
    Cloud sendiri hanya untuk bisa menekan "Masuk dengan Google" — sepuluh
    menit kerja yang tidak ada hubungannya dengan mengklip video.

    Rahasia klien ikut dibagikan, dan itu memang tidak apa-apa di sini: Google
    menerbitkan jenis klien "Desktop app" justru untuk aplikasi yang dipasang
    di komputer orang, dan menyatakan rahasianya BUKAN rahasia. Pengamannya
    PKCE (RFC 8252), dan uji di bawah menjaga PKCE itu benar-benar dipakai.
    """

    def tanpa_berkas(self, fn, *, id_bawaan="uji.apps.googleusercontent.com"):
        """Menjalankan `fn` seolah pemiliknya belum memasang berkas apa pun."""
        import shutil
        import tempfile
        from pathlib import Path

        from app import config as cfg

        asli_id, asli_rahasia = cfg.GOOGLE_CLIENT_ID, cfg.GOOGLE_CLIENT_SECRET
        cfg.GOOGLE_CLIENT_ID = id_bawaan
        cfg.GOOGLE_CLIENT_SECRET = "RAHASIA-UJI" if id_bawaan else ""
        simpan = Path(tempfile.mkdtemp()) / "klien.json"
        ada = gu.CLIENT_SECRET_PATH.is_file()
        if ada:
            shutil.move(str(gu.CLIENT_SECRET_PATH), str(simpan))
        try:
            return fn()
        finally:
            if ada:
                shutil.move(str(simpan), str(gu.CLIENT_SECRET_PATH))
            cfg.GOOGLE_CLIENT_ID, cfg.GOOGLE_CLIENT_SECRET = asli_id, asli_rahasia

    def test_tanpa_bawaan_dan_tanpa_berkas_berarti_belum_siap(self):
        self.assertFalse(self.tanpa_berkas(gu.client_configured, id_bawaan=""))

    def test_bawaan_membuatnya_siap_tanpa_berkas(self):
        self.assertTrue(self.tanpa_berkas(gu.client_configured))
        self.assertTrue(self.tanpa_berkas(gu.client_bawaan_dipakai))

    def test_berkas_pemilik_menang_atas_bawaan(self):
        # Kuota dihitung per project: pemilik yang mendaftarkan projectnya
        # sendiri tidak boleh diam-diam dikembalikan ke jatah bersama.
        from app import config as cfg
        asli = cfg.GOOGLE_CLIENT_ID
        cfg.GOOGLE_CLIENT_ID = "bawaan.apps.googleusercontent.com"
        try:
            if gu.CLIENT_SECRET_PATH.is_file():
                self.assertFalse(gu.client_bawaan_dipakai())
        finally:
            cfg.GOOGLE_CLIENT_ID = asli

    def test_bawaan_memakai_pkce(self):
        import urllib.parse as up

        url = self.tanpa_berkas(lambda: gu.begin_authorization("youtube"))
        q = up.parse_qs(up.urlparse(url).query)
        self.assertTrue(q.get("code_challenge"), "PKCE tidak dipakai")
        self.assertEqual(q.get("code_challenge_method", [""])[0], "S256")
        self.assertEqual(q.get("client_id", [""])[0], "uji.apps.googleusercontent.com")

    def test_bawaan_tidak_pernah_ditulis_ke_cakram(self):
        # Ia datang dari variabel lingkungan; menuliskannya akan membuat salinan
        # rahasia yang tidak pernah diminta siapa pun.
        self.tanpa_berkas(lambda: gu.begin_authorization("youtube"))
        from app import config as cfg
        if cfg.GOOGLE_CLIENT_ID:
            return
        self.assertFalse(
            gu.CLIENT_SECRET_PATH.is_file()
            and "uji.apps.googleusercontent.com"
            in gu.CLIENT_SECRET_PATH.read_text(encoding="utf-8"))

    def test_status_menyebutkan_asalnya(self):
        self.assertIn("client_bawaan", gu.status())
