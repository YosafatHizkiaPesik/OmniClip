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
        # Yang ditulis ke simpanan tidak boleh memuat susunannya.
        self.assertIn('{"posisi": posisi or [], "src_w": w, "src_h": h}', badan)
        # Dan susunannya dihitung ulang, juga saat simpanannya kena.
        self.assertIn('if tersimpan is not None and "posisi" in tersimpan:', badan)
        self.assertIn("return susun(tersimpan)", badan)

    def test_pemanasan_menyimpan_bentuk_yang_sama(self):
        """
        Pemanasan menulis ke simpanan yang SAMA dengan yang dibaca endpoint.

        Bentuk yang berbeda berarti pemanasan mengisi simpanan dengan sesuatu
        yang endpoint-nya tidak kenali, lalu memindai ulang semuanya: kerja
        dua kali, dan justru pada jalur yang ada untuk menghemat kerja.
        """
        awal = (AKAR / "backend" / "app" / "services" / "bingkai_awal.py").read_text(
            encoding="utf-8")
        self.assertIn('{"posisi": posisi or [], "src_w": w, "src_h": h}', awal)
        self.assertIn('if tersimpan is not None and "posisi" in tersimpan:', awal)


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
