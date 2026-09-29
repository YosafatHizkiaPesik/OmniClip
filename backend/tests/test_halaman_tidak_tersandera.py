"""
Pemindaian yang mengantre tidak boleh menyandera halaman biasa.

Dilaporkan pemiliknya 29 September 2026 dengan kalimat yang tepat: "yang saya
tunggu seperti tidak akan pernah selesai". Layarnya berhenti di "Memuat daftar
project..." dan berputar terus, padahal daftar itu dijawab dalam hitungan
milidetik saat mesinnya diam.

Sebabnya cacat yang dibuat sehari sebelumnya, saat pemindaian dibatasi satu per
satu. Batasnya benar, tempat menunggunya yang salah: `asyncio.to_thread`
memakai SATU kolam utas untuk seluruh aplikasi, dan pemindaian yang menunggu
gilirannya tetap memegang utasnya. Belasan klip yang dibuka berturut-turut
menghabiskan kolam itu, lalu setiap permintaan lain ikut mengantre di
belakangnya.

Terukur pada laptop pemiliknya, dengan 14 pemindaian mengantre: `/api/projects`
yang biasanya 26 milidetik menjadi 26 DETIK.
"""

import inspect
import re
import unittest
from concurrent.futures import ThreadPoolExecutor

from app.routers import clips


class PemindaianPunyaKolamSendiri(unittest.TestCase):
    def test_kolamnya_terpisah_dan_terbatas(self):
        self.assertIsInstance(clips._PINDAI_EXEC, ThreadPoolExecutor)
        self.assertEqual(clips._PINDAI_EXEC._max_workers, clips._PINDAI_BERSAMAAN)
        self.assertGreaterEqual(clips._PINDAI_BERSAMAAN, 1)

    def test_pemindaian_tidak_lagi_memakai_kolam_bersama(self):
        """
        Yang berat lewat `_di_kolam_pindai`; `asyncio.to_thread` disediakan
        untuk pekerjaan pendek yang tidak boleh ikut mengantre.
        """
        sumber = inspect.getsource(clips)
        for nama in ("hitung_reframe", "jenis_klip_tersimpan"):
            with self.subTest(fungsi=nama):
                self.assertNotIn(f"asyncio.to_thread(\n        {nama}", sumber)
                self.assertNotIn(f"asyncio.to_thread({nama}", sumber)
        # Pemindaian facecam juga.
        badan = sumber[sumber.index("async def clip_facecam"):]
        self.assertIn("_di_kolam_pindai(kerja)", badan)
        self.assertNotIn("asyncio.to_thread(kerja)", badan)

    def test_gerbangnya_tetap_ada(self):
        """Kolam yang terpisah menggantikan tempat menunggu, bukan batasnya."""
        self.assertTrue(hasattr(clips, "_GERBANG_PINDAI"))
        self.assertIn("with _GERBANG_PINDAI:", inspect.getsource(clips))


class KolamPindaiBekerja(unittest.TestCase):
    def test_antrean_panjang_tidak_menahan_pekerjaan_lain(self):
        """
        Tiruan dari kejadian sungguhan: belasan pemindaian diantrekan, lalu
        satu pekerjaan pendek diminta. Yang pendek harus selesai duluan.
        """
        import threading
        import time

        kolam = ThreadPoolExecutor(max_workers=1)
        bersama = ThreadPoolExecutor(max_workers=4)   # "kolam bersama" yang kecil
        mulai = threading.Event()
        try:
            # 12 pemindaian yang menggantung, semuanya di kolamnya sendiri.
            for _ in range(12):
                kolam.submit(mulai.wait)
            t0 = time.time()
            hasil = bersama.submit(lambda: "daftar proyek").result(timeout=5)
            lama = time.time() - t0
        finally:
            mulai.set()
            kolam.shutdown(wait=False)
            bersama.shutdown(wait=False)
        self.assertEqual(hasil, "daftar proyek")
        self.assertLess(lama, 1.0, "pekerjaan pendek ikut tersandera antrean pemindaian")


if __name__ == "__main__":
    unittest.main()
