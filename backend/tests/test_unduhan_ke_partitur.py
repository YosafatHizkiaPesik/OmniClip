"""
Dari halaman Unduhan, satu tombol untuk memasukkan video ke Partitur.

Diminta pemiliknya 27 September 2026. Sebelumnya video yang berkasnya SUDAH ada
di komputer tetap harus dicari ulang lewat halaman Cari video, lalu dikenali di
sana sebagai "sudah terunduh" — jalan memutar untuk berkas yang sudah ada di
depan mata.
"""

import re
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
KARTU = AKAR / "frontend" / "src" / "components" / "DownloadsTab.jsx"
ROUTER = AKAR / "backend" / "app" / "routers" / "videos.py"


class DaftarUnduhanMembawaIdnya(unittest.TestCase):
    def test_id_diambil_dari_nama_berkas_bila_tak_ada_di_basis_data(self):
        """
        Unduhan lama, atau yang basis datanya hilang, tetap bisa diklip.

        Idnya ada di nama berkasnya; tanpa ini tombolnya tidak muncul untuk
        berkas yang sebenarnya sanggup diklip.
        """
        teks = ROUTER.read_text(encoding="utf-8")
        badan = teks.split("async def downloads")[1].split("\n@router")[0]
        self.assertIn("extract_id_from_filename", badan)
        self.assertIn('f.get("type") != "audio"', badan)

    def test_menyebut_apakah_proyeknya_sudah_ada(self):
        teks = ROUTER.read_text(encoding="utf-8")
        badan = teks.split("async def downloads")[1].split("\n@router")[0]
        self.assertIn('f["ada_partitur"]', badan)
        # Dibaca di utas terpisah: daftar ini dipanggil tiap kali halaman dibuka.
        self.assertIn("asyncio.to_thread(analyses_repo.latest_for_video", badan)


class KartuUnduhanPunyaTombolnya(unittest.TestCase):
    def setUp(self):
        self.teks = KARTU.read_text(encoding="utf-8")

    def test_dua_kalimat_untuk_dua_keadaan(self):
        self.assertIn("Masukkan ke Partitur", self.teks)
        self.assertIn("Buka di Partitur", self.teks)
        self.assertIn("item.ada_partitur", self.teks)

    def test_tidak_muncul_untuk_audio_atau_tanpa_id(self):
        self.assertIn("item.video_id && item.type !== 'audio'", self.teks)

    def test_memakai_jalur_auto_klip_yang_sama(self):
        """
        Jalur yang SAMA dengan Cari video dan Impor.

        Auto-klip sendiri yang tahu videonya sudah terunduh, jadi tidak ada
        jalur kedua yang bisa berbeda diam-diam — termasuk soal setelan model
        dan jumlah klip yang dipilih pengguna.
        """
        self.assertIn("apiPost('/auto-clip'", self.teks)
        for medan in ("max_clips", "whisper_model", "gemini_model"):
            with self.subTest(medan=medan):
                self.assertIn(medan, self.teks)

    def test_membuka_partitur_sesudahnya(self):
        self.assertIn("navigate('/studio')", self.teks)

    def test_tombolnya_terkunci_selama_dikirim(self):
        self.assertIn("disabled={mengirim === item.video_id}", self.teks)

    def test_kegagalan_ditampilkan_bukan_ditelan(self):
        badan = self.teks.split("const kePartitur")[1].split("\n  const ")[0]
        self.assertIn("setActionError(e.message)", badan)


if __name__ == "__main__":
    unittest.main()
