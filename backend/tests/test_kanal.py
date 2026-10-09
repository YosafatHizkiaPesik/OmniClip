"""
Seluruh video kanal, bukan hanya yang diunggah lewat OmniClip.

Dilaporkan pemiliknya 9 Oktober 2026: "disana tidak memuat seluruh video yang
kita upload dan juga tidak ada grafik views atau apapun". Pada kanalnya saat
itu: 4 video di kanal, 1 yang diunggah OmniClip. Tiga perempat datanya hilang
dari halaman yang seharusnya menjawab "video saya harus seperti apa".
"""

import unittest

from app.services import kanal


class DurasiISO(unittest.TestCase):
    """`PT2M39S` dari YouTube harus jadi detik, untuk membandingkan panjangnya."""

    def test_bentuk_yang_benar_benar_dikirim_youtube(self):
        for iso, detik in (("PT2M39S", 159), ("PT1M9S", 69), ("PT1M28S", 88),
                           ("PT1H2M3S", 3723), ("PT45S", 45), ("PT3M", 180)):
            self.assertEqual(kanal.durasi_detik(iso), detik, iso)

    def test_bentuk_yang_tidak_dikenal_tidak_meledak(self):
        for iso in ("", None, "ngawur", "2M39S"):
            self.assertIsNone(kanal.durasi_detik(iso))


class NomorKanalDariApaPun(unittest.TestCase):
    """
    Yang menempelkannya sedang menyalin dari bilah alamat peramban, bukan
    membaca dokumentasi API.
    """

    def test_nomor_langsung(self):
        self.assertEqual(kanal.id_dari_tautan("UCEVjOYBh6sLz7uuS4xBf-Xg"),
                         "UCEVjOYBh6sLz7uuS4xBf-Xg")

    def test_dari_tautan_kanal(self):
        self.assertEqual(
            kanal.id_dari_tautan("https://www.youtube.com/channel/UCEVjOYBh6sLz7uuS4xBf-Xg/videos"),
            "UCEVjOYBh6sLz7uuS4xBf-Xg")

    def test_yang_bukan_nomor_kanal(self):
        for t in ("", "@entertainyhp", "https://youtu.be/NmKNrnKY9s0", None):
            self.assertEqual(kanal.id_dari_tautan(t), "")


class TanpaKunciTidakMeledak(unittest.TestCase):
    def test_tanpa_kunci_api_jawabannya_jujur(self):
        asli = kanal._minta
        kanal._minta = lambda *a, **k: None
        try:
            self.assertEqual(kanal.kanal("UCxxxx"), {})
            self.assertEqual(kanal.video(["a", "b"]), [])
        finally:
            kanal._minta = asli


class CatatanHarian(unittest.TestCase):
    """
    YouTube Data API v3 hanya memberi angka SAAT INI. Riwayat sungguhan ada di
    Analytics API, yang menuntut izin baru dan persetujuan ulang tiap akun.
    Jadi OmniClip mencatatnya sendiri, sekali sehari.
    """

    def setUp(self):
        from app.db import run_migrations
        run_migrations()
        from app.repos import statistik_harian as sh
        self.sh = sh
        self.addCleanup(self._bersihkan)
        self.vid = ["uji-a", "uji-b"]

    def _bersihkan(self):
        from app.db import tx
        with tx() as c:
            c.execute("DELETE FROM statistik_harian WHERE video_id LIKE 'uji-%'")

    def test_dicatat_sekali_per_hari_dan_ditimpa(self):
        self.sh.catat([{"id": "uji-a", "tayangan": 10}], "2026-10-01")
        self.sh.catat([{"id": "uji-a", "tayangan": 14}], "2026-10-01")
        self.assertEqual(self.sh.deret(["uji-a"])["uji-a"][-1]["tayangan"], 14)

    def test_tambahan_harian_bukan_total(self):
        """
        Total kumulatif selalu naik, jadi grafiknya selalu terlihat bagus walau
        tidak ada yang menonton sejak minggu lalu.
        """
        self.sh.catat([{"id": "uji-a", "tayangan": 10}], "2026-10-01")
        self.sh.catat([{"id": "uji-a", "tayangan": 25}], "2026-10-02")
        self.sh.catat([{"id": "uji-a", "tayangan": 25}], "2026-10-03")
        d = self.sh.harian_kanal(["uji-a"])
        self.assertIsNone(d[0]["tambahan"], "hari pertama tidak punya pembanding")
        self.assertEqual(d[1]["tambahan"], 15)
        self.assertEqual(d[2]["tambahan"], 0, "nol tambahan harus terlihat nol")

    def test_hari_yang_tidak_tercatat_dilewati(self):
        """Aplikasi yang tidak dibuka dua hari bukan dua hari tanpa penonton."""
        self.sh.catat([{"id": "uji-a", "tayangan": 10}], "2026-10-01")
        self.sh.catat([{"id": "uji-a", "tayangan": 30}], "2026-10-05")
        d = self.sh.harian_kanal(["uji-a"])
        self.assertEqual([x["tanggal"] for x in d], ["2026-10-01", "2026-10-05"])

    def test_beberapa_video_dijumlahkan_per_hari(self):
        self.sh.catat([{"id": "uji-a", "tayangan": 10},
                       {"id": "uji-b", "tayangan": 5}], "2026-10-01")
        d = self.sh.harian_kanal(self.vid)
        self.assertEqual(d[0]["total"], 15)

    def test_tanpa_video_tidak_meledak(self):
        self.assertEqual(self.sh.deret([]), {})
        self.assertEqual(self.sh.harian_kanal([]), [])


class GrafikJujurSaatDataBelumAda(unittest.TestCase):
    """Satu titik bukan garis, dan menggambarnya sebagai garis datar berbohong."""

    def test_halaman_mengatakan_apa_adanya(self):
        from pathlib import Path
        src = Path("../frontend/src/components/GrafikHarian.jsx").read_text(encoding="utf-8")
        self.assertIn("Baru satu hari tercatat", src)
        self.assertIn("tambahan", src)
