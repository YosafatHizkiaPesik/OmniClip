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
