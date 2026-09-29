"""
Pemindaian bingkai tidak boleh menggandakan dirinya di mesin kecil.

Diukur pada laptop pemiliknya 28 September 2026, Core i5-8250U (4 inti, 15 watt,
RAM 7,6 GB) saat ia mengeluh "kipasnya kencang, lemot, sering tidak terhubung ke
server": SEMBILAN ffmpeg memindai bersamaan dari tiga video berbeda, masing-
masing sekitar 20% CPU, sebagian sudah hidup 171 detik. Dua pasang di antaranya
memindai rentang yang sama persis. Suhu 93°C, beban 21,6 dari 8 utas.

Sebabnya: gerbang CPU menjaga ANTREAN PEKERJAAN, sementara pemindaian yang
diminta Studio datang lewat permintaan HTTP yang tidak pernah melewatinya.
"""

import threading
import time
import unittest
from unittest import mock

from app.routers import clips


class SatuPemindaianPadaSatuWaktu(unittest.TestCase):
    def setUp(self):
        clips._REFRAME_CACHE.clear()
        with clips._SEDANG_KUNCI:
            clips._SEDANG_DIHITUNG.clear()

    def _jalankan(self, permintaan, lambat=0.3):
        """Menjalankan beberapa permintaan bersamaan; mengembalikan jejaknya."""
        bersamaan = {"sekarang": 0, "puncak": 0}
        kunci = threading.Lock()
        dipindai = []

        def palsu(src, segments, **kw):
            with kunci:
                bersamaan["sekarang"] += 1
                bersamaan["puncak"] = max(bersamaan["puncak"], bersamaan["sekarang"])
                dipindai.append((segments[0]["start"], segments[0]["end"]))
            time.sleep(lambat)
            with kunci:
                bersamaan["sekarang"] -= 1
            return None                       # None = "tidak ada rencana", cukup

        with mock.patch("app.services.reframe.plan_reframe", side_effect=palsu), \
                mock.patch("app.services.paths.find_local_video",
                           return_value="/tmp/tidak-ada.mp4"), \
                mock.patch.object(clips, "_simpan_reframe",
                                  side_effect=lambda k, v: clips._simpan_memori(k, v)):
            utas = [threading.Thread(target=clips.hitung_reframe, kwargs=k)
                    for k in permintaan]
            for t in utas:
                t.start()
            for t in utas:
                t.join(timeout=30)
        return bersamaan["puncak"], dipindai

    def test_permintaan_berbeda_tidak_memindai_bersamaan(self):
        permintaan = [{"video_id": "v", "segments": [{"start": i * 10.0, "end": i * 10.0 + 5.0}]}
                      for i in range(4)]
        puncak, dipindai = self._jalankan(permintaan)
        self.assertEqual(puncak, 1, f"{puncak} pemindaian berjalan bersamaan")
        self.assertEqual(len(dipindai), 4, "ada permintaan yang tidak dikerjakan")

    def test_permintaan_kembar_hanya_dipindai_sekali(self):
        sama = {"video_id": "v", "segments": [{"start": 3.639, "end": 109.119}]}
        puncak, dipindai = self._jalankan([dict(sama) for _ in range(4)])
        self.assertEqual(puncak, 1)
        self.assertEqual(len(dipindai), 1,
                         f"video yang sama dipindai {len(dipindai)} kali")

    def test_gagal_tidak_membuat_permintaan_lain_menggantung(self):
        """Yang pertama meledak: yang menunggu harus mencoba sendiri, bukan diam."""
        panggil = {"n": 0}

        def kadang_meledak(src, segments, **kw):
            panggil["n"] += 1
            if panggil["n"] == 1:
                time.sleep(0.2)
                raise RuntimeError("pemindaian gagal")
            return None

        seg = [{"start": 0.0, "end": 5.0}]
        with mock.patch("app.services.reframe.plan_reframe", side_effect=kadang_meledak), \
                mock.patch("app.services.paths.find_local_video",
                           return_value="/tmp/tidak-ada.mp4"), \
                mock.patch.object(clips, "_simpan_reframe",
                                  side_effect=lambda k, v: clips._simpan_memori(k, v)):
            hasil = {}

            def pertama():
                try:
                    clips.hitung_reframe(video_id="v", segments=seg)
                except RuntimeError:
                    hasil["pertama"] = "meledak"

            def kedua():
                time.sleep(0.05)
                hasil["kedua"] = clips.hitung_reframe(video_id="v", segments=seg)

            a, b = threading.Thread(target=pertama), threading.Thread(target=kedua)
            a.start(); b.start(); a.join(timeout=30); b.join(timeout=30)

        self.assertEqual(hasil.get("pertama"), "meledak")
        self.assertIsNotNone(hasil.get("kedua"), "permintaan kedua menggantung")
        self.assertIn("available", hasil["kedua"])

    def test_tidak_meninggalkan_catatan_setelah_selesai(self):
        self._jalankan([{"video_id": "v", "segments": [{"start": 0.0, "end": 5.0}]}])
        with clips._SEDANG_KUNCI:
            self.assertEqual(clips._SEDANG_DIHITUNG, {})


class BatasnyaBisaDisetel(unittest.TestCase):
    def test_bawaannya_satu(self):
        with open(clips.__file__, encoding="utf-8") as f:
            teks = f.read()
        self.assertIn('OMNICLIP_PINDAI_BERSAMAAN", "1"', teks)
        self.assertIn("with _GERBANG_PINDAI:", teks)


if __name__ == "__main__":
    unittest.main()
