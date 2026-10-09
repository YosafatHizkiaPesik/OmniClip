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

    def test_dua_bidang_menutup_tinggi_layar_tanpa_celah(self):
        tata = susun_layout_gaming(self.FACECAM, src_w=1920, src_h=1080,
                                   out_w=1080, out_h=1920)
        bidang = tata["frames"]
        self.assertEqual(len(bidang), 2)
        tinggi = sum(f["dst"]["h"] for f in bidang)
        self.assertAlmostEqual(tinggi, 100.0, places=3)
        for f in bidang:
            for sisi in ("x", "y", "w", "h"):
                self.assertGreaterEqual(f["src"][sisi], -0.001)

    def test_permainan_selebar_layar_penuh(self):
        """Bidang permainan tidak boleh menyusut: itu isi klipnya."""
        tata = susun_layout_gaming(self.FACECAM, src_w=1920, src_h=1080,
                                   out_w=1080, out_h=1920)
        main = tata["frames"][0]
        self.assertAlmostEqual(main["dst"]["x"], 0.0, places=3)
        self.assertAlmostEqual(main["dst"]["w"], 100.0, places=3)

    def test_bidang_wajah_selebar_kanvas(self):
        """
        Bidang wajah mengisi lebar kanvas, tanpa sisa di kiri dan kanan.

        Sempat dipersempit mengikuti bentuk kotak facecam, 1 Oktober 2026, atas
        usul pemiliknya sendiri. Secara ukuran itu memang jadi persis, tapi yang
        ia lihat kotak kecil di tengah dengan permainan kabur di kiri-kanannya:
        "tampilannya malah berbeda dengan yang saya minta". Diminta kembali
        seperti semula di hari yang sama.

        Yang menjaga potongannya tidak ikut membawa meja dan dinding bukan
        lebar bidangnya, melainkan `kotak_reaksi`: ia memotong dengan KEPALA
        sebagai acuan dan tidak pernah keluar dari panel facecamnya.
        """
        tata = susun_layout_gaming(self.FACECAM, src_w=1920, src_h=1080,
                                   out_w=1080, out_h=1920)
        wajah = tata["frames"][1]["dst"]
        self.assertAlmostEqual(wajah["x"], 0.0, places=3)
        self.assertAlmostEqual(wajah["w"], 100.0, places=3)

    def test_tiap_bingkai_punya_id_yang_berbeda(self):
        """
        Studio memilih kotak yang sedang diseret dengan
        `frames.find(f => f.id === frameId)`. Tanpa id, DUA kotak sama-sama
        cocok dengan `undefined`: menyeret kotak Reaksi menulis potongannya ke
        Permainan juga, dan keduanya langsung bertumpuk jadi satu kotak.
        Dilaporkan pemiliknya 1 Oktober 2026.

        Dulu susunan ini selalu lewat `susunanDariServer` di peramban, yang
        memasang id sendiri. Sejak pemanasan menuliskan susunannya langsung ke
        `frame_keys`, jalan itu tidak lagi selalu dilalui.
        """
        tata = susun_layout_gaming(self.FACECAM, src_w=1920, src_h=1080,
                                   out_w=1080, out_h=1920)
        id_ = [f.get("id") for f in tata["frames"]]
        self.assertTrue(all(id_), "ada bingkai tanpa id")
        self.assertEqual(len(set(id_)), len(id_), "id bingkai tidak unik")

    def test_potongan_wajah_tidak_jauh_keluar_panel_facecam(self):
        """
        Yang tampil di bidang wajah harus isi facecam, dengan kelonggaran yang
        TERBATAS dan disengaja di kiri-kanannya.

        Dua permintaan pemiliknya bertabrakan di sini, dan keduanya sah.

        30 September 2026: "bingkai wajahnya terlalu besar melebihi facecam
        bahkan memotong bingkai game". Sejak itu potongan dikurung di dalam
        panel.

        9 Oktober 2026: "bingkai untuk wajahnya terlalu crop wajahnya saja,
        seharusnya dilebihkan juga untuk crop badannya". Kurungan itu membuang
        29% tinggi panel, dan di situlah bahu dan dadanya; terukur pada klip
        pemiliknya, wajahnya jadi 47% lebar kanvas.

        Yang dipakai sekarang bukan membuang kurungannya melainkan memberinya
        batas: melampaui panel ke SAMPING sebanyak LUAR_PANEL_MAKS, demi
        memakai seluruh tinggi panel. Hasilnya wajah 33% lebar kanvas dengan
        14% bidang berisi permainan di tiap sisi. Nol mengembalikan aturan
        30 September persis.
        """
        for panel in (self.FACECAM,
                      {"x": 70.0, "y": 60.0, "w": 28.0, "h": 36.0},
                      {"x": 0.0, "y": 0.0, "w": 16.0, "h": 50.0}):
            with self.subTest(panel=panel):
                src = susun_layout_gaming(panel, src_w=1920, src_h=1080,
                                          out_w=1080, out_h=1920)["frames"][1]["src"]
                from app.services.render import LUAR_PANEL_MAKS
                self.assertGreaterEqual(src["y"], panel["y"] - 0.05)
                self.assertLessEqual(
                    src["w"], panel["w"] * (1 + 2 * LUAR_PANEL_MAKS) + 0.05)
                # Dan panelnya tetap jadi isi utamanya: lebih dari separuh
                # bidang wajah harus benar-benar facecam.
                tumpang = (min(src["x"] + src["w"], panel["x"] + panel["w"])
                           - max(src["x"], panel["x"]))
                self.assertGreater(tumpang / src["w"], 0.55,
                                   "bidang wajah lebih banyak permainan daripada facecam")
                self.assertLessEqual(src["y"] + src["h"],
                                     panel["y"] + panel["h"] + 0.05)

    def test_potongan_sebesar_mungkin_di_dalam_panel(self):
        """
        Syarat yang diminta pemiliknya, 1 Oktober 2026: "bingkai wajah benar-
        benar presisi dengan kotak facecam, tidak boleh lebih bahkan hingga
        memotong sampai ke dalam bingkai game, tapi jika bingkai hanya kurang
        atau lebih kecil sedikit dari kotak facecam maka tidak masalah".

        Jadi dua hal, dan urutannya penting: tidak boleh LEBIH (keras), dan
        sekecil-kecilnya kurang (sebisanya). Yang kedua inilah yang dulu
        dilanggar — potongan diukur dari kepala, jadi ia lebih kecil daripada
        panelnya di kedua sisi sekaligus.

        "Tidak boleh lebih" dilonggarkan 9 Oktober 2026, atas permintaannya
        yang lain: ke SAMPING saja, sebanyak LUAR_PANEL_MAKS lebar panel, demi
        memakai seluruh tinggi panel sehingga bahunya ikut masuk. Ke atas dan
        ke bawah tetap tidak boleh lebih, karena di situlah bingkai permainan
        yang tidak boleh terpotong.
        """
        for panel in (self.FACECAM,
                      {"x": 70.0, "y": 60.0, "w": 28.0, "h": 36.0},
                      {"x": 2.0, "y": 10.0, "w": 6.0, "h": 70.0,
                       "awan_kotak": [3.0, 14.0, 7.0, 24.0]},
                      {"x": 5.0, "y": 5.0, "w": 40.0, "h": 12.0}):
            with self.subTest(panel=panel):
                tata = susun_layout_gaming(panel, src_w=1920, src_h=1080,
                                           out_w=1080, out_h=1920)
                src = tata["frames"][1]["src"]
                # Tidak boleh LEBIH ke atas dan ke bawah: di situlah bingkai
                # permainan yang tidak boleh terpotong.
                self.assertGreaterEqual(src["y"], panel["y"] - 0.05)
                self.assertLessEqual(src["y"] + src["h"], panel["y"] + panel["h"] + 0.05)
                # Ke samping boleh, sebatas yang disengaja. Batasnya TOTAL,
                # bukan per sisi: panel yang menempel tepi layar melempar
                # seluruh kelonggarannya ke satu sisi, dan itu benar.
                from app.services.render import LUAR_PANEL_MAKS
                self.assertLessEqual(
                    src["w"], panel["w"] * (1 + 2 * LUAR_PANEL_MAKS) + 0.05,
                    "potongan melampaui panel lebih jauh dari yang disengaja")
                # Dan sebesar yang bentuknya izinkan: tidak boleh lebih kecil
                # daripada panelnya di KEDUA sisi sekaligus. Itulah kesalahan
                # aslinya, saat potongan diukur dari kepala alih-alih dari
                # panel. Satu sisi boleh lebih besar sekarang (lihat
                # LUAR_PANEL_MAKS), dan itu tetap memenuhi syarat ini.
                cukup_lebar = src["w"] >= panel["w"] - 0.05
                cukup_tinggi = src["h"] >= panel["h"] - 0.05
                self.assertTrue(cukup_lebar or cukup_tinggi,
                                f"potongan {src['w']}x{src['h']} lebih kecil dari "
                                f"panel {panel['w']}x{panel['h']} di KEDUA sisi")

    def test_panel_terlalu_tegak_dipotong_dengan_kepala_sebagai_acuan(self):
        """
        Panel tegak tidak bisa mengisi bidang selebar kanvas, jadi ia harus
        dipotong. Yang dipotong tidak boleh kepalanya.

        Sebelum 1 Oktober 2026 kurungan panel mengembalikan kotak yang
        dipaskan di TENGAH panel, tanpa tahu di mana kepalanya. Pada panel
        6% x 70% dengan kepala di y 14-24%, potongannya mulai di y 37,9% —
        di bawah dagu. Yang terlihat di bidang wajah cuma dada dan perut.
        """
        panel = {"x": 2.0, "y": 10.0, "w": 6.0, "h": 70.0,
                 "awan_kotak": [3.0, 14.0, 7.0, 24.0]}
        src = susun_layout_gaming(panel, src_w=1920, src_h=1080,
                                  out_w=1080, out_h=1920)["frames"][1]["src"]
        # Bukan panel utuh: tingginya dipotong supaya pas bentuk bidangnya.
        self.assertLess(src["h"], panel["h"] - 1.0)
        # Potongan selebar panel 6% hanya setinggi 5,7%, sementara kepalanya
        # 10%: memuatnya UTUH memang mustahil di sini. Yang bisa dituntut, dan
        # yang benar-benar menentukan tampilannya, adalah potongan itu jatuh di
        # KEPALA — bukan di tengah panel, yang pada panel setinggi 70% berarti
        # dada dan perut.
        pusat = src["y"] + src["h"] / 2
        atas, bawah = panel["awan_kotak"][1], panel["awan_kotak"][3]
        self.assertGreaterEqual(pusat, atas)
        self.assertLessEqual(pusat, bawah)

    def test_tinggi_panel_wajah_dijaga_di_rentang_yang_masuk_akal(self):
        """
        Panel wajah yang terlalu pendek memotong dagu, yang terlalu tinggi
        menyisakan sedikit ruang untuk permainannya.

        Batas bawahnya turun dari 40 ke 30 pada 25 September 2026, atas
        permintaan pemiliknya: "adjust lagi agar tampilan game lebih besar
        daripada reaksi". Yang jadi isi klip memang permainannya; wajah pemain
        di situ reaksi, bukan subjek. Yang menjaga agar tidak terlalu pendek
        bukan angka ini melainkan `tinggi_wajah_otomatis` sendiri, yang naik
        lagi begitu kotak reaksinya tidak muat.
        """
        from app.services.render import GAMING_WAJAH_MAKS, GAMING_WAJAH_MIN
        posisi = [{"facecam": dict(self.FACECAM, awan_kotak=None)}]
        n = tinggi_wajah_otomatis(posisi, 1920 / 1080, 1080, 1920)
        self.assertGreaterEqual(n, GAMING_WAJAH_MIN)
        self.assertLessEqual(n, GAMING_WAJAH_MAKS)

    def test_permainan_dapat_bagian_lebih_besar_daripada_wajah(self):
        """Inti permintaannya, dinyatakan sebagai angka: wajah di bawah separuh."""
        from app.services.render import GAMING_WAJAH_MAKS, GAMING_WAJAH_TINGGI
        self.assertLess(GAMING_WAJAH_TINGGI, 50.0)
        # Dan bawaannya jelas lebih kecil daripada bagian permainannya.
        self.assertLess(GAMING_WAJAH_TINGGI, 100 - GAMING_WAJAH_TINGGI)
        # Batas atasnya pun harus menyisakan lebih dari separuh untuk
        # permainan. Turun dari 50 ke 40 pada 25 September 2026, atas permintaan
        # pemiliknya: "wajahnya terlalu besar, buat saja 30-40% untuk wajah".
        # Panel facecam bentuk tinggi yang tidak muat di 40% dibetulkan dengan
        # menyeret pembatasnya di pratinjau, bukan dengan menaikkan batas ini.
        self.assertLessEqual(GAMING_WAJAH_MAKS, 40.0)
        self.assertLess(GAMING_WAJAH_MAKS, 100 - GAMING_WAJAH_MAKS)

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
