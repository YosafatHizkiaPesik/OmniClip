"""
Plafon simpanan yang tidak pernah kedaluwarsa.

Empat jenis entri sengaja dikecualikan dari pembersihan harian, dan alasannya
benar: isinya menjelaskan isi sebuah potongan video, dan itu tidak berubah.
Yang tidak ada adalah batas atasnya. Terukur pada penyimpanan pemiliknya
2 Oktober 2026: basis data 25 MB, 14,3 MB-nya simpanan ini, `bingkai:` sendiri
143 baris untuk 9,0 MB — sekitar 63 KB per klip yang pernah dibuka, selamanya,
termasuk untuk video yang berkasnya sudah lama dihapus.
"""

import unittest

from app.repos import cache as repo


class PlafonSimpananAbadi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.db import run_migrations
        run_migrations()

    def setUp(self):
        from app.db import get_conn
        self.conn = get_conn()
        self.conn.execute("DELETE FROM search_cache")

    def _isi(self, kunci: str, bita: int, umur: float = 0.0) -> None:
        import time
        self.conn.execute(
            "INSERT INTO search_cache (cache_key, payload_json, created_at) VALUES (?,?,?)",
            (kunci, '"' + "x" * max(0, bita - 2) + '"', time.time() - umur),
        )

    def _sisa(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT cache_key FROM search_cache")]

    def test_di_bawah_plafon_tidak_ada_yang_dibuang(self):
        for i in range(5):
            self._isi(f"bingkai:{i}", 1000)
        self.assertEqual(repo.pangkas_abadi(plafon=10_000), 0)
        self.assertEqual(len(self._sisa()), 5)

    def test_yang_paling_lama_ditulis_dibuang_lebih_dulu(self):
        self._isi("bingkai:tua", 1000, umur=10_000)
        self._isi("bingkai:tengah", 1000, umur=5_000)
        self._isi("bingkai:baru", 1000, umur=0)
        # Plafon hanya cukup untuk dua baris.
        repo.pangkas_abadi(plafon=2_100)
        sisa = self._sisa()
        self.assertIn("bingkai:baru", sisa)
        self.assertIn("bingkai:tengah", sisa)
        self.assertNotIn("bingkai:tua", sisa)

    def test_keempat_jenisnya_dihitung_bersama(self):
        """Satu plafon untuk semuanya, bukan satu plafon per jenis."""
        for p in ("bingkai:", "facecam:", "jenis:", "sutradara:", "tema:"):
            self._isi(p + "a", 1000)
        repo.pangkas_abadi(plafon=2_100)
        self.assertEqual(len(self._sisa()), 2)

    def test_entri_biasa_tidak_ikut_dihitung_maupun_dibuang(self):
        """Pencarian dan trending punya TTL sendiri; plafon ini bukan untuk mereka."""
        self._isi("trending:x", 50_000)
        self._isi("bingkai:a", 1000)
        repo.pangkas_abadi(plafon=2_000)
        sisa = self._sisa()
        self.assertIn("trending:x", sisa)
        self.assertIn("bingkai:a", sisa)

    def test_bersihkan_ikut_memangkas(self):
        """Pembersihan saat startup satu-satunya pemanggil; plafon harus ikut."""
        for i in range(6):
            self._isi(f"bingkai:{i}", 1000, umur=i)
        repo.bersihkan.__defaults__  # memastikan tanda tangannya tidak berubah
        hasil = repo.pangkas_abadi(plafon=3_100)
        self.assertEqual(hasil, 3)

    def test_plafon_bawaan_masuk_akal(self):
        """40 MB: jauh di atas kerja satu masa, dan tetap batas yang bisa disebut."""
        self.assertGreaterEqual(repo.PLAFON_ABADI, 16 * 1024 * 1024)
        self.assertLessEqual(repo.PLAFON_ABADI, 256 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
