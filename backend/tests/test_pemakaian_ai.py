"""
Catatan pemakaian AI.

Ada karena satu pertanyaan yang sebelumnya tidak bisa dijawab: "jatah saya masih
sisa berapa?" Jawaban sebelumnya selalu sama, yaitu menunggu sampai gagal lalu
menebak sebabnya.

Yang dijaga di sini terutama dua hal yang kalau salah justru merugikan: catatan
pemakaian tidak boleh menjatuhkan pekerjaan yang sedang berjalan, dan tidak
boleh menyimpan satu pun hal yang rahasia.
"""

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from app.services import pemakaian_ai as pa


class Mencatat(unittest.TestCase):
    def setUp(self):
        import sqlite3
        self.dir = TemporaryDirectory()
        self.c = sqlite3.connect(str(Path(self.dir.name) / "uji.db"))
        self.c.row_factory = sqlite3.Row
        self.asli = pa._conn
        pa._conn = lambda: self.c
        pa.siapkan()

    def tearDown(self):
        pa._conn = self.asli
        self.c.close()
        self.dir.cleanup()

    def test_satu_panggilan_tercatat(self):
        pa.catat(model="gemini-3.6-flash", pekerjaan="pilih-klip", video_id="abc",
                 pakai={"masuk": 12000, "keluar": 800, "berpikir": 300})
        r = self.c.execute("SELECT * FROM pemakaian_ai").fetchone()
        self.assertEqual(r["model"], "gemini-3.6-flash")
        self.assertEqual(r["pekerjaan"], "pilih-klip")
        self.assertEqual((r["masuk"], r["keluar"], r["berpikir"]), (12000, 800, 300))
        self.assertEqual(r["berhasil"], 1)

    def test_kegagalan_ikut_tercatat(self):
        # Panggilan yang gagal TETAP memotong jatah harian Google.
        pa.catat(model="m", pekerjaan="pilih-klip", berhasil=False, sebab="429")
        r = self.c.execute("SELECT berhasil, sebab FROM pemakaian_ai").fetchone()
        self.assertEqual(r["berhasil"], 0)
        self.assertIn("429", r["sebab"])

    def test_tanpa_angka_token_tetap_tercatat(self):
        # Beberapa penyedia tidak mengembalikan hitungan token sama sekali.
        pa.catat(model="m", pekerjaan="caption", pakai=None)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM pemakaian_ai").fetchone()[0], 1)

    def test_mencatat_tidak_pernah_melempar(self):
        # Basis data mati di tengah render bukan alasan rendernya gagal.
        pa._conn = lambda: (_ for _ in ()).throw(RuntimeError("basis data mati"))
        pa.catat(model="m", pekerjaan="x")      # tidak boleh melempar

    def test_tidak_menyimpan_apa_pun_yang_rahasia(self):
        from pathlib import Path as P
        kode = (P(pa.__file__)).read_text(encoding="utf-8")
        for rahasia in ("api_key", "client_secret", "token=", "_sidik"):
            self.assertNotIn(rahasia, kode, f"{rahasia} tidak boleh ikut dicatat")


class Ringkasan(unittest.TestCase):
    def setUp(self):
        import sqlite3
        self.dir = TemporaryDirectory()
        self.c = sqlite3.connect(str(Path(self.dir.name) / "uji.db"))
        self.c.row_factory = sqlite3.Row
        self.asli = pa._conn
        pa._conn = lambda: self.c
        pa.siapkan()

    def tearDown(self):
        pa._conn = self.asli
        self.c.close()
        self.dir.cleanup()

    def test_sisa_jatah_dihitung_per_model(self):
        for _ in range(3):
            pa.catat(model="gemini-3.6-flash", pekerjaan="pilih-klip")
        r = pa.ringkas()
        sisa = {s["model"]: s for s in r["hari_ini"]["sisa"]}
        self.assertEqual(sisa["gemini-3.6-flash"]["terpakai"], 3)
        self.assertEqual(sisa["gemini-3.6-flash"]["sisa"], pa.JATAH_HARIAN_PER_MODEL - 3)

    def test_openrouter_tidak_diberi_sisa_jatah(self):
        # Aturannya berbeda; menebaknya di sini akan menyesatkan.
        pa.catat(model="free/model", pekerjaan="tema-subtitle", penyedia="openrouter")
        self.assertEqual(pa.ringkas()["hari_ini"]["sisa"], [])

    def test_dikelompokkan_per_pekerjaan(self):
        pa.catat(model="m", pekerjaan="pilih-klip")
        pa.catat(model="m", pekerjaan="caption")
        pa.catat(model="m", pekerjaan="caption")
        per = {p["pekerjaan"]: p["panggilan"] for p in pa.ringkas()["per_pekerjaan"]}
        self.assertEqual(per["caption"], 2)
        self.assertEqual(per["pilih-klip"], 1)

    def test_rata_per_video(self):
        for v in ("a", "a", "b"):
            pa.catat(model="m", pekerjaan="pilih-klip", video_id=v)
        r = pa.ringkas()["rata_per_video"]
        self.assertEqual(r["video"], 2)
        self.assertEqual(r["panggilan"], 1.5)

    def test_ringkasan_tidak_pernah_melempar(self):
        pa._conn = lambda: (_ for _ in ()).throw(RuntimeError("mati"))
        r = pa.ringkas()
        self.assertEqual(r["hari_ini"]["panggilan"], 0)


class Penandaan(unittest.TestCase):
    """Nama pekerjaan diteruskan lewat variabel konteks, bukan argumen."""

    def test_blok_pekerjaan_mengubah_penandanya(self):
        from app.services.penyedia_ai import _pekerjaan, pekerjaan

        self.assertEqual(_pekerjaan.get(), ("ai", None))
        with pekerjaan("pilih-klip", "abc"):
            self.assertEqual(_pekerjaan.get(), ("pilih-klip", "abc"))
        self.assertEqual(_pekerjaan.get(), ("ai", None))

    def test_dikembalikan_walau_meledak(self):
        from app.services.penyedia_ai import _pekerjaan, pekerjaan

        with self.assertRaises(RuntimeError):
            with pekerjaan("caption"):
                raise RuntimeError("gagal")
        self.assertEqual(_pekerjaan.get(), ("ai", None))


if __name__ == "__main__":
    unittest.main()


class BatasDariGoogle(unittest.TestCase):
    """
    Google TIDAK PERNAH mengirim sisa kuota: diperiksa 24 September 2026, tidak
    ada satu pun header kuota di jawaban suksesnya. Yang ia sebutkan hanya
    BATASNYA, dan itu pun hanya di dalam galat 429 saat jatahnya sudah habis.
    """

    GALAT = ("429 RESOURCE_EXHAUSTED {'error': {'details': [{'@type': "
             "'type.googleapis.com/google.rpc.QuotaFailure', 'violations': "
             "[{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', "
             "'quotaValue': '50'}]}]}}")

    def test_batas_dibaca_dari_galat(self):
        from app.services.peringkat_model import jatah_dari_galat
        self.assertEqual(jatah_dari_galat(self.GALAT), 50)

    def test_galat_tanpa_angka_tidak_mengarang(self):
        from app.services.peringkat_model import jatah_dari_galat
        for g in ("503 UNAVAILABLE", "401 UNAUTHENTICATED", ""):
            self.assertIsNone(jatah_dari_galat(g))

    def test_batas_bawaan_dipakai_sebelum_google_menyebutkan(self):
        self.assertEqual(pa.batas_model("model-yang-belum-pernah-habis"),
                         pa.JATAH_HARIAN_PER_MODEL)
