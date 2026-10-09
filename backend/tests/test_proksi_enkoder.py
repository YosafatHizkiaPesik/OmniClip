"""
Salinan pratinjau harus jadi, walau kartu grafisnya tidak bisa dipakai.

Dilaporkan 8 Oktober 2026: "menyiapkan video pratinjau sepertinya sama sekali
tidak bergerak". Sebabnya terukur di log mesin pemiliknya: 57 kali berturut-
turut `Unrecognized option 'vaapi_device'`. Aplikasi menaruh ffmpeg bundelan di
depan PATH (`config.use_bundled_ffmpeg`), dan ffmpeg bundelan 7.0.2 statik itu
dibangun TANPA VAAPI. `enkoder.pilih()` sudah benar: ia menguji tiap ffmpeg dan
memilih /usr/bin/ffmpeg yang punya VAAPI. Tapi pembuat salinan memanggil
"ffmpeg" telanjang, jadi pilihan enkodernya dipakai pada binary yang salah.
"""

import unittest
from pathlib import Path

from app.services import proksi


class FfmpegYangDipakai(unittest.TestCase):
    def jalankan_palsu(self, rc_pertama=1):
        """Mencegat `proses.jalankan` dan mencatat tiap perintah."""
        dicatat = []

        class Hasil:
            def __init__(self, rc):
                self.returncode = rc
                self.stderr = "Unrecognized option 'vaapi_device'." if rc else ""
                self.stdout = ""

        def palsu(cmd, **kw):
            dicatat.append(list(cmd))
            return Hasil(rc_pertama if len(dicatat) == 1 else 1)

        return dicatat, palsu

    def siapkan(self, enc):
        import app.services.proses as proses
        from app.services import enkoder
        dicatat, palsu = self.jalankan_palsu()
        self.addCleanup(setattr, proses, "jalankan", proses.jalankan)
        self.addCleanup(setattr, enkoder, "pilih", enkoder.pilih)
        proses.jalankan = palsu
        enkoder.pilih = lambda: enc
        return dicatat

    def test_memakai_ffmpeg_yang_diuji_enkoder(self):
        enc = {"nama": "h264_vaapi", "ffmpeg": "/usr/bin/ffmpeg",
               "global": ["-vaapi_device", "/dev/dri/renderD128"],
               "saring": "format=nv12,hwupload",
               "video": ["-c:v", "h264_vaapi", "-qp", "19"]}
        dicatat = self.siapkan(enc)
        proksi._buat(Path("/tidak/ada/sumber.mp4"), Path("/tmp/claude-1000/uji-proksi.mp4"))
        self.assertTrue(dicatat, "perintahnya tidak pernah dijalankan")
        self.assertEqual(dicatat[0][0], "/usr/bin/ffmpeg")

    def test_gagal_di_kartu_grafis_diulang_dengan_cpu(self):
        enc = {"nama": "h264_vaapi", "ffmpeg": "/usr/bin/ffmpeg",
               "global": ["-vaapi_device", "/dev/dri/renderD128"],
               "saring": "format=nv12,hwupload",
               "video": ["-c:v", "h264_vaapi", "-qp", "19"]}
        dicatat = self.siapkan(enc)
        proksi._buat(Path("/tidak/ada/sumber.mp4"), Path("/tmp/claude-1000/uji-proksi2.mp4"))
        self.assertEqual(len(dicatat), 2, "tidak diulang tanpa kartu grafis")
        kedua = dicatat[1]
        self.assertNotIn("-vaapi_device", kedua)
        self.assertNotIn("h264_vaapi", kedua)
        self.assertIn("libx264", kedua)
        # Dan penyaringnya tidak boleh menyisakan unggahan ke GPU.
        vf = kedua[kedua.index("-vf") + 1]
        self.assertNotIn("hwupload", vf)

    def test_sumber_rusak_tidak_mencabut_kartu_grafis_untuk_render(self):
        """
        Tanda "enkoder gagal" berlaku seumur jalannya aplikasi dan render ikut
        terkena. Satu sumber yang rusak tidak boleh membuat semua render
        sesudahnya kehilangan kartu grafis; yang berarti itu nol byte keluaran.
        """
        from app.services import enkoder
        enc = {"nama": "h264_vaapi", "ffmpeg": "/usr/bin/ffmpeg",
               "global": ["-vaapi_device", "/dev/dri/renderD128"],
               "saring": "format=nv12,hwupload",
               "video": ["-c:v", "h264_vaapi", "-qp", "19"]}
        dicatat = self.siapkan(enc)
        ditandai = []
        self.addCleanup(setattr, enkoder, "tandai_gagal", enkoder.tandai_gagal)
        enkoder.tandai_gagal = lambda e: ditandai.append(e)
        tujuan = Path("/tmp/claude-1000/uji-proksi4.mp4")
        # Sudah ada keluaran separuh jalan: gagalnya bukan karena enkodernya.
        sementara = tujuan.with_suffix(".tmp.mp4")
        sementara.parent.mkdir(parents=True, exist_ok=True)
        sementara.write_bytes(b"x" * 4096)
        proksi._buat(Path("/tidak/ada/sumber.mp4"), tujuan)
        self.assertEqual(len(dicatat), 2, "tetap harus diulang dengan CPU")
        self.assertEqual(ditandai, [], "kartu grafis dicabut tanpa alasan")

    def test_tanpa_kartu_grafis_tidak_diulang_dua_kali(self):
        """x264 yang gagal gagal sungguhan; mengulanginya hanya membuang waktu."""
        enc = {"nama": "x264", "ffmpeg": "ffmpeg", "global": [], "saring": "",
               "video": []}
        dicatat = self.siapkan(enc)
        proksi._buat(Path("/tidak/ada/sumber.mp4"), Path("/tmp/claude-1000/uji-proksi3.mp4"))
        self.assertEqual(len(dicatat), 1)


class FfmpegBundelanMemangTanpaVaapi(unittest.TestCase):
    """
    Penjaga untuk akar masalahnya, bukan untuk gejalanya.

    Kalau suatu hari ffmpeg bundelan diganti dengan yang punya VAAPI, uji ini
    gagal: dan itu kabar baik yang pantas dibaca, bukan kesalahan.
    """

    def test_bundelan_tidak_dianggap_pasti_punya_vaapi(self):
        from app.config import BUNDLE_DIR
        bundel = BUNDLE_DIR / "bin" / "ffmpeg"
        if not bundel.is_file():
            self.skipTest("tidak ada ffmpeg bundelan di pemasangan ini")
        from app.services import enkoder
        # Yang dijamin: enkoder MENGUJI tiap ffmpeg, bukan menebak dari PATH.
        self.assertIn("ffmpeg", enkoder._calon()[0])
