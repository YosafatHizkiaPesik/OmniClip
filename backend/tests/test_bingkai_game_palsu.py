"""
Wajah palsu di dalam gambar permainan, dan panel yang mengaku besar.

Diukur pada video Dwiwoi 17 menit, 7 Oktober 2026, sesudah pemiliknya
melaporkan "auto bingkai yang digunakan hanya bingkai game saja padahal ada
momen wajahnya lebih dominan". Yang ditemukan justru kebalikannya di dalam
mesinnya: 136 detik klip (13% durasi) dibingkai sebagai SOROT WAJAH padahal
layarnya permainan biasa dengan facecam kecil di pojok.

Dua sumber kesalahan, keduanya terbukti dari datanya sendiri:

  1. Pemindai tepi melaporkan "panel" 48x95% bingkai — hampir separuh layar —
     dan `_tandai_panel_besar` memperlakukannya sebagai kamera yang dibesarkan.
     Wajah di dalam panel raksasa itu tetap 5% lebar, persis seperti sepanjang
     sisa klip: tanda bahwa panelnya salah baca, bukan dibesarkan.
  2. Pelacak wajah sesekali menangkap gambar pahlawan pada spanduk "Epic
     Outplay" dan potret papan skor sebagai wajah — 8-12% lebar, di tengah
     layar, berpindah-pindah tempat.
"""

import unittest

from app.services.sutradara_ai import (PANEL_BESAR_WAJAH_MIN, WAJAH_LUAR_PANEL_MIN,
                                       _di_dalam, _label_per_sampel,
                                       _tandai_panel_besar)


class Rencana:
    """Rencana wajah seadanya: cukup untuk menguji penggolongnya."""

    def __init__(self, orang, source_w=1920, source_h=1080):
        # orang: [[(x, cy, w) | None per sampel]]
        self.source_w, self.source_h = source_w, source_h
        self.people = [[t[0] if t else None for t in o] for o in orang]
        self.people_box = [[(t[1], t[2]) if t else None for t in o] for o in orang]
        self.people_seen = [[t is not None for t in o] for o in orang]


class PanelRaksasaDitolak(unittest.TestCase):
    def test_panel_besar_tanpa_wajah_besar_tetap_game(self):
        runs = [["game", 0.0, 60.0]]
        facecam = [{"t": 0.0, "facecam": {"x": 1, "y": 4, "w": 48, "h": 95}}]
        # Wajah 5% lebar sepanjang potongan: panelnya salah baca.
        lebar = [0.05] * int(60 * 8)
        keluar, _ = _tandai_panel_besar(runs, facecam, lebar)
        self.assertEqual([r[0] for r in keluar], ["game"])

    def test_panel_besar_dengan_wajah_besar_tetap_jadi_wajah(self):
        runs = [["game", 0.0, 60.0]]
        facecam = [{"t": 0.0, "facecam": {"x": 1, "y": 4, "w": 48, "h": 95}}]
        lebar = [0.20] * int(60 * 8)      # kamera benar-benar dibesarkan
        keluar, dari = _tandai_panel_besar(runs, facecam, lebar)
        self.assertEqual([r[0] for r in keluar], ["wajah"])
        self.assertTrue(dari)

    def test_tanpa_data_lebar_wajah_perilakunya_seperti_dulu(self):
        runs = [["game", 0.0, 60.0]]
        facecam = [{"t": 0.0, "facecam": {"x": 1, "y": 4, "w": 48, "h": 95}}]
        keluar, _ = _tandai_panel_besar(runs, facecam, None)
        self.assertEqual([r[0] for r in keluar], ["wajah"])


class WajahGambarDiabaikan(unittest.TestCase):
    PANEL = {"x": 8.0, "y": 72.0, "w": 16.0, "h": 25.0}

    def _panel(self, _t):
        return self.PANEL

    def test_wajah_kecil_di_tengah_permainan_bukan_bidikan_wajah(self):
        # Gambar pahlawan di tengah layar: 8% lebar, di luar panel.
        rencana = Rencana([[(1920 * 0.28, 1080 * 0.79, 1920 * 0.08)] * 8])
        label = _label_per_sampel(rencana, self._panel)
        self.assertEqual(set(label), {"game"})

    def test_wajah_besar_di_tengah_tetap_dipercaya(self):
        rencana = Rencana([[(1920 * 0.45, 1080 * 0.50, 1920 * 0.14)] * 8])
        label = _label_per_sampel(rencana, self._panel)
        self.assertEqual(set(label), {"wajah"})

    def test_wajah_di_dalam_panel_adalah_pemainnya(self):
        rencana = Rencana([[(1920 * 0.15, 1080 * 0.85, 1920 * 0.05)] * 8])
        self.assertEqual(set(_label_per_sampel(rencana, self._panel)), {"game"})

    def test_panel_ada_tapi_wajahnya_tidak_terbaca_tetap_game(self):
        rencana = Rencana([[None] * 8])
        self.assertEqual(set(_label_per_sampel(rencana, self._panel)), {"game"})

    def test_tanpa_panel_perilakunya_seperti_dulu(self):
        # Podcast: tidak ada panel, wajah di tengah tetap "wajah".
        rencana = Rencana([[(1920 * 0.45, 1080 * 0.50, 1920 * 0.08)] * 8])
        self.assertEqual(set(_label_per_sampel(rencana)), {"wajah"})

    def test_batas_di_dalam_panel(self):
        self.assertTrue(_di_dalam(1920 * 0.15, 1080 * 0.85, self.PANEL, 1920, 1080))
        self.assertFalse(_di_dalam(1920 * 0.60, 1080 * 0.30, self.PANEL, 1920, 1080))


if __name__ == "__main__":
    unittest.main()


class HapusKlipSabar(unittest.TestCase):
    """
    Menghapus klip jadi tidak boleh gagal hanya karena berkasnya sedang dibuka.

    Dilaporkan pemiliknya 7 Oktober 2026: "saya ingin menghapus klip jadi namun
    tidak bisa terhubung ke server". Di Windows, berkas yang sedang dibuka
    program lain TIDAK BISA dihapus sama sekali — dan yang membukanya hampir
    selalu aplikasi ini sendiri, lewat <video> pratinjau di tiap kartu.
    """

    def test_kuncian_sesaat_dicoba_lagi(self):
        from unittest import mock
        from app.routers.clips import _buang_berkas

        panggil = {"n": 0}

        class Jalur:
            def unlink(self, missing_ok=False):
                panggil["n"] += 1
                if panggil["n"] < 3:
                    raise PermissionError(32, "sedang dipakai")

            def with_suffix(self, _s):
                return self

        with mock.patch("time.sleep"):
            _buang_berkas(Jalur())
        self.assertGreaterEqual(panggil["n"], 3)

    def test_terkunci_terus_memberi_sebab_yang_bisa_dibaca(self):
        from unittest import mock
        from app.errors import AppError
        from app.routers.clips import _buang_berkas

        class Terkunci:
            def unlink(self, missing_ok=False):
                raise PermissionError(32, "sedang dipakai")

            def with_suffix(self, _s):
                return self

        with mock.patch("time.sleep"):
            with self.assertRaises(AppError) as galat:
                _buang_berkas(Terkunci())
        pesan = str(galat.exception)
        self.assertIn("dipakai program lain", pesan)
        self.assertIn("coba lagi", pesan)

    def test_berkas_yang_sudah_hilang_bukan_kegagalan(self):
        from pathlib import Path
        import tempfile
        from app.routers.clips import _buang_berkas

        with tempfile.TemporaryDirectory() as d:
            _buang_berkas(Path(d) / "tidak-ada.mp4")   # tidak melempar


class KemajuanNyata(unittest.TestCase):
    """
    Bilah kemajuan melaporkan hitungan, bukan perkiraan.

    Sampai 7 Oktober 2026 bilah di Studio memakai rumus `6 + 0,36 x panjang
    klip` yang diukur pada klip pendek. Sesudah pemindaian klip panjang
    dipercepat delapan kali, rumus itu menyebut EMPAT MENIT untuk pekerjaan
    empat puluh detik. Diminta pemiliknya: "agar tidak menampilkan perkiraan
    dan menampilkan exact perhitungan waktu yang nyata dan jelas".
    """

    def test_laporan_membawa_langkah_keberapa_dari_berapa(self):
        from app.services.reframe import kemajuan_pindai, lapor_kemajuan

        lapor_kemajuan("kamera wajah", 7, 40)
        k = kemajuan_pindai()
        self.assertEqual(k["tahap"], "kamera wajah")
        self.assertEqual((k["selesai"], k["total"]), (7.0, 40.0))

    def test_laporan_basi_ditandai_tidak_segar(self):
        import time as _t
        from app.services import reframe

        reframe.lapor_kemajuan("melacak wajah", 100, 1000)
        reframe._KEMAJUAN["pada"] = _t.time() - 30
        k = reframe.kemajuan_pindai()
        self.assertGreater(_t.time() - k["pada"], 5)

    def test_pemindai_memanggil_pelapor(self):
        # Dua tempat yang memindai harus melaporkan kemajuannya; tanpa itu
        # bilahnya diam-diam kembali jadi perkiraan.
        from pathlib import Path
        sumber = Path(__import__("app.services.reframe", fromlist=["x"]).__file__)
        teks = sumber.read_text(encoding="utf-8")
        self.assertIn('lapor_kemajuan("kamera wajah"', teks)
        self.assertIn('lapor_kemajuan("melacak wajah"', teks)
