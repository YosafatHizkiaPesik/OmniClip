"""Buang jeda dan kata isian (JOB-4 M5.4)."""

import unittest

from app.montase import jeda


def w(teks, s, e):
    return {"w": teks, "s": s, "e": e}


KATA = [
    w("halo", 0.5, 0.9), w("semua", 1.0, 1.4),            # celah awal 0,5 < 0,6: dibiarkan
    w("eh", 1.5, 1.8),                                     # kata isian
    w("hari", 3.0, 3.3), w("ini", 3.4, 3.6),               # jeda 1,2 dtk sebelum "hari"
    w("seru", 3.7, 4.0),
]
ITEM = {"id": "i1", "mulai": 30, "durasi": 150, "potong_awal": 0, "kecepatan": 1}   # 0-5 dtk bahan


class CariPotongan(unittest.TestCase):
    def test_isian_bergabung_dengan_jeda_sesudahnya(self):
        p = jeda.cari_potongan(KATA, ITEM, 30)
        self.assertEqual(len(p), 2)
        isian, ekor = p
        self.assertEqual(isian["jenis"], "isian")
        self.assertEqual(isian["kata"], "eh")
        # "semua" berakhir 1,4 dtk; "eh" (1,5) dianggap diam dan terpotong
        # seluruhnya: potongan 1,46 -> 3,0 - 0,15.
        self.assertEqual(isian["dari"], 30 + round(1.46 * 30))
        self.assertEqual(isian["sampai"], 30 + round(2.85 * 30))
        # Diam di ujung item (4,0 -> 5,0) dipotong sampai ujung, tanpa sisa di kanan.
        self.assertEqual(ekor["jenis"], "jeda")
        self.assertEqual(ekor["sampai"], 30 + 150)

    def test_kecepatan_dan_potong_awal(self):
        item = {"id": "i1", "mulai": 0, "durasi": 60, "potong_awal": 60, "kecepatan": 2}   # 2-6 dtk
        p = jeda.cari_potongan(KATA, item, 30)
        self.assertTrue(p)
        self.assertEqual(p[0]["dari"], 0)       # awal item ada di tengah jeda 1,8-3,0
        self.assertEqual(p[0]["sampai"], round((2.85 - 2.0) * 30 / 2))

    def test_isian_di_tengah_kalimat_dipotong_sendiri(self):
        kata = [w("jadi", 0.0, 0.3), w("em", 0.4, 0.7), w("begitu", 0.8, 1.2)]
        p = jeda.cari_potongan(kata, {"id": "i", "mulai": 0, "durasi": 36, "potong_awal": 0}, 30)
        self.assertEqual([(x["jenis"], x["kata"]) for x in p], [("isian", "em")])
        self.assertEqual((p[0]["dari"], p[0]["sampai"]), (round(0.36 * 30), round(0.74 * 30)))

    def test_tanpa_kata_tanpa_potongan(self):
        self.assertEqual(jeda.cari_potongan([], ITEM, 30), [])

    def test_operasi_berlabel(self):
        ops = jeda.operasi(jeda.cari_potongan(KATA, ITEM, 30), "i1", 30)
        self.assertEqual([o["jenis"] for o in ops], ["potong", "potong"])
        self.assertEqual(ops[0]["label"], '"eh"')
        self.assertTrue(all(o["item"] == "i1" for o in ops))


if __name__ == "__main__":
    unittest.main()
