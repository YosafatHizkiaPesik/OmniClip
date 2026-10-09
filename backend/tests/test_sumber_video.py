"""
JOB-2 F0-1: identitas video sumber lengkap tersimpan.

Sampai 9 Oktober 2026 hanya NAMA kanal yang diteruskan dari yt-dlp, jadi
`videos.channel_id` selalu kosong padahal yt-dlp memberikannya. Kredit di
deskripsi unggahan (F0-2) dan catatan izin per kanal (F0-3) bergantung pada
identitas ini.
"""

import unittest
from pathlib import Path

from app.db import run_migrations
from app.repos import media


class Penyimpanan(unittest.TestCase):
    def setUp(self):
        run_migrations()
        self.addCleanup(self._bersihkan)

    def _bersihkan(self):
        from app.db import tx
        with tx() as c:
            c.execute("DELETE FROM videos WHERE id LIKE 'uji-%'")

    def info(self, **lain):
        dasar = {"id": "uji-sumber", "title": "Judul Asli", "channel": "KanalAsli",
                 "channel_id": "UCabcdefghijklmnopqrstuv",
                 "channel_url": "https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv",
                 "license": None, "duration": 100}
        dasar.update(lain)
        return dasar


class IdentitasLengkap(Penyimpanan):
    def test_nomor_kanal_tersimpan(self):
        media.upsert_video(self.info())
        s = media.sumber_video("uji-sumber")
        self.assertEqual(s["channel_id"], "UCabcdefghijklmnopqrstuv")
        self.assertEqual(s["kanal"], "KanalAsli")
        self.assertEqual(s["judul"], "Judul Asli")
        self.assertEqual(s["url"], "https://www.youtube.com/watch?v=uji-sumber")

    def test_nomor_kanal_tidak_ditimpa_kosong(self):
        """Pengambilan berikutnya yang tidak membawanya tidak boleh menghapusnya."""
        media.upsert_video(self.info())
        media.upsert_video(self.info(channel_id=None))
        self.assertEqual(media.sumber_video("uji-sumber")["channel_id"],
                         "UCabcdefghijklmnopqrstuv")

    def test_nomor_kanal_lama_terisi_saat_diambil_ulang(self):
        """Baris lama yang kosong terisi begitu video itu diambil lagi."""
        media.upsert_video(self.info(channel_id=None))
        self.assertEqual(media.sumber_video("uji-sumber")["channel_id"], "")
        media.upsert_video(self.info())
        self.assertEqual(media.sumber_video("uji-sumber")["channel_id"],
                         "UCabcdefghijklmnopqrstuv")

    def test_lisensi_tersimpan(self):
        media.upsert_video(self.info(license="Creative Commons Attribution license (reuse allowed)"))
        self.assertIn("Creative Commons", media.sumber_video("uji-sumber")["lisensi"])

    def test_video_tak_dikenal_kosong_bukan_karangan(self):
        s = media.sumber_video("uji-tidak-ada")
        self.assertEqual((s["judul"], s["kanal"], s["channel_id"]), ("", "", ""))
        # Alamat videonya tetap bisa dibentuk dari nomornya.
        self.assertEqual(s["url"], "https://www.youtube.com/watch?v=uji-tidak-ada")


class DiteruskanDariYtdlp(unittest.TestCase):
    """Dijaga di sumbernya: ketiga medan itu harus keluar dari `get_video_info`."""

    def test_medan_ada_di_keluaran(self):
        from app.services import ytdlp
        src = Path(ytdlp.__file__).read_text(encoding="utf-8")
        awal = src.index("def get_video_info(")
        badan = src[awal:awal + 3000]
        for medan in ('"channel_id"', '"channel_url"', '"license"'):
            self.assertIn(medan, badan, medan)

    def test_sidecar_klip_membawa_sumber(self):
        from app.services import render
        src = Path(render.__file__).read_text(encoding="utf-8")
        self.assertIn('"sumber": _sumber_klip(vid)', src)
