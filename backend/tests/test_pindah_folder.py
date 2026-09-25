"""
Memindahkan folder unduhan atau klip.

Yang dijaga di sini adalah tiga hal yang baru terasa pada hari buruk: berkas
yang sudah pindah tidak disalin dua kali, pemindahan yang dibatalkan tidak
meninggalkan berkas separuh yang terlihat seperti video utuh, dan setiap salinan
`DOWNLOAD_DIR`/`CLIPS_DIR` di modul lain ikut diperbarui.
"""

import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.errors import JobCancelled
from app.services import pindah_folder as pf


def isi(d: Path, nama: str, data: bytes) -> Path:
    f = d / nama
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(data)
    return f


class Pindahkan(unittest.TestCase):
    def test_berkas_dan_subfolder_ikut(self):
        with TemporaryDirectory() as t:
            asal, tujuan = Path(t) / "a", Path(t) / "b"
            isi(asal, "satu.mp4", b"x" * 100)
            isi(asal, "Profil (2)/dua.mp4", b"y" * 50)

            hasil = pf.pindahkan(asal, tujuan)

            self.assertEqual(hasil["dipindah"], 2)
            self.assertEqual((tujuan / "satu.mp4").read_bytes(), b"x" * 100)
            self.assertEqual((tujuan / "Profil (2)" / "dua.mp4").read_bytes(), b"y" * 50)
            self.assertFalse((asal / "satu.mp4").exists())
            # Subfolder yang sudah kosong tidak ditinggalkan.
            self.assertFalse((asal / "Profil (2)").exists())

    def test_berkas_yang_sudah_di_sana_dilewati(self):
        # Pemindahan yang terputus dilanjutkan, bukan diulang dari nol.
        with TemporaryDirectory() as t:
            asal, tujuan = Path(t) / "a", Path(t) / "b"
            isi(asal, "sama.mp4", b"z" * 30)
            isi(tujuan, "sama.mp4", b"z" * 30)

            hasil = pf.pindahkan(asal, tujuan)

            self.assertEqual((hasil["dipindah"], hasil["dilewati"]), (0, 1))
            self.assertFalse((asal / "sama.mp4").exists())

    def test_ukuran_berbeda_tetap_disalin_ulang(self):
        with TemporaryDirectory() as t:
            asal, tujuan = Path(t) / "a", Path(t) / "b"
            isi(asal, "beda.mp4", b"a" * 40)
            isi(tujuan, "beda.mp4", b"b" * 10)     # sisa salinan yang terputus

            pf.pindahkan(asal, tujuan)

            self.assertEqual((tujuan / "beda.mp4").read_bytes(), b"a" * 40)

    def test_batal_tidak_meninggalkan_berkas_separuh(self):
        with TemporaryDirectory() as t:
            asal, tujuan = Path(t) / "a", Path(t) / "b"
            isi(asal, "besar.mp4", b"q" * (3 * pf.POTONGAN))

            panggil = [0]

            def batal():
                panggil[0] += 1
                if panggil[0] > 2:
                    raise JobCancelled("dibatalkan")

            # os.replace di dalam satu direktori sementara tidak pernah gagal,
            # jadi jalur salinan diuji langsung.
            with self.assertRaises(JobCancelled):
                pf._salin(asal / "besar.mp4", tujuan / "besar.mp4",
                          lambda n: None, batal)

            self.assertFalse((tujuan / "besar.mp4").exists())
            self.assertEqual((asal / "besar.mp4").stat().st_size, 3 * pf.POTONGAN)

    def test_berkas_sementara_tidak_ikut_dihitung(self):
        with TemporaryDirectory() as t:
            asal = Path(t) / "a"
            isi(asal, "utuh.mp4", b"x" * 10)
            isi(asal, "separuh.mp4" + pf.AKHIRAN_SEMENTARA, b"x" * 999)

            self.assertEqual(pf.ukuran_total(asal), (1, 10))

    def test_lapor_membawa_nama_berkas_dan_kemajuan(self):
        with TemporaryDirectory() as t:
            asal, tujuan = Path(t) / "a", Path(t) / "b"
            isi(asal, "satu.mp4", b"x" * 100)
            catatan = []
            pf.pindahkan(asal, tujuan,
                         lapor=lambda selesai, total, nama: catatan.append((selesai, total, nama)))
            self.assertTrue(catatan)
            self.assertEqual(catatan[-1][0], catatan[-1][1])
            self.assertEqual(catatan[-1][2], "satu.mp4")


class SalinanFolder(unittest.TestCase):
    """
    `config.setel_folder` hanya benar selama daftarnya lengkap. Modul yang
    menyalin DOWNLOAD_DIR atau CLIPS_DIR ke namanya sendiri tapi tidak terdaftar
    akan diam-diam menulis ke folder lama sesudah pemindahan.
    """

    POLA = re.compile(r"^from \.\.config import (.+)$", re.M)

    def test_setiap_modul_yang_mengimpor_terdaftar(self):
        from app import config as cfg

        akar = Path(cfg.__file__).resolve().parent
        terdaftar = {(m, n) for daftar in cfg._SALINAN_FOLDER.values()
                     for m, n, _ in daftar}
        kurang = []
        for berkas in akar.rglob("*.py"):
            if berkas.name == "config.py":
                continue
            teks = berkas.read_text(encoding="utf-8")
            modul = "app." + str(berkas.relative_to(akar).with_suffix("")).replace("/", ".")
            for baris in self.POLA.findall(teks):
                for bagian in baris.split(","):
                    nama = bagian.strip().split(" as ")[0].strip()
                    alias = bagian.strip().split(" as ")[-1].strip()
                    if nama not in ("DOWNLOAD_DIR", "CLIPS_DIR"):
                        continue
                    if (modul, alias) not in terdaftar:
                        kurang.append(f"{modul}.{alias}")
        self.assertEqual(kurang, [], "belum terdaftar di config._SALINAN_FOLDER")

    def test_setel_folder_memperbarui_semua_salinan(self):
        import importlib
        from app import config as cfg

        asli = cfg.DOWNLOAD_DIR
        with TemporaryDirectory() as t:
            baru = Path(t) / "unduhan-baru"
            try:
                cfg.setel_folder("unduhan", baru)
                self.assertEqual(cfg.DOWNLOAD_DIR, baru.resolve())
                self.assertEqual(cfg.MEDIA_DIRS["local_downloads"], baru.resolve())
                for nama_modul, nama, ubah in cfg._SALINAN_FOLDER["unduhan"]:
                    modul = importlib.import_module(nama_modul)
                    harap = ubah(baru.resolve()) if ubah else baru.resolve()
                    self.assertEqual(getattr(modul, nama), harap, nama_modul)
            finally:
                cfg.setel_folder("unduhan", asli)

    def test_jenis_tak_dikenal_ditolak(self):
        from app import config as cfg
        with self.assertRaises(ValueError):
            cfg.setel_folder("sampul", Path("/tmp"))


class Penunjuk(unittest.TestCase):
    """
    Penunjuk folder yang menyebut tempat BAWAAN akan salah begitu seluruh
    penyimpanan dipindahkan, dan salahnya baru terlihat saat itu. Karena itu
    kembali ke bawaan berarti penunjuknya dihapus.

    Ujinya tidak pernah menyentuh folder klip yang sebenarnya: memindahkan
    gigabita milik orang demi sebuah uji adalah harga yang tidak pantas, dan
    uji yang lambat akhirnya tidak dijalankan siapa pun.
    """

    def jalankan(self, jenis, tujuan):
        class Ctx:
            payload = {"jenis": jenis, "tujuan": str(tujuan)}
            check_cancelled = staticmethod(lambda: None)
            progress = staticmethod(lambda *a, **k: None)

        return pf.run_pindah_folder(Ctx())

    def test_kembali_ke_bawaan_menghapus_penunjuk(self):
        from app import config as cfg

        asli_klip = cfg.CLIPS_DIR
        asli_storage = cfg.STORAGE_DIR
        penunjuk = cfg._user_data_dir() / "lokasi-klip.txt"
        sebelumnya = penunjuk.read_text(encoding="utf-8") if penunjuk.is_file() else None

        with TemporaryDirectory() as t:
            akar = Path(t)
            bawaan = akar / "edited_clips"
            isi(bawaan, "satu.mp4", b"x" * 20)
            lain = akar / "klip-lain"
            try:
                cfg.STORAGE_DIR = akar
                cfg.setel_folder("klip", bawaan)

                self.jalankan("klip", lain)
                self.assertTrue(penunjuk.is_file())
                self.assertEqual((lain / "satu.mp4").read_bytes(), b"x" * 20)

                self.jalankan("klip", bawaan)
                self.assertFalse(penunjuk.is_file())
                self.assertEqual((bawaan / "satu.mp4").read_bytes(), b"x" * 20)
            finally:
                cfg.STORAGE_DIR = asli_storage
                cfg.setel_folder("klip", asli_klip)
                if sebelumnya is None:
                    penunjuk.unlink(missing_ok=True)
                else:
                    penunjuk.write_text(sebelumnya, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()


class BerkasDiLuarPenyimpanan(unittest.TestCase):
    """
    Folder unduhan boleh berada di luar penyimpanan OmniClip, dan memang itu
    gunanya fitur pindah folder.

    Terukur 24 September 2026: sesudah folder unduhan dipindahkan ke
    /home/ynot/Videos/OmniClip, SETIAP auto-klip baru berhenti dengan
    ValueError tepat sesudah unduhannya selesai, karena jalannya dipaksa
    relatif terhadap penyimpanan. Yang terlihat di layar hanya "video gagal
    diklip", tanpa sebab yang bisa ditebak siapa pun.
    """

    def test_jalan_di_dalam_penyimpanan_tetap_relatif(self):
        from app.config import STORAGE_DIR
        from app.repos.media import rel_to_storage
        self.assertEqual(rel_to_storage(STORAGE_DIR / "downloads" / "a.mp4"),
                         "downloads/a.mp4")

    def test_jalan_di_luar_penyimpanan_disimpan_mutlak(self):
        from app.repos.media import rel_to_storage
        luar = "/home/pengguna/Videos/OmniClip/Raw Video/a.mp4"
        self.assertEqual(rel_to_storage(luar), luar)

    def test_keduanya_bisa_dibaca_kembali(self):
        from app.config import STORAGE_DIR
        from app.repos.media import abs_from_storage, rel_to_storage
        for asal in (STORAGE_DIR / "downloads" / "a.mp4",
                     Path("/home/pengguna/Videos/OmniClip/Raw Video/a.mp4")):
            self.assertEqual(abs_from_storage(rel_to_storage(asal)), asal)
