"""
Folder klip hanya lahir kalau ada yang menulis ke dalamnya.

Dilaporkan pemiliknya 9 Oktober 2026, dengan empat folder kosong bernama
"Akun baru (2)" sampai "(5)" di penyimpanannya: "hapus saja folder akun baru
dan jangan pernah lagi ada akun baru yang tidak jelas itu".

Sebabnya `folder_klip()` selalu `mkdir`, padahal pemanggil terbanyaknya cuma
ingin tahu jalurnya. Membuka daftar akun saja sudah melahirkan satu folder
untuk tiap profil, termasuk wadah "Akun baru" yang izinnya sedang ditunggu dan
sebentar lagi dibuang.
"""

import unittest
from pathlib import Path

from app.db import run_migrations
from app.repos import profil as repo
from app.services import profil as layanan


class FolderTidakLahirSendiri(unittest.TestCase):
    def setUp(self):
        run_migrations()
        self.dibuat = []
        self.addCleanup(self._bersihkan)

    def _bersihkan(self):
        for pid in self.dibuat:
            d = layanan.folder_klip(pid)
            try:
                repo.hapus(pid)
            except Exception:                        # noqa: BLE001
                pass
            try:
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass

    def akun(self, nama="Uji folder", sementara=False) -> int:
        pid = repo.buat(nama, sementara=sementara)
        self.dibuat.append(pid)
        return pid

    def test_menyebut_jalur_tidak_membuat_folder(self):
        pid = self.akun()
        d = layanan.folder_klip(pid)
        self.assertFalse(d.exists(), f"folder lahir tanpa diminta: {d}")

    def test_wadah_akun_baru_tidak_punya_folder(self):
        """Wadah yang izinnya gagal dibuang lagi; foldernya tidak boleh tersisa."""
        pid = self.akun("Akun baru", sementara=True)
        d = layanan.folder_klip(pid)
        self.assertFalse(d.exists())

    def test_buat_true_memang_membuatnya(self):
        pid = self.akun()
        d = layanan.folder_klip(pid, buat=True)
        self.assertTrue(d.is_dir())

    def test_hanya_render_yang_membuatnya(self):
        """
        Dijaga di sumbernya. Pemanggil yang hanya MENYEBUTKAN jalurnya tidak
        boleh memakai `buat=True`; kalau ia memakainya, folder kosong yang baru
        saja dibereskan akan lahir lagi dari halaman yang cuma menampilkannya.
        """
        menulis = {"app/services/render.py"}
        menyebut = {"app/routers/profil.py", "app/services/pemeliharaan.py",
                    "app/routers/clips.py", "app/services/paths.py"}
        for berkas in menulis | menyebut:
            baris = [b for b in Path(berkas).read_text(encoding="utf-8").splitlines()
                     if "folder_klip(" in b and "def folder_klip" not in b]
            self.assertTrue(baris, f"{berkas} tidak lagi memanggil folder_klip")
            for b in baris:
                if berkas in menulis:
                    self.assertIn("buat=True", b, f"{berkas}: {b.strip()}")
                else:
                    self.assertNotIn("buat=True", b, f"{berkas}: {b.strip()}")


class DaftarKlipTahanFolderHilang(unittest.TestCase):
    """Folder yang belum pernah ada bukan galat; ia cuma berarti belum ada klip."""

    def test_daftar_kosong_bukan_galat(self):
        from app.services.render import list_local_clips
        self.assertEqual(list_local_clips(Path("/tidak/ada/folder/ini")), [])
