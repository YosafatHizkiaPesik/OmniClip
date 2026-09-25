"""
Penyedia AI, font aksara, pemilihan model, dan keamanan jalur berkas.

Yang terakhir itu yang paling penting di berkas ini: nama berkas datang dari
peramban, dan "../../omniclip.db" adalah nama berkas yang sah. Pemeriksaannya
tidak boleh hilang tanpa ada yang menyadarinya.
"""

import unittest
from pathlib import Path

from app.services import fonts, openrouter, pemeliharaan
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
    """
    RAM-nya dipalsukan, dan itu bukan kemalasan.

    `model_untuk` menanyakan RAM bebas mesin yang SEDANG berjalan, jadi tanpa
    dipalsukan ujinya menjawab berbeda tergantung apa lagi yang kebetulan
    sedang terbuka. Terukur 24 September 2026: lolos saat dijalankan sendirian,
    gagal saat dijalankan bersama seluruh berkas uji — bukan karena ada yang
    rusak, melainkan karena berkas uji lain sudah memuat numpy dan opencv.
    Uji yang jawabannya bergantung pada cuaca adalah uji yang akhirnya
    diabaikan orang.
    """

    def setUp(self):
        from app.services import whisper
        self.asli = whisper.available_ram_mb
        whisper.available_ram_mb = lambda: 8000      # cukup untuk model apa pun

    def tearDown(self):
        from app.services import whisper
        whisper.available_ram_mb = self.asli

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

    def test_ram_sempit_menahan_kenaikan(self):
        # Menaikkan model lalu mati kehabisan memori jauh lebih buruk daripada
        # transkrip yang kurang tepat.
        from app.services import whisper
        whisper.available_ram_mb = lambda: 400
        model, alasan = model_untuk("ja", "base")
        self.assertEqual(model, "base")
        self.assertIn("RAM", alasan)

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


if __name__ == "__main__":
    unittest.main()


class SalinanPratinjau(unittest.TestCase):
    """
    Kapan Studio memutar salinan, dan kapan ia memutar sumbernya.

    Dua pertanyaan berbeda yang dulu dijawab satu angka lebar, dan itu yang
    membuat gambar di editor selalu lebih buruk daripada hasil rendernya:
    sumber 1080p h264 yang bisa diputar peramban mana pun tetap diganti salinan
    720p crf 26.
    """

    def jawab(self, info):
        from app.services import proksi
        from app.services import media
        asli = media.probe
        media.probe = lambda p: info
        try:
            return proksi.butuh_salinan(Path("/tmp/contoh.mp4"))
        finally:
            media.probe = asli

    def test_h264_1080p_diputar_langsung(self):
        self.assertFalse(self.jawab({"width": 1920, "height": 1080, "vcodec": "h264"}))

    def test_4k_selalu_butuh_salinan(self):
        self.assertTrue(self.jawab({"width": 3840, "height": 2160, "vcodec": "h264"}))

    def test_vp9_besar_butuh_salinan(self):
        # Terukur: Firefox memutar 4K VP9 pada 0,44x kecepatan.
        self.assertTrue(self.jawab({"width": 1920, "height": 1080, "vcodec": "vp9"}))

    def test_vp9_kecil_tidak_perlu(self):
        self.assertFalse(self.jawab({"width": 854, "height": 480, "vcodec": "vp9"}))


class LebarSalinan(unittest.TestCase):
    """
    Salinan yang ikut DITONTON dibuat lebih besar daripada yang hanya dibaca
    mesin. Pada sumber 4K bedanya paling terasa, justru karena sumbernya paling
    tajam, dan di sanalah salinan tidak bisa dihindari.
    """

    def lebar(self, info):
        from app.services import media, proksi
        asli = media.probe
        media.probe = lambda p: info
        try:
            return proksi._lebar_untuk(Path("/tmp/contoh.mp4"))
        finally:
            media.probe = asli

    def test_sumber_yang_ikut_diputar_dapat_salinan_lebih_besar(self):
        from app.services import proksi
        self.assertEqual(self.lebar({"width": 3840, "height": 2160, "vcodec": "h264"}),
                         proksi.LEBAR_PUTAR)

    def test_sumber_yang_hanya_dianalisis_tetap_kecil(self):
        from app.services import proksi
        self.assertEqual(self.lebar({"width": 1920, "height": 1080, "vcodec": "h264"}),
                         proksi.LEBAR)

    def test_salinan_tonton_lebih_besar_daripada_salinan_analisis(self):
        from app.services import proksi
        self.assertGreater(proksi.LEBAR_PUTAR, proksi.LEBAR)


class IzinGoogle(unittest.TestCase):
    """
    Izin yang diminta OmniClip, dan yang harus didaftarkan pemiliknya di Google
    Cloud Console. Keduanya harus sama; kalau tidak, pemiliknya mendaftarkan
    izin yang salah dan baru tahu saat login pertama gagal.
    """

    @staticmethod
    def dari_antarmuka() -> list[str]:
        import re
        akar = Path(__file__).resolve().parents[2]
        teks = (akar / "frontend" / "src" / "components"
                / "TambahAkun.jsx").read_text(encoding="utf-8")
        blok = teks[teks.index("const SCOPES_TEKS = ["):]
        return re.findall(r"'(https://[^']+)'", blok[:blok.index("]")])

    def test_yang_ditampilkan_sama_dengan_yang_diminta(self):
        from app.services.google_upload import SCOPES

        https = [s for s in SCOPES if s.startswith("https://")]
        self.assertEqual(sorted(self.dari_antarmuka()), sorted(https))

    def test_openid_tidak_ikut_ditampilkan(self):
        # Kotak "Manually add scopes" hanya menerima alamat https, dan Google
        # memberikan openid sendiri saat userinfo.email diminta.
        self.assertNotIn("openid", self.dari_antarmuka())

    def test_izinnya_tetap_sekecil_mungkin(self):
        from app.services.google_upload import SCOPES

        # drive.file hanya berkas buatan aplikasi ini; youtube.upload tidak bisa
        # membaca atau menghapus video yang sudah ada.
        self.assertIn("https://www.googleapis.com/auth/drive.file", SCOPES)
        self.assertNotIn("https://www.googleapis.com/auth/drive", SCOPES)
        self.assertNotIn("https://www.googleapis.com/auth/youtube.force-ssl", SCOPES)


class BerandaDariKebiasaan(unittest.TestCase):
    """
    Beranda yang isinya mengikuti apa yang MEMANG dicari, bukan apa yang
    kebetulan terakhir diketik. Dilaporkan: "buat agar beranda berisi konten
    yang sering kita cari, jadi tidak perlu mencari ulang terus."
    """

    def kolam(self, minat, sering, riwayat):
        from app.repos import profil as repo
        from app.routers import videos
        from app.services import profil as ps

        asli = (repo.ambil, repo.kueri_sering, repo.riwayat_cari, ps.kini)
        repo.ambil = lambda p: {"minat": minat}
        repo.kueri_sering = lambda p, n=6, minimal=2: [{"query": q} for q in sering]
        repo.riwayat_cari = lambda p, n=8: [{"query": q} for q in riwayat]
        ps.kini = lambda: 1
        try:
            return videos._kolam_beranda()
        finally:
            repo.ambil, repo.kueri_sering, repo.riwayat_cari, ps.kini = asli

    def test_minat_paling_berat(self):
        k = self.kolam(["horor"], ["podcast"], ["gaming"])
        self.assertEqual(k.count("horor"), 3)
        self.assertEqual(k.count("podcast"), 2)
        self.assertEqual(k.count("gaming"), 1)

    def test_yang_sering_dicari_mengalahkan_yang_terakhir(self):
        k = self.kolam([], ["podcast bisnis"], ["sekali ketik"])
        self.assertGreater(k.count("podcast bisnis"), k.count("sekali ketik"))

    def test_tanpa_apa_pun_memakai_kolam_umum(self):
        from app.routers import videos
        self.assertEqual(self.kolam([], [], []), videos.TRENDING_QUERIES)

    def test_kueri_sering_menolak_yang_cuma_sekali(self):
        # Sekali bisa berarti salah ketik, atau penasaran yang sudah selesai.
        import inspect
        from app.repos import profil as repo
        sumber = inspect.getsource(repo.kueri_sering)
        self.assertIn("HAVING kali >= ?", sumber)
        self.assertIn("ORDER BY kali DESC", sumber)


class MesinPemilihKlipYangDiizinkan(unittest.TestCase):
    """
    Skema basis data harus mengenal setiap nilai `engine` yang bisa ditulis kode.

    Batasan lama hanya mengenal 'heuristic' dan 'gemini'. Ia ditulis sebelum
    OpenRouter ada dan tidak ikut dilonggarkan ketika jalur cadangannya
    dibangun, jadi hasil OpenRouter yang SUDAH selesai gagal disimpan di baris
    terakhir pekerjaannya. Tertangkap 24 September 2026 di catatan job
    sungguhan: "CHECK constraint failed: engine IN ('heuristic','gemini')".

    Cacat paling mahal bentuknya begini: sukses yang dibuang di detik terakhir,
    dan yang terlihat pemiliknya cuma "auto-klip gagal".
    """

    def _skema(self) -> str:
        from pathlib import Path
        return (Path(__file__).resolve().parents[1] / "app" / "db.py").read_text(encoding="utf-8")

    def test_skema_mengenal_ketiga_mesin(self):
        skema = self._skema()
        for mesin in ("heuristic", "gemini", "openrouter"):
            self.assertIn(f"'{mesin}'", skema, f"skema tidak mengenal {mesin}")

    def test_setiap_mesin_di_pipeline_ada_di_skema(self):
        """Yang dijaga bukan daftarnya, melainkan bahwa keduanya tidak berpisah."""
        import re
        from pathlib import Path

        pipeline = (Path(__file__).resolve().parents[1] / "app" / "services"
                    / "pipeline.py").read_text(encoding="utf-8")
        dipakai = set(re.findall(r'engine(?:,\s*\w+)?\s*=\s*"(\w+)"', pipeline))
        self.assertTrue(dipakai, "tidak ada nilai engine yang terbaca dari pipeline")
        m = re.search(r"engine\s+TEXT NOT NULL CHECK \(engine IN \(([^)]*)\)\)", self._skema())
        self.assertIsNotNone(m, "batasan engine tidak ditemukan di skema")
        diizinkan = set(re.findall(r"'(\w+)'", m.group(1)))
        self.assertTrue(dipakai <= diizinkan,
                        f"pipeline memakai {dipakai - diizinkan} yang ditolak skema")


class KemajuanSalinanPratinjau(unittest.TestCase):
    """
    Salinan pratinjau video dua jam memakan puluhan menit sampai berjam-jam,
    dan sampai 25 September 2026 yang terlihat hanya lingkaran berputar tanpa
    angka. Dilaporkan dari Windows: "sudah berapa jam masih loading, tidak bisa
    mengedit apa pun". Yang hilang bukan kecepatannya melainkan kabarnya.
    """

    def _tulis(self, tmp, detik_selesai):
        """Berkas `-progress` milik ffmpeg, seperti yang ia tulis sungguhan."""
        from pathlib import Path
        p = Path(tmp) / "proksi.tmp.kemajuan"
        p.write_text(
            "frame=120\nfps=30\nout_time_ms=1000000\nprogress=continue\n"
            f"frame=999\nfps=31\nout_time_ms={int(detik_selesai * 1_000_000)}\n"
            "progress=continue\n", encoding="utf-8")
        return p

    def test_membaca_baris_terakhir_bukan_yang_pertama(self):
        """Berkasnya ditulis terus-menerus; yang berlaku nilai TERAKHIR."""
        import tempfile
        from unittest import mock
        from app.services import proksi

        with tempfile.TemporaryDirectory() as tmp:
            prog = self._tulis(tmp, 300.0)
            tujuan = prog.with_name("proksi.mp4")
            with mock.patch.object(proksi, "_nama", return_value=tujuan), \
                 mock.patch("app.services.media.probe", return_value={"duration": 600.0}):
                self.assertAlmostEqual(proksi.kemajuan("/apa/saja.mp4"), 0.5, places=2)

    def test_tanpa_berkas_kemajuan_menjawab_none(self):
        """Belum mulai dan tidak sedang dibuat sengaja tidak dibedakan."""
        import tempfile
        from pathlib import Path
        from unittest import mock
        from app.services import proksi

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(proksi, "_nama",
                                   return_value=Path(tmp) / "belum-ada.mp4"):
                self.assertIsNone(proksi.kemajuan("/apa/saja.mp4"))

    def test_tidak_pernah_melewati_satu(self):
        import tempfile
        from unittest import mock
        from app.services import proksi

        with tempfile.TemporaryDirectory() as tmp:
            prog = self._tulis(tmp, 9999.0)
            with mock.patch.object(proksi, "_nama", return_value=prog.with_name("proksi.mp4")), \
                 mock.patch("app.services.media.probe", return_value={"duration": 600.0}):
                self.assertEqual(proksi.kemajuan("/apa/saja.mp4"), 1.0)

    def test_ffmpeg_benar_benar_diminta_menulis_kemajuan(self):
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "proksi.py").read_text(encoding="utf-8")
        self.assertIn('"-progress", str(sementara.with_suffix(".kemajuan"))', sumber)
        # Dan dibersihkan sesudahnya, kalau tidak ia tertinggal selamanya.
        self.assertIn('sementara.with_suffix(".kemajuan").unlink(missing_ok=True)', sumber)


class SalinanPratinjauYangTidakMenahanPemiliknya(unittest.TestCase):
    """
    "Loading terus tidak selesai-selesai sehingga mengganggu proses klipping",
    dilaporkan 25 September 2026 pada gameplay 2560x1440 VP9 60 fps sepanjang
    1 jam 45 menit. Salinannya memang selesai, setelah SATU SETENGAH JAM.

    Diukur per 30 detik sumber, dan angkanya yang menentukan ketiga perubahan
    di bawah:

        dekode saja, batas bawah                      5,9 detik
        seperti dulu: 1600p 60 fps x264 veryfast, 2 inti   17,5 detik
        1600p 30 fps, enkoder kartu grafis, 2 inti        13,9 detik
        1600p 30 fps, enkoder kartu grafis, 4 inti        10,5 detik

    62 menit jadi sekitar 37.
    """

    def test_laju_bingkai_diturunkan(self):
        """
        Salinan ini ditonton di editor dan dibaca analisis pada 8 sampel per
        detik. Tidak satu pun butuh 60 fps, dan 60 memakan dua kali kerja.
        """
        from app.services.proksi import FPS_PROKSI
        self.assertEqual(FPS_PROKSI, 30)

    def test_inti_lebih_banyak_saat_studio_menunggu(self):
        """
        Dua inti benar untuk pekerjaan latar. Begitu Studio menunggunya, ia
        BUKAN lagi pekerjaan latar, dan menahannya di dua inti berarti menahan
        pemiliknya. Jenuh di empat, jadi empat, bukan seluruhnya.
        """
        from app.services.proksi import INTI, INTI_DITUNGGU
        self.assertGreater(INTI_DITUNGGU, INTI)
        self.assertLessEqual(INTI_DITUNGGU, 6)

    def test_mutu_salinan_lebih_longgar_daripada_mutu_render(self):
        """
        `enkoder.pilih()` menyetel qp 19 karena yang ia layani video yang akan
        diterbitkan. Salinan ini cuma ditonton di editor: qp 19 menghasilkan
        17 MB per 30 detik, qp 26 menghasilkan 7 MB dengan wajah sama jelasnya.
        """
        from app.services.proksi import _mutu_proksi
        asli = ["-c:v", "h264_vaapi", "-rc_mode", "CQP", "-qp", "19"]
        self.assertEqual(_mutu_proksi(asli)[-1], "26")
        # Enkoder CPU memakai -crf, dan itu pun ditukar.
        self.assertEqual(_mutu_proksi(["-c:v", "libx264", "-crf", "18"])[-1], "26")
        # Tanpa enkoder kartu grafis, tidak ada yang perlu ditukar.
        self.assertEqual(_mutu_proksi([]), [])

    def test_kartu_grafis_dipakai_bila_ada(self):
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "proksi.py").read_text(encoding="utf-8")
        self.assertIn("from .enkoder import pilih as _enkoder", sumber)
        # Dan kegagalannya tidak boleh menjatuhkan pembuatan salinan.
        self.assertIn("except Exception:", sumber.split("_enkoder")[2][:200])
