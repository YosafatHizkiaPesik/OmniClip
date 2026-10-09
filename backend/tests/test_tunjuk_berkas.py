"""
Menunjuk berkas klip di pengelola berkas, dan menaruhnya di papan klip.

Dilaporkan pemiliknya 9 Oktober 2026: "saat mengklik klip yang jadi disana
hanya ada simpan berkas bukan membuka folder dan menunjuk video itu dimana,
karena sering saat upload saya harus cari foldernya dahulu, jika tidak maka
saya mendownload ulang hasil klip dan upload".

Mengunduh ulang berkas yang sudah ada di cakram bukan cuma lambat: ia
melahirkan salinan kedua dengan nama berbeda, dan dari situlah video tertukar
saat diunggah. Itu kerugian yang jauh lebih besar daripada waktunya.
"""

import unittest
from pathlib import Path


class JalurDijaga(unittest.TestCase):
    """
    Endpoint ini menjalankan perintah sistem dengan jalur dari permintaan HTTP.
    Jadi jalurnya harus lewat `safe_media_path`, bukan disusun sendiri.
    """

    def _sumber(self) -> str:
        import app.routers.media as m
        return Path(m.__file__).read_text(encoding="utf-8")

    def test_keduanya_memakai_safe_media_path(self):
        src = self._sumber()
        for fungsi in ("tunjuk_berkas", "salin_berkas_ke_papan"):
            awal = src.index(f"async def {fungsi}(")
            badan = src[awal:awal + 2000]
            self.assertIn("safe_media_path(req.kategori, req.nama)", badan, fungsi)

    def test_berkas_yang_tidak_ada_ditolak(self):
        src = self._sumber()
        self.assertEqual(src.count('raise NotFound("Berkas tidak ada lagi di folder itu.")'), 2)

    def test_windows_memakai_satu_argumen(self):
        """
        explorer menuntut /select,"jalur" sebagai SATU argumen. Dipecah jadi
        daftar, ia membuka Documents alih-alih menyorot apa pun.
        """
        src = self._sumber()
        self.assertIn('subprocess.Popen(f\'explorer /select,"{jalur}"\'', src)

    def test_linux_punya_jalan_mundur(self):
        """Pengelola berkas yang tidak bicara D-Bus tetap dilayani."""
        src = self._sumber()
        awal = src.index("async def tunjuk_berkas(")
        badan = src[awal:awal + 2500]
        self.assertIn("FileManager1.ShowItems", badan)
        self.assertIn("xdg-open", badan)

    def test_papan_klip_yang_tidak_ada_dilaporkan_jujur(self):
        """
        Di Linux tanpa wl-copy maupun xclip, yang benar adalah mengatakannya,
        bukan diam lalu membiarkan Ctrl+V menempel sesuatu yang lain.
        """
        src = self._sumber()
        self.assertIn("CLIPBOARD_MISSING", src)
        self.assertIn("pakai tombol tunjuk di folder", src)


class TersediaDiLayar(unittest.TestCase):
    """Dua tempat menyebutnya, dan keduanya tempat orang mencarinya."""

    def test_tombol_di_daftar_klip_jadi(self):
        src = Path("../frontend/src/components/ClipsTab.jsx").read_text(encoding="utf-8")
        self.assertIn("tunjukBerkas", src)
        self.assertIn("/berkas/tunjuk", src)

    def test_tombol_di_panel_siapkan_terbit(self):
        src = Path("../frontend/src/components/SiapkanTerbit.jsx").read_text(encoding="utf-8")
        self.assertIn("Tunjuk berkasnya", src)
        self.assertIn("Salin berkasnya", src)

    def test_disembunyikan_saat_diakses_dari_komputer_lain(self):
        """
        Membuka pengelola berkas di komputer SERVER tidak menolong siapa pun
        yang sedang membuka OmniClip dari ponsel.
        """
        for berkas in ("ClipsTab.jsx", "SiapkanTerbit.jsx"):
            src = Path(f"../frontend/src/components/{berkas}").read_text(encoding="utf-8")
            self.assertIn("dijalankanDiKomputerIni", src, berkas)
