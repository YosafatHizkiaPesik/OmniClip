"""
Judul bertema: tema lengkap (latar, huruf, gerak), judul yang menempel di
dalam video, dan gambar pratinjaunya.

Gambar pratinjau dan hasil render sama-sama dibuat dari `tema_judul.ass_judul`,
jadi yang diuji di sini terutama bahwa jalurnya tersambung: dari permintaan
render sampai baris ASS yang dibakar, dan dari panel Studio sampai payload.
"""

import asyncio
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.services import tema_judul
from app.services.render import _baris_judul_video
from app.services.subtitles import build_ass
from app.services.titlecard import TitleCardSpec, card_ass

AKAR = Path(__file__).resolve().parents[2]
STUDIO = AKAR / "frontend" / "src" / "features" / "studio"


class TemaMenghasilkanASS(unittest.TestCase):
    def test_setiap_tema_menghasilkan_baris_dialog(self):
        for tid in tema_judul.TEMA:
            with self.subTest(tema=tid):
                baris = tema_judul.ass_judul(
                    tid, "Pelajar Indonesia kalah jauh?", mulai=0.0, akhir=4.0,
                    pos_x=50, pos_y=20, box_w=84, ukuran=80, out_w=1080, out_h=1920)
                self.assertTrue(baris)
                for b in baris:
                    self.assertTrue(b.startswith("Dialogue: "), b[:40])
                    # Waktu mulai dan akhirnya sesuai permintaan.
                    self.assertIn("0:00:00.00,0:00:04.00", b)

    def test_tanpa_gerak_tidak_membawa_tag_gerak(self):
        baris = tema_judul.ass_judul(
            "kartu-putih", "Halo", mulai=0, akhir=3, pos_x=50, pos_y=50, box_w=84,
            ukuran=80, out_w=540, out_h=960, dengan_gerak=False)
        self.assertFalse(any(r"\fad" in b or r"\move" in b for b in baris))

    def test_kartu_bertema_memakai_jalur_tema(self):
        spec = TitleCardSpec(text="Judul uji", variant="berita")
        ass = card_ass(spec, 3.0, 1080, 1920)
        self.assertIn("Style: Default", ass)
        self.assertGreaterEqual(ass.count("Dialogue:"), 2)


class KartuSamaDenganPratinjau(unittest.TestCase):
    def test_latar_kartu_digelapkan_seperti_pratinjau(self):
        from app.services import titlecard as tc
        plan = tc.CardPlan(mode="freeze", seconds=3.0, text="Judul", ass_path=Path("k.ass"))
        graf = tc.video_filters(plan, "[v]", "kartu", "utama", 1080, 1920)
        self.assertIn(f"color=black@{tc.LATAR_REDUP}", graf)
        pratinjau = (STUDIO / "ClipPreview.jsx").read_text(encoding="utf-8")
        self.assertIn(f"rgba(0,0,0,{tc.LATAR_REDUP})", pratinjau)


class JudulDiDalamVideo(unittest.TestCase):
    def test_mati_atau_kosong_tidak_menambah_apa_pun(self):
        self.assertEqual(_baris_judul_video(None, 30, 1080, 1920), [])
        self.assertEqual(_baris_judul_video({"aktif": False, "teks": "x"}, 30, 1080, 1920), [])
        self.assertEqual(_baris_judul_video({"aktif": True, "teks": "  "}, 30, 1080, 1920), [])

    def test_sepanjang_klip_bila_durasi_kosong(self):
        baris = _baris_judul_video({"aktif": True, "teks": "Judul", "tema": "kaca-gelap",
                                    "durasi": None}, 42.5, 1080, 1920)
        self.assertTrue(baris)
        self.assertTrue(all("0:00:42.50" in b for b in baris))

    def test_durasi_dipotong_panjang_klip(self):
        baris = _baris_judul_video({"aktif": True, "teks": "Judul", "mulai": 2,
                                    "durasi": 5}, 30, 1080, 1920)
        self.assertTrue(all("0:00:02.00,0:00:07.00" in b for b in baris))
        pendek = _baris_judul_video({"aktif": True, "teks": "Judul", "durasi": 60}, 8, 1080, 1920)
        self.assertTrue(all(",0:00:08.00," in b for b in pendek))

    def test_build_ass_menyertakan_gaya_dan_barisnya(self):
        tambahan = _baris_judul_video({"aktif": True, "teks": "Judul"}, 10, 1080, 1920)
        ass = build_ass(lines=[], play_res=(1080, 1920), clip_duration=10, tambahan=tambahan)
        self.assertIn("Style: Default,", ass)
        for b in tambahan:
            self.assertIn(b, ass)
        # Tanpa judul, gaya itu tidak ikut.
        self.assertNotIn("Style: Default,", build_ass(lines=[], play_res=(1080, 1920), clip_duration=10))

    def test_permintaan_render_membawanya_ke_pekerjaan(self):
        teks = (AKAR / "backend" / "app" / "routers" / "clips.py").read_text(encoding="utf-8")
        self.assertIn("judul_video: Optional[JudulVideoModel] = None", teks)
        self.assertIn('"judul_video": (req.judul_video.model_dump()', teks)
        pipa = (AKAR / "backend" / "app" / "services" / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn('judul_video=ctx.payload.get("judul_video")', pipa)


class GambarPratinjau(unittest.TestCase):
    def setUp(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg tidak ada")

    def test_png_tembus_pandang_seukuran_kanvas(self):
        from app.routers import judul

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(judul, "_SIMPANAN", Path(d)):
            r = asyncio.run(judul.gambar(judul.GambarRequest(
                tema="merah-tebal", teks="Uji gambar", aspek="9:16")))
        self.assertEqual(r.media_type, "image/png")
        data = r.body
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        lebar = int.from_bytes(data[16:20], "big")
        tinggi = int.from_bytes(data[20:24], "big")
        self.assertEqual((lebar, tinggi), (540, 960))
        self.assertEqual(data[25], 6)        # jenis warna 6 = RGBA

    def test_tema_tak_dikenal_ditolak(self):
        from app.errors import AppError
        from app.routers import judul
        with self.assertRaises(AppError):
            asyncio.run(judul.gambar(judul.GambarRequest(tema="tidak-ada", teks="x")))


class FolderUnduhanLama(unittest.TestCase):
    """Video yang diunduh sebelum folder unduhan diganti tetap ditemukan."""

    def test_berkas_di_folder_bawaan_tetap_ditemukan(self):
        from app import config
        from app.services import paths
        with tempfile.TemporaryDirectory() as baru, tempfile.TemporaryDirectory() as lama:
            berkas = Path(lama) / "Judul_Video_qDyANZ4wQhU.mp4"
            berkas.write_bytes(b"x")
            with mock.patch.object(paths, "DOWNLOAD_DIR", Path(baru)), \
                    mock.patch.object(config, "DOWNLOAD_DIR_BAWAAN", Path(lama)):
                self.assertEqual(paths.find_local_video("qDyANZ4wQhU"), berkas)
                # Dilayani lewat jalur yang mencari ulang berkasnya, bukan lewat
                # folder media unduhan yang sekarang menunjuk ke folder baru.
                self.assertEqual(paths.url_sumber("qDyANZ4wQhU", berkas),
                                 "/api/impor/qDyANZ4wQhU/berkas")


class StudioTersambung(unittest.TestCase):
    def test_editor_mengirim_judul_video(self):
        editor = (STUDIO / "Editor.jsx").read_text(encoding="utf-8")
        self.assertRegex(editor, r"judul_video: clip\.judul_video\?\.aktif")
        self.assertIn("onJudulVideoChange={patchJudulVideo}", editor)

    def test_pratinjau_dan_panel_memakai_gambar_server(self):
        pratinjau = (STUDIO / "ClipPreview.jsx").read_text(encoding="utf-8")
        self.assertIn("<LapisJudul", pratinjau)
        panel = (STUDIO / "TitlePanel.jsx").read_text(encoding="utf-8")
        self.assertIn("Judul di dalam video", panel)
        self.assertIn("<GaleriTema", panel)
        lapis = (STUDIO / "JudulTema.jsx").read_text(encoding="utf-8")
        self.assertIn("/api/judul/gambar", lapis)

    def test_setiap_gerak_tema_punya_animasi_css(self):
        css = (AKAR / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
        for g in {t.gerak for t in tema_judul.TEMA.values()}:
            with self.subTest(gerak=g):
                self.assertRegex(css, rf"\.gerak-{re.escape(g)}\s*\{{")


if __name__ == "__main__":
    unittest.main()
