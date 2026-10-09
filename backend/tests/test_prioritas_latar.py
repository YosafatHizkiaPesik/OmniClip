"""
Pekerjaan latar tidak boleh merebut CAKRAM, bukan hanya CPU.

Dilaporkan pemiliknya 8 Oktober 2026 dengan layar Partitur yang menjawab
"server tidak menjawab dalam 30 detik": laptopnya sedang memanaskan bingkai di
latar, dan daftar project tidak pernah sampai. Terukur saat pemanasan berjalan:
daftar project yang biasanya 0,0001 detik jadi 1,3 detik.

`nice(19)` yang sudah ada hanya mengurus CPU. Yang membuatnya terasa macet
justru cakram: video sumber, salinan analisis, dan basis data OmniClip tinggal
di cakram luar yang sama, dan ffmpeg yang membaca video dua belas menit membuat
satu pembacaan sqlite ikut mengantre di belakangnya.
"""

import shutil
import unittest
from unittest import mock

from app.services import proses


class PrioritasCakram(unittest.TestCase):
    def test_pekerjaan_latar_diberi_awalan_ionice(self):
        with mock.patch.object(proses.shutil, "which", return_value="/usr/bin/ionice"):
            hasil = proses._awalan_io(["ffmpeg", "-i", "a.mp4"])
        self.assertEqual(hasil[:3], ["/usr/bin/ionice", "-c", "3"])
        self.assertEqual(hasil[3:], ["ffmpeg", "-i", "a.mp4"])

    def test_tanpa_ionice_perintahnya_apa_adanya(self):
        with mock.patch.object(proses.shutil, "which", return_value=None):
            self.assertEqual(proses._awalan_io(["ffmpeg"]), ["ffmpeg"])

    def test_tidak_dibungkus_dua_kali(self):
        with mock.patch.object(proses.shutil, "which", return_value="/usr/bin/ionice"):
            sekali = proses._awalan_io(["ffmpeg"])
            dua_kali = proses._awalan_io(sekali)
        self.assertEqual(sekali, dua_kali)

    @unittest.skipUnless(shutil.which("ionice"), "ionice tidak terpasang")
    def test_anak_latar_sungguhan_berkelas_idle(self):
        import subprocess
        import time

        p = proses.popen(["sleep", "2"], rendah=True)
        try:
            time.sleep(0.4)
            keluar = subprocess.run(["ionice", "-p", str(p.pid)],
                                    capture_output=True, text=True)
            self.assertIn("idle", (keluar.stdout or "").lower())
        finally:
            p.kill()
            proses.lepas(p)


if __name__ == "__main__":
    unittest.main()


class SalinanYangDitungguIkutDihitung(unittest.TestCase):
    """
    Salinan pratinjau yang ditunggu Studio dikecualikan dari gerbang CPU, dan
    itu benar: orangnya sedang menatap layar menunggu salinan itu. Tapi ia
    tetap merebut mesin yang sama.

    Terlihat pada mesin pemiliknya 9 Oktober 2026: satu salinan pratinjau pada
    262% CPU dan satu pemindaian wajah pada 118% berjalan berdampingan di
    laptop empat inti, beban sistem 20, dan yang dilaporkannya "mengapa
    progress auto bingkai satu video tidak selesai selesai". Pemanasan tidak
    pernah minggir karena `ada_penunggu` tetap False.
    """

    def test_menghitung_diri_sebagai_penunggu(self):
        from app.services.jobs import gerbang_cpu
        self.assertFalse(gerbang_cpu.ada_penunggu)
        with gerbang_cpu.sebagai_penunggu():
            self.assertTrue(gerbang_cpu.ada_penunggu)
        self.assertFalse(gerbang_cpu.ada_penunggu)

    def test_tidak_ikut_memakai_gerbangnya(self):
        """Ia tidak boleh ditahan; yang ditambahkan cuma hitungan penunggu."""
        from app.services.jobs import gerbang_cpu
        with gerbang_cpu.sebagai_penunggu():
            self.assertFalse(gerbang_cpu.sedang_dipakai)

    def test_tetap_bersih_saat_ada_galat(self):
        from app.services.jobs import gerbang_cpu
        with self.assertRaises(ValueError):
            with gerbang_cpu.sebagai_penunggu():
                raise ValueError("gagal di tengah")
        self.assertFalse(gerbang_cpu.ada_penunggu)

    def test_dipakai_pembuat_salinan(self):
        from pathlib import Path
        import app.services.proksi as pr
        src = Path(pr.__file__).read_text(encoding="utf-8")
        self.assertIn("gerbang_cpu.sebagai_penunggu() if buru else nullcontext()", src)
