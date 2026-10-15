"""JOB-3: ikuti channel, riwayat tontonan, halaman channel (tanpa jaringan)."""

import unittest
from unittest import mock

from app.db import run_migrations
from app.repos import profil as profil_repo
from app.services import channel as ch

CID = "UCIPPMRA040LQr5QPyJEbmXA"


class Ikuti(unittest.TestCase):
    def setUp(self):
        run_migrations()
        self.pid = profil_repo.buat("uji-ikuti")

    def test_ikuti_dan_berhenti(self):
        ch.ikuti(self.pid, CID, "MrBeast Gaming", "https://x/a.jpg")
        ch.ikuti(self.pid, CID, "MrBeast Gaming", "")       # tidak dobel
        self.assertEqual(len(ch.diikuti(self.pid)), 1)
        ch.berhenti_ikuti(self.pid, CID)
        self.assertEqual(ch.diikuti(self.pid), [])

    def test_id_tidak_sah_ditolak(self):
        with self.assertRaises(ValueError):
            ch.ikuti(self.pid, "bukan-id")

    def test_riwayat_terbaru_di_depan_dan_tanpa_dobel(self):
        ch.catat_tonton(self.pid, {"id": "h8VE9_aHd94", "title": "a"})
        ch.catat_tonton(self.pid, {"id": "PyLGTmWz37U", "title": "b"})
        ch.catat_tonton(self.pid, {"id": "h8VE9_aHd94", "title": "a"})
        self.assertEqual([v["id"] for v in ch.riwayat(self.pid)], ["h8VE9_aHd94", "PyLGTmWz37U"])
        ch.hapus_riwayat(self.pid, "PyLGTmWz37U")
        self.assertEqual(len(ch.riwayat(self.pid)), 1)
        ch.hapus_riwayat(self.pid)
        self.assertEqual(ch.riwayat(self.pid), [])


class Halaman(unittest.TestCase):
    def setUp(self):
        run_migrations()

    def test_info_dan_urut_populer(self):
        info = {"channel_id": CID, "channel": "MrBeast Gaming", "uploader_id": "@MrBeastGaming",
                "channel_follower_count": 60600000, "description": "d",
                "thumbnails": [{"id": "avatar_uncropped", "url": "https://yt3/a"},
                               {"id": "banner_uncropped", "url": "https://yt3/b"}],
                "entries": [{"id": "aaaaaaaaaaa", "view_count": 5, "duration": 10},
                            {"id": "bbbbbbbbbbb", "view_count": 50, "duration": 10},
                            {"id": "pendek", "view_count": 9}]}
        with mock.patch.object(ch, "_ytdl_tab", return_value=info):
            h = ch.halaman("@MrBeastGaming-uji", "videos", "populer", 10)
        self.assertEqual(h["info"]["avatar"], "https://yt3/a")
        self.assertEqual(h["info"]["banner"], "https://yt3/b")
        self.assertEqual([v["id"] for v in h["video"]], ["bbbbbbbbbbb", "aaaaaaaaaaa"])

    def test_ref_aneh_ditolak(self):
        with self.assertRaises(ValueError):
            ch._ref_ke_url("../../etc", "videos")


if __name__ == "__main__":
    unittest.main()
