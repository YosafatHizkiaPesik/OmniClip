"""
JOB-4 M0.6: token jalur bahan Montase, CORS bertoken, dan jalur terbuka.

Jalur `/api/montase/t/...` dibaca tanpa sesi (iframe kotak pasir, Chrome
headless), jadi satu-satunya penjaganya adalah token di alamatnya. Tes di sini
memastikan tanpa token yang sah jawabannya 404, dan bahwa izin CORS `*` hanya
berlaku di bawah awalan itu.
"""

import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from app.errors import NotFound
from app.montase import cors, router, token, uji
from app.services import auth


class Token(unittest.TestCase):
    def test_bolak_balik(self):
        t = token.buat("uji")
        self.assertTrue(token.sah(t, "uji"))
        self.assertEqual(token.lingkup(t), "uji")

    def test_lingkup_lain_ditolak(self):
        self.assertFalse(token.sah(token.buat("proyek:mt_a"), "proyek:mt_b"))

    def test_kedaluwarsa_ditolak(self):
        self.assertIsNone(token.lingkup(token.buat("uji", berlaku_detik=-1)))

    def test_diubah_ditolak(self):
        isi, tanda = token.buat("uji").split(".")
        palsu = token._b64(f"proyek:x|{int(time.time()) + 999}".encode())
        self.assertIsNone(token.lingkup(f"{palsu}.{tanda}"))
        self.assertIsNone(token.lingkup(f"{isi}.{tanda[:-2]}AA"))
        for rusak in ("", "tanpa-titik", "a.b.c", "!!!.???"):
            self.assertIsNone(token.lingkup(rusak))

    def test_lingkup_dengan_pemisah_ditolak(self):
        with self.assertRaises(ValueError):
            token.buat("uji|9999999999")


class BerkasBertoken(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)
        (self.folder / uji.NAMA_VIDEO).write_bytes(b"\x00" * 64)
        (self.folder / "rahasia.db").write_bytes(b"jangan")
        self._p = mock.patch.object(uji, "folder", return_value=self.folder)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()

    def _ambil(self, tkn, nama):
        return asyncio.run(router.berkas_uji(tkn, nama))

    def test_token_sah_menyajikan_berkas(self):
        respons = self._ambil(token.buat(uji.LINGKUP), uji.NAMA_VIDEO)
        self.assertEqual(Path(respons.path), self.folder / uji.NAMA_VIDEO)
        self.assertEqual(respons.media_type, "video/mp4")

    def test_tanpa_token_sah_404(self):
        for tkn in ("palsu.abc", token.buat("proyek:lain"), token.buat(uji.LINGKUP, -1)):
            with self.assertRaises(NotFound):
                self._ambil(tkn, uji.NAMA_VIDEO)

    def test_hanya_nama_dalam_daftar(self):
        tkn = token.buat(uji.LINGKUP)
        for nama in ("rahasia.db", "../rahasia.db", "..%2Frahasia.db", ""):
            with self.assertRaises(NotFound):
                self._ambil(tkn, nama)


def _panggil(app, scope):
    """Menjalankan aplikasi ASGI satu kali, mengembalikan (status, kepala, dipanggil)."""
    terkirim = []
    dipanggil = []

    async def penerima():
        return {"type": "http.request", "body": b""}

    async def pengirim(pesan):
        terkirim.append(pesan)

    async def jalan():
        await app(scope, penerima, pengirim)

    asyncio.run(jalan())
    awal = next(p for p in terkirim if p["type"] == "http.response.start")
    return awal["status"], {k.decode(): v.decode() for k, v in awal["headers"]}, dipanggil


async def _aplikasi_dalam(scope, receive, send):
    await send({"type": "http.response.start", "status": 206,
                "headers": [(b"content-range", b"bytes 0-9/100")]})
    await send({"type": "http.response.body", "body": b"x" * 10})


class Cors(unittest.TestCase):
    def setUp(self):
        self.app = cors.CorsBertoken(_aplikasi_dalam)

    def test_preflight_dijawab_sebelum_aplikasi(self):
        status, kepala, _ = _panggil(self.app, {
            "type": "http", "method": "OPTIONS", "path": "/api/montase/t/abc/uji/x.mp4",
            "headers": [(b"origin", b"null")]})
        self.assertEqual(status, 204)
        self.assertEqual(kepala["access-control-allow-origin"], "*")
        self.assertIn("Range", kepala["access-control-allow-headers"])

    def test_jawaban_bertoken_diberi_izin(self):
        status, kepala, _ = _panggil(self.app, {
            "type": "http", "method": "GET", "path": "/api/montase/t/abc/uji/x.mp4", "headers": []})
        self.assertEqual(status, 206)
        self.assertEqual(kepala["access-control-allow-origin"], "*")
        self.assertIn("Content-Range", kepala["access-control-expose-headers"])

    def test_jalur_lain_tidak_disentuh(self):
        for jalur in ("/api/settings", "/api/montase/mesin", "/api/montase/uji"):
            _, kepala, _ = _panggil(self.app, {"type": "http", "method": "GET",
                                               "path": jalur, "headers": []})
            self.assertNotIn("access-control-allow-origin", kepala, jalur)


class JalurTerbuka(unittest.TestCase):
    MAIN = Path(__file__).resolve().parents[1] / "app" / "main.py"

    def test_awalan_hanya_jalur_bertoken(self):
        self.assertEqual(auth.OPEN_PREFIXES, ("/api/montase/t/",))
        self.assertEqual(cors.AWALAN, auth.OPEN_PREFIXES[0])

    def test_gerbang_memakai_awalan(self):
        teks = self.MAIN.read_text(encoding="utf-8")
        self.assertIn("not path.startswith(auth.OPEN_PREFIXES)", teks)

    def test_cors_bertoken_lapisan_terluar(self):
        """Dipasang sesudah gerbang dan CORSMiddleware, jadi paling luar."""
        teks = self.MAIN.read_text(encoding="utf-8")
        self.assertGreater(teks.index("app.add_middleware(CorsBertoken)"),
                           teks.index("async def gerbang("))
        self.assertGreater(teks.index("app.add_middleware(CorsBertoken)"),
                           teks.index("CORSMiddleware,"))

    def test_aset_build_boleh_dibaca_kotak_pasir(self):
        teks = self.MAIN.read_text(encoding="utf-8")
        self.assertIn('kepala["Access-Control-Allow-Origin"] = "*"', teks)


if __name__ == "__main__":
    unittest.main()
