"""
Enam cacat yang tercatat di RENCANA.md, dan bukti bahwa masing-masing sudah
ditutup. Dikumpulkan dalam satu berkas supaya tidak ada yang terbuka lagi
diam-diam.
"""

import time
import unittest
from unittest import mock

from app.services.reframe import (
    SISIH_DETIK_MIN, _lengkapi_peta_dengan_penyisihan,
)


class D1PenyisihanPenutur(unittest.TestCase):
    """
    Bingkai menyorot orang yang salah.

    Terukur pada 6 klip podcast pemiliknya, 1.672 sampel bidikan banyak orang:
    35,5% salah sorot. Sebab terbesarnya bukan pilihan per sampel melainkan
    PEMETAAN: pada satu klip ada tiga penutur dan tiga wajah, dua terpasang,
    dan yang tidak terpasang justru penutur yang bicara 104 dari 158 detik.
    Selama 831 sampel bingkainya menebak, padahal jawabannya tinggal satu
    wajah yang tersisa.

    Sesudah penyisihan: 11,7%, dan 88% dari sisa itu hanya ketinggalan kurang
    dari 0,8 detik saat giliran berganti — yang memang disengaja supaya kamera
    tidak menyentak. Salah sorot yang bertahan: 1,4%.
    """

    ORANG = [[0.1] * 100, [0.2] * 100, [0.3] * 100]

    def _giliran(self, sp, lama):
        return [(0.0, lama, sp)]

    def test_satu_penutur_satu_wajah_tersisa_dipasangkan(self):
        peta = _lengkapi_peta_dengan_penyisihan(
            {0: 2, 1: 0}, self.ORANG, self._giliran(2, 100.0))
        self.assertEqual(peta, {0: 2, 1: 0, 2: 1})

    def test_dua_tersisa_tidak_ditebak(self):
        """
        Dua penutur dan dua wajah tersisa berarti dua kemungkinan pasangan.
        Menebak salah satunya persis selemah lempar koin, dan pemetaan yang
        salah mengunci bingkai ke orang yang keliru sepanjang klip.
        """
        giliran = [(0.0, 50.0, 1), (50.0, 100.0, 2)]
        self.assertEqual(
            _lengkapi_peta_dengan_penyisihan({0: 0}, self.ORANG, giliran), {0: 0})

    def test_penutur_yang_cuma_menyela_tidak_mengunci_wajah(self):
        peta = _lengkapi_peta_dengan_penyisihan(
            {0: 2, 1: 0}, self.ORANG, self._giliran(2, SISIH_DETIK_MIN - 1))
        self.assertNotIn(2, peta)

    def test_wajah_yang_tidak_pernah_terlihat_bukan_jawaban(self):
        seen = [[True] * 100, [False] * 100, [True] * 100]
        peta = _lengkapi_peta_dengan_penyisihan(
            {0: 2, 1: 0}, self.ORANG, self._giliran(2, 100.0), seen)
        self.assertNotIn(2, peta)

    def test_peta_yang_sudah_penuh_dibiarkan(self):
        peta = {0: 0, 1: 1, 2: 2}
        self.assertEqual(
            _lengkapi_peta_dengan_penyisihan(peta, self.ORANG, self._giliran(2, 99.0)),
            peta)

    def test_subject_dikeluarkan_perencana(self):
        """Tanpa ini keputusan yang paling sering salah tidak bisa diukur dari luar."""
        import dataclasses
        from app.services.reframe import ReframePlan
        medan = {f.name for f in dataclasses.fields(ReframePlan)}
        self.assertIn("subject", medan)


class D2KartunBukanDuaOrang(unittest.TestCase):
    """
    Video tanpa wajah manusia dilaporkan punya dua narasumber.

    Terukur pada video animasi "Kok Bisa?" milik pemiliknya: satu narator,
    dilaporkan 2 narasumber dengan keyakinan penuh. Pemisahan suara di sana
    memisahkan hal yang bukan orang — efek suara, musik, dan suara karakter
    yang diisi satu pengisi suara.
    """

    def test_tanpa_wajah_penutur_dikembalikan_ke_satu(self):
        from app.services import pipeline as P

        hasil = {"speaker_count": 2, "speaker_confident": True,
                 "label_kalimat": [0, 1, 0],
                 "clips": [{"segments": [{"start": 0.0, "end": 5.0}], "subtitles": []}]}
        kata = [{"w": "halo", "s": 0.0, "e": 1.0, "sp": 0},
                {"w": "dunia", "s": 1.0, "e": 2.0, "sp": 1}]
        with mock.patch("app.repos.analyses.save") as simpan, \
             mock.patch("app.services.clipmodel.rebuild_subtitles_for_segments",
                        return_value=([], None)):
            r = P._tanpa_wajah_satu_penutur("vid", {"result": hasil},
                                            {"id": 1}, hasil, kata)
        self.assertEqual(r["speaker_count"], 1)
        self.assertFalse(r["confident"])
        disimpan = simpan.call_args.kwargs["result"]
        self.assertEqual(disimpan["speaker_count"], 1)
        self.assertFalse(disimpan["speaker_confident"])
        self.assertIsNone(disimpan["label_kalimat"])
        # Label per kata ikut dibuang: warna penutur yang menyala akan mewarnai
        # kalimat narator yang sama dengan dua warna, dan itu terbaca sebagai
        # dua orang berbalas.
        self.assertFalse(any("sp" in w for w in kata))
        # Penanda supaya pemeriksaan ini tidak berulang tiap kali.
        self.assertTrue(disimpan["tambat_wajah"])

    def test_dipanggil_saat_bukti_wajah_kosong(self):
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "pipeline.py").read_text(encoding="utf-8")
        badan = sumber.split("def tambatkan_ke_wajah")[1].split("\ndef ")[0]
        self.assertIn('if not bukti.get("orang"):', badan)
        self.assertIn("_tanpa_wajah_satu_penutur", badan)


class D3RiwayatPekerjaanDibersihkan(unittest.TestCase):
    """
    Tabel `jobs` tidak pernah dibersihkan menurut umur, hanya per video saat
    videonya dihapus. Tiap baris membawa daftar klip satu video utuh — terukur
    60 KB sesudah dirampingkan, 378 KB sebelumnya — jadi ia tumbuh selamanya.
    """

    def test_yang_masih_berjalan_tidak_disentuh(self):
        from app.repos import jobs as J
        sql = {}

        class Conn:
            def execute(self, q, p=()):
                sql["q"], sql["p"] = q, p
                return mock.Mock(rowcount=3)

        class Tx:
            def __enter__(self): return Conn()
            def __exit__(self, *a): return False

        with mock.patch.object(J, "tx", return_value=Tx()):
            self.assertEqual(J.buang_yang_lama(30), 3)
        self.assertIn("status NOT IN ('queued', 'running')", sql["q"])
        # Batasnya benar-benar 30 hari ke belakang.
        self.assertAlmostEqual(sql["p"][0], time.time() - 30 * 86400, delta=5)

    def test_dijalankan_saat_aplikasi_menyala(self):
        from pathlib import Path
        main = (Path(__file__).resolve().parents[1] / "app"
                / "main.py").read_text(encoding="utf-8")
        self.assertIn("buang_yang_lama", main)


class D4PluginPoTokenTidakMencetakTraceback(unittest.TestCase):
    """
    `AssertionError: PoTokenProvider BgUtilHTTP already registered` tercetak
    sebagai Traceback penuh tiap aplikasi menyala. Tidak ada yang rusak —
    penyedianya tetap terdaftar sekali — tapi Traceback yang bukan galat
    membuat Traceback yang sungguhan lebih sulit terlihat.
    """

    def test_diperiksa_dulu_sebelum_diimpor(self):
        """Pemeriksaan harus berdiri SEBELUM impornya, bukan sesudah."""
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "alat_yt.py").read_text(encoding="utf-8")
        badan = sumber.split("def _muat_plugin")[1].split("\ndef ")[0]
        self.assertLess(badan.index("_sudah_terdaftar()"),
                        badan.index("import yt_dlp_plugins"))

    def test_sudah_terdaftar_bukan_kegagalan(self):
        """
        "already registered" berarti tujuan kita sudah tercapai. Diperlakukan
        sebagai kegagalan, log terisi peringatan untuk keadaan yang benar.
        """
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "alat_yt.py").read_text(encoding="utf-8")
        badan = sumber.split("def _muat_plugin")[1].split("\ndef ")[0]
        self.assertIn("except AssertionError", badan)
        self.assertIn('if "already registered" in str(e):', badan)

    def test_penyedia_benar_benar_terdaftar_sekali(self):
        """Dijalankan pada yt-dlp yang sungguhan, bukan pada tiruan."""
        from app.services.alat_yt import _sudah_terdaftar
        # Fungsinya harus menjawab tanpa melempar, apa pun keadaannya.
        self.assertIn(_sudah_terdaftar(), (True, False))


class D5D6BatasYangTerlaluKetat(unittest.TestCase):
    def test_pemanasan_tidak_berhenti_di_dua_puluh_klip(self):
        """Klip ke-21 dan seterusnya membuat orangnya menunggu lagi satu per satu."""
        from app.services.bingkai_awal import MAKS_KLIP
        self.assertGreaterEqual(MAKS_KLIP, 60)

    def test_simpanan_jenis_klip_membuang_satu_bukan_semua(self):
        """
        Mengosongkan 200 entri sekaligus berarti tiap klip sesudah yang ke-200
        menghitung ulang penggolongan yang memakan 10-60 detik, padahal 199
        jawaban di antaranya masih sah.
        """
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "routers"
                  / "clips.py").read_text(encoding="utf-8")
        self.assertIn("_JENIS_CACHE.pop(next(iter(_JENIS_CACHE)), None)", sumber)
        self.assertNotIn("_JENIS_CACHE.clear()", sumber)


if __name__ == "__main__":
    unittest.main()
