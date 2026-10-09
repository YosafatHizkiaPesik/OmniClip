"""
Mesin pendeteksi sampah: apa yang boleh dibuang, dan apa yang tidak pernah.

Diminta pemiliknya 9 Oktober 2026: "buat saja mesin yang mendeteksi sampah dan
dapat membersihkannya seperti sampah file yang gagal terunduh atau corupt".

Yang dijaga kelas-kelas di sini bukan "apakah ia menemukan sampah", melainkan
"apakah ia pernah menyentuh yang bukan sampah". Satu kesalahan ke arah itu
berarti pekerjaan berbulan-bulan hilang, dan tidak ada tombol urungnya.
"""

import os
import unittest
from pathlib import Path


class Penyimpanan(unittest.TestCase):
    """Penyimpanan uji sendiri, supaya tidak ada berkas sungguhan yang kena."""

    def setUp(self):
        import tempfile
        from app.services import sampah as S
        self.S = S
        self.akar = Path(tempfile.mkdtemp(prefix="uji-sampah-"))
        self.addCleanup(self._bersihkan)
        for n in ("unduhan", "klip", "proksi", "suara", "sampul", "impor"):
            (self.akar / n).mkdir(parents=True, exist_ok=True)
        self.asli = S._folder
        S._folder = lambda: {n: self.akar / n for n in
                             ("unduhan", "klip", "proksi", "suara", "sampul", "impor")}
        self.asli_dalam = S._di_dalam_penyimpanan
        S._di_dalam_penyimpanan = lambda p: str(Path(p).resolve()).startswith(
            str(self.akar.resolve()))
        self.asli_panggung = S._panggung_pembaruan
        S._panggung_pembaruan = lambda: []
        self.asli_folder_kosong = S._folder_kosong
        S._folder_kosong = lambda folder: []

    def _bersihkan(self):
        import shutil
        self.S._folder = self.asli
        self.S._di_dalam_penyimpanan = self.asli_dalam
        self.S._panggung_pembaruan = self.asli_panggung
        self.S._folder_kosong = self.asli_folder_kosong
        shutil.rmtree(self.akar, ignore_errors=True)

    def tulis(self, rel, isi=b"x", umur_detik=0):
        p = self.akar / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(isi)
        if umur_detik:
            lampau = __import__("time").time() - umur_detik
            os.utime(p, (lampau, lampau))
        return p

    def jalur(self, hasil):
        return {b["jalur"] for k in hasil["kelompok"] for b in k["berkas"]}


class YangBukanSampahTidakPernahDisentuh(Penyimpanan):
    """Daftar ini yang paling penting di seluruh berkas uji."""

    def test_video_sumber_tidak_pernah_masuk(self):
        """59 GB video sumber: berharga, dan mengunduhnya lagi makan berjam-jam."""
        p = self.tulis("unduhan/video-besar.mp4", b"x" * 1000, umur_detik=90 * 86400)
        self.assertNotIn(str(p), self.jalur(self.S.pindai()))

    def test_klip_jadi_tidak_pernah_masuk(self):
        p = self.tulis("klip/hasil.mp4", b"x" * 1000, umur_detik=90 * 86400)
        self.assertNotIn(str(p), self.jalur(self.S.pindai()))

    def test_sidecar_yang_videonya_ada_tidak_masuk(self):
        self.tulis("klip/hasil.mp4", b"x" * 100)
        j = self.tulis("klip/hasil.json", b"{}")
        s = self.tulis("klip/hasil.srt", b"1")
        ada = self.jalur(self.S.pindai())
        self.assertNotIn(str(j), ada)
        self.assertNotIn(str(s), ada)

    def test_salinan_pratinjau_yang_sehat_tidak_masuk(self):
        """Salinan yang SELESAI adalah hasil kerja berpuluh menit."""
        self.tulis("proksi/abc.mp4", b"x" * 1000, umur_detik=30 * 86400)
        sumber = self.tulis("unduhan/asli.mp4", b"x" * 10)
        self.tulis("proksi/abc.sumber", str(sumber).encode())
        self.assertEqual(self.jalur(self.S.pindai()), set())

    def test_penyalinan_yang_sedang_berjalan_tidak_disentuh(self):
        """Berkas yang baru saja ditulis berarti ada yang sedang menulisnya."""
        p = self.tulis("proksi/xyz.tmp.mp4", b"x" * 1000)
        k = self.tulis("proksi/xyz.tmp.kemajuan", b"out_time=1")
        ada = self.jalur(self.S.pindai())
        self.assertNotIn(str(p), ada)
        self.assertNotIn(str(k), ada)

    def test_unduhan_yang_sedang_berjalan_tidak_disentuh(self):
        p = self.tulis("unduhan/sedang.mp4.part", b"x" * 500)
        self.assertNotIn(str(p), self.jalur(self.S.pindai()))


class SampahDikenali(Penyimpanan):
    def test_penyalinan_terputus(self):
        p = self.tulis("proksi/mati.tmp.mp4", b"x" * 900, umur_detik=7200)
        k = self.tulis("proksi/mati.tmp.kemajuan", b"out_time=1", umur_detik=7200)
        ada = self.jalur(self.S.pindai())
        self.assertIn(str(p), ada)
        self.assertIn(str(k), ada)

    def test_pecahan_unduhan_terputus(self):
        p = self.tulis("unduhan/putus.mp4.part", b"x" * 900, umur_detik=7200)
        q = self.tulis("unduhan/putus.mp4.ytdl", b"{}", umur_detik=7200)
        ada = self.jalur(self.S.pindai())
        self.assertIn(str(p), ada)
        self.assertIn(str(q), ada)

    def test_berkas_media_kosong(self):
        p = self.tulis("klip/kosong.mp4", b"", umur_detik=600)
        self.assertIn(str(p), self.jalur(self.S.pindai()))

    def test_berkas_kosong_yang_baru_dibuat_diberi_tenggang(self):
        """Berkas yang baru dibuat memang nol byte sesaat."""
        p = self.tulis("klip/baru.mp4", b"")
        self.assertNotIn(str(p), self.jalur(self.S.pindai()))

    def test_sidecar_tanpa_videonya(self):
        p = self.tulis("klip/hilang.json", b"{}")
        self.assertIn(str(p), self.jalur(self.S.pindai()))

    def test_turunan_dari_video_yang_sudah_dihapus(self):
        self.tulis("proksi/yatim.mp4", b"x" * 500)
        self.tulis("proksi/yatim.sumber", b"/tidak/ada/video.mp4")
        ada = self.jalur(self.S.pindai())
        self.assertIn(str(self.akar / "proksi" / "yatim.mp4"), ada)

    def test_saat_mulai_memakai_ambang_yang_jauh_lebih_pendek(self):
        """Saat aplikasi menyala, tidak ada pekerjaannya sendiri yang menulis."""
        p = self.tulis("proksi/baru-mati.tmp.mp4", b"x" * 900, umur_detik=300)
        self.assertNotIn(str(p), self.jalur(self.S.pindai()))
        self.assertIn(str(p), self.jalur(self.S.pindai(saat_mulai=True)))


class MembuangDijaga(Penyimpanan):
    def test_hanya_yang_dinilai_sampah_yang_bisa_dibuang(self):
        """
        Permintaan HTTP tidak boleh menghapus berkas apa pun yang kebetulan ada
        di folder itu, hanya yang sudah dinilai sampah oleh aturannya sendiri.
        """
        berharga = self.tulis("klip/penting.mp4", b"x" * 1000)
        self.S.bersihkan([str(berharga)])
        self.assertTrue(berharga.is_file(), "berkas berharga ikut terhapus")

    def test_jalur_di_luar_penyimpanan_ditolak(self):
        import tempfile
        luar = Path(tempfile.mkdtemp(prefix="di-luar-")) / "jangan.txt"
        luar.write_text("milik orang lain")
        self.addCleanup(lambda: __import__("shutil").rmtree(luar.parent,
                                                            ignore_errors=True))
        self.S.bersihkan([str(luar)])
        self.assertTrue(luar.is_file())

    def test_membuang_tanpa_daftar_membuang_semua_temuan(self):
        p = self.tulis("unduhan/putus.mp4.part", b"x" * 900, umur_detik=7200)
        aman = self.tulis("unduhan/asli.mp4", b"x" * 900, umur_detik=7200)
        hasil = self.S.bersihkan()
        self.assertEqual(hasil["dibuang"], 1)
        self.assertFalse(p.exists())
        self.assertTrue(aman.is_file())

    def test_sapuan_awal_hanya_kelompok_yang_tidak_mungkin_keliru(self):
        from pathlib import Path as P
        src = P(self.S.__file__).read_text(encoding="utf-8")
        awal = src.index("def bersihkan_di_latar(")
        badan = src[awal:]
        for k in ("salinan_terbengkalai", "pecahan_unduhan", "panggung_pembaruan"):
            self.assertIn(k, badan)
        for k in ("berkas_kosong", "sidecar_yatim", "turunan_yatim", "folder_kosong"):
            self.assertNotIn(f'"{k}"', badan.split("aman = ")[1][:200], k)


class PeriksaIsiDipisah(unittest.TestCase):
    """
    Membuka tiap berkas dengan ffprobe memakan menit-menit CPU, dan pemiliknya
    sudah pernah melaporkan laptopnya tidak bisa dipakai gara-gara pekerjaan
    latar. Jadi ia tidak pernah ikut pemindaian biasa.
    """

    def test_tidak_ikut_pindai(self):
        from app.services import sampah as S
        src = Path(S.__file__).read_text(encoding="utf-8")
        awal = src.index("def pindai(")
        akhir = src.index("def periksa_rusak(")
        self.assertNotIn("ffprobe", src[awal:akhir])

    def test_tidak_ikut_sapuan_awal(self):
        from app.services import sampah as S
        src = Path(S.__file__).read_text(encoding="utf-8")
        badan = src[src.index("def bersihkan_di_latar("):]
        self.assertNotIn("periksa_rusak", badan)
