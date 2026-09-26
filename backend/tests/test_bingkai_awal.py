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
                 mock.patch.object(B, "_jenis_video", return_value=gameplay), \
                 mock.patch.object(B, "_daftar_terbaru", side_effect=lambda v, d: d), \
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

    def test_jenis_video_tidak_punya_pemindaian_sendiri(self):
        """
        Jawabannya datang dari kerja klip pertama, bukan dari pemeriksaan
        terpisah.

        Versi sebelumnya memindai satu klip khusus untuk bertanya; pada klip
        podcast 159 detik itu 21 detik penuh di 0% sebelum satu bingkai pun
        dikerjakan, dan orang yang menunggu tidak melihat apa-apa bergerak.
        """
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "bingkai_awal.py").read_text(encoding="utf-8")
        badan = sumber.split("def run_bingkai_awal")[1].split("\ndef ")[0]
        self.assertNotIn("_ini_gameplay", sumber)
        # Jawabannya diambil sekali, di luar perulangan klip.
        self.assertEqual(badan.count("_jenis_video("), 1)
        self.assertLess(badan.index("_jenis_video("), badan.index("for i, klip in"))
        # Dan jawabannya datang dari penggolong yang sama dengan yang dipakai
        # Studio, bukan dari pemindai panel facecam sendirian: pemindai itu
        # mengira wajah orang di podcast sebagai panel, 32% x 49% dengan
        # kehadiran 100%.
        self.assertIn("jenis_klip_tersimpan", sumber)
        # Dan penambatan suara — yang menulis ulang label penutur, dan label
        # itu ikut jadi kunci simpanan bingkai — dikerjakan SEBELUM bingkainya
        # dihitung. Terbalik, seluruh hasil pemanasan terbuang.
        self.assertLess(badan.index("tambatkan_ke_wajah"), badan.index("for i, klip in"))

    def test_kemajuan_menyebut_klip_ke_berapa_dari_berapa(self):
        """
        "Sedang memproses" tanpa nomor tidak bisa dibedakan dari macet, dan
        pekerjaan inilah yang paling lama tanpa ada yang menunggunya di layar.
        Terlapor dua kali: "tampilan yang memproses semua klip tidak ada".
        """
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "bingkai_awal.py").read_text(encoding="utf-8")
        self.assertIn('f"Bingkai klip {i + 1} dari {len(daftar)}{sisa}"', sumber)
        # Dan judul klipnya ikut, supaya terbaca sebagai pekerjaan nyata.
        self.assertIn('judul = (klip.get("title") or "").strip()', sumber)

    def test_sakelar_mati_menghentikan_di_tengah_jalan(self):
        """
        Sakelarnya berlaku SEKARANG, bukan mulai video berikutnya.

        Orang menekan "matikan pemakaian CPU di latar" justru saat CPU-nya
        sedang dipakai. Sakelar yang hanya berlaku untuk video berikutnya tidak
        melakukan apa pun pada satu-satunya saat ia ditekan.
        """
        from unittest import mock
        from app.services import bingkai_awal as B

        klip = [{"segments": [{"start": 0.0, "end": 30.0}], "subtitles": [],
                 "title": f"K{i}"} for i in range(8)]

        class Ctx:
            payload = {"video_id": "vid", "aspect_ratio": "9:16", "klip": klip}
            def __init__(self): self.pesan = []
            def check_cancelled(self): pass
            def progress(self, p, stage=None, message=None):
                self.pesan.append((p, message))

        panggil = {"n": 0}

        # Sekali dibaca sebelum menambatkan suara, lalu sekali per klip. Mati
        # sesudah dua klip.
        def sakelar():
            panggil["n"] += 1
            return panggil["n"] <= 3

        with mock.patch("app.services.pipeline.pemanasan_bingkai", side_effect=sakelar), \
             mock.patch.object(B, "_jenis_video", return_value=False), \
             mock.patch.object(B, "_daftar_terbaru", side_effect=lambda v, d: d), \
             mock.patch.object(B, "_panaskan_facecam"), \
             mock.patch.object(B, "_tema_untuk_semua", return_value=0) as tema, \
             mock.patch("app.routers.clips.hitung_reframe") as jejak, \
             mock.patch("app.services.pipeline.tambatkan_ke_wajah") as tambat:
            ctx = Ctx()
            hasil = B.run_bingkai_awal(ctx)

        self.assertTrue(hasil.get("dihentikan"))
        self.assertEqual(hasil["siap"], 2)
        self.assertEqual(jejak.call_count, 2, "klip sesudahnya tidak dikerjakan")
        # Menambatkan suara ke wajah kini dikerjakan DI DEPAN, karena ia
        # menulis ulang label penutur yang ikut jadi kunci simpanan bingkai.
        # Jadi ia sudah selesai saat sakelarnya dimatikan; yang harus berhenti
        # adalah langkah yang belum dimulai.
        self.assertEqual(tema.call_count, 0, "pemilihan tema ikut berhenti")
        self.assertEqual(tambat.call_count, 1)
        # Dan pesannya mengatakan berapa yang sudah siap, supaya menyalakannya
        # lagi terbaca sebagai melanjutkan, bukan mengulang.
        self.assertIn("Dihentikan", ctx.pesan[-1][1])
        self.assertIn("2 dari 8", ctx.pesan[-1][1])

    def test_kemajuan_langkah_pinjaman_dipetakan(self):
        """
        Langkah yang dipakai bersama melapor dalam rentangnya SENDIRI.

        `tambatkan_ke_wajah` melapor 0,20-0,42 karena di dalam auto-klip ia
        memang di situ. Diteruskan apa adanya, bilah kemajuan melompat dari 96%
        ke 20% di akhir pekerjaan — dan bilah yang mundur terbaca persis seperti
        macet, yang justru sedang kita hilangkan.
        """
        from app.services.bingkai_awal import _Ekor

        dicatat = []

        class Ctx:
            def check_cancelled(self): pass
            def progress(self, p, **kw): dicatat.append(p)

        ekor = _Ekor(Ctx(), 0.94, 0.99)
        for p in (0.0, 0.20, 0.42, 1.0):
            ekor.progress(p)
        self.assertEqual([round(x, 4) for x in dicatat], [0.94, 0.95, 0.961, 0.99])
        # Di luar batas pun tidak boleh keluar dari rentangnya.
        dicatat.clear()
        ekor.progress(-1.0)
        ekor.progress(9.0)
        self.assertEqual(dicatat, [0.94, 0.99])

    def test_pemanasan_ikut_menghitung_facecam(self):
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "bingkai_awal.py").read_text(encoding="utf-8")
        self.assertIn("_panaskan_facecam(video_id, segmen)", sumber)
        # Dan memakai simpanan yang SAMA dengan yang dibaca endpointnya.
        self.assertIn("_kunci_facecam", sumber)


class SakelarDiPanelBingkai(unittest.TestCase):
    """
    Letak dan perilaku sakelarnya di layar.

    Dibaca sebagai teks; proyek ini tidak punya penjalan uji JavaScript.
    """

    PANEL = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "features"
             / "studio" / "FramePanel.jsx")

    def test_sakelar_ada_di_paling_atas_panel(self):
        """
        Sebelumnya ia terselip di antara setelan yang hanya muncul untuk
        sebagian cara membingkai, jadi letaknya berpindah-pindah tergantung
        mode yang sedang dipilih — dan sering tidak terlihat sama sekali.
        """
        jsx = self.PANEL.read_text(encoding="utf-8")
        badan = jsx[jsx.index("export default function FramePanel"):]
        self.assertLess(badan.index("<PemanasanBingkai"),
                        badan.index("Cara membingkai"),
                        "sakelarnya harus berdiri sebelum daftar cara membingkai")
        self.assertEqual(badan.count("<PemanasanBingkai"), 1)

    def test_menyalakan_kembali_menyebut_videonya(self):
        """
        Tanpa `video_id`, menyalakannya hanya menyalakan sakelar: video yang
        sedang dibuka tidak dilanjutkan, dan orangnya menunggu sesuatu yang
        tidak pernah dimulai.
        """
        jsx = self.PANEL.read_text(encoding="utf-8")
        self.assertIn("'/settings/pemanasan-bingkai'", jsx)
        self.assertIn("video_id: videoId || null", jsx)


class SakelarDiServer(unittest.TestCase):
    def test_dimatikan_membatalkan_yang_sedang_berjalan(self):
        from unittest import mock
        from app.routers import settings as S

        aktif = [{"id": "a", "type": "bingkai_awal"},
                 {"id": "b", "type": "auto_clip"},
                 {"id": "c", "type": "bingkai_awal"}]
        with mock.patch("app.repos.jobs.active", return_value=aktif), \
             mock.patch("app.services.jobs.queue.cancel", return_value=True) as batal:
            n = S._hentikan_pemanasan()
        self.assertEqual(n, 2)
        # Pekerjaan lain tidak boleh ikut dibatalkan.
        self.assertEqual([c.args[0] for c in batal.call_args_list], ["a", "c"])

    def test_dinyalakan_memakai_jalur_yang_sama_dengan_tombolnya(self):
        """
        Melanjutkan dan memulai dari tombol tidak boleh berbeda perilakunya;
        dua jalur yang menjadwalkan pekerjaan yang sama akan bergeser sendiri.
        """
        from unittest import mock
        from app.routers import settings as S

        cached = {"result": {"clips": [{"segments": [{"start": 0, "end": 5}]}],
                             "aspect_ratio": "9:16"}}
        with mock.patch("app.repos.analyses.latest_for_video", return_value=cached), \
             mock.patch("app.services.pipeline._jadwalkan_jejak_sekarang",
                        return_value="job-1") as jadwal:
            self.assertEqual(S._lanjutkan_pemanasan("vid"), 1)
        jadwal.assert_called_once()

    def test_tanpa_klip_tidak_menjadwalkan_apa_apa(self):
        from unittest import mock
        from app.routers import settings as S
        with mock.patch("app.repos.analyses.latest_for_video", return_value=None):
            self.assertEqual(S._lanjutkan_pemanasan("vid"), 0)


class JalurPekerjaanRingan(unittest.TestCase):
    """
    Pemantau kemajuan tidak boleh menarik seluruh isi tabel job.

    Bilah penyiapan bingkai versi pertama menjajaki `/api/jobs?limit=40` tiap
    enam detik. Terukur pada penyimpanan pemiliknya: 2,4 MB per jawaban dalam
    0,48 detik, karena tiap baris membawa seluruh daftar klip beserta
    subtitle-nya. Yang ditanyakan hanya "apakah ada yang berjalan".
    """

    def test_ringkasan_tidak_membawa_muatan(self):
        from app.routers.jobs import RINGKAS
        self.assertNotIn("payload", RINGKAS)
        self.assertNotIn("result", RINGKAS)
        # Dan tetap membawa yang dibutuhkan sebuah bilah kemajuan.
        for k in ("id", "type", "status", "progress", "message", "video_id"):
            self.assertIn(k, RINGKAS)

    def test_jalur_aktif_menyaring_video_dan_jenis(self):
        import asyncio
        from unittest import mock
        from app.routers import jobs as J

        semua = [
            {"id": "a", "type": "bingkai_awal", "video_id": "v1", "status": "running",
             "progress": 0.5, "message": "x", "payload": {"besar": "x" * 1000}},
            {"id": "b", "type": "bingkai_awal", "video_id": "v2", "status": "running"},
            {"id": "c", "type": "render", "video_id": "v1", "status": "running"},
        ]
        with mock.patch("app.repos.jobs.active", return_value=semua):
            r = asyncio.run(J.list_active_jobs(video_id="v1", type="bingkai_awal"))
        self.assertEqual([j["id"] for j in r["jobs"]], ["a"])
        self.assertNotIn("payload", r["jobs"][0])

    def test_bilah_memakai_jalur_ringan_dan_aliran(self):
        """Dibaca sebagai teks; proyek ini tidak punya penjalan uji JavaScript."""
        jsx = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "features"
               / "studio" / "BilahBingkaiAwal.jsx").read_text(encoding="utf-8")
        self.assertIn("/jobs/aktif?video_id=", jsx)
        self.assertIn("/api/jobs/events", jsx)
        # Tidak boleh ada penjajakan berkala ke daftar job yang penuh.
        self.assertNotIn("apiGet('/jobs?limit", jsx)
        self.assertNotIn("setTimeout(cari", jsx)
