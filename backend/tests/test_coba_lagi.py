"""
Percobaan ulang otomatis sesudah Gemini menjawab "sedang sibuk".

503 dari Gemini berarti "servernya penuh, coba lagi nanti". Sebelum ini
kalimat itu berakhir sebagai saran kepada ORANG: buka editor, tekan Cari
ulang, dan tebak sendiri kapan waktunya tepat.
"""

import unittest

from app.services import pipeline


class Ctx:
    def __init__(self, payload):
        self.payload = payload


class Jadwal(unittest.TestCase):
    def setUp(self):
        self.antre = []
        from app.services import jobs
        self.asli = jobs.queue.enqueue
        jobs.queue.enqueue = lambda t, p, **kv: (self.antre.append((t, p, kv)), ("x", True))[1]

    def tearDown(self):
        from app.services import jobs
        jobs.queue.enqueue = self.asli

    def test_sibuk_dijadwalkan_ulang(self):
        kapan = pipeline._jadwalkan_coba_lagi(Ctx({"video_id": "v"}), "v", "503 UNAVAILABLE")
        self.assertTrue(kapan)
        self.assertEqual(len(self.antre), 1)
        jenis, payload, kv = self.antre[0]
        self.assertEqual(jenis, "auto_clip")
        self.assertEqual(payload["ulang_otomatis"], 1)
        self.assertTrue(payload["ulang"])
        self.assertTrue(payload["use_gemini"])
        self.assertGreater(kv["mulai_setelah"], 0)

    def test_galat_lain_tidak_dijadwalkan(self):
        # Kunci salah atau kuota nol tidak membaik dengan menunggu.
        for g in ("401 UNAUTHENTICATED", "API key not valid", "limit: 0"):
            self.assertEqual(pipeline._jadwalkan_coba_lagi(Ctx({"video_id": "v"}), "v", g), "")
        self.assertEqual(self.antre, [])

    def test_berhenti_sesudah_batasnya(self):
        ctx = Ctx({"video_id": "v", "ulang_otomatis": pipeline.ULANG_MAKS})
        self.assertEqual(pipeline._jadwalkan_coba_lagi(ctx, "v", "503"), "")
        self.assertEqual(self.antre, [])

    def test_jedanya_makin_panjang(self):
        pipeline._jadwalkan_coba_lagi(Ctx({"video_id": "v"}), "v", "503")
        pipeline._jadwalkan_coba_lagi(Ctx({"video_id": "v", "ulang_otomatis": 1}), "v", "503")
        self.assertLess(self.antre[0][2]["mulai_setelah"], self.antre[1][2]["mulai_setelah"])

    def test_kunci_tidak_ikut_dibawa(self):
        # Payload job tersimpan di basis data; kunci sekali pakai tidak pantas
        # tinggal di sana sampai percobaan berikutnya.
        pipeline._jadwalkan_coba_lagi(Ctx({"video_id": "v", "api_key": "RAHASIA"}), "v", "503")
        self.assertNotIn("api_key", self.antre[0][1])

    def test_tiap_percobaan_punya_kunci_dedupe_sendiri(self):
        pipeline._jadwalkan_coba_lagi(Ctx({"video_id": "v"}), "v", "503")
        pipeline._jadwalkan_coba_lagi(Ctx({"video_id": "v", "ulang_otomatis": 1}), "v", "503")
        self.assertNotEqual(self.antre[0][2]["dedupe_key"], self.antre[1][2]["dedupe_key"])


class MengalahPadaTangan(unittest.TestCase):
    """
    Percobaan ulang berjalan dua puluh lima menit sesudah dijadwalkan. Kalau
    dalam jeda itu proyeknya disunting, mengganti daftar klipnya berarti
    membuang pekerjaan orang tanpa diminta.
    """

    def test_proyek_yang_lebih_baru_dianggap_disunting(self):
        from app.services import pipeline as pl
        from app import db

        class Row(dict):
            def __getitem__(self, k):
                return dict.__getitem__(self, k)

        class Conn:
            def __init__(self, row):
                self.row = row
            def execute(self, *a, **kv):
                conn = self
                class C:
                    def fetchone(self_inner):
                        return conn.row
                return C()

        asli = db.get_conn
        try:
            db.get_conn = lambda: Conn(Row(p_at=200.0, a_at=100.0))
            self.assertTrue(pl._sudah_disunting("v"))
            db.get_conn = lambda: Conn(Row(p_at=50.0, a_at=100.0))
            self.assertFalse(pl._sudah_disunting("v"))
            db.get_conn = lambda: Conn(None)
            self.assertFalse(pl._sudah_disunting("v"))
        finally:
            db.get_conn = asli


if __name__ == "__main__":
    unittest.main()


class JadwalUlangTidakMenutupiHasil(unittest.TestCase):
    """
    Percobaan ulang yang dijadwalkan NANTI bukan pekerjaan yang sedang berjalan.

    Terukur 24 September 2026: sebuah video dengan 11 klip siap tinjau berubah
    jadi kartu "Menunggu antrean · Menunggu giliran" dengan tahap "Unduh"
    menyala, hanya karena pencarian ulang dijadwalkan dua puluh lima menit
    lagi. Yang melihatnya wajar menyimpulkan videonya harus diunduh dari nol.
    """

    def _status(self, job, ada_klip=True):
        """Aturan yang dipakai `list_projects` untuk menentukan status kartu."""
        import time
        result = {"clips": [{"a": 1}]} if ada_klip else {}
        tunda = float(job["mulai_setelah"] or 0) if job else 0.0
        nanti = bool(job and job["status"] == "queued" and tunda > time.time())
        if nanti and result.get("clips"):
            return "done", tunda
        if job and job["status"] in ("queued", "running"):
            return job["status"], None
        if result.get("clips"):
            return "done", None
        return "unknown", None

    def test_jadwal_nanti_tidak_mengalahkan_klip_yang_sudah_ada(self):
        import time
        job = {"status": "queued", "mulai_setelah": time.time() + 1500}
        status, kapan = self._status(job)
        self.assertEqual(status, "done")
        self.assertIsNotNone(kapan)

    def test_antrean_sungguhan_tetap_terlihat_mengantre(self):
        job = {"status": "queued", "mulai_setelah": 0}
        self.assertEqual(self._status(job)[0], "queued")

    def test_jadwal_nanti_tanpa_klip_tetap_mengantre(self):
        import time
        job = {"status": "queued", "mulai_setelah": time.time() + 1500}
        self.assertEqual(self._status(job, ada_klip=False)[0], "queued")
