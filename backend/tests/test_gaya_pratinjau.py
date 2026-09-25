"""
Gaya sebaris pratinjau subtitle.

Uji ini membaca berkas JSX, bukan menjalankannya, karena proyek ini tidak punya
penjalan uji JavaScript. Itu kasar, tapi cacat yang dijaganya nyata dan sudah
dua kali lolos ke layar pemiliknya: jarak antar kata hilang pada mode kotak,
sehingga "BANYAK ORANG" terbaca "BANYAKORANG".

Sebabnya bukan angka jaraknya. `gayaKata` mengembalikan properti RINGKAS
`margin`, sementara pemanggilnya memasang properti TUNGGAL `marginRight` untuk
jarak antar kata. React menerapkan gaya sebaris properti demi properti, dan
begitu keduanya ada di satu objek, urutan penerapannya berubah saat gaya
diperbarui: yang ringkas menghapus jarak yang baru saja dipasang. Karena itu
cacatnya hanya muncul pada mode kotak, dan hanya saat sorotan berpindah.
"""

import re
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
BERKAS = AKAR / "frontend" / "src" / "features" / "studio" / "ClipPreview.jsx"

# Properti ringkas yang bertabrakan dengan properti tunggal yang dipasang
# pemanggil `gayaKata`.
RINGKAS = ("margin", "padding-right", "paddingRight")


def _badan_gayakata() -> str:
    teks = BERKAS.read_text(encoding="utf-8")
    mulai = teks.index("export function gayaKata")
    # Sampai deklarasi tingkat atas berikutnya.
    sisa = teks[mulai:]
    akhir = sisa.index("\n}\n") + 3
    return sisa[:akhir]


def _tanpa_komentar(js: str) -> str:
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(b for b in js.splitlines() if not b.strip().startswith("//"))


class GayaKata(unittest.TestCase):
    def setUp(self):
        self.badan = _tanpa_komentar(_badan_gayakata())

    def test_tidak_memakai_properti_margin_ringkas(self):
        self.assertNotRegex(
            self.badan, r"\bmargin\s*:",
            "gayaKata tidak boleh memakai `margin` ringkas: ia menghapus "
            "marginRight milik pemanggilnya saat gaya diperbarui.")

    def test_tidak_menyentuh_margin_sama_sekali(self):
        # Jarak antar kata milik pemanggil, satu-satunya pemiliknya.
        for nama in ("marginRight", "marginLeft", "marginInline"):
            self.assertNotIn(nama, self.badan, f"gayaKata tidak boleh memasang {nama}")

    def test_mode_kotak_masih_punya_latar_dan_empuk(self):
        # Perbaikannya tidak boleh menghapus kotaknya sendiri.
        self.assertIn("background: warna.kotak", self.badan)
        self.assertIn("padding:", self.badan)


class JarakKata(unittest.TestCase):
    def test_angka_pratinjau_sama_dengan_render(self):
        from app.services.subtitles import JARAK_KATA

        teks = BERKAS.read_text(encoding="utf-8")
        m = re.search(r"export const JARAK_KATA = ([\d.]+);", teks)
        self.assertIsNotNone(m, "JARAK_KATA tidak ditemukan di ClipPreview.jsx")
        self.assertAlmostEqual(float(m.group(1)), JARAK_KATA, places=3,
                               msg="pratinjau dan hasil render harus sepakat")

    def test_dipasang_sebagai_margin_kanan_per_kata(self):
        teks = BERKAS.read_text(encoding="utf-8")
        # Keduanya boleh terpisah baris; yang dijaga adalah jarak itu memang
        # dipasang sebagai margin kanan, bukan sebagai spasi di dalam teks.
        self.assertRegex(teks, r"(?s)marginRight:.{0,200}?jarakKata\(")

    def test_batasnya_sama_dengan_render(self):
        """
        Angka bawaannya boleh disetel pengguna sekarang, jadi yang harus
        sepakat bukan cuma bawaannya melainkan juga batas atas dan bawahnya:
        penggeser yang boleh melewati batas render akan menampilkan pratinjau
        yang tidak bisa dihasilkan videonya.
        """
        from app.services.subtitles import JARAK_KATA_MAKS, JARAK_KATA_MIN

        teks = BERKAS.read_text(encoding="utf-8")
        for nama, nilai in (("JARAK_KATA_MIN", JARAK_KATA_MIN),
                            ("JARAK_KATA_MAKS", JARAK_KATA_MAKS)):
            m = re.search(rf"export const {nama} = ([\d.]+);", teks)
            self.assertIsNotNone(m, f"{nama} tidak ditemukan di ClipPreview.jsx")
            self.assertAlmostEqual(float(m.group(1)), nilai, places=3)

    def test_pratinjau_memakai_nilai_gaya_bukan_tetapan(self):
        """
        Penggeser yang tidak terlihat di pratinjau sama saja tidak ada: orang
        menyetel jarak sambil MELIHAT kalimatnya, bukan sambil membayangkannya.
        """
        teks = BERKAS.read_text(encoding="utf-8")
        self.assertIn("export function jarakKata(style)", teks)
        self.assertIn("style?.jarak_kata", teks)


if __name__ == "__main__":
    unittest.main()
