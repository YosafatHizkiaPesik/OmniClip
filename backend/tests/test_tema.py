"""
Memilih tema subtitle dari isi klip.

Yang dijaga: daftar tema di backend dan di antarmuka tidak boleh berbeda, id
karangan model tidak boleh lolos, dan warna per penutur tidak boleh menyala di
klip satu orang.
"""

import re
import unittest
from pathlib import Path

from app.services import tema

AKAR = Path(__file__).resolve().parents[2]
PANEL = AKAR / "frontend" / "src" / "features" / "studio" / "EditorPanels.jsx"


def id_antarmuka() -> list[str]:
    teks = PANEL.read_text(encoding="utf-8")
    blok = teks[teks.index("const STYLE_PRESETS = ["):]
    return re.findall(r"id: '([a-z_0-9]+)', label: '", blok)


class DaftarSama(unittest.TestCase):
    """
    Model memilih dari daftar backend, antarmuka yang menerapkan wujudnya.
    Begitu keduanya berbeda, model akan menyebut tema yang tidak bisa dipasang.
    """

    def test_id_backend_dan_antarmuka_sama_persis(self):
        self.assertEqual(sorted(tema.TEMA), sorted(id_antarmuka()))

    def test_bawaannya_ada(self):
        self.assertIn(tema.BAWAAN, tema.TEMA)

    def test_tiap_tema_punya_keterangan_yang_berguna(self):
        # Keterangan ini yang dibaca model; ia tidak pernah melihat hasilnya.
        for k, v in tema.TEMA.items():
            self.assertGreater(len(v), 25, k)
            self.assertIn("cocok", v, k)


class TebakanLokal(unittest.TestCase):
    def klip(self, **kv):
        dasar = {"duration": 60.0, "jenis": "wajah",
                 "subtitles": [{"text": "halo", "speaker": 0}]}
        return {**dasar, **kv}

    def test_game_dapat_getar(self):
        self.assertEqual(tema.pilih_lokal(self.klip(jenis="game"))["tema"], "getar")

    def test_tanpa_wajah_dapat_yang_paling_terbaca(self):
        self.assertEqual(tema.pilih_lokal(self.klip(jenis="tanpa_wajah"))["tema"], "papan")

    def test_klip_sangat_pendek_dapat_satu_kata(self):
        self.assertEqual(tema.pilih_lokal(self.klip(duration=14))["tema"], "satu_kata")

    def test_sisanya_dapat_tema_bawaan(self):
        self.assertEqual(tema.pilih_lokal(self.klip())["tema"], tema.BAWAAN)

    def test_semua_tebakan_ada_di_daftar(self):
        for j in ("game", "wajah", "tanpa_wajah", ""):
            for d in (10.0, 60.0, 300.0):
                t = tema.pilih_lokal(self.klip(jenis=j, duration=d))["tema"]
                self.assertIn(t, tema.TEMA, f"{j}/{d}")


class WarnaPerPenutur(unittest.TestCase):
    def test_dua_orang_menyalakannya(self):
        klip = {"subtitles": [{"text": "a", "speaker": 0}, {"text": "b", "speaker": 1}]}
        self.assertTrue(tema.pilih_lokal(klip)["warna_per_penutur"])

    def test_satu_orang_tidak(self):
        klip = {"subtitles": [{"text": "a", "speaker": 0}, {"text": "b", "speaker": 0}]}
        self.assertFalse(tema.pilih_lokal(klip)["warna_per_penutur"])

    def test_jawaban_model_ditolak_pada_klip_satu_orang(self):
        # Warna berbeda per penutur di klip satu orang hanya membuat warnanya
        # berkedip tanpa arti.
        klip = {"subtitles": [{"text": "a", "speaker": 0}]}
        hasil = tema._bersihkan({"tema": "tebal", "alasan": "x",
                                 "warna_per_penutur": True}, klip)
        self.assertFalse(hasil["warna_per_penutur"])


class JawabanModel(unittest.TestCase):
    def test_tema_karangan_jatuh_ke_tebakan_lokal(self):
        klip = {"jenis": "game", "duration": 40.0, "subtitles": [{"text": "a", "speaker": 0}]}
        hasil = tema._bersihkan({"tema": "kotak_pelangi_ajaib", "alasan": "x"}, klip)
        self.assertEqual(hasil["tema"], "getar")
        self.assertIn("tidak ada", hasil["alasan"])

    def test_tanda_pisah_dibuang_dari_alasan(self):
        klip = {"subtitles": [{"text": "a", "speaker": 0}]}
        hasil = tema._bersihkan(
            {"tema": "tebal", "alasan": "klip serius — tema tenang"}, klip)
        self.assertNotIn("—", hasil["alasan"])

    def test_tema_huruf_besar_tetap_dikenali(self):
        klip = {"subtitles": [{"text": "a", "speaker": 0}]}
        self.assertEqual(tema._bersihkan({"tema": "  TEBAL ", "alasan": ""}, klip)["tema"],
                         "tebal")

    def test_tanpa_kunci_memakai_tebakan_lokal(self):
        hasil = tema.pilih({"jenis": "game", "duration": 40.0,
                            "subtitles": [{"text": "halo", "speaker": 0}]},
                           api_key="", models=[])
        self.assertEqual(hasil["sumber"], "lokal")


if __name__ == "__main__":
    unittest.main()


class SatuPanggilanUntukSemua(unittest.TestCase):
    """
    Jatah harian Gemini gratis 20 permintaan per model per project, dan satu
    video menghasilkan belasan klip. Memilihkan tema satu per satu akan
    menghabiskan hampir seluruh jatah hari itu hanya untuk menyiapkan tema,
    dan pemilihan klip video berikutnya kehabisan.
    """

    def klip(self, n):
        return [{"title": f"Klip {i}", "duration": 60.0, "jenis": "wajah",
                 "subtitles": [{"text": f"isi klip {i}", "speaker": 0}]}
                for i in range(n)]

    def jalankan(self, daftar, jawab=None, meledak=False):
        from app.services import penyedia_ai
        dipanggil = []

        def palsu(bahan, **kv):
            dipanggil.append(bahan)
            if meledak:
                raise RuntimeError("model tidak menjawab")
            return jawab, "model-uji", {}

        # `tanya` diimpor DI DALAM fungsi, jadi menambal modulnya sudah cukup.
        asli = penyedia_ai.tanya
        penyedia_ai.tanya = palsu
        try:
            return tema.pilih_banyak(daftar, api_key="K", models=["m"]), dipanggil
        finally:
            penyedia_ai.tanya = asli

    def test_lima_belas_klip_satu_panggilan(self):
        jawab = {"klip": [{"nomor": i + 1, "tema": "tebal", "alasan": "a",
                           "warna_per_penutur": False} for i in range(15)]}
        hasil, dipanggil = self.jalankan(self.klip(15), jawab)
        self.assertEqual(len(dipanggil), 1, "harus satu panggilan, bukan per klip")
        self.assertEqual(len(hasil), 15)
        self.assertTrue(all(h["tema"] == "tebal" for h in hasil))

    def test_klip_yang_tidak_dijawab_jatuh_ke_tebakan_lokal(self):
        # Model boleh melewatkan satu baris; sisanya tidak ikut hilang.
        jawab = {"klip": [{"nomor": 1, "tema": "tebal", "alasan": "a",
                           "warna_per_penutur": False}]}
        hasil, _ = self.jalankan(self.klip(3), jawab)
        self.assertEqual(len(hasil), 3)
        self.assertEqual(hasil[0]["tema"], "tebal")
        self.assertEqual(hasil[1]["sumber"], "lokal")

    def test_model_gagal_tidak_menjatuhkan_apa_pun(self):
        hasil, _ = self.jalankan(self.klip(4), meledak=True)
        self.assertEqual(len(hasil), 4)
        self.assertTrue(all(h["sumber"] == "lokal" for h in hasil))

    def test_tanpa_kunci_tidak_memanggil_model(self):
        hasil = tema.pilih_banyak(self.klip(5), api_key="", models=[])
        self.assertEqual(len(hasil), 5)
        self.assertTrue(all(h["sumber"] == "lokal" for h in hasil))

    def test_daftar_kosong_aman(self):
        self.assertEqual(tema.pilih_banyak([], api_key="K", models=["m"]), [])
