"""
Apa yang terjadi saat Gemini tidak bisa dipakai.

Diukur 23 September 2026: enam dari enam model Gemini menjawab 503 sepanjang
hari, dan tiga kali auto-klip berturut-turut jatuh ke mesin lokal. Yang dijaga
di sini adalah tiga hal yang membuat hari seperti itu tidak terulang diam-diam.
"""

import contextlib
import time
import unittest
import unittest.mock

from app.services import gemini, openrouter
from app.services import peringkat_model as pm


@contextlib.contextmanager
def _tanpa_menulis_pemakaian():
    """
    Menahan `pemakaian_ai.tandai_habis` selama tes.

    `catat_habis_harian` memanggilnya untuk menyamakan hitungan pemakaian
    dengan batas asli Google pada satu-satunya saat batas itu diketahui pasti.
    Di dalam tes, panggilan itu menulis dua puluh baris ke tabel pemakaian
    SUNGGUHAN atas nama model karangan. Tertangkap 24 September 2026:
    "gemini-uji-habis-3.9-flash" muncul di kartu pemakaian AI milik pengguna,
    lengkap dengan 20 panggilan yang tidak pernah terjadi.
    """
    import app.services.pemakaian_ai as pa
    asli = pa.tandai_habis
    pa.tandai_habis = lambda *a, **k: None
    try:
        yield
    finally:
        pa.tandai_habis = asli


class ModelTerakhirBerhasil(unittest.TestCase):
    """
    Urutan "terkuat dulu" saja salah arah saat model terkuat yang justru penuh:
    rantai menghabiskan anggaran waktunya pada empat model yang sama-sama 503
    sebelum sampai ke model yang sebenarnya menjawab.
    """

    def setUp(self):
        self.asli = pm._berhasil
        pm._dimuat = True                  # jangan sentuh basis data
        pm._berhasil = None

    def tearDown(self):
        pm._berhasil = self.asli

    def test_yang_baru_berhasil_dicoba_lebih_dulu(self):
        urut = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3-flash-preview"]
        pm._berhasil = ("gemini-3-flash-preview", time.time())
        self.assertEqual(pm.terakhir_berhasil(), "gemini-3-flash-preview")
        depan = [m for m in (None, pm.terakhir_berhasil()) if m]
        self.assertEqual((depan + [m for m in urut if m not in depan])[0],
                         "gemini-3-flash-preview")

    def test_catatan_lama_diabaikan(self):
        # Esok harinya, model terkuat kembali dicoba lebih dulu.
        pm._berhasil = ("gemini-3-flash-preview", time.time() - pm._LAMA_BERHASIL - 1)
        self.assertIsNone(pm.terakhir_berhasil())

    def test_pilihan_pengguna_tetap_menang(self):
        pm._berhasil = ("gemini-3.5-flash", time.time())
        depan = [m for m in ("gemini-3.8-flash", pm.terakhir_berhasil()) if m]
        self.assertEqual(depan[0], "gemini-3.8-flash")
        self.assertIn("gemini-3.5-flash", depan)

    def test_catatan_sebelum_jatah_berputar_diabaikan(self):
        """
        Jatah harian berputar tengah malam waktu Pasifik. Catatan yang dibuat
        sebelum putaran itu menunjuk keadaan KEMARIN, dan enam jam saja tidak
        menangkapnya: jatah yang habis pukul sebelas malam Pasifik pulih satu
        jam kemudian, sementara catatannya masih berumur satu jam.
        """
        # Jatah berputar satu jam yang lalu, jadi aturan enam jam sendirian
        # TIDAK akan membuang catatan yang dibuat dua jam lalu.
        with unittest.mock.patch.object(pm, "detik_ke_putaran",
                                        return_value=86400 - 3600):
            pm._berhasil = ("gemini-3.5-flash", time.time() - 7200)
            self.assertIsNone(pm.terakhir_berhasil())
            # Catatan sesudah putaran tetap berlaku.
            pm._berhasil = ("gemini-3.5-flash", time.time() - 60)
            self.assertEqual(pm.terakhir_berhasil(), "gemini-3.5-flash")

    def test_lite_tidak_pernah_memimpin_rantai(self):
        """
        Lite menjawab justru KARENA yang lain sedang kehabisan jatah. Menaruhnya
        di depan berarti seluruh pemilihan klip dikerjakan model paling lemah
        selama enam jam sesudah jatah harian pulih, dan itulah yang terbaca
        sebagai "hasil klipnya tidak berbobot".
        """
        dasar = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
        pm._berhasil = ("gemini-3.5-flash-lite", time.time())
        with unittest.mock.patch.object(pm, "daftar_kunci", return_value=dasar), \
             unittest.mock.patch.object(pm, "tanpa_kuota", return_value=False), \
             unittest.mock.patch.object(pm, "habis_harian", return_value=False):
            urutan = pm.rantai("kunci-palsu")
        self.assertEqual(urutan[0], "gemini-3.8-flash")
        self.assertEqual(urutan[-1], "gemini-3.5-flash-lite")

    def test_model_penuh_yang_baru_berhasil_tetap_memimpin(self):
        dasar = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
        pm._berhasil = ("gemini-3.6-flash", time.time())
        with unittest.mock.patch.object(pm, "daftar_kunci", return_value=dasar), \
             unittest.mock.patch.object(pm, "tanpa_kuota", return_value=False), \
             unittest.mock.patch.object(pm, "habis_harian", return_value=False):
            urutan = pm.rantai("kunci-palsu")
        self.assertEqual(urutan[0], "gemini-3.6-flash")


class RantaiTeksOpenRouter(unittest.TestCase):
    """
    Memilih klip dari transkrip satu jam dan menonton klip adalah dua tugas
    dengan syarat yang berlawanan. Model penonton berjendela kecil, dan
    transkrip yang dipotong diam-diam kehilangan justru bagian akhir video.
    """

    MODEL = [
        {"id": "kecil-penonton", "nama": "a", "video": True, "gambar": True, "suara": True,
         "json": True, "gratis": True, "konteks": 32_000},
        {"id": "besar-teks", "nama": "b", "video": False, "gambar": False, "suara": False,
         "json": True, "gratis": True, "konteks": 200_000},
        {"id": "besar-berbayar", "nama": "c", "video": False, "gambar": False, "suara": False,
         "json": True, "gratis": False, "konteks": 1_000_000},
        {"id": "sedang-tanpa-json", "nama": "d", "video": False, "gambar": False,
         "suara": False, "json": False, "gratis": True, "konteks": 300_000},
    ]

    def jalankan(self, pilihan=None):
        asli = openrouter.daftar
        openrouter.daftar = lambda segarkan=False: list(self.MODEL)
        try:
            return openrouter.rantai_teks(pilihan)
        finally:
            openrouter.daftar = asli

    def test_jendela_kecil_dibuang(self):
        ids = [m["id"] for m in self.jalankan()]
        self.assertNotIn("kecil-penonton", ids)

    def test_berbayar_tidak_ikut(self):
        self.assertNotIn("besar-berbayar", [m["id"] for m in self.jalankan()])

    def test_jawaban_terstruktur_didahulukan(self):
        ids = [m["id"] for m in self.jalankan()]
        self.assertEqual(ids[0], "besar-teks")
        self.assertIn("sedang-tanpa-json", ids)

    def test_pilihan_pengguna_di_depan(self):
        ids = [m["id"] for m in self.jalankan("sedang-tanpa-json")]
        self.assertEqual(ids[0], "sedang-tanpa-json")

    def test_daftar_gagal_bukan_alasan_meledak(self):
        asli = openrouter.daftar
        def marah(segarkan=False):
            raise OSError("jaringan mati")
        openrouter.daftar = marah
        try:
            self.assertEqual(openrouter.rantai_teks(), [])
        finally:
            openrouter.daftar = asli


class SkemaDuaBentuk(unittest.TestCase):
    """
    Skema pemilihan klip ditulis dua kali: bentuk SDK Google dan dict biasa
    untuk penyedia lain. Keduanya harus tetap sebangun, kalau tidak salah satu
    penyedia akan mengembalikan bentuk yang tidak dikenal `_apply_selections`.
    """

    def test_kolom_wajibnya_sama(self):
        polos = gemini._skema_polos()
        item = polos["properties"]["selections"]["items"]
        self.assertEqual(
            set(item["required"]),
            {"konteks", "candidate_id", "start_sentence", "end_sentence",
             "score", "reason", "hook_text", "suggested_title"})
        self.assertIn("hashtags", item["properties"])

    def test_urutan_menulis_menaruh_konteks_paling_awal(self):
        # Model menulis dari atas ke bawah: alasan memilih ditulis sebelum
        # nomor kalimat, bukan sesudahnya.
        item = gemini._skema_polos()["properties"]["selections"]["items"]
        self.assertEqual(item["property_ordering"][0], "konteks")

    def test_bisa_diterjemahkan_ke_json_schema(self):
        js = openrouter._json_schema(gemini._skema_polos())
        self.assertEqual(js["type"], "object")
        self.assertIn("selections", js["properties"])


class TanpaKunci(unittest.TestCase):
    def test_openrouter_tanpa_kunci_menolak_dengan_jelas(self):
        asli = openrouter.aktif
        openrouter.aktif = lambda: False
        try:
            with self.assertRaises(RuntimeError) as e:
                gemini.refine_openrouter(sentences=[], candidates=[], video_title="x")
            self.assertIn("OpenRouter", str(e.exception))
        finally:
            openrouter.aktif = asli


if __name__ == "__main__":
    unittest.main()


class BeberapaKunci(unittest.TestCase):
    """
    Kuota Gemini dihitung per PROJECT Google, bukan per kunci (kalimat dari
    dokumentasi Google). Dua kunci dari project yang sama berbagi jatah yang
    sama; yang menambah jatah adalah kunci dari project kedua.
    """

    def test_dipisah_baris_koma_atau_spasi(self):
        from app.config import _pecah_kunci
        for pemisah in ("\n", ", ", " ", ";\n"):
            self.assertEqual(_pecah_kunci(f"AAA{pemisah}BBB"), ["AAA", "BBB"])

    def test_kembar_hanya_sekali(self):
        from app.config import _pecah_kunci
        self.assertEqual(_pecah_kunci("AAA\nBBB\nAAA"), ["AAA", "BBB"])

    def test_kosong_dan_spasi_dibuang(self):
        from app.config import _pecah_kunci
        self.assertEqual(_pecah_kunci("  \n\n  "), [])
        self.assertEqual(_pecah_kunci(""), [])

    def test_urutannya_dipertahankan(self):
        # Kunci pertama adalah yang dicoba lebih dulu, jadi urutan ketikan
        # pemiliknya bukan sesuatu yang boleh diacak.
        from app.config import _pecah_kunci
        self.assertEqual(_pecah_kunci("SATU\nDUA\nTIGA"), ["SATU", "DUA", "TIGA"])

    def test_basis_data_dan_env_digabung(self):
        import os
        from app import config as cfg
        from app.repos import settings as settings_repo

        asli_get = settings_repo.get
        asli_env = os.environ.get("GEMINI_API_KEY", "")
        settings_repo.get = lambda k, *a, **kv: "DB1\nDB2" if k == "ai.api_key" else ""
        os.environ["GEMINI_API_KEY"] = "ENV1"
        try:
            self.assertEqual(cfg.get_api_keys(), ["DB1", "DB2", "ENV1"])
            self.assertEqual(cfg.get_api_key(), "DB1")
        finally:
            settings_repo.get = asli_get
            if asli_env:
                os.environ["GEMINI_API_KEY"] = asli_env
            else:
                os.environ.pop("GEMINI_API_KEY", None)


class JatahHabis(unittest.TestCase):
    """
    Jatah Gemini dihitung per project, bukan per model. Terukur 24 September
    2026: satu permintaan menghasilkan dua belas panggilan 429 berturut-turut
    sebelum sistem menyerah, dan tak satu pun punya peluang berhasil.
    """

    HABIS = ("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': "
             "'You exceeded your current quota, please check your plan'}}")
    NOL = "429 RESOURCE_EXHAUSTED. {'error': {'message': 'quota limit: 0'}}"

    def test_jatah_habis_dikenali(self):
        self.assertTrue(pm.kuota_habis(self.HABIS))

    def test_kuota_nol_bukan_jatah_habis(self):
        # "limit: 0" berarti model itu memang tidak pernah boleh dipakai kunci
        # ini; model LAIN dengan kunci yang sama masih mungkin bisa.
        self.assertFalse(pm.kuota_habis(self.NOL))

    def test_galat_lain_bukan_jatah_habis(self):
        for g in ("503 UNAVAILABLE", "404 NOT_FOUND", "401 UNAUTHENTICATED"):
            self.assertFalse(pm.kuota_habis(g), g)

    def test_kunci_yang_dicatat_dilewati_lalu_pulih(self):
        import time as _t
        kunci = "KUNCI-UJI-XYZ"
        try:
            self.assertFalse(pm.kunci_habis(kunci))
            pm.catat_kunci_habis(kunci)
            self.assertTrue(pm.kunci_habis(kunci))
            # Catatannya berumur pendek: jatah harian Google berputar.
            with pm._kunci:
                pm._kunci_habis[pm._sidik(kunci)] = _t.time() - pm._LAMA_KUNCI_HABIS - 1
            self.assertFalse(pm.kunci_habis(kunci))
        finally:
            with pm._kunci:
                pm._kunci_habis.pop(pm._sidik(kunci), None)

    def test_kunci_tidak_disimpan_apa_adanya(self):
        # Yang dicatat sidiknya, bukan kuncinya.
        kunci = "AIza-RAHASIA-SEKALI"
        try:
            pm.catat_kunci_habis(kunci)
            self.assertNotIn(kunci, pm._kunci_habis)
        finally:
            with pm._kunci:
                pm._kunci_habis.pop(pm._sidik(kunci), None)


class ModelLite(unittest.TestCase):
    """
    Jatah harian Gemini gratis dihitung PER MODEL per project: dua puluh
    permintaan, masing-masing punya jatahnya sendiri. Terukur 24 September 2026,
    saat enam model penuh sudah habis semua, empat model lite masih utuh, dan
    dengan itu pemilihan tema tetap dikerjakan model, bukan mesin lokal.

    Yang dijaga: lite tidak boleh naik mendahului model penuh. Ia memang menilai
    lebih dangkal; ia hanya lebih baik daripada tidak ada model sama sekali.
    """

    DAFTAR = ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-2.5-flash-lite",
              "gemini-3.8-flash", "gemini-flash-latest"]

    def test_lite_selalu_di_belakang(self):
        urut = pm.urutkan(self.DAFTAR)
        penuh = [n for n in urut if not pm.lite(n)]
        litenya = [n for n in urut if pm.lite(n)]
        self.assertEqual(urut, penuh + litenya)
        self.assertEqual(penuh[0], "gemini-3.8-flash")

    def test_lite_yang_lebih_baru_lebih_dulu(self):
        urut = [n for n in pm.urutkan(self.DAFTAR) if pm.lite(n)]
        self.assertEqual(urut, ["gemini-3.5-flash-lite", "gemini-2.5-flash-lite"])

    def test_lite_tetap_dikenali_sebagai_model_yang_dipakai(self):
        self.assertTrue(pm.lite("gemini-3.5-flash-lite"))
        self.assertFalse(pm.lite("gemini-3.6-flash"))
        self.assertFalse(pm.cocok("gemini-3.5-flash-lite"))

    def test_varian_yang_bukan_untuk_tugas_ini_tetap_ditolak(self):
        for n in ("gemini-3.5-flash-lite-tts", "gemini-3.5-flash-lite-image",
                  "gemma-3-27b-it", "gemini-3-deep-research"):
            self.assertFalse(pm.lite(n), n)
            self.assertFalse(pm.cocok(n), n)

    def test_jatah_habis_menandai_model_bukan_kunci(self):
        # Kalimat kuncinya dari id kuota Google: PerProjectPerModel.
        model = "gemini-uji-habis-3.9-flash"
        asli = pm._simpan
        pm._simpan = lambda: None          # jangan kotori basis data sungguhan
        try:
            with _tanpa_menulis_pemakaian():
                self.assertFalse(pm.habis_harian(model))
                pm.catat_habis_harian(model)
                self.assertTrue(pm.habis_harian(model))
                # Tercatat sebagai jatah harian, bukan sebagai "kuota nol".
                self.assertFalse(pm.tanpa_kuota(model))
        finally:
            pm._simpan = asli
            with pm._kunci:
                pm._habis_harian.pop(model, None)

    def test_catatan_berakhir_saat_jatah_berputar(self):
        # Jatah yang habis pukul delapan malam Pasifik pulih empat jam kemudian;
        # menungguinya sehari penuh membuang satu hari jatah yang sudah ada.
        sehari = 86400
        for jam in range(0, 24, 3):
            sisa = pm.detik_ke_putaran(jam * 3600)
            self.assertGreater(sisa, 0)
            self.assertLessEqual(sisa, sehari)

    def test_model_yang_habis_dilewati_rantai(self):
        model = "gemini-uji-habis-3.9-flash"
        asli = pm._simpan
        pm._simpan = lambda: None
        try:
            with _tanpa_menulis_pemakaian():
                pm.catat_habis_harian(model)
                urut = [m for m in pm.urutkan([model, "gemini-3.6-flash"])]
                self.assertIn("gemini-3.6-flash", urut)
                self.assertTrue(pm.habis_harian(model))
        finally:
            pm._simpan = asli
            with pm._kunci:
                pm._habis_harian.pop(model, None)


class SaldoVideoOpenRouter(unittest.TestCase):
    """
    OpenRouter menagih saldo untuk masukan VIDEO, bahkan pada model ":free".

    Terukur 24 September 2026 pada kunci yang jatah teksnya masih utuh:
    HTTP 402, "This request requires at least $1.00 in balance for video".
    Kode 402 sebelumnya selalu berarti "saldo kunci ini habis", jadi sutradara
    langsung menyerah dan kembali ke mesin lokal, padahal jalur gambar kunci +
    suara ada dan tidak menagih apa-apa.
    """

    MODEL = [{"id": "penonton:free", "nama": "a", "video": True, "gambar": True,
              "suara": True, "json": True, "gratis": True, "konteks": 200_000}]

    def _tanya(self, galat_pertama, *, cadangan=True):
        """Menjalankan `tanya` dengan `_panggil` palsu; mengembalikan catatannya."""
        catatan = []

        def palsu(m, bagian, **_):
            jenis = [b.get("jenis") for b in bagian] if isinstance(bagian, list) else []
            catatan.append(jenis)
            if len(catatan) == 1:
                raise galat_pertama
            return {"ok": True}, {"masuk": 1, "keluar": 1}

        asli_panggil, asli_bagian, asli_muat = (openrouter._panggil,
                                                openrouter._bagian, openrouter._muat)
        openrouter._panggil = palsu
        openrouter._bagian = lambda bahan, m: bahan
        openrouter._muat = lambda bahan: 1.0
        try:
            hasil = openrouter.tanya(
                [{"jenis": "video", "data": b"x"}], skema={}, sistem="s",
                api_key="k", models=list(self.MODEL),
                cadangan=(lambda: [{"jenis": "gambar", "data": b"y"}]) if cadangan else None)
            return hasil, catatan
        finally:
            (openrouter._panggil, openrouter._bagian,
             openrouter._muat) = asli_panggil, asli_bagian, asli_muat

    def _galat(self, pesan, kode):
        e = openrouter.Ditolak(pesan)
        e.kode = kode
        return e

    def test_402_video_dicoba_lagi_tanpa_video(self):
        galat = self._galat("HTTP 402: requires at least $1.00 in balance for video", 402)
        (data, model, _), catatan = self._tanya(galat)
        self.assertTrue(data["ok"])
        self.assertEqual(model, "openrouter:penonton:free")
        # Percobaan kedua memakai gambar, bukan video.
        self.assertEqual(catatan, [["video"], ["gambar"]])

    def test_402_saldo_biasa_tetap_menyerah(self):
        galat = self._galat("HTTP 402: insufficient credits", 402)
        with self.assertRaises(openrouter.Ditolak):
            self._tanya(galat)

    def test_402_video_tanpa_jalur_cadangan_tetap_menyerah(self):
        galat = self._galat("HTTP 402: requires at least $1.00 in balance for video", 402)
        with self.assertRaises(openrouter.Ditolak):
            self._tanya(galat, cadangan=False)


class JatahDisisakanUntukPemilihanKlip(unittest.TestCase):
    """
    Dua pekerjaan berebut jatah harian yang sama, dan keduanya tidak setara.

    Memilih klip menentukan seluruh isi video, dan mesin lokal tidak bisa
    menggantikannya: ia menemukan momen yang terukur keras dan berjeda tepat,
    tapi tidak bisa menilai apakah sesuatu lucu. Menyusun bingkai punya mesin
    lokal yang hasilnya masih masuk akal.

    Terukur 24 September 2026: 171 panggilan dalam sehari, tujuh model penuh
    habis sebelum tengah malam, dan video berikutnya dipilih mesin lokal.
    Yang menghabiskannya sutradara bingkai, satu panggilan per klip.
    """

    DASAR = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash"]

    def _rantai(self, sisa_per_model, **kw):
        with unittest.mock.patch.object(pm, "daftar_kunci", return_value=list(self.DASAR)), \
             unittest.mock.patch.object(pm, "tanpa_kuota", return_value=False), \
             unittest.mock.patch.object(pm, "habis_harian", return_value=False), \
             unittest.mock.patch.object(pm, "terakhir_berhasil", return_value=None), \
             unittest.mock.patch.object(pm, "sisa_model",
                                        side_effect=lambda m: sisa_per_model[m]):
            return pm.rantai("kunci-palsu", **kw)

    def test_tanpa_sisakan_semua_model_ikut(self):
        sisa = {"gemini-3.8-flash": 1, "gemini-3.6-flash": 0, "gemini-3.5-flash": 20}
        self.assertEqual(self._rantai(sisa), self.DASAR)

    def test_model_yang_jatahnya_menipis_dilewati(self):
        sisa = {"gemini-3.8-flash": 3, "gemini-3.6-flash": 6, "gemini-3.5-flash": 12}
        urut = self._rantai(sisa, sisakan=pm.CADANGAN_KLIP)
        # 3 dan 6 tidak lolos ambang 6; hanya yang sisa 12 yang boleh dipakai.
        self.assertEqual(urut, ["gemini-3.5-flash"])

    def test_semua_menipis_berarti_mengalah_bukan_memakai_sisanya(self):
        """
        Jaring "kalau kosong pakai saja semuanya" akan menghapus seluruh
        gunanya menyisakan jatah, jadi daftar kosong memang jawabannya.
        """
        sisa = {m: 2 for m in self.DASAR}
        self.assertEqual(self._rantai(sisa, sisakan=pm.CADANGAN_KLIP), [])

    def test_sisa_model_tidak_pernah_negatif(self):
        from app.services import pemakaian_ai
        with unittest.mock.patch.object(pemakaian_ai, "terpakai_hari_ini",
                                        return_value=99), \
             unittest.mock.patch.object(pemakaian_ai, "batas_model", return_value=20):
            self.assertEqual(pemakaian_ai.sisa_model("apa-saja"), 0)
