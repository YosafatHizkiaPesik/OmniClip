"""
Cookies yang diminta di awal dan disimpan, supaya tidak ada yang mengklip
sebulan tanpa sesi login.

Dilaporkan 9 Oktober 2026: seorang pengguna Windows dengan browser bawaan,
sudah mengklip sebulan, lalu ditandai YouTube sebagai bot. Sebabnya terbaca di
kode: `cookies.mode` bawaannya "mati", satu-satunya cara menyalakannya ada di
Pengaturan, dan ia tidak pernah membukanya. Jadi sepanjang bulan itu OmniClip
memang mengirim permintaan tanpa sesi login sama sekali.

Yang dijaga di sini: sistem memilih sendiri bila bisa, bertanya bila tidak
bisa, tidak pernah bertanya dua kali, dan tidak pernah menimpa pilihan orang.
"""

import unittest

from app.services import cookies as ck


class Setelan(unittest.TestCase):
    """Setelan di memori, supaya uji tidak menyentuh basis data siapa pun."""

    def setUp(self):
        from app.repos import settings as repo
        self.nilai = {}
        self.asli = (repo.get, repo.set_value)
        repo.get = lambda n, b=None: self.nilai.get(n, b)
        repo.set_value = lambda n, v: self.nilai.__setitem__(n, v)
        self.addCleanup(self._pulihkan)
        # `simpan` memeriksa keberadaan berkas, bukan browser, jadi mode
        # browser bisa diuji tanpa browser sungguhan.
        self.asli_cari = ck.cari_yang_login
        self.addCleanup(setattr, ck, "cari_yang_login", self.asli_cari)

    def _pulihkan(self):
        from app.repos import settings as repo
        repo.get, repo.set_value = self.asli

    def browser(self, *daftar):
        ck.cari_yang_login = lambda: list(daftar)

    def ada(self, nama, login=True, jumlah=20, galat=""):
        return {"nama": nama, "profil": "", "terpasang": True,
                "login": login, "jumlah": jumlah, "galat": galat}


class MemintaIzinDulu(Setelan):
    """
    Tidak ada cookies yang disimpan sebelum orangnya mengizinkan.

    Ditanyakan pemiliknya 9 Oktober 2026: "apakah diawal menjalankan sistem ada
    pemberitahuan persetujuan untuk menggunakan cookies atau tidak". Versi
    sebelumnya menyimpan diam-diam begitu menemukan browser yang login, dan
    membaca cookie browser berarti memegang sesi Google seseorang.
    """

    def test_browser_yang_login_tidak_langsung_dipakai(self):
        self.browser(self.ada("firefox"))
        h = ck.periksa_awal()
        self.assertTrue(h["perlu_tanya"])
        self.assertEqual(ck.siaga(), "", "tidak boleh ada yang tersimpan")
        self.assertFalse(ck.sudah_ditanya(), "pertanyaannya belum dijawab")

    def test_memeriksa_tidak_mengubah_apa_pun(self):
        self.browser(self.ada("firefox"))
        ck.periksa_awal()
        ck.periksa_awal()
        self.assertEqual(ck.sumber()["mode"], "mati")
        self.assertFalse(ck.aktif())
        self.assertEqual(ck.siaga(), "")

    def test_izin_diberikan_baru_disimpan(self):
        self.browser(self.ada("firefox"))
        ck.simpan_siaga("firefox")
        ck.tandai_ditanya()
        self.assertEqual(ck.siaga(), "firefox")
        # Dan tetap belum dikirim: siaga, bukan menyala. Terukur dari IP yang
        # TIDAK ditandai: tanpa cookies 12 format, dengan cookies 7.
        self.assertEqual(ck.sumber()["mode"], "mati")
        self.assertFalse(ck.aktif())

    def test_ditolak_tidak_menyimpan_apa_pun(self):
        """"Jangan, tanpa cookies saja" harus benar-benar berarti tidak ada."""
        self.browser(self.ada("firefox"))
        ck.tandai_ditanya()
        self.assertEqual(ck.siaga(), "")
        self.assertFalse(ck.periksa_awal()["perlu_tanya"])

    def test_browser_yang_tidak_login_dilaporkan_dengan_alasannya(self):
        """
        Browser terpasang bukan browser yang login; bedanya penentu. Alasannya
        dibawa ke layar: tombol mati tanpa keterangan hanya memindahkan
        kebingungannya.
        """
        self.browser(self.ada("edge", login=False, galat="tidak bisa dibaca"))
        h = ck.periksa_awal()
        self.assertTrue(h["perlu_tanya"])
        self.assertEqual(h["browser_tersedia"][0]["galat"], "tidak bisa dibaca")
        self.assertEqual(ck.siaga(), "")
        self.assertFalse(ck.sudah_ditanya())

    def test_yang_login_disebut_dalam_jawaban(self):
        self.browser(self.ada("edge", login=False), self.ada("firefox"))
        h = ck.periksa_awal()
        self.assertIn("1 browser sedang login", h["alasan"])

    def test_tanpa_browser_sama_sekali(self):
        self.browser()
        h = ck.periksa_awal()
        self.assertTrue(h["perlu_tanya"])
        self.assertIn("tidak ada browser", h["alasan"])
        self.assertFalse(ck.sudah_ditanya())


class TidakMenimpaPilihanOrang(Setelan):
    def test_pilihan_mati_yang_disengaja_dihormati(self):
        """"Nanti saja" bukan "belum ditanya"; kalau sama, ia ditanya terus."""
        self.browser(self.ada("firefox"))
        ck.tandai_ditanya()
        h = ck.periksa_awal()
        self.assertFalse(h["perlu_tanya"])
        self.assertEqual(h["mode"], "mati")

    def test_pilihan_browser_lain_tidak_ditukar(self):
        self.browser(self.ada("firefox"))
        self.nilai[ck.KUNCI_MODE] = "browser"
        self.nilai[ck.KUNCI_BROWSER] = "chrome"
        h = ck.periksa_awal()
        self.assertFalse(h["perlu_tanya"])
        self.assertEqual(h["browser"], "chrome")
        self.assertEqual(ck.siaga(), "")

    def test_pemasangan_lama_ditandai_sudah_ditanya(self):
        """Yang sudah menyetelnya sebelum penanda ini ada tidak ditanya lagi."""
        self.browser(self.ada("firefox"))
        self.nilai[ck.KUNCI_MODE] = "browser"
        self.nilai[ck.KUNCI_BROWSER] = "chrome"
        ck.periksa_awal()
        self.assertTrue(ck.sudah_ditanya())

    def test_menyimpan_sendiri_menutup_pertanyaan(self):
        self.assertFalse(ck.sudah_ditanya())
        ck.simpan("mati")
        self.assertTrue(ck.sudah_ditanya())


class PemeriksaanBrowserNyata(unittest.TestCase):
    """
    `periksa_browser` harus MENGUJI, bukan menebak dari nama browsernya.

    Di Windows, yt-dlp 2026.08.19 belum mengerti app-bound encryption milik
    Chrome dan Edge sejak versi 127: browsernya terpasang, pemakainya login,
    dan pembacaan cookie-nya tetap gagal.
    """

    def test_browser_yang_tidak_terpasang_dilaporkan_apa_adanya(self):
        h = ck.periksa_browser("vivaldi")
        self.assertIn("terpasang", h)
        if not h["terpasang"]:
            self.assertFalse(h["login"])

    def test_cookie_login_yang_dicari_memang_cookie_sesi(self):
        """Tanpa SID/SAPISID, "ada cookie youtube" tidak berarti login."""
        for nama in ("SID", "SAPISID", "__Secure-1PSID", "__Secure-3PAPISID"):
            self.assertIn(nama, ck.COOKIE_LOGIN)

    def test_hasil_selalu_punya_bentuk_yang_sama(self):
        h = ck.periksa_browser("firefox")
        for k in ("nama", "profil", "terpasang", "login", "jumlah", "galat"):
            self.assertIn(k, h)


class JedaPermintaan(unittest.TestCase):
    """
    Jeda antar permintaan metadata: pencegah ditandai, bukan penyembuh.

    Yang membuat sebuah IP ditandai bukan satu permintaan buruk melainkan pola
    puluhan permintaan beruntun tanpa jeda dari satu alamat.
    """

    def test_jeda_ikut_di_opsi_dasar(self):
        from app.services import ytdlp
        o = ytdlp._base_opts()
        self.assertIn("sleep_interval_requests", o)
        a, b = ytdlp.JEDA_PERMINTAAN
        self.assertGreaterEqual(o["sleep_interval_requests"], a)
        self.assertLessEqual(o["sleep_interval_requests"], b)

    def test_jedanya_tidak_sama_tiap_kali(self):
        """Jeda tetap sendiri adalah pola; yt-dlp tidak mengacaknya sendiri."""
        from app.services import ytdlp
        nilai = {round(ytdlp._base_opts()["sleep_interval_requests"], 6)
                 for _ in range(12)}
        self.assertGreater(len(nilai), 1)

    def test_unduhan_tidak_ikut_diperlambat(self):
        """Memperlambat unduhan hanya menyiksa yang menunggunya di layar."""
        from app.services import ytdlp
        o = ytdlp._base_opts()
        self.assertNotIn("sleep_interval", o)
        self.assertNotIn("max_sleep_interval", o)

class SiagaDinyalakanSaatDituduhBot(Setelan):
    """
    Yang memutuskan bukan setelan, melainkan kejadian.

        dari IP sehat      tanpa cookies 12 format, dengan cookies 7
        dari IP ditandai   tanpa cookies ditolak, dengan cookies 1080p

    Tidak ada satu setelan tetap yang benar untuk keduanya, jadi penolakan
    pertama dari YouTube itulah yang menyalakan sesi yang sudah disiapkan.
    """

    def setUp(self):
        super().setUp()
        self.asli_periksa = ck.periksa_browser
        self.addCleanup(setattr, ck, "periksa_browser", self.asli_periksa)
        ck.periksa_browser = lambda n, p="": {
            "nama": n, "profil": p, "terpasang": True, "login": True,
            "jumlah": 20, "galat": ""}

    def test_siaga_dinyalakan(self):
        ck.simpan_siaga("firefox")
        self.assertEqual(ck.nyalakan_siaga(), "firefox")
        self.assertEqual(ck.sumber()["mode"], "browser")
        self.assertTrue(ck.aktif())

    def test_tanpa_siaga_tidak_ada_yang_dinyalakan(self):
        self.assertEqual(ck.nyalakan_siaga(), "")
        self.assertEqual(ck.sumber()["mode"], "mati")

    def test_tidak_dinyalakan_dua_kali(self):
        """Cookies yang sudah menyala bukan jawaban untuk tuduhan berikutnya."""
        ck.simpan_siaga("firefox")
        ck.nyalakan_siaga()
        self.assertEqual(ck.nyalakan_siaga(), "")

    def test_sesi_yang_sudah_mati_tidak_dinyalakan(self):
        """Menukar satu kegagalan dengan kegagalan lain bukan perbaikan."""
        ck.periksa_browser = lambda n, p="": {
            "nama": n, "profil": p, "terpasang": True, "login": False,
            "jumlah": 0, "galat": "tidak login"}
        ck.simpan_siaga("firefox")
        self.assertEqual(ck.nyalakan_siaga(), "")
        self.assertEqual(ck.sumber()["mode"], "mati")
        # Dan siaganya dibersihkan, supaya tidak dicoba lagi tiap kegagalan.
        self.assertEqual(ck.siaga(), "")

    def test_jalur_galat_bot_memakainya(self):
        from app.services import ytdlp
        ck.simpan_siaga("firefox")
        self.assertEqual(ytdlp._coba_cookies_siaga(), "firefox")
        self.assertTrue(ck.aktif())

class KartuPersetujuanAdaDiBeranda(unittest.TestCase):
    """Dijaga di sumbernya: pertanyaannya harus benar-benar sampai ke layar."""

    def test_kartu_dipasang_di_beranda(self):
        from pathlib import Path
        src = Path("../frontend/src/routes/Home.jsx").read_text(encoding="utf-8")
        self.assertIn("<CookiesAwal />", src)

    def test_kartu_meminta_izin_bukan_memberitahu(self):
        from pathlib import Path
        src = Path("../frontend/src/components/CookiesAwal.jsx").read_text(encoding="utf-8")
        self.assertIn("Boleh OmniClip memakai sesi YouTube Anda", src)
        self.assertIn("Izinkan, pakai", src)
        # Dan menyebut apa yang terjadi pada datanya.
        self.assertIn("hanya\n                dikirim ke YouTube", src)

    def test_startup_tidak_lagi_memilih_sendiri(self):
        from pathlib import Path
        import app.main as m
        src = Path(m.__file__).read_text(encoding="utf-8")
        self.assertIn("periksa_awal_di_latar", src)
        self.assertNotIn("pilih_otomatis", src)
