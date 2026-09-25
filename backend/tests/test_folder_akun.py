"""
Folder klip yang mengikuti nama akunnya.

Folder yang isinya milik akun "Horor" tapi bernama "Akun baru (3)" adalah folder
yang tidak bisa dikenali dari luar aplikasi, dan di luar aplikasi itulah orang
mencarinya: di pengelola berkas, saat hendak mengunggah dari HP.
"""

import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services import profil as ps


@contextmanager
def dunia(pid, nama, *, folder_sendiri=None, buat_folder=True, tabrakan_nama=None):
    """
    Folder klip sementara berisi satu akun.

    Pemeriksaannya dilakukan DI DALAM blok ini: folder sementara terhapus begitu
    bloknya selesai, dan jalur yang dibawa keluar menunjuk tempat yang sudah
    tidak ada.
    """
    from app.repos import profil as repo

    asli_ambil, asli_clips = repo.ambil, ps.CLIPS_DIR
    with TemporaryDirectory() as t:
        ps.CLIPS_DIR = Path(t)
        repo.ambil = lambda p: {"id": pid, "nama": nama, "folder_klip": folder_sendiri}
        lama = ps.CLIPS_DIR / f"{ps._slug(nama)} ({pid})"
        if buat_folder:
            lama.mkdir(parents=True)
            (lama / "klip.mp4").write_bytes(b"x")
        if tabrakan_nama:
            (ps.CLIPS_DIR / f"{ps._slug(tabrakan_nama)} ({pid})").mkdir(parents=True)
        try:
            yield ps.CLIPS_DIR, lama
        finally:
            repo.ambil, ps.CLIPS_DIR = asli_ambil, asli_clips


class IkutNama(unittest.TestCase):
    def test_folder_ikut_berganti_nama(self):
        with dunia(3, "Akun baru") as (akar, lama):
            hasil = ps.ikutkan_nama_folder(3, "Horor")
            self.assertIsNotNone(hasil)
            self.assertTrue((akar / "Horor (3)").is_dir())
            self.assertFalse(lama.exists())

    def test_klipnya_ikut_pindah(self):
        with dunia(3, "Akun baru") as (akar, _):
            ps.ikutkan_nama_folder(3, "Horor")
            self.assertEqual((akar / "Horor (3)" / "klip.mp4").read_bytes(), b"x")

    def test_folder_pilihan_sendiri_tidak_disentuh(self):
        # "Pindahkan ke..." adalah pilihan yang sudah dinyatakan; mengubahnya
        # karena akunnya diganti nama berarti membatalkannya tanpa diminta.
        with dunia(3, "Akun baru", folder_sendiri="/tempat/pilihan/sendiri"):
            self.assertIsNone(ps.ikutkan_nama_folder(3, "Horor"))

    def test_profil_utama_tidak_dipindah(self):
        # Klipnya tinggal di akar edited_clips; memindahkannya berarti
        # memindahkan seluruh klip lama hanya karena namanya diganti.
        with dunia(ps.UTAMA, "Utama"):
            self.assertIsNone(ps.ikutkan_nama_folder(ps.UTAMA, "Kerja"))

    def test_nama_yang_sama_bukan_perpindahan(self):
        with dunia(3, "Horor"):
            self.assertIsNone(ps.ikutkan_nama_folder(3, "Horor"))

    def test_nama_yang_menghasilkan_folder_sama_juga_tidak(self):
        # "Horor!!" dan "Horor" menghasilkan nama folder yang sama.
        with dunia(3, "Horor"):
            self.assertIsNone(ps.ikutkan_nama_folder(3, "Horor!!"))

    def test_tidak_menimpa_folder_yang_sudah_ada(self):
        with dunia(3, "Akun baru", tabrakan_nama="Horor") as (akar, lama):
            self.assertIsNone(ps.ikutkan_nama_folder(3, "Horor"))
            self.assertTrue(lama.is_dir(), "folder lama tidak boleh hilang")
            self.assertEqual((lama / "klip.mp4").read_bytes(), b"x")

    def test_folder_yang_belum_ada_dibuatkan(self):
        with dunia(3, "Akun baru", buat_folder=False) as (akar, _):
            self.assertIsNotNone(ps.ikutkan_nama_folder(3, "Horor"))
            self.assertTrue((akar / "Horor (3)").is_dir())


class NamaBerkas(unittest.TestCase):
    def test_nomor_akun_membedakan_dua_nama_yang_sama(self):
        self.assertNotEqual(f"{ps._slug('Horor')} (2)", f"{ps._slug('Horor')} (3)")

    def test_tanda_baca_berbahaya_dibuang(self):
        for jahat in ("../../etc", "a/b", "a:b", "a\\b"):
            s = ps._slug(jahat)
            for c in ("/", ":", "..", "\\"):
                self.assertNotIn(c, s, jahat)

    def test_nama_kosong_tetap_menghasilkan_sesuatu(self):
        self.assertTrue(ps._slug("").strip())


if __name__ == "__main__":
    unittest.main()


@contextmanager
def akun(pid, *, folder_klip=""):
    """Satu profil di folder klip sementara, dengan folder yang bisa diatur."""
    from app.repos import profil as repo

    asli_ambil, asli_ubah, asli_clips = repo.ambil, repo.ubah, ps.CLIPS_DIR
    with TemporaryDirectory() as t:
        ps.CLIPS_DIR = Path(t)
        baris = {"id": pid, "nama": "Akun baru",
                 "folder_klip": folder_klip.replace("<AKAR>", t)}
        repo.ambil = lambda p: dict(baris)
        repo.ubah = lambda p, **kv: baris.update(kv)
        try:
            yield ps.CLIPS_DIR, baris
        finally:
            repo.ambil, repo.ubah, ps.CLIPS_DIR = asli_ambil, asli_ubah, asli_clips


class FolderIkutAkunGoogle(unittest.TestCase):
    """
    Dilaporkan sungguhan: login gagal berkali-kali, profilnya dihapus dan dibuat
    lagi tiap percobaan, dan yang akhirnya berhasil mendarat di folder bernama
    "Akun baru (6)". Nama itu tidak memberi tahu siapa pun akun mana isinya, dan
    keluar lalu masuk lagi membuat folder baru sekali lagi.
    """

    SUREL = "entertainyhp@gmail.com"

    def test_folder_dinamai_dari_surel(self):
        with akun(6, folder_klip="<AKAR>/Akun baru (6)") as (akar, baris):
            (akar / "Akun baru (6)").mkdir()
            ps.folder_untuk_akun(6, self.SUREL)
            self.assertEqual(Path(baris["folder_klip"]).name, "entertainyhp")

    def test_nomor_profil_tidak_ikut(self):
        # Itu yang membuat masuk lagi memakai folder yang sama, bukan yang baru.
        with akun(9) as (akar, baris):
            ps.folder_untuk_akun(9, self.SUREL)
            self.assertNotIn("(9)", baris["folder_klip"])

    def test_masuk_lagi_memakai_folder_yang_sama(self):
        with akun(6) as (akar, baris):
            ps.folder_untuk_akun(6, self.SUREL)
            pertama = baris["folder_klip"]
            (Path(pertama) / "klip.mp4").write_bytes(b"x")
            # Profil dihapus lalu dibuat lagi: nomornya berubah, surelnya tidak.
            baris.update(id=11, folder_klip="")
            ps.folder_untuk_akun(11, self.SUREL)
            self.assertEqual(baris["folder_klip"], pertama)
            self.assertTrue((Path(pertama) / "klip.mp4").is_file())

    def test_klip_di_folder_bernomor_ikut_pindah(self):
        with akun(6, folder_klip="<AKAR>/Akun baru (6)") as (akar, baris):
            lama = akar / "Akun baru (6)"
            lama.mkdir()
            (lama / "klip.mp4").write_bytes(b"x")
            ps.folder_untuk_akun(6, self.SUREL)
            self.assertEqual((akar / "entertainyhp" / "klip.mp4").read_bytes(), b"x")
            self.assertFalse(lama.exists())

    def test_folder_pilihan_sendiri_tidak_disentuh(self):
        with akun(6, folder_klip="/tempat/pilihan/sendiri") as (akar, baris):
            self.assertIsNone(ps.folder_untuk_akun(6, self.SUREL))
            self.assertEqual(baris["folder_klip"], "/tempat/pilihan/sendiri")

    def test_surel_kosong_atau_salah_diabaikan(self):
        with akun(6) as (akar, baris):
            for s in ("", "bukan-surel", None):
                self.assertIsNone(ps.folder_untuk_akun(6, s))

    def test_dijalankan_dua_kali_tidak_berubah(self):
        with akun(6) as (akar, baris):
            ps.folder_untuk_akun(6, self.SUREL)
            pertama = baris["folder_klip"]
            self.assertIsNone(ps.folder_untuk_akun(6, self.SUREL))
            self.assertEqual(baris["folder_klip"], pertama)


class FolderOtomatis(unittest.TestCase):
    def test_pola_bernomor_dikenali_sebagai_pilihan_sistem(self):
        self.assertTrue(ps._folder_otomatis(str(ps.CLIPS_DIR / "Akun baru (6)")))
        self.assertTrue(ps._folder_otomatis(""))

    def test_folder_di_luar_folder_klip_dianggap_pilihan_sendiri(self):
        self.assertFalse(ps._folder_otomatis("/media/cakram-lain/klip"))
