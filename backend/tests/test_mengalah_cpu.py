"""
Pekerjaan latar tidak boleh menahan pekerjaan yang ditunggu orang.

Dilaporkan pemiliknya 27 September 2026: empat video diklip bersamaan, dua di
antaranya berhenti di "menunggu giliran analisis" sementara satu video sedang
memanaskan bingkainya. Tebakannya tepat.

Sebabnya: "prioritas paling rendah" pada antrean hanya memutuskan siapa yang
MASUK lebih dulu. Begitu pemanasan bingkai masuk, ia memegang gerbang CPU
sampai seluruh klipnya selesai, dan analisis video lain menunggu di belakangnya
selama itu.
"""

import threading
import time
import unittest
from pathlib import Path

from app.services import jobs

AKAR = Path(__file__).resolve().parents[2]


def _ctx(gerbang) -> jobs.JobContext:
    return jobs.JobContext(job_id="uji", type="bingkai_awal", payload={},
                           queue=None, _cancel=threading.Event())


class GerbangTahuPenunggunya(unittest.TestCase):
    def setUp(self):
        self.asli = jobs.gerbang_cpu
        jobs.gerbang_cpu = jobs._GerbangCPU(1)

    def tearDown(self):
        jobs.gerbang_cpu = self.asli

    def test_hitungan_pemakai_dan_penunggu(self):
        g = jobs.gerbang_cpu
        self.assertFalse(g.sedang_dipakai)
        self.assertFalse(g.ada_penunggu)
        self.assertTrue(g.acquire())
        self.assertTrue(g.sedang_dipakai)
        self.assertFalse(g.ada_penunggu)

        siap = threading.Event()

        def penunggu():
            siap.set()
            g.acquire()
            g.release()

        t = threading.Thread(target=penunggu)
        t.start()
        siap.wait()
        # Beri waktu utas itu benar-benar masuk antrean.
        for _ in range(100):
            if g.ada_penunggu:
                break
            time.sleep(0.01)
        self.assertTrue(g.ada_penunggu, "gerbang tidak menghitung penunggunya")
        g.release()
        t.join(timeout=5)
        self.assertFalse(g.sedang_dipakai)

    def test_tanpa_penunggu_tidak_melepas_apa_pun(self):
        c = _ctx(jobs.gerbang_cpu)
        c.giliran_cpu()
        self.assertFalse(c.mengalah_cpu(), "minggir padahal tidak ada yang menunggu")
        self.assertTrue(c._pegang_cpu)
        jobs.gerbang_cpu.release()

    def test_yang_menunggu_didahulukan(self):
        """Inti perbaikannya: yang datang belakangan tidak menunggu sampai selesai."""
        g = jobs.gerbang_cpu
        panjang = _ctx(g)
        panjang.giliran_cpu()

        tunggu = {}

        def analisis():
            c = _ctx(g)
            t0 = time.time()
            c.giliran_cpu()
            tunggu["detik"] = time.time() - t0
            g.release()

        t = threading.Thread(target=analisis)
        t.start()
        for _ in range(200):                 # sampai ia benar-benar mengantre
            if g.ada_penunggu:
                break
            time.sleep(0.01)

        # "Klip" berikutnya: di sinilah pekerjaan panjang minggir.
        self.assertTrue(panjang.mengalah_cpu(), "tidak minggir padahal ada yang menunggu")
        t.join(timeout=5)
        self.assertIn("detik", tunggu, "analisis tidak pernah dapat giliran")
        self.assertLess(tunggu["detik"], 1.0,
                        "analisis masih menunggu lama walau sudah diberi jalan")
        if panjang._pegang_cpu:
            g.release()


class PemanasanMinggirTiapKlip(unittest.TestCase):
    def test_pemanasan_memanggil_mengalah(self):
        teks = (AKAR / "backend" / "app" / "services" / "bingkai_awal.py").read_text(
            encoding="utf-8")
        self.assertIn("ctx.mengalah_cpu(", teks)
        # Di dalam perulangan klip, bukan sekali di awal.
        sesudah = teks.split("for i, klip in enumerate(daftar):", 1)
        self.assertEqual(len(sesudah), 2)
        self.assertIn("ctx.mengalah_cpu(", sesudah[1])


class SalinanTidakBerebutDenganPemindai(unittest.TestCase):
    """Video yang sama tidak didekode dua kali sekaligus."""

    def test_pembuat_salinan_menunggu_gerbang(self):
        from app.services import proksi
        teks = (AKAR / "backend" / "app" / "services" / "proksi.py").read_text(
            encoding="utf-8")
        self.assertIn("_tunggu_analisis_reda", teks)
        self.assertIn("sedang_dipakai", teks)
        self.assertTrue(hasattr(proksi, "TUNGGU_ANALISIS_MAKS"))

    def test_yang_ditunggu_studio_tidak_pernah_ditahan(self):
        from app.services import proksi
        asli = jobs.gerbang_cpu
        jobs.gerbang_cpu = jobs._GerbangCPU(1)
        jobs.gerbang_cpu.acquire()
        src = Path("/tmp/omniclip-uji-proksi.mp4")
        try:
            with proksi._kunci:
                proksi._diburu.add(str(src))
            t0 = time.time()
            proksi._tunggu_analisis_reda(src)     # harus lewat seketika
            self.assertLess(time.time() - t0, 0.5)
        finally:
            with proksi._kunci:
                proksi._diburu.discard(str(src))
            jobs.gerbang_cpu.release()
            jobs.gerbang_cpu = asli


if __name__ == "__main__":
    unittest.main()
