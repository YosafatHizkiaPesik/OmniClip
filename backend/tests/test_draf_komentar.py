"""
JOB-2 F1-2: draf komentar pemilik kanal per klip.

Yang diuji di sini bukan mutu tulisan modelnya, itu tidak bisa diuji. Yang
diuji adalah pagar di sekelilingnya: frasa templat dibuang, sela hanya jatuh
di jeda yang sungguhan, em dash tidak lolos, dan tanpa AI tidak ada komentar
karangan.
"""

import unittest
from unittest import mock

from app.services import komentar as km


def baris(*jeda):
    """Baris subtitle berurutan; `jeda[i]` adalah jarak sesudah baris ke-i."""
    out, t = [], 0.0
    for i, j in enumerate(list(jeda) + [0]):
        out.append({"start": t, "end": t + 2.0,
                    "text": f"kalimat ke {i} tentang kasbon pak budi"})
        t += 2.0 + j
    return out


def klip(**ubah):
    return {"title": "Kasbon hari pertama", "konteks": "Ditanya soal kasbon.",
            "duration": 20, "subtitles": baris(0.1, 0.8, 0.05, 0.6), **ubah}


def jawab(**isi):
    hasil = {"pembuka": "Pak Budi ditanya soal kasbon di hari pertama kerja.",
             "sela_baris": 1, "sela": "Jujur, gue juga pernah begini.",
             "penutup": "Kalau kalian jadi bosnya, kasih atau tidak?",
             "kartu_konteks": "Pak Budi ditanya soal kasbon di hari pertama"}
    hasil.update(isi)
    return mock.patch("app.services.penyedia_ai.tanya",
                      return_value=(hasil, "gemini-uji", {}))


class TempatSela(unittest.TestCase):
    def test_sela_di_akhir_baris_yang_dipilih(self):
        t = km.tempat_sela(km._baris(baris(0.1, 0.8)), 1)
        self.assertEqual(t["baris"], 1)
        self.assertAlmostEqual(t["detik"], 4.1, places=2)
        self.assertAlmostEqual(t["jeda"], 0.8, places=2)

    def test_jeda_sempit_digeser_ke_jeda_terdekat(self):
        t = km.tempat_sela(km._baris(baris(0.1, 0.8)), 0)
        self.assertEqual(t["baris"], 1)

    def test_tanpa_jeda_di_dekatnya_ditolak(self):
        b = km._baris(baris(0.1, 0.1, 0.1, 0.1, 0.1, 0.8))
        self.assertIsNone(km.tempat_sela(b, 0))
        self.assertEqual(km.tempat_sela(b, 3)["baris"], 5)

    def test_jeda_ditandai_untuk_model(self):
        teks = km._bahan(klip(), km._baris(baris(0.1, 0.8)), "")
        self.assertIn("[1] kalimat ke 1 tentang kasbon pak budi   (jeda 0.8 dtk)", teks)
        self.assertNotIn("[0] kalimat ke 0 tentang kasbon pak budi   (jeda", teks)

    def test_sesudah_baris_terakhir_bukan_sela(self):
        b = km._baris(baris(0.5, 0.5))
        self.assertIsNone(km.tempat_sela(b, len(b) - 1))
        self.assertIsNone(km.tempat_sela(b, -1))
        self.assertIsNone(km.tempat_sela(b, 99))
        self.assertIsNone(km.tempat_sela(b, "bukan angka"))


class Draf(unittest.TestCase):
    def test_draf_lengkap(self):
        with jawab():
            d = km.draf(klip(), api_key="k", models=["m"])
        self.assertTrue(d["pembuka"].startswith("Pak Budi"))
        self.assertEqual(d["sela"]["baris"], 1)
        self.assertEqual(d["sumber"], "gemini-uji")
        self.assertEqual(d["catatan"], [])

    def test_frasa_templat_dibuang(self):
        with jawab(pembuka="Lihat apa yang terjadi ketika Pak Budi minta kasbon"):
            d = km.draf(klip(), api_key="k", models=["m"])
        self.assertEqual(d["pembuka"], "")
        self.assertTrue(d["penutup"])
        self.assertTrue(any("templat" in c for c in d["catatan"]))

    def test_sela_di_tempat_salah_tidak_dipakai(self):
        rapat = baris(0.1, 0.1, 0.1, 0.1, 0.1, 0.1)
        with jawab(sela_baris=2):
            d = km.draf(klip(subtitles=rapat), api_key="k", models=["m"])
        self.assertIsNone(d["sela"])
        self.assertTrue(d["catatan"])

    def test_tanpa_sela(self):
        with jawab(sela_baris=-1, sela=""):
            d = km.draf(klip(), api_key="k", models=["m"])
        self.assertIsNone(d["sela"])
        self.assertEqual(d["catatan"], [])

    def test_em_dash_dibersihkan_dan_panjang_dibatasi(self):
        with jawab(penutup="Menurut gue — ini " + "panjang sekali " * 30):
            d = km.draf(klip(), api_key="k", models=["m"])
        self.assertNotIn("—", d["penutup"])
        self.assertLessEqual(len(d["penutup"]), km.MAKS_PENUTUP + 3)

    def test_konteks_kosong_tetap_jalan(self):
        with jawab() as t:
            d = km.draf(klip(konteks=""), api_key="k", models=["m"])
        self.assertTrue(d["pembuka"])
        self.assertIn("tidak ada", t.call_args[0][0][0]["teks"])

    def test_gaya_kanal_ikut_ke_model(self):
        with jawab() as t:
            km.draf(klip(), api_key="k", models=["m"], gaya="santai, pakai gue")
        self.assertIn("santai, pakai gue", t.call_args[0][0][0]["teks"])


class KartuKonteks(unittest.TestCase):
    def test_ikut_kembali_dan_dibatasi(self):
        with jawab():
            d = km.draf(klip(), api_key="k", models=["m"])
        self.assertEqual(d["kartu_konteks"], "Pak Budi ditanya soal kasbon di hari pertama")
        with jawab(kartu_konteks="x " * 80):
            d = km.draf(klip(), api_key="k", models=["m"])
        self.assertLessEqual(len(d["kartu_konteks"]), km.MAKS_KARTU_KONTEKS + 3)

    def test_tanpa_ai_kosong(self):
        self.assertEqual(km.draf(klip(), api_key="", models=[])["kartu_konteks"], "")


class TanpaAI(unittest.TestCase):
    def test_tanpa_kunci_tidak_mengarang(self):
        with mock.patch("app.services.penyedia_ai.tanya") as t:
            d = km.draf(klip(), api_key="", models=[])
        t.assert_not_called()
        self.assertEqual((d["pembuka"], d["sela"], d["penutup"]), ("", None, ""))
        self.assertTrue(d["catatan"])

    def test_semua_model_gagal(self):
        from app.services.penyedia_ai import SemuaGagal
        with mock.patch("app.services.penyedia_ai.tanya", side_effect=SemuaGagal("habis")):
            d = km.draf(klip(), api_key="k", models=["m"])
        self.assertEqual(d["pembuka"], "")
        self.assertEqual(d["sumber"], "")

    def test_klip_tanpa_ucapan(self):
        with mock.patch("app.services.penyedia_ai.tanya") as t:
            d = km.draf(klip(subtitles=[]), api_key="k", models=["m"])
        t.assert_not_called()
        self.assertTrue(d["catatan"])


class KelompokSetelan(unittest.TestCase):
    def test_kelompok_komentar_terdaftar(self):
        from app.repos import profil
        self.assertIn("komentar", profil.KELOMPOK)


if __name__ == "__main__":
    unittest.main()
