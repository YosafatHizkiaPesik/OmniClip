"""
Jejak wajah yang dihitung sebelum ada yang membukanya.

Dilaporkan: "ada beberapa yang langsung mengikuti wajah dan ada beberapa yang
perlu menunggu lagi padahal pemrosesan sudah selesai". Terukur pada klip 20
detik di komputer pemiliknya: 29 detik untuk hitungan pertama, 0,015 detik
sesudah tersimpan.
"""

import unittest

from app.errors import JobCancelled
from app.services import bingkai_awal as ba


class Ctx:
    def __init__(self, payload, batal_pada=None):
        self.payload = payload
        self.pesan = []
        self._n = 0
        self._batal_pada = batal_pada

    def check_cancelled(self):
        self._n += 1
        if self._batal_pada is not None and self._n > self._batal_pada:
            raise JobCancelled("dibatalkan")

    def progress(self, *a, **kv):
        self.pesan.append(kv.get("message") or (a[2] if len(a) > 2 else ""))


class Pemanasan(unittest.TestCase):
    def setUp(self):
        self.dipanggil = []
        self.asli = ba.__dict__.get("_uji_hitung")

    def jalankan(self, ctx, hitung):
        import app.routers.clips as clips
        asli = clips.hitung_reframe
        clips.hitung_reframe = hitung
        try:
            return ba.run_bingkai_awal(ctx)
        finally:
            clips.hitung_reframe = asli

    def klip(self, n):
        return [{"segments": [{"start": i * 10.0, "end": i * 10.0 + 8.0}],
                 "subtitles": [{"start": i * 10.0, "end": i * 10.0 + 2.0, "speaker": 0}]}
                for i in range(n)]

    def test_semua_klip_dihitung(self):
        ctx = Ctx({"video_id": "v", "klip": self.klip(3)})
        hasil = self.jalankan(ctx, lambda **kv: self.dipanggil.append(kv) or {})
        self.assertEqual(hasil["siap"], 3)
        self.assertEqual(len(self.dipanggil), 3)
        self.assertEqual(self.dipanggil[0]["video_id"], "v")

    def test_satu_klip_gagal_tidak_menghentikan_sisanya(self):
        def kadang_gagal(**kv):
            if kv["segments"][0]["start"] == 10.0:
                raise OSError("berkas rusak")
            return {}
        ctx = Ctx({"video_id": "v", "klip": self.klip(3)})
        hasil = self.jalankan(ctx, kadang_gagal)
        self.assertEqual((hasil["siap"], hasil["gagal"]), (2, 1))

    def test_pembatalan_dihormati(self):
        ctx = Ctx({"video_id": "v", "klip": self.klip(5)}, batal_pada=2)
        with self.assertRaises(JobCancelled):
            self.jalankan(ctx, lambda **kv: {})

    def test_segmen_terlalu_pendek_dilewati(self):
        ctx = Ctx({"video_id": "v",
                   "klip": [{"segments": [{"start": 0.0, "end": 0.1}]}]})
        hasil = self.jalankan(ctx, lambda **kv: self.dipanggil.append(kv) or {})
        self.assertEqual(hasil["siap"], 0)
        self.assertEqual(self.dipanggil, [])

    def test_jumlahnya_dibatasi(self):
        ctx = Ctx({"video_id": "v", "klip": self.klip(ba.MAKS_KLIP + 6)})
        hasil = self.jalankan(ctx, lambda **kv: {})
        self.assertEqual(hasil["siap"], ba.MAKS_KLIP)

    def test_tanpa_klip_selesai_diam_diam(self):
        ctx = Ctx({"video_id": "v", "klip": []})
        self.assertEqual(self.jalankan(ctx, lambda **kv: {})["siap"], 0)


class KunciSimpanan(unittest.TestCase):
    """
    Pemanasan dan editor harus menghasilkan kunci yang SAMA persis, kalau tidak
    pemanasannya menghitung sesuatu yang tidak pernah dibaca siapa pun.
    """

    def test_kunci_sama_untuk_permintaan_yang_sama(self):
        from app.routers.clips import _kunci_reframe
        a = ("v", "9:16", ((0.0, 8.0),), ((0.0, 2.0, 0),), None, (), False, "wajah")
        b = ("v", "9:16", ((0.0, 8.0),), ((0.0, 2.0, 0),), None, (), False, "wajah")
        self.assertEqual(_kunci_reframe(a), _kunci_reframe(b))

    def test_kunci_berbeda_saat_segmennya_berbeda(self):
        from app.routers.clips import _kunci_reframe
        a = ("v", "9:16", ((0.0, 8.0),), (), None, (), False, "wajah")
        b = ("v", "9:16", ((0.0, 9.0),), (), None, (), False, "wajah")
        self.assertNotEqual(_kunci_reframe(a), _kunci_reframe(b))

    def test_berawalan_bingkai_supaya_tidak_ikut_dibuang(self):
        # repos/cache.bersihkan() menyimpan awalan ini selamanya.
        from app.routers.clips import _kunci_reframe
        self.assertTrue(_kunci_reframe(("v",)).startswith("bingkai:"))


if __name__ == "__main__":
    unittest.main()
