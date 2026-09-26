"""
Gaya kartu judul: yang di pratinjau dan yang di MP4 harus gaya yang sama.

Daftarnya ditulis dua kali — `VARIANTS` di `titlecard.py` dan `CARD_VARIANTS`
di `cardStyles.js` — karena yang satu menggambar dengan ASS dan yang lain
dengan CSS. Dua salinan berarti keduanya bisa bergeser sendiri-sendiri, dan
kegagalannya adalah jenis yang paling mahal di editor: pengguna memilih gaya,
melihatnya di layar, merender sepuluh menit, lalu mendapat gaya yang lain.

Uji ini membaca berkas JSX dan CSS-nya sebagai teks, bukan menjalankannya;
proyek ini tidak punya penjalan uji JavaScript.
"""

import re
import unittest
from pathlib import Path

from app.services.titlecard import (
    DEFAULT_VARIANT, VARIANTS, TitleCardSpec, card_ass,
)

AKAR = Path(__file__).resolve().parents[2]
GAYA_JS = AKAR / "frontend" / "src" / "features" / "studio" / "cardStyles.js"
CSS = AKAR / "frontend" / "src" / "index.css"
PRATINJAU = AKAR / "frontend" / "src" / "features" / "studio" / "ClipPreview.jsx"


def _entri_js() -> dict[str, dict]:
    """Membaca id, angka ASS, dan nama geraknya dari cardStyles.js."""
    teks = GAYA_JS.read_text(encoding="utf-8")
    keluar: dict[str, dict] = {}
    for blok in re.split(r"\n  \{\n", teks)[1:]:
        m = re.search(r"id: '([^']+)'", blok)
        if not m:
            continue
        angka = re.search(
            r"ass: \{ border: (\d+), outline: (\d+), shadow: (\d+), back: (\w+|'\w+')",
            blok)
        gerak = re.search(r"anim: (?:'([\w-]+)[^']*'|null)", blok)
        keluar[m.group(1)] = {
            "border": int(angka.group(1)),
            "outline": int(angka.group(2)),
            "shadow": int(angka.group(3)),
            "kotak": angka.group(4) != "null",
            "anim": gerak.group(1) if gerak else None,
        }
    return keluar


class DaftarGaya(unittest.TestCase):
    def setUp(self):
        self.js = _entri_js()

    def test_daftarnya_sama(self):
        self.assertEqual(sorted(self.js), sorted(VARIANTS),
                         "gaya yang hanya ada di satu sisi tidak bisa dipilih "
                         "pengguna, atau dipilih tapi tidak dirender")

    def test_angkanya_sama(self):
        for nama, py in VARIANTS.items():
            with self.subTest(nama):
                js = self.js[nama]
                for medan in ("border", "outline", "shadow", "kotak"):
                    self.assertEqual(js[medan], py[medan],
                                     f"{nama}.{medan} berbeda antara JS dan Python")

    def test_bawaannya_ada(self):
        self.assertIn(DEFAULT_VARIANT, VARIANTS)
        self.assertIn(DEFAULT_VARIANT, self.js)


class GerakKartu(unittest.TestCase):
    """Gerak ASS-nya sah, dan tiap gerak CSS punya keyframe yang benar-benar ada."""

    def _dialogue(self, nama: str, w: int = 1080, h: int = 1920) -> str:
        ass = card_ass(TitleCardSpec(text="JUDUL UJI", variant=nama), 3.0, w, h)
        baris = [b for b in ass.splitlines() if b.startswith("Dialogue:")]
        self.assertEqual(len(baris), 1, f"{nama}: kartunya bukan satu baris")
        return baris[0]

    def test_tiap_gaya_menghasilkan_baris_sah(self):
        for nama in VARIANTS:
            with self.subTest(nama):
                b = self._dialogue(nama)
                self.assertNotIn("%(", b, "penanda gerak tidak terisi")
                self.assertEqual(b.count("{"), b.count("}"))
                self.assertIn("\\an5", b)

    def test_pos_dan_move_tidak_bersamaan(self):
        """Satu baris yang menyebut dua letak sekaligus: libass yang memilih."""
        for nama in VARIANTS:
            with self.subTest(nama):
                b = self._dialogue(nama)
                self.assertNotEqual("\\pos(" in b, "\\move(" in b,
                                    f"{nama}: harus persis satu dari \\pos atau \\move")

    def test_gerak_ikut_kanvas_16_9(self):
        """Kanvas mendatar juga harus dapat letak di dalam kanvasnya."""
        for nama in VARIANTS:
            with self.subTest(nama):
                b = self._dialogue(nama, 1920, 1080)
                for x, y in re.findall(r"(?:pos|move)\((\d+),(\d+)", b):
                    self.assertLessEqual(int(x), 1920)
                    self.assertLessEqual(int(y), 1080 + 60)

    def test_keyframe_pratinjau_ada(self):
        css = CSS.read_text(encoding="utf-8")
        ada = set(re.findall(r"@keyframes ([\w-]+)", css))
        for nama, js in _entri_js().items():
            if js["anim"]:
                with self.subTest(nama):
                    self.assertIn(js["anim"], ada,
                                  "gaya bergerak di render tapi diam di pratinjau")

    def test_pratinjau_memasang_geraknya(self):
        jsx = PRATINJAU.read_text(encoding="utf-8")
        self.assertIn("cardStyleSpec.anim", jsx)
        # Tanpa `key`, mengganti gaya memakai elemen yang sama dan animasinya
        # tidak pernah dimulai lagi: gaya baru terlihat diam.
        self.assertIn("key={card?.variant", jsx)


if __name__ == "__main__":
    unittest.main()
