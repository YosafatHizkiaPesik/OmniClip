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


class KedipSusunSendiri(unittest.TestCase):
    """
    Pindah ke "Susun sendiri" dari bingkai yang mengikuti wajah.

    Dulu susunannya mulai dari kotak bawaan yang letaknya tidak ada hubungannya
    dengan apa yang barusan di layar, jadi gambarnya melompat lalu berkedip
    hitam sesaat. Sekarang kotak pertamanya diletakkan persis di tempat kotak
    otomatis itu berdiri. Yang diuji di sini rumusnya, dibaca dari berkas JS
    yang sama yang dipakai antarmuka.
    """

    @staticmethod
    def sumber() -> str:
        from pathlib import Path
        akar = Path(__file__).resolve().parents[2]
        return (akar / "frontend" / "src" / "features" / "studio"
                / "frames.js").read_text(encoding="utf-8")

    def test_rumus_lebarnya_ada_dan_dipagari(self):
        js = self.sumber()
        self.assertIn("export function layoutDariCrop", js)
        # Lebar jendela = rasio kanvas / rasio sumber, dipagari MIN_PCT dan 100.
        self.assertRegex(js, r"\(canvasAspect / sourceAspect\) \* 100")
        self.assertRegex(js, r"Math\.max\(MIN_PCT,")

    def test_pusatnya_dari_orang_yang_benar_benar_terlihat(self):
        js = self.sumber()
        self.assertIn("export function pusatWajahPada", js)
        self.assertIn("people_seen", js)

    def test_editor_memakainya_saat_pindah_dari_ikut_wajah(self):
        from pathlib import Path
        akar = Path(__file__).resolve().parents[2]
        ed = (akar / "frontend" / "src" / "features" / "studio"
              / "Editor.jsx").read_text(encoding="utf-8")
        # Jaraknya longgar: di antara keduanya ada komentar yang menjelaskan
        # kenapa, dan komentar itu bagian dari kodenya.
        self.assertRegex(ed, r"(?s)frameModeEfektif === 'smart'.{0,900}layoutDariCrop")


class PetakWajahTerlaluBesarBukanFacecam(unittest.TestCase):
    """
    "Ada facecam" adalah SATU-SATUNYA bukti yang dipakai `sutradara.susun`
    untuk menyimpulkan sebuah klip adalah rekaman permainan.

    Jadi satu salah tebak di sini tidak berhenti sebagai potongan yang meleset:
    podcast disusun sebagai wajah di atas dan permainan di bawah, dan separuh
    bawah kanvasnya berisi dinding ruangan berlabel "Main game". Terlapor 24
    September 2026 pada podcast Kajian Kitab Rongawi: petak 59%x55%.

    Diukur pada sebelas video sungguhan di penyimpanan, luas petak sebagai
    pecahan bingkai:

        gameplay berfacecam   6,3%   6,4%   11,9%
        podcast / bicara      23,7%  32,5%  38,6%

    Jurangnya lebar, jadi ambangnya berdiri di tengah tanpa menyentuh satu pun
    facecam sungguhan.
    """

    def test_ambang_memisahkan_kedua_kelompok(self):
        from app.services.reframe import FACECAM_LUAS_MAKS
        gameplay = [0.063, 0.064, 0.119]
        bicara = [0.237, 0.325, 0.386]
        self.assertGreater(FACECAM_LUAS_MAKS, max(gameplay))
        self.assertLess(FACECAM_LUAS_MAKS, min(bicara))

    def test_ambangnya_punya_margin_ke_dua_arah(self):
        """Ambang yang menempel di salah satu sisi akan goyah pada video lain."""
        from app.services.reframe import FACECAM_LUAS_MAKS
        self.assertGreater(FACECAM_LUAS_MAKS - 0.119, 0.03)
        self.assertGreater(0.237 - FACECAM_LUAS_MAKS, 0.03)


class BatasBidikanTidakBolehBeruntun(unittest.TestCase):
    """
    Getaran bingkai datang dari BATAS rentang filter, bukan dari filternya.

    Diukur tahap demi tahap pada podcast 30 detik, kekasaran = rata-rata
    |percepatan| bingkai sebagai persen lebar sumber:

        mentah 1,0645 -> median 0,8197 -> deadzone 0,7767
        -> EMA 0,0586 -> plafon kecepatan 0,0416

    Satu rentang utuh berakhir di 0,0416. Hasil `_smooth` yang memecahnya per
    bidikan: 0,5722, empat belas kali lipat. Seluruh selisihnya ada di batas
    rentang, dan pada klip itu ada dua belas batas dalam tiga puluh detik,
    yang terdekat berjarak 0,38 detik.
    """

    def _batas_dipakai(self, batas_mentah, jeda_min_sampel):
        """Aturan penyaringan yang dipakai `_smooth`."""
        dipakai, terakhir = [], -(10 ** 9)
        for b in sorted(batas_mentah):
            if b - terakhir >= jeda_min_sampel:
                dipakai.append(b)
                terakhir = b
        return dipakai

    def test_batas_beruntun_disaring(self):
        from app.services.reframe import JEDA_BATAS_MIN, SAMPLE_FPS
        jeda = max(1, int(round(JEDA_BATAS_MIN * SAMPLE_FPS)))
        # Batas pada detik 0, 1.25, 2.5, 3.75, 12 (sampel 8 Hz).
        mentah = [0, 10, 20, 30, 96]
        dipakai = self._batas_dipakai(mentah, jeda)
        self.assertEqual(dipakai, [0, 20, 96])

    def test_batas_yang_berjauhan_tidak_disentuh(self):
        from app.services.reframe import JEDA_BATAS_MIN, SAMPLE_FPS
        jeda = max(1, int(round(JEDA_BATAS_MIN * SAMPLE_FPS)))
        mentah = [0, 40, 100, 200]          # 0, 5, 12,5, dan 25 detik
        self.assertEqual(self._batas_dipakai(mentah, jeda), mentah)

    def test_jeda_minimum_masuk_akal(self):
        """
        Dua detik dipilih dari pengukuran, bukan dari selera:
        2 dtk turun 28% getaran dengan ongkos 0,13 poin ketepatan;
        3 dtk turun 65% tapi p90 galatnya melewati 5%, yaitu keluhan lama
        "bingkainya tidak pas di muka orangnya".
        """
        from app.services.reframe import JEDA_BATAS_MIN
        self.assertGreaterEqual(JEDA_BATAS_MIN, 1.0)
        self.assertLessEqual(JEDA_BATAS_MIN, 2.5)

    def test_penyaring_benar_benar_dipasang_di_smooth(self):
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "reframe.py").read_text(encoding="utf-8")
        potong = sumber.split("bounds: list[int] = []")[1][:400]
        self.assertIn("JEDA_BATAS_MIN", sumber)
        self.assertIn("jeda_min", potong)


class PerbesarDanGeserBingkaiWajah(unittest.TestCase):
    """
    Bingkai wajah memakai SELURUH tinggi sumber, jadi secara tegak tidak ada
    yang bisa digeser: potongannya sudah setinggi gambarnya. Memperbesar
    memotong lebih sedikit dari tingginya, dan barulah ada sisa untuk memilih
    bagian mana yang dipakai.

    Diminta 25 September 2026: sisipan ditaruh di atas menutupi wajah, dan
    wajahnya tidak bisa dipindahkan ke bawah.
    """

    class Rencana:
        crop_w, crop_h, source_w, source_h = 608, 1080, 1920, 1080

    def _petak(self, zoom=1.0, geser=0.0):
        from app.services.reframe import petak_zoom
        return petak_zoom(self.Rencana(), zoom, geser)

    def test_tanpa_perbesaran_sama_persis_dengan_sebelumnya(self):
        """Klip yang tidak menyentuh setelan ini tidak boleh berubah sedikit pun."""
        w, h, y = self._petak()
        self.assertEqual((w, h, y), (608, 1080, 0))

    def test_tanpa_perbesaran_geseran_tidak_berpengaruh(self):
        """Tidak ada ruang untuk digeser, jadi angka apa pun harus jadi nol."""
        for g in (-100, -1, 0, 50, 100):
            self.assertEqual(self._petak(1.0, g)[2], 0)

    def test_perbesaran_memberi_ruang_tegak(self):
        w, h, _ = self._petak(1.5)
        self.assertLess(h, 1080)
        self.assertLess(w, 608)
        # Rasio potongannya tetap, kalau tidak gambarnya akan diregangkan.
        self.assertAlmostEqual(w / h, 608 / 1080, places=2)

    def test_angkanya_memindahkan_WAJAH_bukan_jendelanya(self):
        """
        Keduanya berlawanan, dan ini yang paling mudah terbalik: menurunkan
        JENDELA berarti mengambil bagian bawah sumber, dan wajah yang tadinya
        di tengah lalu NAIK di layar. Yang diminta pemiliknya adalah wajahnya
        yang turun, supaya sisipan di atasnya tidak menutupinya.
        """
        _, h, wajah_naik = self._petak(1.5, -100)
        _, _, tengah = self._petak(1.5, 0)
        _, _, wajah_turun = self._petak(1.5, 100)
        # Wajah turun = jendela naik = y kecil.
        self.assertEqual(wajah_turun, 0)
        self.assertEqual(wajah_naik, 1080 - h)
        self.assertEqual(tengah, (1080 - h) // 2)
        self.assertLess(wajah_turun, tengah)
        self.assertLess(tengah, wajah_naik)

    def test_pratinjau_memakai_tanda_yang_sama(self):
        """
        Pratinjau menghitung geserannya sendiri di peramban. Tandanya harus
        sama, kalau tidak yang terlihat di Studio berlawanan dengan hasil
        rendernya, dan itu cacat yang baru ketahuan sesudah merender.
        """
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[2] / "frontend" / "src"
                  / "features" / "studio" / "ClipPreview.jsx").read_text(encoding="utf-8")
        self.assertIn("0.5 - Math.max(-100, Math.min(100, Number(frameGeserY) || 0)) / 200",
                      sumber)

    def test_tidak_pernah_keluar_gambar(self):
        for z in (1.0, 1.1, 1.7, 2.0):
            for g in (-999, -100, 0, 100, 999):
                w, h, y = self._petak(z, g)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(y + h, 1080)
                self.assertLessEqual(w, 1920)

    def test_perbesaran_dijepit(self):
        """Di atas 2x, sumber 1080p tinggal 540 piksel dan hasilnya bubur."""
        from app.services.reframe import ZOOM_MAKS
        self.assertEqual(self._petak(9.0), self._petak(ZOOM_MAKS))

    def test_ukuran_selalu_genap(self):
        for z in (1.0, 1.13, 1.37, 1.62, 2.0):
            w, h, _ = self._petak(z)
            self.assertEqual(w % 2, 0, f"lebar ganjil pada zoom {z}")
            self.assertEqual(h % 2, 0, f"tinggi ganjil pada zoom {z}")


class PerpindahanOrangDipotongBukanDiPan(unittest.TestCase):
    """
    "Ada 1 detik bingkai tidak mengikuti wajah", dilaporkan 25 September 2026.

    Ditelusuri sampel demi sampel pada podcast Dokter Tirta: penuturnya
    berganti DI DALAM satu bidikan, 543 piksel atau 28% lebar layar, tanpa
    potongan adegan yang menandainya. Penghalus dua arah bersifat non-kausal,
    jadi kotaknya mulai bergerak 1,6 detik SEBELUM perpindahannya dan sudah
    meninggalkan orang pertama sebelum orang kedua bicara. Selama 0,88 detik
    bingkainya tidak memuat siapa pun.
    """

    def _jejak(self, lompat_di=None, n=240, sw=1920):
        """Jejak datar, dengan satu perpindahan mendadak bila diminta."""
        kiri, kanan = 470.0, 1013.0
        return [(kiri if (lompat_di is None or i < lompat_di) else kanan)
                for i in range(n)]

    def test_perpindahan_besar_jadi_batas_bidikan(self):
        from app.services.reframe import SAMPLE_FPS, _smooth
        sw, crop_w = 1920, 608
        centers = self._jejak(lompat_di=120)
        out = _smooth(centers, [False] * len(centers), source_w=sw, crop_w=crop_w)
        # Sesudah perpindahan, kotak harus SEGERA berada di orang barunya:
        # setengah detik cukup, sedangkan mem-pan 28% lebar butuh lebih dari
        # sedetik pada plafon kecepatan mana pun yang masuk akal.
        # `_smooth` mengembalikan PUSAT potongan, bukan tepi kirinya.
        i = 120 + int(0.5 * SAMPLE_FPS)
        galat = abs(out[i] - 1013.0) / sw * 100
        self.assertLess(galat, 8.0, f"kotak masih {galat:.1f}% dari wajah barunya")

    def test_gerakan_kepala_biasa_tidak_memotong(self):
        """
        Yang dipotong hanya perpindahan sebesar ORANG LAIN. Gerakan kepala
        antar sampel terukur 1 sampai 2% lebar; memotong di situ akan membuat
        bingkai berkedip sepanjang klip.
        """
        from app.services.reframe import _smooth
        sw, crop_w = 1920, 608
        # Bergoyang 2% lebar, jauh di bawah ambang.
        centers = [900 + (38 if i % 2 else 0) for i in range(120)]
        out = _smooth(centers, [False] * len(centers), source_w=sw, crop_w=crop_w)
        lompatan = [abs(out[i] - out[i - 1]) / sw * 100 for i in range(1, len(out))]
        self.assertLess(max(lompatan), 2.0,
                        "goyangan kepala tidak boleh menghasilkan potongan")

    def test_ambangnya_di_antara_keduanya(self):
        """Di atas gerakan kepala (2%), di bawah pergantian orang (28%)."""
        from app.services.reframe import LOMPAT_POTONG
        self.assertGreater(LOMPAT_POTONG, 0.04)
        self.assertLess(LOMPAT_POTONG, 0.20)

    def test_plafon_kecepatan_tidak_lagi_menahan_terlalu_lama(self):
        """
        0,10 lebar per detik terukur menahan kamera di belakang wajahnya:
        perpindahan 15,9% lebar butuh 1,6 detik. Diukur pada empat podcast,
        di atas 0,16 plafonnya berhenti mengikat sama sekali.
        """
        from app.services.reframe import MAX_SPEED_RATIO
        self.assertGreaterEqual(MAX_SPEED_RATIO, 0.16)
