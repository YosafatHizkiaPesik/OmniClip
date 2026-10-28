"""
Besar bidang wajah pada susunan Main game.

Pemiliknya dua kali melaporkan hal yang sama: wajah pemain terlalu besar, dan
permainan — yang sebenarnya jadi isi klip — tinggal separuh kanvas. Yang
pertama dijawab dengan menurunkan titik berangkatnya (40 -> 32), yang kedua
dengan menurunkan batas atas otomatisnya (50 -> 40) dan dengan pembatas yang
bisa diseret di pratinjau.

Uji ini menjaga dua hal: bidang wajah otomatis tidak pernah lebih dari 40%,
dan pembatas di pratinjau memanggil penyusun yang sama dengan penggeser di
panel — dua jalur yang menghitung susunan yang sama adalah cara pratinjau
mulai berbeda dari hasil render.
"""

import re
import unittest
from pathlib import Path

from teks_ui import teks_ui

from app.services.render import (
    GAMING_WAJAH_MAKS, GAMING_WAJAH_MIN, GAMING_WAJAH_TINGGI,
    kotak_reaksi, susun_layout_gaming, tinggi_wajah_otomatis,
)

AKAR = Path(__file__).resolve().parents[2]
PRATINJAU = AKAR / "frontend" / "src" / "features" / "studio" / "ClipPreview.jsx"
EDITOR = AKAR / "frontend" / "src" / "features" / "studio" / "Editor.jsx"


def _panel(w: float, h: float) -> dict:
    """Panel facecam di pojok kanan bawah, dengan petak wajah di dalamnya."""
    fc = {"x": 100.0 - w - 1.0, "y": max(0.0, 98.0 - h), "w": w, "h": h}
    cx, cy = fc["x"] + w / 2, fc["y"] + h * 0.38
    fc["awan_kotak"] = [cx - w * 0.22, cy - h * 0.09, cx + w * 0.22, cy + h * 0.09]
    return fc


BENTUK = [(w, h) for w in (12, 16, 20, 25, 30, 36, 44)
          for h in (18, 26, 34, 45, 60, 75, 90)]


class BidangWajahOtomatis(unittest.TestCase):
    def test_tidak_pernah_lebih_dari_40_persen(self):
        """
        Permintaan pemiliknya: 30-40% untuk wajah, sisanya permainan.

        Sebelum ini batas atasnya 50, dan pada panel facecam yang sempit dan
        tinggi ia benar-benar terpakai: permainan tinggal separuh kanvas.
        """
        self.assertEqual(GAMING_WAJAH_MAKS, 40.0)
        for w, h in BENTUK:
            with self.subTest(panel=f"{w}x{h}"):
                nilai = tinggi_wajah_otomatis(
                    [{"t": 0.0, "facecam": _panel(w, h)}], 16 / 9, 1080, 1920)
                self.assertGreaterEqual(nilai, GAMING_WAJAH_MIN)
                self.assertLessEqual(nilai, GAMING_WAJAH_MAKS)

    def test_titik_berangkat_ada_di_dalam_rentangnya(self):
        self.assertGreaterEqual(GAMING_WAJAH_TINGGI, GAMING_WAJAH_MIN)
        self.assertLessEqual(GAMING_WAJAH_TINGGI, GAMING_WAJAH_MAKS)

    def test_permainan_selalu_dapat_lebih_dari_separuh(self):
        """Yang jadi isi klip adalah permainannya; wajah di situ reaksi."""
        for w, h in BENTUK:
            with self.subTest(panel=f"{w}x{h}"):
                tata = susun_layout_gaming(_panel(w, h), src_w=1920, src_h=1080,
                                           out_w=1080, out_h=1920)
                main = next(f for f in tata["frames"] if f["label"] == "Permainan")
                self.assertGreater(main["dst"]["h"], 50.0)

    def test_kedua_bidang_bertemu_tanpa_celah(self):
        """Celah di antara keduanya tampil sebagai bilah kosong di klip jadinya."""
        for w, h in BENTUK[:12]:
            with self.subTest(panel=f"{w}x{h}"):
                tata = susun_layout_gaming(_panel(w, h), src_w=1920, src_h=1080,
                                           out_w=1080, out_h=1920)
                muka = next(f for f in tata["frames"] if f["label"] == "Reaksi")
                main = next(f for f in tata["frames"] if f["label"] == "Permainan")
                self.assertAlmostEqual(muka["dst"]["y"] + muka["dst"]["h"],
                                       main["dst"]["y"], places=2)
                self.assertAlmostEqual(main["dst"]["y"] + main["dst"]["h"],
                                       100.0, places=2)

    def test_wajah_yang_disetel_tangan_dihormati(self):
        """Pembatas yang diseret pengguna menang atas tebakan otomatis."""
        for minta in (18.0, 30.0, 44.0, 70.0):
            tata = susun_layout_gaming(_panel(25, 38), wajah=minta,
                                       src_w=1920, src_h=1080, out_w=1080, out_h=1920)
            self.assertAlmostEqual(tata["gaming"]["wajah"], minta, places=2)

    def test_potongan_wajah_ikut_berubah_saat_bidangnya_berubah(self):
        """
        Bidang yang lebih pendek berarti potongan sumbernya lebih lebar.

        Kalau potongannya tidak ikut dihitung ulang, menyeret pembatas akan
        meregangkan wajahnya, bukan membingkainya ulang.
        """
        fc = _panel(25, 38)
        a = susun_layout_gaming(fc, wajah=25.0, out_w=1080, out_h=1920)
        b = susun_layout_gaming(fc, wajah=50.0, out_w=1080, out_h=1920)
        ra = next(f for f in a["frames"] if f["label"] == "Reaksi")["src"]
        rb = next(f for f in b["frames"] if f["label"] == "Reaksi")["src"]
        self.assertGreater(ra["w"] / ra["h"], rb["w"] / rb["h"])


class SinggahanFacecam(unittest.TestCase):
    """
    Yang disimpan adalah PEMINDAIAN, bukan susunan jadinya.

    Sebelum ini susunan ikut tersimpan, dan begitu aturannya berubah klip yang
    pernah dibuka memakai susunan lama selamanya. Terlihat saat mengujinya:
    batas atas sudah turun ke 40%, satu video gameplay masih menjawab 47,5%.
    """

    def test_yang_disimpan_hanya_letak_panelnya(self):
        rute = (AKAR / "backend" / "app" / "routers" / "clips.py").read_text(encoding="utf-8")
        badan = rute[rute.index("async def clip_facecam"):]
        badan = badan[:badan.index("\n@router")] if "\n@router" in badan else badan
        # Yang ditulis ke simpanan tidak boleh memuat susunan jadinya.
        #
        # `potongan` boleh: ia hasil PEMINDAIAN juga (bagian mana klip ini
        # permainan, bagian mana wajah satu layar penuh), bukan susunan yang
        # diturunkan dari aturan yang bisa berubah. Susunan di dalamnya tetap
        # disusun ulang tiap kali oleh `susun()`.
        self.assertIn('"posisi": posisi or [], "src_w": w, "src_h": h', badan)
        simpanan = badan[badan.index("def kerja():"):badan.index("pindai = await")]
        self.assertNotIn("susun_layout_gaming", simpanan,
                         "susunan jadinya ikut tersimpan")
        # Dan susunannya dihitung ulang, juga saat simpanannya kena.
        self.assertIn('if tersimpan is not None and "posisi" in tersimpan:', badan)
        self.assertIn("return susun(tersimpan)", badan)

    def test_pemanasan_menyimpan_bentuk_yang_sama(self):
        """
        Pemanasan menulis ke simpanan yang SAMA dengan yang dibaca endpoint,
        LENGKAP dengan pemecahan klipnya.

        Bentuk yang berbeda berarti pemanasan mengisi simpanan dengan sesuatu
        yang endpoint-nya tidak kenali, lalu memindai ulang semuanya: kerja
        dua kali, dan justru pada jalur yang ada untuk menghemat kerja.

        `potongan` ditambahkan 1 Oktober 2026. Sebelumnya pemanasan menyimpan
        letak panelnya saja, jadi setengah pekerjaannya tersisa untuk Studio:
        lajur Bingkai baru terpecah saat klipnya DIBUKA, satu per satu,
        sementara pekerjaannya sudah melaporkan diri selesai. Dilaporkan
        pemiliknya: "proses sudah selesai namun bingkai belum tersusun".
        """
        awal = (AKAR / "backend" / "app" / "services" / "bingkai_awal.py").read_text(
            encoding="utf-8")
        self.assertIn('"posisi": posisi or [], "src_w": w, "src_h": h', awal)
        self.assertIn('"potongan": _potongan_game(str(src), segmen, posisi)', awal)
        self.assertIn('if tersimpan is not None and "posisi" in tersimpan:', awal)
        # Simpanan lama yang belum punya pemecahan ikut dilengkapi, bukan
        # dibiarkan menyisakan pekerjaan itu ke Studio selamanya.
        self.assertIn('if "potongan" not in tersimpan', awal)

    def test_pemanasan_menuliskan_bingkainya_ke_klip(self):
        """
        Pemanasan yang melaporkan diri selesai harus benar-benar MENYUSUN
        bingkainya, bukan cuma menghangatkan simpanan.

        Dan tidak boleh menimpa kunci yang sudah ada — milik pengguna maupun
        milik sutradara.
        """
        awal = (AKAR / "backend" / "app" / "services" / "bingkai_awal.py").read_text(
            encoding="utf-8")
        self.assertIn("def _tulis_bingkai(", awal)
        self.assertIn('if _tulis_bingkai(video_id, klip.get("clip_id"), segmen, rasio):',
                      awal)
        badan = awal[awal.index("def _tulis_bingkai("):]
        badan = badan[:badan.index("\ndef ", 10)]
        self.assertIn('klip[sasaran].get("frame_keys")', badan)
        self.assertIn("return False", badan)
        # clip_id harus ikut sampai ke sini, kalau tidak tidak ada yang bisa
        # ditulisi.
        pipa = (AKAR / "backend" / "app" / "services" / "pipeline.py").read_text(
            encoding="utf-8")
        self.assertIn('"clip_id": c.get("clip_id")', pipa)


class IdBingkaiDiSusunanTersimpan(unittest.TestCase):
    """
    Susunan yang terlanjur tersimpan tanpa id harus disembuhkan saat DIBACA.

    Memperbaiki sumbernya tidak mengubah apa yang sudah ada di `frame_keys`
    milik proyek orang, dan di sana akibatnya langsung terasa: menyeret satu
    kotak memindahkan keduanya.
    """

    def test_frames_js_punya_penyembuhnya(self):
        js = (AKAR / "frontend" / "src" / "features" / "studio"
              / "frames.js").read_text(encoding="utf-8")
        self.assertIn("export function berIdLengkap", js)

    def test_editor_memakainya_untuk_susunan_dari_kunci(self):
        jsx = (AKAR / "frontend" / "src" / "features" / "studio"
               / "Editor.jsx").read_text(encoding="utf-8")
        self.assertIn("berIdLengkap(kunciBingkaiAktif.layout)", jsx)
        # Lewat useMemo: id yang berganti tiap render memutus seretan yang
        # sedang berjalan.
        self.assertIn("const kunciLayout = useMemo(", jsx)


class PembatasDiPratinjau(unittest.TestCase):
    """Dibaca sebagai teks; proyek ini tidak punya penjalan uji JavaScript."""

    def test_pratinjau_punya_pembatas_yang_bisa_diseret(self):
        jsx = PRATINJAU.read_text(encoding="utf-8")
        self.assertIn("onGamingWajah", jsx)
        self.assertIn("startBatasDrag", jsx)
        # Batasnya harus sama dengan `susunGaming` di frames.js, kalau tidak
        # pratinjau membiarkan nilai yang penyusunnya sendiri akan menjepit.
        self.assertIn("Math.max(15, Math.min(75,", jsx)

    def test_editor_menyambungkannya_ke_penyusun_yang_sama(self):
        """
        Pembatas dan penggeser panel HARUS memanggil `setelGaming` yang sama.

        Menulis `dst` kedua kotak sendiri dari pratinjau akan melupakan
        potongan sumbernya, dan susunan di layar berbeda dari yang dirender.
        """
        jsx = EDITOR.read_text(encoding="utf-8")
        self.assertRegex(jsx, r"onGamingWajah=\{\(wajah\) => setelGaming\(\{ wajah \}\)\}")


if __name__ == "__main__":
    unittest.main()


class MutuPratinjauDiKanvas(unittest.TestCase):
    """
    Dua keluhan yang tampak bertentangan, dan jalan keluarnya.

    "Lebih baik preview kualitas terbaik daripada lancar tapi jelek"
    (1 Oktober 2026), lalu — sesudah kerapatan kanvas dinaikkan sampai ukuran
    render — "video looping atau hitam terjadi lagi".

    Keduanya benar. Ongkos penskalaan kanvas pada Firefox tiga puluh kali
    ongkosnya pada Chromium (terukur: 15,33 ms lawan 0,49 ms untuk 1080x1920),
    dan 15 ms per bingkai di atas pembacaan dekoder memang meruntuhkan
    pemutaran. Yang memisahkan keduanya BUKAN satu angka melainkan keadaan:
    yang bergerak dibuat lancar, yang diam dibuat setajam hasil render.
    """

    def setUp(self):
        self.jsx = teks_ui(PRATINJAU)

    def test_kerapatan_mengikuti_berjalan_atau_dijeda(self):
        self.assertIn("const diam = v.paused && !berubah;", self.jsx)
        # "Dijeda" saja tidak cukup: menggeser garis main pada pratinjau yang
        # berhenti mengganti bingkainya puluhan kali sedetik.
        self.assertIn("const berubah = v.currentTime !== waktuGambarRef.current;",
                      self.jsx)
        # Dijeda: sampai plafon ukuran render. Berjalan: dijepit dua kali.
        self.assertIn("const dpr = diam", self.jsx)
        self.assertIn("Math.min(Math.max(dprLayar, 2)", self.jsx)

    def test_bingkai_diam_tidak_digambar_ulang(self):
        """
        Loop rAF memanggil penggambar enam puluh kali sedetik, juga saat
        videonya berhenti. Tanpa penjaga ini, pratinjau yang dijeda membakar
        15 ms tiap bingkai layar untuk menggambar gambar yang sama persis.
        """
        self.assertIn("if (sidikGambarRef.current === sidik) return;", self.jsx)
        # Ukuran kanvas ikut ke dalam sidiknya; itu yang membuat bingkai yang
        # sama digambar sekali lagi dengan rapat penuh saat gambarnya berhenti.
        self.assertIn("const sidik = `${v.currentTime}|${bw}x${bh}|${tandaFrames}`;",
                      self.jsx)
        # Sidiknya harus ikut berubah saat kotaknya digeser, kalau tidak
        # menyeret kotak pada pratinjau yang dijeda tidak terlihat apa-apa.
        self.assertIn("tandaFrames", self.jsx)

    def test_hitam_selalu_punya_keterangan(self):
        """
        "Apakah layar hitam ini pertanda bahwa sistem sedang menyiapkan
        preview, jika iya hingga kapan saya harus menunggu" — pertanyaan yang
        tidak boleh dijawab dengan menebak warna.
        """
        self.assertIn("pakaiKanvas && !kanvasSiap", self.jsx)
        self.assertIn("Menyiapkan pratinjau", self.jsx)
        self.assertIn("pratinjau-merayap", self.jsx)
        # Dan kesiapan itu ditandai hanya sesudah bingkai benar-benar terbaca.
        self.assertIn("kanvasSiapRef.current = true;", self.jsx)

    def test_bilahnya_ada_di_lembar_gaya(self):
        css = (AKAR / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
        self.assertIn("@keyframes pratinjau-merayap", css)
        self.assertIn("prefers-reduced-motion", css)


class FacecamHanyaKepalaDilonggarkan(unittest.TestCase):
    """
    18 Oktober 2026, MiawAug (facecam tanpa bingkai): kotak terdeteksi 15x29%
    untuk wajah 7x15%, jadi bidang wajah hanya berisi kepala.
    """

    def test_kotak_sempit_dilonggarkan(self):
        from app.services.render import kotak_reaksi
        r = kotak_reaksi({"x": 77.24, "y": 69.27, "w": 15.32, "h": 28.56},
                         [81.19, 70.34, 88.3, 84.88], 1080 / 768, 16 / 9)
        # Sama persis dengan uji kembarannya di frames.test.js.
        self.assertEqual(r, {"x": 72.49, "y": 61.62, "w": 24.51, "h": 30.99})

    def test_panel_wajar_tidak_berubah(self):
        from app.services.render import _longgarkan_wajah
        k = {"x": 10, "y": 10, "w": 30, "h": 40}
        self.assertIsNone(_longgarkan_wajah(dict(k), k, [18, 15, 28, 28], 1080 / 768, 16 / 9))

    def test_konstanta_sama_dengan_frames_js(self):
        import re
        from app.services import render
        js = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "features"
              / "studio" / "frames.js").read_text(encoding="utf-8")
        for nama in ("LONGGAR_PICU", "LONGGAR_ATAS", "LONGGAR_BADAN", "LONGGAR_LEBAR"):
            m = re.search(rf"const {nama} = ([0-9.]+);", js)
            self.assertIsNotNone(m, nama)
            self.assertAlmostEqual(float(m.group(1)), getattr(render, nama), msg=nama)


class FacecamTidakMembanjirPermainan(unittest.TestCase):
    """
    28 Oktober 2026, klip Windah: potongan reaksi 51 x 48% layar untuk kotak
    facecam 18 x 34%, separuh permainan masuk ke bidang wajah. Contoh yang
    disusun pemiliknya sendiri: reaksi kira-kira x 74, y 64, 24 x 36%, bidang
    wajah 37%.
    """
    F = {"x": 78.78, "y": 65.62, "w": 18.0, "h": 34.38,
         "awan_kotak": [83.69, 75.12, 91.88, 93.71]}

    def test_lebar_dibatasi_dan_badan_masuk(self):
        from app.services.render import LONGGAR_LEBAR, kotak_reaksi
        for wajah in (30, 35, 40):
            r = kotak_reaksi(self.F, self.F["awan_kotak"], 1080 / (1920 * wajah / 100), 16 / 9)
            self.assertLessEqual(r["w"], LONGGAR_LEBAR * self.F["w"] + 0.01, wajah)
            self.assertLess(r["y"], 75.12, wajah)              # kepala utuh
            self.assertGreater(r["y"] + r["h"], 93.71, wajah)  # sampai di bawah dagu

    def test_bidang_wajah_otomatis_memilih_yang_memuat_badan(self):
        from app.services.render import susun_layout_gaming
        l = susun_layout_gaming(self.F)
        self.assertEqual(l["gaming"]["wajah"], 40.0)
        reaksi = l["frames"][1]["src"]
        self.assertAlmostEqual(reaksi["y"], 64, delta=3)
        self.assertAlmostEqual(reaksi["y"] + reaksi["h"], 100, delta=0.5)
        # Bingkai orangnya tidak menyentuh permainan: kotak Reaksi dimulai
        # tepat di tempat kotak Permainan berakhir, seperti contoh pemiliknya.
        main = l["frames"][0]["src"]
        self.assertLessEqual(main["x"] + main["w"], reaksi["x"] + 0.01)
        for r in l["reaksi"]:
            self.assertLessEqual(r["main"]["x"] + r["main"]["w"], r["src"]["x"] + 0.01)

    def test_pisahkan_memangkas_reaksi_bila_permainan_sudah_di_tepi(self):
        from app.services.render import _pisahkan_reaksi
        main = {"x": 0, "y": 0, "w": 80, "h": 100}
        src = {"x": 70, "y": 60, "w": 30, "h": 40}
        m, r = _pisahkan_reaksi(main, src, 1.406, 16 / 9)
        self.assertEqual(m["x"], 0)
        self.assertEqual(r["x"], 80)
        self.assertEqual(r["w"], 20)
        self.assertAlmostEqual(r["h"], 20 * (16 / 9) / 1.406, places=1)
        self.assertEqual(r["y"], 60)                      # kepala tetap acuan
