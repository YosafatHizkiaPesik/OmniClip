"""
Jejak wajah yang dihitung sebelum ada yang membukanya.

Dilaporkan: "ada beberapa yang langsung mengikuti wajah dan ada beberapa yang
perlu menunggu lagi padahal pemrosesan sudah selesai". Terukur pada klip 20
detik di komputer pemiliknya: 29 detik untuk hitungan pertama, 0,015 detik
sesudah tersimpan.
"""

import unittest
from pathlib import Path

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


class SakelarPemanasanBingkai(unittest.TestCase):
    """
    Pemanasan bingkai bisa dimatikan sejak 25 September 2026, dari panel Bingkai.

    Diminta pemiliknya, dan alasannya sah dua arah: menyala berarti tidak perlu
    menunggu tiap kali membuka klip, mati berarti CPU di latar bebas. Yang
    menentukan pertukarannya pemiliknya, bukan kode.
    """

    def setUp(self):
        from app.repos import settings as repo
        self.repo, self.nilai = repo, {}
        self.asli = (repo.get, repo.set_value)
        repo.get = lambda n, b=None: self.nilai.get(n, b)
        repo.set_value = lambda n, v: self.nilai.__setitem__(n, v)

    def tearDown(self):
        self.repo.get, self.repo.set_value = self.asli

    def test_bawaannya_menyala(self):
        """Perilaku yang sudah ada tidak boleh berubah sendiri saat sakelar ada."""
        from app.services.pipeline import pemanasan_bingkai
        self.assertTrue(pemanasan_bingkai())

    def test_bisa_dimatikan_dan_dinyalakan_lagi(self):
        from app.services.pipeline import pemanasan_bingkai, setel_pemanasan_bingkai
        setel_pemanasan_bingkai(False)
        self.assertFalse(pemanasan_bingkai())
        setel_pemanasan_bingkai(True)
        self.assertTrue(pemanasan_bingkai())

    def test_sakelar_mati_tidak_ikut_mematikan_permintaan_langsung(self):
        """
        Tombol "Siapkan bingkai video ini sekarang" memakai jalur yang sama,
        TANPA memeriksa sakelarnya: yang menekan tombol sudah menyatakan maunya.
        """
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "pipeline.py").read_text(encoding="utf-8")
        badan = sumber.split("def _jadwalkan_jejak_sekarang")[1][:600]
        self.assertNotIn("pemanasan_bingkai()", badan)
        # Dan yang memeriksa sakelarnya adalah pembungkus otomatisnya.
        otomatis = sumber.split("def _jadwalkan_jejak(")[1][:1400]
        self.assertIn("not pemanasan_bingkai()", otomatis)


class FacecamDisimpanDanDipanaskan(unittest.TestCase):
    """
    Video gameplay tidak memakai jejak wajah: Studio memintanya lewat
    `/clip-facecam`. Sampai 25 September 2026 endpoint itu tidak punya simpanan
    APA PUN, jadi tiap klip memindai ulang videonya dan menutup aplikasi
    menghapus seluruhnya. Pada gameplay 1 jam 45 menit berisi 28 klip, itu dua
    puluh delapan pemindaian, tiap kali orangnya menunggu di depan layar.

    Pemanasan pun menghitung hal yang tidak pernah dipakai pada video seperti
    itu: jejak wajah, bukan facecam.
    """

    def test_kunci_simpanan_mengikuti_potongannya(self):
        from app.routers.clips import _kunci_facecam
        a = _kunci_facecam("vid", [{"start": 1.0, "end": 2.0}])
        self.assertEqual(a, _kunci_facecam("vid", [{"start": 1.0, "end": 2.0}]))
        # Potongan lain berarti gambar lain, jadi simpanan lain.
        self.assertNotEqual(a, _kunci_facecam("vid", [{"start": 1.0, "end": 3.0}]))
        # Video lain juga.
        self.assertNotEqual(a, _kunci_facecam("lain", [{"start": 1.0, "end": 2.0}]))

    def test_yang_tersimpan_dibaca_kembali(self):
        from unittest import mock
        from app.routers import clips as r

        simpanan = {}
        with mock.patch("app.repos.cache.simpan",
                        side_effect=lambda k, v: simpanan.__setitem__(k, v)), \
             mock.patch("app.repos.cache.ambil",
                        side_effect=lambda k, ttl=None: simpanan.get(k)):
            segmen = [{"start": 5.0, "end": 9.0}]
            self.assertIsNone(r._facecam_tersimpan("vid", segmen))
            r._simpan_facecam("vid", segmen, {"ditemukan": True, "layout": {"a": 1}})
            self.assertEqual(r._facecam_tersimpan("vid", segmen),
                             {"ditemukan": True, "layout": {"a": 1}})

    def test_endpoint_membaca_simpanan_sebelum_memindai(self):
        """Urutannya menentukan: memindai dulu lalu menyimpan tidak menolong."""
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "routers"
                  / "clips.py").read_text(encoding="utf-8")
        # Seluruh badan fungsinya, bukan sekian ratus karakter pertama:
        # menambahkan satu penolong di atasnya pernah membuat uji ini gagal
        # tanpa ada yang rusak.
        badan = sumber.split('async def clip_facecam')[1].split('\n@router')[0]
        self.assertLess(badan.index("_facecam_tersimpan"), badan.index("def kerja"))

    def test_video_gameplay_tidak_menghitung_jejak_wajah(self):
        """
        Separuh lebih waktu pemanasan dulu terbuang di video gameplay.

        Klip gameplay disusun dari letak panel facecam; jejak wajah tidak
        pernah dibacanya. Terukur pada video horor 2560x1440 milik pemiliknya:
        18,3 detik jejak wajah yang tidak dipakai ditambah 11,7 detik pindai
        facecam yang dipakai, 30 detik per klip, 10 menit untuk 20 klip.
        Sesudah dipisah: 4,6 menit.
        """
        from unittest import mock
        from app.services import bingkai_awal as B

        klip = [{"segments": [{"start": 0.0, "end": 30.0}], "subtitles": []}
                for _ in range(3)]

        class Ctx:
            payload = {"video_id": "vid", "aspect_ratio": "9:16", "klip": klip}
            def check_cancelled(self): pass
            def progress(self, *a, **k): pass

        for gameplay in (True, False):
            with self.subTest(gameplay=gameplay), \
                 mock.patch.object(B, "_ini_gameplay", return_value=gameplay), \
                 mock.patch.object(B, "_panaskan_facecam") as panas, \
                 mock.patch.object(B, "_tema_untuk_semua", return_value=0), \
                 mock.patch("app.routers.clips.hitung_reframe") as jejak, \
                 mock.patch("app.services.pipeline.tambatkan_ke_wajah",
                            return_value=None) as tambat:
                B.run_bingkai_awal(Ctx())
                if gameplay:
                    self.assertEqual(jejak.call_count, 0, "jejak wajah tidak dipakai")
                    self.assertEqual(panas.call_count, 3)
                    self.assertEqual(tambat.call_count, 0,
                                     "menambat suara ke wajah butuh jejak yang tidak ada")
                else:
                    self.assertEqual(jejak.call_count, 3)
                    self.assertEqual(panas.call_count, 0,
                                     "video biasa tidak punya panel facecam untuk dipindai")

    def test_jenis_video_ditanyakan_sekali(self):
        """
        Letak panel facecam tidak berpindah sepanjang video, jadi satu klip
        cukup. Menanyakannya per klip akan mengembalikan biaya yang baru saja
        dihemat.
        """
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "bingkai_awal.py").read_text(encoding="utf-8")
        badan = sumber.split("def run_bingkai_awal")[1].split("\ndef ")[0]
        self.assertEqual(badan.count("_ini_gameplay("), 1)
        # Dan di LUAR perulangan klipnya.
        self.assertLess(badan.index("_ini_gameplay("), badan.index("for i, klip in"))

    def test_pemanasan_ikut_menghitung_facecam(self):
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "bingkai_awal.py").read_text(encoding="utf-8")
        self.assertIn("_panaskan_facecam(video_id, segmen)", sumber)
        # Dan memakai simpanan yang SAMA dengan yang dibaca endpointnya.
        self.assertIn("_kunci_facecam", sumber)
