"""
JOB-2 F0-2: kredit video sumber di deskripsi unggahan.

Sampai 9 Oktober 2026 deskripsi bawaan hanya `{judul}\\n\\n{hashtag}`, tanpa
menyebut sumber sama sekali, padahal judul dan kanalnya tersimpan.
"""

import unittest
from pathlib import Path

from app.services import unggah

SUMBER = {"judul": "Aku Menjaga Warung Di Game Night Shift", "kanal": "MiawAug",
          "url": "https://www.youtube.com/watch?v=76s3N9SdzEE"}


class BarisKredit(unittest.TestCase):
    def test_bentuk_lengkap(self):
        self.assertEqual(
            unggah.kredit(SUMBER),
            'Sumber: "Aku Menjaga Warung Di Game Night Shift" oleh MiawAug\n'
            "https://www.youtube.com/watch?v=76s3N9SdzEE")

    def test_tanpa_kanal(self):
        k = unggah.kredit({**SUMBER, "kanal": ""})
        self.assertNotIn(" oleh ", k)
        self.assertIn("watch?v=76s3N9SdzEE", k)

    def test_sumber_tak_dikenal_kosong_bukan_karangan(self):
        self.assertEqual(unggah.kredit({}), "")
        self.assertEqual(unggah.kredit(None), "")


class Deskripsi(unittest.TestCase):
    def test_templat_baru_memuat_kredit_di_tengah(self):
        d = unggah.deskripsi("{judul}\n\n{sumber}\n\n{hashtag}", judul="Kasbon",
                             hashtag=["#game"], sumber=SUMBER)
        self.assertEqual(d.splitlines()[0], "Kasbon")
        self.assertIn("oleh MiawAug", d)
        self.assertTrue(d.endswith("#game"))

    def test_templat_lama_tetap_mendapat_kredit(self):
        """
        Setiap profil yang dibuat sebelum JOB-2 punya templat tanpa {sumber}.
        Tanpa penambahan di akhir, profil itu diam-diam tetap mengunggah tanpa
        kredit selamanya.
        """
        d = unggah.deskripsi("{judul}\n\n{hashtag}", judul="Kasbon",
                             hashtag=["#game"], sumber=SUMBER)
        self.assertIn("oleh MiawAug", d)
        self.assertTrue(d.rstrip().endswith("watch?v=76s3N9SdzEE"))

    def test_kredit_bisa_dimatikan(self):
        d = unggah.deskripsi("{judul}\n\n{sumber}\n\n{hashtag}", judul="Kasbon",
                             hashtag=["#game"], sumber=SUMBER, pakai_kredit=False)
        self.assertNotIn("Sumber:", d)
        self.assertNotIn("\n\n\n", d, "baris kosong beruntun tertinggal")

    def test_sumber_tak_dikenal_tidak_meninggalkan_baris_kosong(self):
        d = unggah.deskripsi("{judul}\n\n{sumber}\n\n{hashtag}", judul="Kasbon",
                             hashtag=["#game"], sumber={})
        self.assertEqual(d, "Kasbon\n\n#game")

    def test_bawaan_profil_memuat_sumber(self):
        from app.services.profil import UNGGAH_BAWAAN
        self.assertIn("{sumber}", UNGGAH_BAWAAN["deskripsi"])
        self.assertTrue(UNGGAH_BAWAAN["kredit"])


class DuaJalurSatuSumber(unittest.TestCase):
    """Unggah otomatis dan formulir manual harus memakai deskripsi yang sama."""

    def test_unggah_otomatis_membawa_sumber(self):
        src = Path(unggah.__file__).read_text(encoding="utf-8")
        self.assertIn("sumber=sumber_klip(clip_name, pid)", src)

    def test_formulir_manual_memakai_saran_server(self):
        src = Path("../frontend/src/components/UploadModal.jsx").read_text(encoding="utf-8")
        self.assertIn("/uploads/saran-deskripsi", src)

    def test_ketikan_orang_tidak_ditimpa_saran(self):
        """Saran yang datang terlambat tidak boleh menimpa yang sudah diketik."""
        src = Path("../frontend/src/components/UploadModal.jsx").read_text(encoding="utf-8")
        self.assertIn("disentuh.current ? lama : r.deskripsi", src)
