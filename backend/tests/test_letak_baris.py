"""
Letak bebas per baris subtitle, dan pemecahan baris.

Diminta pemiliknya 5 Oktober 2026: "buat agar tiap baris subtitle itu kita
dapat pindahkan lokasinya di kanvas agar lebih menarik, jadi buat agar tiap
kalimat atau kata di subtitle bisa kita pecah-pecah".

Keduanya satu fitur: memecah tanpa bisa memindahkan hanya menghasilkan dua
baris di tempat yang sama, dan memindahkan tanpa bisa memecah berarti seluruh
kalimat ikut pindah.
"""

import re
import unittest
from pathlib import Path

from app.services.subtitles import CaptionStyle, build_ass

AKAR = Path(__file__).resolve().parents[2]


def _dialog(ass: str, memuat: str) -> list[str]:
    return [b for b in ass.splitlines()
            if b.startswith("Dialogue") and memuat.upper() in b.upper()]


class LetakBebasDiAss(unittest.TestCase):
    GAYA = CaptionStyle()

    def _ass(self, lines):
        return build_ass(lines=lines, style=self.GAYA, play_res=(1080, 1920))

    def test_baris_biasa_tidak_memakai_pos(self):
        ass = self._ass([{"start": 0.0, "end": 1.0, "text": "Baris biasa"}])
        for b in _dialog(ass, "biasa"):
            self.assertNotIn("\\pos(", b)

    def test_baris_berletak_memakai_pos_dan_an5(self):
        ass = self._ass([{"start": 0.0, "end": 1.0, "text": "Dipindah",
                          "x": 25.0, "y": 30.0}])
        baris = _dialog(ass, "dipindah")
        self.assertTrue(baris)
        for b in baris:
            self.assertIn("\\an5", b)
            # 25% dari 1080 = 270, 30% dari 1920 = 576.
            self.assertIn("\\pos(270,576)", b)

    def test_persen_dijepit_di_dalam_kanvas(self):
        ass = self._ass([{"start": 0.0, "end": 1.0, "text": "Jauh",
                          "x": -40.0, "y": 180.0}])
        for b in _dialog(ass, "jauh"):
            m = re.search(r"\\pos\((\d+),(\d+)\)", b)
            self.assertIsNotNone(m)
            x, y = int(m.group(1)), int(m.group(2))
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x, 1080)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(y, 1920)

    def test_angka_rusak_tidak_melempar(self):
        """Satu baris yang nilainya kacau tidak boleh menggagalkan seluruh render."""
        ass = self._ass([{"start": 0.0, "end": 1.0, "text": "Rusak",
                          "x": "entah", "y": None}])
        self.assertTrue(_dialog(ass, "rusak"))

    def test_satu_baris_berletak_tidak_memindahkan_yang_lain(self):
        ass = self._ass([
            {"start": 0.0, "end": 1.0, "text": "Tetap"},
            {"start": 1.0, "end": 2.0, "text": "Pindah", "x": 20.0, "y": 20.0},
        ])
        self.assertFalse(any("\\pos(" in b for b in _dialog(ass, "tetap")))
        self.assertTrue(all("\\pos(" in b for b in _dialog(ass, "pindah")))


class PratinjauDanPanelSejalan(unittest.TestCase):
    """Dibaca sebagai teks; uji JavaScript proyek ini belum mencakup komponen."""

    def test_pratinjau_memakai_letak_baris(self):
        jsx = (AKAR / "frontend" / "src" / "features" / "studio"
               / "ClipPreview.jsx").read_text(encoding="utf-8")
        self.assertIn("Number.isFinite(line?.x) && Number.isFinite(line?.y)", jsx)
        self.assertIn("'baris-move'", jsx)
        # Perilaku lama tidak berubah sampai sebuah baris dilepaskan.
        self.assertIn("barisPunyaLetak ? 'baris-move' : 'move'", jsx)

    def test_panel_bisa_memecah_dan_melepaskan(self):
        jsx = (AKAR / "frontend" / "src" / "features" / "studio"
               / "EditorPanels.jsx").read_text(encoding="utf-8")
        self.assertIn("onSplit(clip.clip_id, i, kata)", jsx)
        self.assertIn("{ x: null, y: null }", jsx)

    def test_pemecah_memakai_waktu_kata(self):
        js = (AKAR / "frontend" / "src" / "features" / "studio"
              / "useClipEditor.js").read_text(encoding="utf-8")
        self.assertIn("const splitSubtitle = useCallback", js)
        # Waktunya dari kata, bukan dibagi rata.
        self.assertIn("Number.isFinite(w[n]?.s)", js)


if __name__ == "__main__":
    unittest.main()
