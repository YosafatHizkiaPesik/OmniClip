"""
Tema subtitle: sorotan per kata dan animasi masuk.

Yang dijaga di sini bukan "apakah tampilannya bagus" — itu hanya bisa dinilai
dengan mata, dan sudah dinilai dengan merender bingkai sungguhan. Yang dijaga
adalah hal-hal yang bisa rusak diam-diam: gaya lama yang berubah arti sendiri,
dan lapis kotak yang harus sama persis dengan lapis teksnya.
"""

import unittest

from app.services.subtitles import (SOROT_KOTAK, SOROT_LAPIS, CaptionStyle,
                                    _normalkan, build_ass)


def baris(teks="satu dua tiga", mulai=0.0, akhir=1.5):
    kata = teks.split()
    lebar = (akhir - mulai) / len(kata)
    return [{
        "start": mulai, "end": akhir, "text": teks,
        "words": [{"w": w, "s": mulai + i * lebar, "e": mulai + (i + 1) * lebar}
                  for i, w in enumerate(kata)],
    }]


class GayaLama(unittest.TestCase):
    """Klip yang sudah tersimpan tidak boleh berubah tampilannya sendiri."""

    def test_karaoke_pop_jadi_sorot_pop_tanpa_animasi_masuk(self):
        st = _normalkan(CaptionStyle(animation="karaoke_pop"))
        self.assertEqual((st.animation, st.sorot), ("none", "pop"))

    def test_karaoke_wipe_jadi_sorot_warna(self):
        st = _normalkan(CaptionStyle(animation="karaoke_wipe"))
        self.assertEqual((st.animation, st.sorot), ("none", "warna"))

    def test_tanpa_animasi_tetap_tanpa_sorotan(self):
        # Preset "Sinema" dan "Bersih" bergantung pada ini.
        self.assertEqual(_normalkan(CaptionStyle(animation="none")).sorot, "mati")

    def test_highlight_words_mati_tetap_dihormati(self):
        st = _normalkan(CaptionStyle(animation="fade", highlight_words=False))
        self.assertEqual(st.sorot, "mati")

    def test_sorot_yang_dipilih_sendiri_menang(self):
        st = _normalkan(CaptionStyle(animation="fade", sorot="kotak"))
        self.assertEqual((st.animation, st.sorot), ("fade", "kotak"))


class LapisKotak(unittest.TestCase):
    def test_kotak_menambah_gaya_kembar(self):
        ass = build_ass(lines=baris(), style=CaptionStyle(sorot="kotak"), clip_duration=1.5)
        self.assertIn("Style: CaptionKotak,", ass)

    def test_tanpa_kotak_tidak_ada_gaya_kembar(self):
        ass = build_ass(lines=baris(), style=CaptionStyle(sorot="warna"), clip_duration=1.5)
        self.assertNotIn("CaptionKotak", ass)

    def test_tiap_kata_punya_dua_lapis_yang_waktunya_sama(self):
        ass = build_ass(lines=baris(), style=CaptionStyle(sorot="kotak"), clip_duration=1.5)
        teks, kotak = [], []
        for b in ass.splitlines():
            if not b.startswith("Dialogue:"):
                continue
            kolom = b.split(",")
            if kolom[3] == "CaptionKotak":
                kotak.append((kolom[1], kolom[2]))
            elif kolom[3] == "Caption":
                teks.append((kolom[1], kolom[2]))
        self.assertEqual(len(teks), 3)
        # Waktunya harus sama persis; kalau tidak, kotaknya berkedip sendiri.
        self.assertEqual(teks, kotak)

    def test_lapis_kotak_selalu_di_bawah_teks(self):
        ass = build_ass(lines=baris(), style=CaptionStyle(sorot="kotak"), clip_duration=1.5)
        for b in ass.splitlines():
            if not b.startswith("Dialogue:"):
                continue
            layer = b.split(":", 1)[1].split(",")[0].strip()
            gaya = b.split(",")[3]
            if gaya == "CaptionKotak":
                self.assertEqual(layer, "0")
            elif gaya == "Caption":
                self.assertEqual(layer, "1")

    def test_huruf_di_lapis_kotak_dibuat_tembus_pandang(self):
        ass = build_ass(lines=baris(), style=CaptionStyle(sorot="kotak"), clip_duration=1.5)
        for b in ass.splitlines():
            if b.startswith("Dialogue:") and ",CaptionKotak," in b:
                self.assertIn(r"\1a&HFF&", b)

    def test_glow_juga_berlapis_tapi_tanpa_gaya_kembar(self):
        # Nyalanya digambar dengan gaya Caption yang sama, jadi metriknya pasti
        # sama dan kedua lapis bertumpuk tepat.
        self.assertIn("glow", SOROT_LAPIS)
        self.assertNotIn("glow", SOROT_KOTAK)
        ass = build_ass(lines=baris(), style=CaptionStyle(sorot="glow"), clip_duration=1.5)
        self.assertNotIn("CaptionKotak", ass)
        self.assertIn(r"\blur", ass)


class JarakKata(unittest.TestCase):
    """
    Dilaporkan pemiliknya dari klip yang sudah jadi: "KASUS TERAKHIRKU" terbaca
    sebagai satu kata panjang. Sebabnya spasi bawaan font display memang
    sempit, dan sempitnya berbeda-beda per font.
    """

    def test_font_berspasi_sempit_dilebarkan_lebih_banyak(self):
        from app.services.fonts import lebar_spasi
        from app.services.subtitles import JARAK_KATA, _sela
        sempit = lebar_spasi("Bebas Neue")
        lebar = lebar_spasi("Archivo Black")
        self.assertLess(sempit, lebar, "prasyarat: kedua font memang berbeda")

        def tambahan(font):
            # "{\fspN} {\fsp0}" -> N
            s = _sela(CaptionStyle(font=font, size=100))
            return int(s.split("fsp")[1].split("}")[0]) if "fsp" in s else 0

        self.assertGreater(tambahan("Bebas Neue"), tambahan("Archivo Black"))
        # Hasilnya yang disamakan, bukan tambahannya.
        for font in ("Bebas Neue", "Archivo Black", "Montserrat", "Anton"):
            total = lebar_spasi(font) + tambahan(font) / 100.0
            self.assertAlmostEqual(total, JARAK_KATA, delta=0.01, msg=font)

    def test_jarak_lebih_lebar_daripada_pelat_sorotan(self):
        """
        Kotak sorotan melebar ke kanan-kiri kata yang disorot. Bila jaraknya
        tidak melebihi pelebaran itu, kotaknya menempel pada kata berikutnya
        dan dua kata terbaca sebagai satu. Ini yang dilaporkan dua kali.
        """
        from app.services.subtitles import JARAK_KATA
        EMPUK = 0.16                      # lihat `gaya_kotak` di build_ass
        # Batasnya diukur, bukan ditebak. Pada bingkai sungguhan, sisa 0,24 em
        # membuat kotak menempel pada kata berikutnya; sisa 0,30 em tidak.
        # Angka di bawah duduk di antara keduanya.
        self.assertGreater(JARAK_KATA - EMPUK, 0.28)

    def test_spasi_dilebarkan_hanya_di_antara_kata(self):
        ass = build_ass(lines=baris("satu dua"), clip_duration=1.5,
                        style=CaptionStyle(font="Bebas Neue", sorot="warna"))
        dialog = next(b for b in ass.splitlines() if b.startswith("Dialogue: "))
        isi = dialog.split(",,", 1)[1]
        self.assertIn(r"\fsp", isi)
        # Yang berada di dalam lingkup \fsp yang MELEBARKAN hanya satu spasi;
        # huruf di dalam kata tidak boleh ikut merenggang. Lingkup \fsp0 adalah
        # penutupnya, jadi ia memang diikuti kata berikutnya.
        for potong in isi.split("{\\fsp")[1:]:
            angka, sisa = potong.split("}", 1)
            if angka == "0":
                continue
            dalam = sisa.split("{", 1)[0]
            self.assertEqual(dalam, " ", f"lingkup fsp memuat {dalam!r}")

    def test_teks_cjk_tidak_diberi_spasi(self):
        ass = build_ass(lines=baris("天 井"), clip_duration=1.5,
                        style=CaptionStyle(sorot="warna"))
        dialog = next(b for b in ass.splitlines() if b.startswith("Dialogue: "))
        self.assertNotIn(r"\fsp", dialog.split(",,", 1)[1])

    def test_pemisah_khusus_dipakai_apa_adanya(self):
        from app.services.teks import sambung_bagian
        self.assertEqual(sambung_bagian(["a", "b"], ["a", "b"], sela="<S>"), "a<S>b")
        self.assertEqual(sambung_bagian(["天", "井"], ["天", "井"], sela="<S>"), "天井")


class AnimasiMasuk(unittest.TestCase):
    def test_tiap_animasi_menghasilkan_tag_yang_berbeda(self):
        dilihat = {}
        for anim in ("fade", "pop_in", "pantul", "putar", "blur_masuk",
                     "geser_kiri", "geser_kanan", "slide_up", "getar"):
            ass = build_ass(lines=baris(), clip_duration=1.5,
                            style=CaptionStyle(animation=anim, sorot="warna"))
            dialog = [b for b in ass.splitlines() if b.startswith("Dialogue: ")
                      and ",Caption," in b]
            self.assertTrue(dialog, anim)
            dilihat[anim] = dialog[0]
        # Sembilan animasi harus menghasilkan sembilan baris yang berbeda;
        # kalau dua sama, salah satunya diam-diam tidak berlaku.
        self.assertEqual(len(set(dilihat.values())), len(dilihat))

    def test_animasi_masuk_hanya_pada_kata_pertama(self):
        ass = build_ass(lines=baris(), clip_duration=1.5,
                        style=CaptionStyle(animation="pantul", sorot="warna"))
        dialog = [b for b in ass.splitlines() if b.startswith("Dialogue: ")]
        self.assertIn(r"\fscx68", dialog[0])
        for b in dialog[1:]:
            self.assertNotIn(r"\fscx68", b)

    def test_satu_kata_menampilkan_satu_kata_saja(self):
        ass = build_ass(lines=baris("satu dua tiga"), clip_duration=1.5,
                        style=CaptionStyle(animation="satu_kata"))
        dialog = [b for b in ass.splitlines() if b.startswith("Dialogue: ")]
        self.assertEqual(len(dialog), 3)
        for b, kata in zip(dialog, ("SATU", "DUA", "TIGA")):
            isi = b.split(",,", 1)[1]
            self.assertIn(kata, isi)
            for lain in ("SATU", "DUA", "TIGA"):
                if lain != kata:
                    self.assertNotIn(lain, isi)


if __name__ == "__main__":
    unittest.main()


class KapitalPerAksara(unittest.TestCase):
    """
    HURUF KAPITAL tidak berlaku untuk aksara Jepang, Korea, Mandarin, dan Arab:
    tidak ada satu pun huruf yang berubah. Membiarkannya menyala bukan sekadar
    tidak berguna, ia membuat pratinjau berbohong tentang lebar barisnya, dan
    lebar baris itulah yang dipakai memilih ukuran huruf.
    """

    def gaya(self, teks, **kv):
        from app.services.subtitles import CaptionStyle, _font_aksara
        return _font_aksara(CaptionStyle(uppercase=True, **kv),
                            [{"text": teks}])

    def test_jepang_kapital_dimatikan(self):
        self.assertFalse(self.gaya("天井にいたらどのくらい").uppercase)

    def test_korea_arab_mandarin_juga(self):
        for t in ("안녕하세요 반갑습니다", "مرحبا بالعالم", "你好世界啊"):
            self.assertFalse(self.gaya(t).uppercase, t)

    def test_latin_tidak_disentuh(self):
        self.assertTrue(self.gaya("Halo dunia, apa kabar").uppercase)

    def test_pilihan_mati_tetap_mati(self):
        from app.services.subtitles import CaptionStyle, _font_aksara
        st = _font_aksara(CaptionStyle(uppercase=False), [{"text": "Halo dunia"}])
        self.assertFalse(st.uppercase)

    def test_font_tetap_diganti_bersamaan(self):
        # Dua hal sekaligus, dan yang satu tidak boleh membatalkan yang lain.
        st = self.gaya("天井にいたらどのくらい")
        self.assertNotEqual(st.font, "Montserrat")


class WarnaPenuturBawaanMati(unittest.TestCase):
    """
    Warna berbeda per penutur mati secara bawaan, dan itu keputusan yang diukur.

    Pada podcast tiga orang, penambatan wajah benar menemukan tiga orang, tapi
    model suara yang dilatih dari bukti itu hanya benar 62% pada potongan yang
    tidak dilatihkan (37 dari 60), dan menambah bukti dari 8 ke 15 klip
    menurunkannya ke 60%. Empat dari sepuluh kalimat berwarna salah, dengan
    warna yang berganti di tengah kalimat orang yang sama, lebih mengganggu
    daripada satu warna yang tidak pernah salah.

    Yang dijaga di sini: gaya yang tidak menyebut apa-apa memberi SATU warna.
    """

    def _baris_dua_orang(self):
        a = baris("halo dunia ini", 0.0, 1.5)[0]
        b = baris("balasan dari lawan", 1.6, 3.0)[0]
        a["speaker"], b["speaker"] = 0, 1
        return [a, b]

    def test_bawaannya_mati(self):
        self.assertFalse(CaptionStyle().per_speaker_colors)

    def test_kedua_penutur_memakai_warna_yang_sama(self):
        ass = build_ass(lines=self._baris_dua_orang(),
                        style=CaptionStyle(primary="#FFFFFF"), clip_duration=3.0)
        # #7CFFB2, warna orang kedua dari palet bawaan, dalam urutan byte ASS.
        self.assertNotIn("B2FF7C", ass)

    def test_masih_bisa_dinyalakan_dengan_sengaja(self):
        ass = build_ass(lines=self._baris_dua_orang(),
                        style=CaptionStyle(per_speaker_colors=True),
                        clip_duration=3.0)
        self.assertIn("B2FF7C", ass)


class SakelarIndukWarnaPenutur(unittest.TestCase):
    """
    Satu kebenaran untuk seluruh aplikasi, bukan satu kotak centang per klip.

    Gaya yang sudah tersimpan di peramban masih menyimpan `per_speaker_colors:
    true` dari sebelum keputusan ini. Tanpa sakelar induk yang menang, gaya lama
    itu akan menghidupkan kembali pewarnaan yang sudah diputuskan mati, pada
    klip yang dirender berbulan-bulan sesudahnya.
    """

    def setUp(self):
        from app.repos import settings as repo
        self.repo = repo
        self.nilai = {}
        self.asli_get = repo.get
        self.asli_set = repo.set_value
        repo.get = lambda nama, bawaan=None: self.nilai.get(nama, bawaan)
        repo.set_value = lambda nama, nilai: self.nilai.__setitem__(nama, nilai)

    def tearDown(self):
        self.repo.get = self.asli_get
        self.repo.set_value = self.asli_set

    def test_bawaannya_mati(self):
        from app.services.subtitles import warna_penutur_aktif
        self.assertFalse(warna_penutur_aktif())

    def test_bisa_dinyalakan_dan_dimatikan_lagi(self):
        from app.services.subtitles import setel_warna_penutur, warna_penutur_aktif
        setel_warna_penutur(True)
        self.assertTrue(warna_penutur_aktif())
        setel_warna_penutur(False)
        self.assertFalse(warna_penutur_aktif())

    def test_perender_benar_benar_menanyakan_sakelarnya(self):
        """
        Dibaca dari sumbernya, karena `run_render` tidak bisa dijalankan tanpa
        video sungguhan. Yang dijaga hanya satu: gaya dari klien tidak boleh
        lagi sampai ke CaptionStyle tanpa melewati sakelar induk.
        """
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1]
                  / "app" / "services" / "pipeline.py").read_text(encoding="utf-8")
        potong = sumber.split("per_speaker_colors=")[1][:200]
        self.assertIn("warna_penutur_aktif()", potong)
        self.assertNotIn('"per_speaker_colors", True', sumber)


class JarakKataBisaDisetel(unittest.TestCase):
    """
    Jarak antar kata pernah dipatok mati di 0,46.

    Patokan itu selalu salah untuk sebagian orang: font yang lebih lebar butuh
    jarak lebih rapat, dan seleranya sendiri berbeda beda. Yang tetap dijaga
    adalah HASILNYA, yaitu jarak akhir yang sama untuk semua font, bukan
    tambahan yang sama.
    """

    def test_tanpa_disetel_memakai_bawaan(self):
        from app.services.subtitles import JARAK_KATA, jarak_kata
        self.assertEqual(jarak_kata(CaptionStyle()), JARAK_KATA)

    def test_nilai_pengguna_dipakai(self):
        from app.services.subtitles import jarak_kata
        self.assertAlmostEqual(jarak_kata(CaptionStyle(jarak_kata=0.30)), 0.30)

    def test_nilai_liar_dijepit(self):
        from app.services.subtitles import (JARAK_KATA_MAKS, JARAK_KATA_MIN,
                                            jarak_kata)
        self.assertEqual(jarak_kata(CaptionStyle(jarak_kata=-5)), JARAK_KATA_MIN)
        self.assertEqual(jarak_kata(CaptionStyle(jarak_kata=99)), JARAK_KATA_MAKS)

    def test_lebih_rapat_menghasilkan_fsp_lebih_kecil(self):
        """Yang diperiksa bukan angkanya, melainkan arahnya: rapat = fsp kecil."""
        import re

        from app.services.subtitles import _sela

        def fsp(nilai):
            m = re.search(r"\\fsp(\d+)", _sela(CaptionStyle(jarak_kata=nilai,
                                                           font="Montserrat", size=96)))
            return int(m.group(1)) if m else 0

        self.assertLess(fsp(0.34), fsp(0.46))
        self.assertLess(fsp(0.46), fsp(0.62))

    def test_font_lebar_diberi_tambahan_lebih_kecil(self):
        """Jarak akhir yang sama, walau spasi bawaan tiap font berbeda."""
        import re

        from app.services.fonts import lebar_spasi
        from app.services.subtitles import _sela

        def fsp(font):
            m = re.search(r"\\fsp(\d+)", _sela(CaptionStyle(jarak_kata=0.60,
                                                           font=font, size=96)))
            return int(m.group(1)) if m else 0

        sempit, lebar = "Bebas Neue", "Archivo Black"
        if lebar_spasi(sempit) >= lebar_spasi(lebar):
            sempit, lebar = lebar, sempit
        self.assertGreater(fsp(sempit), fsp(lebar))


class GayaSampaiKeRenderUtuh(unittest.TestCase):
    """
    Setiap bidang gaya yang dikenal harus benar-benar sampai ke perender.

    `run_render` dulu menyusun CaptionStyle dari daftar tangan berisi dua puluh
    bidang, dan diam-diam membuang empat belas sisanya: `sorot`, `kotak_warna`,
    `kotak_teks`, `bg`, `aktif`, dan seterusnya. Akibatnya setiap tema
    berkotak, berpendar, atau bergaris bawah dirender sebagai sorotan biasa.

    Terlapor 25 September 2026 sesudah sebuah klip terunggah ke YouTube: kotak
    kuning di belakang kata ada di pratinjau, tidak ada di videonya. Cacat
    seperti ini tidak pernah membuat render GAGAL, jadi ia hanya bisa terlihat
    dengan menonton hasilnya, berminggu-minggu sesudah temanya dipilih.
    """

    def _bidang(self):
        from dataclasses import fields
        return {f.name for f in fields(CaptionStyle)}

    def test_perender_tidak_memakai_daftar_tangan(self):
        from pathlib import Path
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn("dikenal = {f.name for f in _bidang(CaptionStyle)}", sumber)
        self.assertIn("style = CaptionStyle(**nilai)", sumber)

    def test_model_permintaan_menerima_semua_bidang_gaya(self):
        """Penyaring kedua ada di router; dua daftar yang berpisah sama saja."""
        from app.routers.clips import CaptionStyleModel
        hilang = self._bidang() - set(CaptionStyleModel.model_fields)
        self.assertEqual(hilang, set(), f"router membuang {hilang}")

    def test_mode_kotak_menghasilkan_lapis_pelat(self):
        """Yang membedakan mode kotak: ada lapis pelat di bawah teksnya."""
        def n_dialog(sorot):
            baris = [{"start": 0.0, "end": 1.5, "text": "satu dua",
                      "words": [{"w": "satu", "s": 0.0, "e": 0.7},
                                {"w": "dua", "s": 0.7, "e": 1.5}]}]
            ass = build_ass(lines=baris, style=CaptionStyle(sorot=sorot),
                            clip_duration=1.5)
            return sum(1 for l in ass.splitlines() if l.startswith("Dialogue"))

        self.assertGreater(n_dialog("kotak"), n_dialog("warna"))
        self.assertGreater(n_dialog("kotak_pop"), n_dialog("pop"))
