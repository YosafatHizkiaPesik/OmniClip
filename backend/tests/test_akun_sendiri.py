"""
Setiap akun punya setelannya sendiri, dan login yang gagal tidak meninggalkan
akun kosong.

Dua keluhan, 9 Oktober 2026:

  "login gagal tapi akun baru ditambahkan, jika bisa jangan ada akun dengan
   nama akun baru jika login gagal"

  "biasa saya menggunakan watermark tapi saat beralih akun dan mencoba klip
   pada akun tersebut watermark tersebut settingannya masih ada jadi tiap akun
   tidak memiliki settingnya masing masing"
"""

import unittest

from app.db import run_migrations
from app.repos import profil as repo
from app.services import profil as layanan


class Bersih(unittest.TestCase):
    def setUp(self):
        run_migrations()
        # Akun uji dibuang lagi, supaya uji tidak saling mewarisi keadaan.
        self.dibuat = []
        self.addCleanup(self._bersihkan)

    def _bersihkan(self):
        for pid in self.dibuat:
            try:
                repo.hapus(pid)
            except Exception:                        # noqa: BLE001
                pass

    def akun(self, nama="Uji", sementara=False) -> int:
        pid = repo.buat(nama, sementara=sementara)
        self.dibuat.append(pid)
        return pid


class GayaMilikTiapAkun(Bersih):
    def test_akun_baru_tidak_mewarisi_tanda_air(self):
        """Tanda air itu nama kanal; ia tidak boleh menyeberang antar akun."""
        a, b = self.akun("Kanal A"), self.akun("Kanal B")
        repo.simpan_gaya(a, {"watermark": "@kanalA"})
        self.assertEqual(repo.gaya(b), {})
        self.assertEqual(repo.gaya(a)["watermark"], "@kanalA")

    def test_mengubah_satu_akun_tidak_mengubah_akun_lain(self):
        a, b = self.akun("Kanal A"), self.akun("Kanal B")
        repo.simpan_gaya(a, {"watermark": "@kanalA", "wm_size": 34})
        repo.simpan_gaya(b, {"watermark": "@kanalB"})
        self.assertEqual(repo.gaya(a)["watermark"], "@kanalA")
        self.assertEqual(repo.gaya(b)["watermark"], "@kanalB")
        self.assertEqual(repo.gaya(a)["wm_size"], 34)
        self.assertNotIn("wm_size", repo.gaya(b))

    def test_menyimpan_menggabung_bukan_menukar(self):
        """Bagian lain aplikasi bisa menyimpan satu kunci saja."""
        a = self.akun()
        repo.simpan_gaya(a, {"watermark": "@a", "font": "Montserrat"})
        repo.simpan_gaya(a, {"wm_size": 40})
        g = repo.gaya(a)
        self.assertEqual((g["watermark"], g["font"], g["wm_size"]),
                         ("@a", "Montserrat", 40))

    def test_gaya_bukan_kamus_diabaikan(self):
        a = self.akun()
        repo.simpan_gaya(a, {"watermark": "@a"})
        repo.simpan_gaya(a, None)
        self.assertEqual(repo.gaya(a)["watermark"], "@a")

    def test_akun_dihapus_tidak_meninggalkan_gayanya(self):
        a = self.akun()
        repo.simpan_gaya(a, {"watermark": "@a"})
        repo.hapus(a)
        self.assertEqual(repo.gaya(a), {})


class SetelanUmumPerAkun(Bersih):
    """
    Keluhan lanjutannya 9 Oktober 2026: "ini bukan tentang watermark saja bisa
    saja hal hal lain dimana tiap akun memiliki settingnya masing masing".
    Jadi yang diuji bukan tanda airnya, melainkan WADAHNYA.
    """

    def test_kelompok_berdiri_sendiri(self):
        a = self.akun()
        repo.simpan_setelan(a, "gaya", {"watermark": "@a"})
        repo.simpan_setelan(a, "klip", {"max_clips": 8})
        self.assertEqual(repo.setelan(a, "gaya"), {"watermark": "@a"})
        self.assertEqual(repo.setelan(a, "klip"), {"max_clips": 8})

    def test_preferensi_klip_tidak_menyeberang_antar_akun(self):
        a, b = self.akun("A"), self.akun("B")
        repo.simpan_setelan(a, "klip", {"max_clips": 30, "whisper_model": "small"})
        self.assertEqual(repo.setelan(b, "klip"), {})
        self.assertEqual(repo.setelan(a, "klip")["max_clips"], 30)

    def test_kelompok_asing_ditolak(self):
        """Salah ketik tidak boleh menulis kelompok yang tidak dibaca siapa pun."""
        a = self.akun()
        self.assertEqual(repo.simpan_setelan(a, "ngawur", {"x": 1}), {})
        self.assertEqual(repo.setelan(a), {})

    def test_gaya_lama_dipindahkan_saat_pertama_dibaca(self):
        """
        Migrasi kolom gaya yang sempat ada sebelum wadahnya dibuat umum.
        Dipindahkan di Python, bukan SQL: lihat migrasi `setelan_json`.
        """
        a = self.akun()
        repo.ubah(a, gaya={"watermark": "@lama", "wm_size": 34})
        self.assertEqual(repo.setelan(a, "gaya")["watermark"], "@lama")
        # Dan kolom lamanya dikosongkan, jadi pemindahannya tidak berulang.
        self.assertEqual(repo.ambil(a)["gaya"], {})

    def test_gaya_lama_tidak_menimpa_setelan_yang_sudah_ada(self):
        a = self.akun()
        repo.simpan_setelan(a, "gaya", {"watermark": "@baru"})
        repo.ubah(a, gaya={"watermark": "@lama"})
        self.assertEqual(repo.setelan(a, "gaya")["watermark"], "@baru")

    def test_auto_clip_memakai_setelan_akun(self):
        """
        Dibaca di SERVER, supaya jalur mana pun memakai setelan akun yang sama.
        Dijaga di sumbernya: halaman bisa lupa mengirim, server tidak boleh.
        """
        from pathlib import Path
        import app.routers.clips as c
        src = Path(c.__file__).read_text(encoding="utf-8")
        awal = src.index("async def start_auto_clip(")
        badan = src[awal:awal + 3000]
        self.assertIn('profil_repo.setelan(pid, "klip")', badan)
        for kunci in ("max_clips", "whisper_model", "gemini_model"):
            self.assertIn(kunci, badan)


class LoginGagalTidakMeninggalkanAkun(Bersih):
    def setUp(self):
        super().setUp()
        from app.services import google_upload
        self.asli = google_upload.tersambung
        self.addCleanup(setattr, google_upload, "tersambung", self.asli)
        google_upload.tersambung = lambda pid, n: False

    def test_wadah_gagal_dibuang_tanpa_menunggu(self):
        """
        `sapu_sementara` menunggu 15 menit karena ia MENDUGA dari umur. Di sini
        kegagalannya sudah pasti, jadi tidak ada yang perlu ditunggu.
        """
        pid = self.akun("Akun baru", sementara=True)
        self.assertTrue(layanan.buang_wadah_gagal(pid))
        self.assertIsNone(repo.ambil(pid))

    def test_akun_sungguhan_tidak_ikut_dibuang(self):
        pid = self.akun("Horor", sementara=False)
        self.assertFalse(layanan.buang_wadah_gagal(pid))
        self.assertIsNotNone(repo.ambil(pid))

    def test_akun_utama_tidak_pernah_dibuang(self):
        self.assertFalse(layanan.buang_wadah_gagal(layanan.UTAMA))
        self.assertIsNotNone(repo.ambil(layanan.UTAMA))

    def test_wadah_yang_sudah_punya_google_disahkan_bukan_dibuang(self):
        """Gagal pada layanan KEDUA tidak boleh membuang akun yang sudah jadi."""
        from app.services import google_upload
        google_upload.tersambung = lambda pid, n: n == "youtube"
        pid = self.akun("Akun baru", sementara=True)
        self.assertFalse(layanan.buang_wadah_gagal(pid))
        pr = repo.ambil(pid)
        self.assertIsNotNone(pr)
        self.assertFalse(pr.get("sementara"))

    def test_wadah_yang_sudah_punya_video_disahkan_bukan_dibuang(self):
        pid = self.akun("Akun baru", sementara=True)
        repo.tandai_video(pid, "76s3N9SdzEE")
        self.assertFalse(layanan.buang_wadah_gagal(pid))
        self.assertIsNotNone(repo.ambil(pid))

    def test_nomor_kosong_tidak_meledak(self):
        self.assertFalse(layanan.buang_wadah_gagal(0))


class JalurGagalMembersihkanDiri(unittest.TestCase):
    """Dijaga di sumbernya: setiap jalur gagal callback harus membersihkan."""

    def test_semua_jalur_gagal_memanggil_pembersih(self):
        from pathlib import Path
        import app.routers.uploads as u
        src = Path(u.__file__).read_text(encoding="utf-8")
        awal = src.index("async def callback(")
        akhir = src.index("def _page(")
        badan = src[awal:akhir]
        self.assertEqual(badan.count("_bersihkan"), 4,
                         "tiga jalur gagal plus definisinya")

    def test_kegagalan_dikabarkan_ke_tab_omniclip(self):
        """Tanpa kabar ini, halaman "Menunggu izin" menyala sampai lima menit."""
        from pathlib import Path
        import app.routers.uploads as u
        src = Path(u.__file__).read_text(encoding="utf-8")
        self.assertIn("omniclip:google-gagal", src)

    def test_tab_gagal_tidak_menutup_dirinya(self):
        """Pesan dari Google layak dibaca, bukan dikedipkan."""
        html = u_page = None
        import app.routers.uploads as u
        res = u._page("Gagal", "sebab apa pun", ok=False)
        body = res.body.decode("utf-8")
        self.assertIn("omniclip:google-gagal", body)
        self.assertNotIn("window.close()", body)

    def test_tab_berhasil_tetap_menutup_dirinya(self):
        import app.routers.uploads as u
        body = u._page("Berhasil", "siap", ok=True).body.decode("utf-8")
        self.assertIn("omniclip:google-tersambung", body)
        self.assertIn("window.close()", body)

class TabIzinDitutupBegituSaja(Bersih):
    """
    Keadaan yang tidak pernah sampai ke server: tab izin Google ditutup tanpa
    menyelesaikan apa pun. Tidak ada callback, jadi tidak ada jalur gagal yang
    bisa membuang wadahnya, dan dulu "Akun baru" berdiri sampai 15 menit.
    """

    def setUp(self):
        super().setUp()
        from app.services import google_upload
        self.g = google_upload
        self.asli = (google_upload.tersambung, google_upload.profil_sedang_menunggu)
        self.addCleanup(self._pulihkan)
        google_upload.tersambung = lambda pid, n: False
        google_upload.profil_sedang_menunggu = lambda: set()

    def _pulihkan(self):
        self.g.tersambung, self.g.profil_sedang_menunggu = self.asli

    def _tuakan(self, pid, detik):
        from app.db import tx
        import time as t
        with tx() as c:
            c.execute("UPDATE profil SET created_at = ? WHERE id = ?",
                      (t.time() - detik, pid))

    def test_wadah_tanpa_sesi_disapu_cepat(self):
        pid = self.akun("Akun baru", sementara=True)
        self._tuakan(pid, layanan.SEMENTARA_TANPA_SESI + 5)
        layanan.sapu_sementara()
        self.assertIsNone(repo.ambil(pid))

    def test_wadah_baru_dibuat_tidak_ikut_disapu(self):
        """Antara akun dibuat dan sesinya tercatat ada jeda dua permintaan."""
        pid = self.akun("Akun baru", sementara=True)
        layanan.sapu_sementara()
        self.assertIsNotNone(repo.ambil(pid))

    def test_sesi_yang_masih_hidup_tidak_disentuh(self):
        """Halaman izin yang masih terbuka boleh selama apa pun."""
        pid = self.akun("Akun baru", sementara=True)
        self._tuakan(pid, layanan.SEMENTARA_TANPA_SESI + 60)
        self.g.profil_sedang_menunggu = lambda: {pid}
        layanan.sapu_sementara()
        self.assertIsNotNone(repo.ambil(pid))

    def test_sesi_hidup_tetap_kena_batas_lamanya(self):
        pid = self.akun("Akun baru", sementara=True)
        self._tuakan(pid, layanan.SEMENTARA_KEDALUWARSA + 5)
        self.g.profil_sedang_menunggu = lambda: {pid}
        layanan.sapu_sementara()
        self.assertIsNone(repo.ambil(pid))

    def test_halaman_melepas_wadahnya_sendiri(self):
        """
        Penyapu server butuh satu menit. Halaman yang menyerah membuang
        wadahnya saat itu juga, supaya "Akun baru" tidak sempat terlihat.
        """
        from pathlib import Path
        src = Path("../frontend/src/components/TambahAkun.jsx").read_text(encoding="utf-8")
        self.assertIn("const lepasWadah", src)
        self.assertIn("lepasWadah()", src)
        self.assertIn("wadahRef", src)


class VersiLamaDibuangSendiri(unittest.TestCase):
    """
    Ditanyakan pemiliknya 9 Oktober 2026: "saya masih tidak paham tujuan
    menyimpan versi lama setelah update".

    Jawabannya: folder lama itu JALAN KEMBALI selama penukaran. Skrip pemasang
    mengganti namanya jadi `-lama-<waktu>`, memasang yang baru, dan kalau
    langkah itu gagal ia mengembalikan yang lama. Ia hanya tertinggal ketika
    pembersihannya sendiri ditolak, misalnya oleh pemindai antivirus yang masih
    memegang berkasnya.

    Yang dijaga di sini: pembuangannya tidak menunggu kartu Pembaruan dibuka,
    dan kabar berhasil atau gagalnya tidak ikut terhapus saat dibuang.
    """

    def test_dibuang_saat_aplikasi_menyala(self):
        from pathlib import Path
        import app.main as m
        src = Path(m.__file__).read_text(encoding="utf-8")
        self.assertIn("_bereskan_pembaruan", src)
        self.assertIn("hasil_pemasangan(bersihkan=False)", src)

    def test_hanya_dibuang_sesudah_versi_baru_terbukti_jalan(self):
        """Dibuang lebih awal berarti pemasangan gagal tanpa jalan kembali."""
        from pathlib import Path
        from app.services import updater
        src = Path(updater.__file__).read_text(encoding="utf-8")
        awal = src.index("def hasil_pemasangan(")
        akhir = src.index("def bersihkan_sisa(")
        badan = src[awal:akhir]
        # Pembuangannya ada DI DALAM cabang berhasil, bukan di luarnya.
        cabang = badan.index("if berhasil:")
        self.assertGreater(badan.index("buang_cadangan()"), cabang)

    def test_kabar_pemasangan_tidak_hilang_saat_dibuang(self):
        """
        `bersihkan=False` dipakai di startup supaya kartu Pembaruan masih bisa
        melaporkan hasilnya. Kalau penandanya ikut dihapus di sana, orangnya
        tidak pernah tahu pembaruannya berhasil atau gagal.
        """
        from app.services import updater
        import app.repos.settings as sr
        nilai = {}
        asli = (sr.get, sr.set_value)
        sr.get = lambda n, b=None: nilai.get(n, b)
        sr.set_value = lambda n, v: nilai.__setitem__(n, v)
        try:
            updater._simpan(updater.NIAT_KUNCI,
                            '{"versi": "0.0.0", "dari": "1.0.0", "log": "", "pada": 1}')
            h = updater.hasil_pemasangan(bersihkan=False)
            self.assertFalse(h["berhasil"])
            self.assertTrue(updater._baca(updater.NIAT_KUNCI),
                            "penandanya tidak boleh hilang")
            h2 = updater.hasil_pemasangan(bersihkan=True)
            self.assertIsNotNone(h2)
            self.assertFalse(updater._baca(updater.NIAT_KUNCI))
        finally:
            sr.get, sr.set_value = asli
