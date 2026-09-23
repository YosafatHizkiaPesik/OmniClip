"""
Geometri bingkai dan penilaian isi klip.

Bingkai yang salah tidak pernah membuat render gagal — ia menghasilkan video
yang wajahnya terpotong, dan itu baru terlihat sesudah ditonton. Yang dijaga di
sini termasuk cacat yang pernah lolos sungguhan: wawancara dilabeli "permainan"
selama 27% klipnya hanya karena ada satu wajah kecil di pojok layar.
"""

import unittest

from app.services import sutradara_ai as sa
from app.services.render import (SUARA_RANTAI, _rantai_suara, kotak_reaksi,
                                 susun_layout_gaming, tinggi_wajah_otomatis)


class LabelIsiKlip(unittest.TestCase):
    """`_label_per_sampel` lewat rencana tiruan — tanpa membuka video apa pun."""

    class Rencana:
        def __init__(self, orang, kotak, terlihat, w=1920, h=1080):
            self.people = orang
            self.people_box = kotak
            self.people_seen = terlihat
            self.source_w, self.source_h = w, h

    def test_wajah_pojok_sendirian_berarti_permainan(self):
        # Satu wajah kecil di pojok kiri atas: facecam pemain.
        p = self.Rencana(orang=[[100.0, 100.0]],
                         kotak=[[(90.0, 120.0), (90.0, 120.0)]],
                         terlihat=[[True, True]])
        self.assertEqual(sa._label_per_sampel(p), ["game", "game"])

    def test_wajah_pojok_bersama_wajah_tengah_berarti_percakapan(self):
        # Inilah cacat yang pernah lolos: tamu yang duduk di tepi layar membuat
        # wawancara dibingkai sebagai gameplay dengan panel facecam khayalan.
        p = self.Rencana(orang=[[100.0], [950.0]],
                         kotak=[[(90.0, 120.0)], [(540.0, 420.0)]],
                         terlihat=[[True], [True]])
        self.assertEqual(sa._label_per_sampel(p), ["wajah"])

    def test_tanpa_wajah_berarti_gerak(self):
        p = self.Rencana(orang=[[None]], kotak=[[None]], terlihat=[[False]])
        self.assertEqual(sa._label_per_sampel(p), ["gerak"])


class PotonganDasar(unittest.TestCase):
    def test_potongan_pendek_disatukan_ke_tetangga(self):
        runs = [["wajah", 0.0, 10.0], ["game", 10.0, 11.0], ["wajah", 11.0, 20.0]]
        hasil = sa._rapikan_potongan(runs)
        self.assertEqual(len(hasil), 1)
        self.assertEqual(hasil[0][0], "wajah")

    def test_game_sekelumit_pada_klip_berwajah_dibatalkan(self):
        runs = [["wajah", 0.0, 90.0], ["game", 90.0, 100.0]]
        hasil = sa._buang_game_sekilas(runs, 100.0)
        self.assertEqual([r[0] for r in hasil], ["wajah"])

    def test_game_yang_mendominasi_dipertahankan(self):
        runs = [["game", 0.0, 80.0], ["wajah", 80.0, 100.0]]
        hasil = sa._buang_game_sekilas(runs, 100.0)
        self.assertEqual([r[0] for r in hasil], ["game", "wajah"])


class GeometriGaming(unittest.TestCase):
    FACECAM = {"x": 2.0, "y": 4.0, "w": 22.0, "h": 24.0}

    def test_dua_bidang_memenuhi_layar_tanpa_celah(self):
        tata = susun_layout_gaming(self.FACECAM, src_w=1920, src_h=1080,
                                   out_w=1080, out_h=1920)
        bidang = tata["frames"]
        self.assertEqual(len(bidang), 2)
        tinggi = sum(f["dst"]["h"] for f in bidang)
        self.assertAlmostEqual(tinggi, 100.0, places=3)
        for f in bidang:
            self.assertAlmostEqual(f["dst"]["w"], 100.0, places=3)
            for sisi in ("x", "y", "w", "h"):
                self.assertGreaterEqual(f["src"][sisi], -0.001)

    def test_tinggi_panel_wajah_dijaga_di_rentang_yang_masuk_akal(self):
        # Panel wajah yang terlalu pendek memotong dagu, yang terlalu tinggi
        # menyisakan sedikit ruang untuk permainannya.
        posisi = [{"facecam": dict(self.FACECAM, awan_kotak=None)}]
        n = tinggi_wajah_otomatis(posisi, 1920 / 1080, 1080, 1920)
        self.assertGreaterEqual(n, 40.0)
        self.assertLessEqual(n, 50.0)

    def test_kotak_reaksi_tetap_di_dalam_gambar(self):
        r = kotak_reaksi(self.FACECAM, None, 1080 / (1920 * 0.45), 1920 / 1080)
        self.assertGreaterEqual(r["x"], -0.001)
        self.assertGreaterEqual(r["y"], -0.001)
        self.assertLessEqual(r["x"] + r["w"], 100.001)
        self.assertLessEqual(r["y"] + r["h"], 100.001)


class RantaiSuara(unittest.TestCase):
    def test_bawaan_menyeimbangkan(self):
        self.assertEqual(_rantai_suara(), SUARA_RANTAI["seimbang"])

    def test_tiga_pilihan_dan_semuanya_terisi(self):
        self.assertEqual(set(SUARA_RANTAI), {"mati", "seimbang", "bersih"})
        for rantai in SUARA_RANTAI.values():
            self.assertTrue(rantai.strip())


if __name__ == "__main__":
    unittest.main()
