"""
Caption klip disusun TANPA AI saat panel terbit dibuka.

Judul dan tagar klipnya sudah ada di sidecar — dibuat saat auto-klip — jadi
memanggil model lagi hanya untuk merangkainya berarti menunggu lama dan
membakar kuota untuk hal yang sudah ada di cakram. Dilaporkan pemiliknya
5 Oktober 2026: "saat saya klik masih loading lama sedangkan judul, hastag
bukannya sudah langsung tersedia jadi kita tidak perlu lagi untuk ai generate
ulang karena menghabiskan banyak token nantinya".
"""

import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
PANEL = AKAR / "frontend" / "src" / "components" / "SiapkanTerbit.jsx"


class CaptionTanpaAiSaatDibuka(unittest.TestCase):
    def setUp(self):
        self.jsx = PANEL.read_text(encoding="utf-8")

    def test_dibuka_tanpa_ai(self):
        """`muat()` tanpa argumen — yaitu saat panelnya dibuka — tidak memakai AI."""
        self.assertIn("const muat = async (pakaiAi = false) => {", self.jsx)
        self.assertIn("pakai_ai: pakaiAi", self.jsx)

    def test_ai_hanya_atas_permintaan(self):
        self.assertIn("muat(true)", self.jsx)
        self.assertIn("Tulis ulang dengan AI", self.jsx)

    def test_tidak_ada_lagi_pakai_ai_yang_selalu_benar(self):
        self.assertNotIn("pakai_ai: true", self.jsx)

    def test_sumbernya_dikatakan(self):
        """Pengguna tidak boleh menebak caption ini datang dari mana."""
        self.assertIn("data?.sumber", self.jsx)


class JalurLokalMemakaiYangSudahAda(unittest.TestCase):
    def test_tagar_sidecar_dipakai_apa_adanya(self):
        from app.services.keterangan import paket
        meta = {
            "title": "Momen paling sial di Minecraft",
            "hashtags": ["#minecraft", "#gaming", "#lucu", "#fyp"],
            "subtitles": [{"text": "Eh tunggu dulu, ini kenapa bisa begini?"},
                          {"text": "Gue beneran nggak nyangka sama sekali."}],
            "duration": 30.0,
        }
        hasil = paket(meta, api_key="", models=[], pakai_ai=False)
        self.assertEqual(hasil["sumber"], "lokal")
        self.assertTrue(hasil["platform"])
        semua = " ".join(p["caption"] for p in hasil["platform"])
        self.assertIn("#minecraft", semua)

    def test_tanpa_kunci_tetap_memberi_caption(self):
        """Tidak ada kunci AI bukan alasan panelnya kosong."""
        from app.services.keterangan import paket
        hasil = paket({"title": "Uji", "subtitles": [{"text": "Halo semuanya."}],
                       "duration": 10.0}, api_key="", models=[], pakai_ai=True)
        self.assertEqual(hasil["sumber"], "lokal")
        self.assertTrue(all(p.get("caption") for p in hasil["platform"]))


if __name__ == "__main__":
    unittest.main()
