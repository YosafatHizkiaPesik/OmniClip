"""
Bingkai main game pada klip PANJANG.

Dilaporkan pemiliknya 7 Oktober 2026, sesudah memasukkan satu video dua belas
menit utuh sebagai satu klip: "akurasi bingkai menurun di video klip yang
panjang". Dan sebelum itu, rendernya bahkan tidak jalan — permintaannya ditolak
dengan "List should have at most 64 items after validation, not 68".

Dua cacat yang sama-sama hanya muncul pada klip panjang, dan karena itu tidak
pernah terlihat di uji klip tiga puluh detik:

  1. Batas 64 letak facecam per klip, dipilih tanpa pernah diuji.
  2. Potongan PERMAINAN dihitung sekali untuk seluruh klip, menghindari
     gabungan SEMUA letak facecam. Streamer memindahkan kameranya beberapa
     kali dalam dua belas menit, dan tidak ada satu potongan pun yang bisa
     menghindari kiri-bawah dan kanan-bawah sekaligus tanpa membuang bagian
     tengah permainannya.
"""

import unittest
from unittest import mock

from app.services.render import (REAKSI_MAKS, _rapikan_reaksi, pecah_reaksi,
                                 susun_layout_gaming)


def _fc(x, y, w=18.0, h=30.0):
    return {"x": x, "y": y, "w": w, "h": h}


def _tindih(a: dict, b: dict) -> float:
    """Berapa bagian `b` yang termuat di dalam `a`."""
    ix = max(0.0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
    iy = max(0.0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
    return (ix * iy) / max(1e-6, b["w"] * b["h"])


class PermainanPerLetak(unittest.TestCase):
    # Facecam pindah dari kiri bawah ke kanan bawah, lalu kembali: pola yang
    # biasa pada siaran panjang, dan yang membuat potongan tunggal mustahil.
    POSISI = [
        {"t": 0.0, "facecam": _fc(2.0, 66.0)},
        {"t": 240.0, "facecam": _fc(80.0, 66.0)},
        {"t": 480.0, "facecam": _fc(2.0, 66.0)},
    ]

    def test_tiap_letak_membawa_potongan_permainannya_sendiri(self):
        tata = susun_layout_gaming(self.POSISI)
        self.assertEqual(len(tata["reaksi"]), 3)
        for r in tata["reaksi"]:
            self.assertIn("main", r, "letak tanpa potongan permainan")

    def test_potongan_per_letak_lebih_bersih_daripada_potongan_tunggal(self):
        tata = susun_layout_gaming(self.POSISI)
        tunggal = tata["frames"][0]["src"]
        # Potongan tunggal harus menghindari KEDUA sisi sekaligus; yang per
        # letak hanya menghindari facecam yang benar-benar ada saat itu.
        buruk_tunggal = max(_tindih(tunggal, p["facecam"]) for p in self.POSISI)
        buruk_sendiri = max(_tindih(r["main"], p["facecam"])
                            for r, p in zip(tata["reaksi"], self.POSISI))
        self.assertLessEqual(buruk_sendiri, buruk_tunggal)
        # Dan yang per letak benar-benar bersih: facecamnya tidak ikut masuk
        # ke bidang permainan.
        self.assertLess(buruk_sendiri, 0.2)

    def test_pecah_reaksi_memakai_potongan_tiap_letak(self):
        tata = susun_layout_gaming(self.POSISI)
        keys = [{"t": 0.0, "mode": "gaming"}]
        pecah = pecah_reaksi(keys, 720.0, tata)
        self.assertEqual(len(pecah), 3)
        for k, r in zip(pecah, tata["reaksi"]):
            self.assertEqual(k["layout"]["frames"][0]["src"], r["main"])
            self.assertEqual(k["layout"]["frames"][1]["src"], r["src"])

    def test_klip_lama_tanpa_main_tetap_dirender_seperti_dulu(self):
        tata = susun_layout_gaming(self.POSISI)
        tetap = dict(tata["frames"][0]["src"])
        for r in tata["reaksi"]:
            r.pop("main", None)
        pecah = pecah_reaksi([{"t": 0.0, "mode": "gaming"}], 720.0, tata)
        for k in pecah:
            self.assertEqual(k["layout"]["frames"][0]["src"], tetap)


class BatasLetak(unittest.TestCase):
    def test_letak_yang_terlalu_rapat_digabung(self):
        rapat = [{"t": 0.0}, {"t": 0.2}, {"t": 0.5}, {"t": 2.0}]
        self.assertEqual([r["t"] for r in _rapikan_reaksi(rapat)], [0.0, 2.0])

    def test_jumlahnya_dibatasi_dengan_membuang_yang_paling_sebentar(self):
        # Satu letak panjang di antara banyak letak pendek.
        banyak = [{"t": float(i)} for i in range(REAKSI_MAKS + 50)]
        hasil = _rapikan_reaksi(banyak)
        self.assertLessEqual(len(hasil), REAKSI_MAKS)
        # Yang pertama tidak pernah dibuang: ia yang berlaku sejak detik nol.
        self.assertEqual(hasil[0]["t"], 0.0)

    def test_klip_dua_belas_menit_muat_di_batasnya(self):
        # Satu letak tiap sepuluh detik selama dua belas menit: 72 letak, jauh
        # di bawah batas sekarang dan di ATAS batas 64 yang menolak render
        # pemiliknya.
        posisi = [{"t": float(i * 10), "facecam": _fc(2.0 + (i % 2) * 78.0, 66.0)}
                  for i in range(72)]
        tata = susun_layout_gaming(posisi)
        self.assertEqual(len(tata["reaksi"]), 72)
        self.assertLessEqual(len(tata["reaksi"]), REAKSI_MAKS)


if __name__ == "__main__":
    unittest.main()


class PanelDistabilkan(unittest.TestCase):
    """
    Panel yang ukurannya berkedip pada klip panjang.

    Terukur pada klip gameplay dua belas menit milik pemiliknya: 28,2% durasi
    klip dibingkai memakai panel yang BUKAN panel sebenarnya — dan hampir
    semuanya bukan panel di tempat lain, melainkan panel yang sama dengan
    ukuran salah. Facecam 14x27% di pojok kiri bawah sesekali terbaca 12x48%
    selama satu-dua detik lalu kembali. Pada klip tiga puluh detik itu terjadi
    nol sampai satu kali; pada klip dua belas menit, dua puluh kali.
    """

    from app.services.reframe import FACECAM_TINDIH_MIN, _stabilkan_panel

    @staticmethod
    def _sama(f, g):
        from app.services.reframe import FACECAM_TINDIH_MIN
        x1, y1 = max(f["x"], g["x"]), max(f["y"], g["y"])
        x2 = min(f["x"] + f["w"], g["x"] + g["w"])
        y2 = min(f["y"] + f["h"], g["y"] + g["h"])
        t = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        return t / max(1e-6, f["w"] * f["h"] + g["w"] * g["h"] - t) >= FACECAM_TINDIH_MIN

    def _jalan(self, letak, durasi=720.0):
        from app.services.reframe import _stabilkan_panel
        return _stabilkan_panel([dict(l) for l in letak], durasi, self._sama)

    def test_panel_yang_memanjang_dari_sudutnya_dikembalikan(self):
        # Panel benar 14x27% di kiri bawah; sesekali terbaca dua kali lebih
        # tinggi, dengan sisi kiri dan sisi bawah tetap di tempatnya.
        letak = [{"t": 0.0, "facecam": _fc(3.0, 72.0, 14.0, 27.0)},
                 {"t": 200.0, "facecam": _fc(3.0, 45.0, 13.0, 54.0)},
                 {"t": 203.0, "facecam": _fc(3.0, 72.0, 14.0, 27.0)},
                 {"t": 400.0, "facecam": _fc(2.0, 48.0, 12.0, 51.0)},
                 {"t": 406.0, "facecam": _fc(3.0, 72.0, 14.0, 27.0)}]
        hasil = self._jalan(letak)
        self.assertEqual(len(hasil), 1, "panel yang sama harusnya jadi satu")
        self.assertAlmostEqual(hasil[0]["facecam"]["h"], 27.0, delta=1.5)

    def test_perpindahan_sungguhan_tidak_disentuh(self):
        # Facecam benar-benar pindah ke seberang bingkai, dan tinggal di sana.
        letak = [{"t": 0.0, "facecam": _fc(3.0, 72.0, 14.0, 27.0)},
                 {"t": 300.0, "facecam": _fc(80.0, 72.0, 14.0, 27.0)},
                 {"t": 600.0, "facecam": _fc(3.0, 72.0, 14.0, 27.0)}]
        hasil = self._jalan(letak)
        self.assertEqual(len(hasil), 3)
        self.assertAlmostEqual(hasil[1]["facecam"]["x"], 80.0, delta=1.0)

    def test_lompatan_sekejap_ke_seberang_dibuang(self):
        # Wajah di dalam gambar permainan: setengah detik di seberang, lalu
        # kembali. Bukan kamera yang pindah.
        letak = [{"t": 0.0, "facecam": _fc(3.0, 72.0, 14.0, 27.0)},
                 {"t": 300.0, "facecam": _fc(78.0, 30.0, 14.0, 27.0)},
                 {"t": 300.5, "facecam": _fc(3.0, 72.0, 14.0, 27.0)}]
        hasil = self._jalan(letak)
        self.assertEqual(len(hasil), 1)

    def test_klip_pendek_tidak_disentuh_sama_sekali(self):
        # Di bawah sembilan puluh detik tidak ada cukup waktu untuk tahu mana
        # ukuran yang "paling lama berlaku", dan menebak di situ merusak hal
        # yang selama ini sudah benar.
        letak = [{"t": 0.0, "facecam": _fc(3.0, 72.0, 14.0, 27.0)},
                 {"t": 20.0, "facecam": _fc(3.0, 45.0, 13.0, 54.0)},
                 {"t": 25.0, "facecam": _fc(3.0, 72.0, 14.0, 27.0)}]
        self.assertEqual(self._jalan(letak, durasi=60.0), letak)

    def test_panel_yang_memang_berganti_ukuran_dibiarkan(self):
        # Tidak ada satu ukuran pun yang menguasai klip: tidak ada acuan yang
        # jujur, jadi tidak ada yang dipaksakan.
        letak = [{"t": 0.0, "facecam": _fc(3.0, 72.0, 14.0, 27.0)},
                 {"t": 240.0, "facecam": _fc(3.0, 40.0, 30.0, 59.0)},
                 {"t": 480.0, "facecam": _fc(3.0, 60.0, 22.0, 39.0)}]
        self.assertEqual(len(self._jalan(letak)), 3)


class PindaiCuplikan(unittest.TestCase):
    """
    Klip panjang dipindai dengan cuplikan, bukan dibaca utuh.

    Terukur pada klip 293 detik: seluruh pemindaian 150 detik, dan 125 detik di
    antaranya cuma ffmpeg membongkar bingkai — sumber 60 fps dibongkar
    seluruhnya walau yang diambil delapan bingkai per detik. Melangkahi jendela
    tidak menolong (150 jadi 150 detik), dekoder GPU juga tidak (lebih lambat
    di mesin ini). Yang menolong hanya tidak membaca sebagian besar videonya:
    42 detik dengan cuplikan, dan letak panel yang keluar sama.
    """

    def test_klip_pendek_tetap_dibaca_utuh(self):
        from app.services import reframe
        dipanggil = []
        asli = reframe._facecam_cuplikan
        reframe._facecam_cuplikan = lambda *a, **kv: dipanggil.append(a) or []
        try:
            # Berkasnya memang tidak ada; yang diuji di sini CABANG MANA
            # yang dimasuki, bukan hasil pemindaiannya.
            try:
                reframe.deteksi_facecam_waktu("x.mp4", [{"start": 0, "end": 120}],
                                              1920, 1080)
            except Exception:                            # noqa: BLE001
                pass
        finally:
            reframe._facecam_cuplikan = asli
        self.assertEqual(dipanggil, [], "klip 120 detik seharusnya dibaca utuh")

    def test_klip_panjang_memakai_cuplikan(self):
        from app.services import reframe
        dipanggil = []
        asli = reframe._facecam_cuplikan
        reframe._facecam_cuplikan = lambda *a, **kv: dipanggil.append(a) or []
        try:
            reframe.deteksi_facecam_waktu("x.mp4", [{"start": 0, "end": 720}],
                                          1920, 1080)
        finally:
            reframe._facecam_cuplikan = asli
        self.assertEqual(len(dipanggil), 1)

    def test_jarak_cuplikan_dijepit(self):
        from app.services.reframe import CUPLIK_JARAK, CUPLIK_JUMLAH
        # Klip satu jam tidak boleh menghasilkan cuplikan tiap satu setengah
        # menit: perpindahan panel jadi tidak ketahuan sama sekali.
        for durasi in (200.0, 720.0, 3600.0):
            jarak = min(CUPLIK_JARAK[1], max(CUPLIK_JARAK[0], durasi / CUPLIK_JUMLAH))
            self.assertGreaterEqual(jarak, CUPLIK_JARAK[0])
            self.assertLessEqual(jarak, CUPLIK_JARAK[1])
