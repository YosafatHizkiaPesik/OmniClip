"""
Penyedia AI, font aksara, pemilihan model, dan keamanan jalur berkas.

Yang terakhir itu yang paling penting di berkas ini: nama berkas datang dari
peramban, dan "../../omniclip.db" adalah nama berkas yang sah. Pemeriksaannya
tidak boleh hilang tanpa ada yang menyadarinya.
"""

import unittest
from pathlib import Path

from app.services import fonts, openrouter, pemeliharaan, sosial
from app.services.whisper import AKSARA_SULIT, model_untuk


class SkemaOpenRouter(unittest.TestCase):
    SKEMA = {
        "type": "OBJECT",
        "required": ["a"],
        "property_ordering": ["a", "b"],
        "properties": {
            "a": {"type": "STRING", "enum": ["x", "y"]},
            "b": {"type": "ARRAY", "items": {"type": "NUMBER"}},
        },
    }

    def test_jenis_jadi_huruf_kecil_dan_urutan_dibuang(self):
        js = openrouter._json_schema(self.SKEMA)
        self.assertEqual(js["type"], "object")
        self.assertEqual(js["properties"]["a"]["type"], "string")
        self.assertEqual(js["properties"]["b"]["items"]["type"], "number")
        # `property_ordering` milik Gemini; JSON Schema biasa menolaknya.
        self.assertNotIn("property_ordering", js)

    def test_objek_ketat_menolak_kolom_karangan(self):
        js = openrouter._json_schema(self.SKEMA)
        self.assertFalse(js["additionalProperties"])

    def test_enum_dipertahankan(self):
        js = openrouter._json_schema(self.SKEMA)
        self.assertEqual(js["properties"]["a"]["enum"], ["x", "y"])

    def test_bentuk_teks_memuat_semua_kolom(self):
        bentuk = openrouter._bentuk(self.SKEMA)
        self.assertIn('"a"', bentuk)
        self.assertIn('"b"', bentuk)
        self.assertIn('"x" | "y"', bentuk)


class JawabanModel(unittest.TestCase):
    def test_json_polos(self):
        self.assertEqual(openrouter._uraikan('{"a": 1}'), {"a": 1})

    def test_json_di_dalam_pagar_kode(self):
        self.assertEqual(openrouter._uraikan('Ini hasilnya:\n```json\n{"a": 2}\n```'), {"a": 2})

    def test_json_sesudah_penalaran(self):
        self.assertEqual(openrouter._uraikan('<think>hmm</think> {"a": 3}'), {"a": 3})

    def test_jawaban_tanpa_json_ditolak_jelas(self):
        with self.assertRaises(ValueError):
            openrouter._uraikan("maaf saya tidak bisa")

    def test_jawaban_kosong_ditolak(self):
        with self.assertRaises(ValueError):
            openrouter._uraikan("")


class PeringkatModelOpenRouter(unittest.TestCase):
    def model(self, **kv):
        dasar = {"id": "m", "nama": "M", "video": False, "suara": False,
                 "gambar": True, "json": False, "gratis": True, "konteks": 1000}
        return {**dasar, **kv}

    def test_yang_bisa_menonton_didahulukan(self):
        gambar = self.model(id="gambar")
        video = self.model(id="video", video=True)
        urut = openrouter.urutkan([gambar, video])
        self.assertEqual(urut[0]["id"], "video")

    def test_yang_mendengar_didahulukan_di_antara_yang_setara(self):
        # Tawa lebih jelas terdengar daripada terlihat.
        diam = self.model(id="diam", video=True)
        dengar = self.model(id="dengar", video=True, suara=True)
        self.assertEqual(openrouter.urutkan([diam, dengar])[0]["id"], "dengar")

    def test_model_berbayar_tidak_pernah_masuk_daftar(self):
        bayar = self.model(id="bayar", video=True, gratis=False)
        self.assertEqual(openrouter.urutkan([bayar]), [])


class FontAksara(unittest.TestCase):
    def test_teks_latin_tidak_butuh_font_tambahan(self):
        self.assertIsNone(fonts.aksara("Halo dunia 123"))

    def test_kana_dikenali_sebagai_jepang(self):
        self.assertEqual(fonts.aksara("天井にいたら"), "jp")

    def test_han_tanpa_kana_dikenali_sebagai_mandarin(self):
        self.assertEqual(fonts.aksara("天井"), "sc")

    def test_hangul_dan_arab(self):
        self.assertEqual(fonts.aksara("안녕하세요"), "kr")
        self.assertEqual(fonts.aksara("مرحبا"), "ar")

    def test_tiap_aksara_punya_berkas_dan_sidik(self):
        for kode, (berkas, keluarga, alamat, sha) in fonts.NOTO.items():
            self.assertTrue(berkas and keluarga and alamat)
            self.assertEqual(len(sha), 64, f"sidik {kode} harus SHA-256 penuh")


class ModelWhisper(unittest.TestCase):
    def test_bahasa_sulit_menaikkan_model_kecil(self):
        model, alasan = model_untuk("ja", "base")
        self.assertEqual(model, "small")
        self.assertTrue(alasan)

    def test_pilihan_yang_lebih_besar_tidak_pernah_diturunkan(self):
        self.assertEqual(model_untuk("ja", "medium"), ("medium", ""))

    def test_bahasa_latin_tidak_diubah(self):
        self.assertEqual(model_untuk("id", "base"), ("base", ""))
        self.assertEqual(model_untuk("", "base"), ("base", ""))

    def test_kode_wilayah_diabaikan(self):
        self.assertEqual(model_untuk("zh-CN", "base")[0], "small")

    def test_daftar_aksara_sulit_memuat_yang_penting(self):
        for kode in ("ja", "ko", "zh", "ar", "th", "ru"):
            self.assertIn(kode, AKSARA_SULIT)


class KeamananJalur(unittest.TestCase):
    def test_folder_yang_dilindungi_tidak_bisa_dibersihkan(self):
        from app.errors import AppError
        for nama in ("klip", "model", "alat", "entah"):
            with self.assertRaises(AppError):
                pemeliharaan.buang(nama, ["apa.mp4"])

    def test_nama_berkas_tidak_bisa_keluar_dari_foldernya(self):
        # Yang dijaga: nama dari peramban yang menunjuk ke basis data.
        hasil = pemeliharaan.buang("proksi", ["../../omniclip.db", "/etc/passwd"])
        self.assertEqual(hasil["dibuang"], 0)


class Sosial(unittest.TestCase):
    def test_alamat_balik_meta_dipakai_bersama(self):
        # Facebook dan Instagram satu aplikasi, jadi satu alamat balik.
        self.assertEqual(sosial.redirect_uri("facebook"), sosial.redirect_uri("instagram"))
        self.assertNotEqual(sosial.redirect_uri("tiktok"), sosial.redirect_uri("facebook"))

    def test_pesan_galat_meta_terbaca_orang(self):
        pesan = sosial._pesan_galat('{"error": {"message": "Invalid OAuth token"}}')
        self.assertIn("Invalid OAuth token", pesan)

    def test_pesan_galat_yang_bukan_json_tetap_ditampilkan(self):
        self.assertIn("Bad Gateway", sosial._pesan_galat("Bad Gateway"))

    def test_tiap_platform_menyebut_kunci_yang_dibutuhkannya(self):
        for nama, p in sosial.PLATFORM.items():
            self.assertTrue(p["kunci"], nama)
            self.assertTrue(p["catatan"], nama)


if __name__ == "__main__":
    unittest.main()
