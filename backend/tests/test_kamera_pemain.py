"""
Apakah klip ini punya kamera pemain (facecam), dinilai dari jejak wajahnya.

Dilaporkan 8 Oktober 2026: "saya sedang mengklip video game tapi ada button
1,2,3 yang biasanya untuk mengikuti wajah, tapi inikan game". Terukur pada
video gameplay pemiliknya: 9 dari 20 klip digolongkan ikut-wajah, karena
penggolong per klip melabeli sampel TANPA diberi tahu letak panel facecam-nya,
sementara sutradara per momen sudah tahu. Satu wajah gambar di tengah
permainan karena itu cukup untuk membuat sampel dilabeli "wajah".

Angka pada kelas ini diambil dari pengukuran 9 Oktober 2026, bukan dikarang:

  letak median wajah, sumbu y   gameplay 0,81-0,86   podcast 0,31-0,52
  porsi klip wajah terlihat     gameplay 0,70-1,00
"""

import unittest

from app.services import sutradara_ai as SA


class Plan:
    """Rencana wajah seminimal mungkin: cukup untuk `ada_facecam`."""

    def __init__(self, orang, n=80, sw=1920, sh=1080):
        # orang: [(x_pecahan, y_pecahan, lebar_pecahan, porsi_terlihat)]
        self.source_w, self.source_h = sw, sh
        self.people, self.people_box, self.people_seen = [], [], []
        for x, y, w, ada in orang:
            batas = int(n * ada)
            self.people.append([x * sw] * n)
            self.people_box.append([(y * sh, w * sw)] * n)
            self.people_seen.append([i < batas for i in range(n)])


class KameraPemainTerbaca(unittest.TestCase):
    def test_facecam_kanan_bawah(self):
        """Angka sebenarnya dari klip 1, 2, dan 6 video pemiliknya."""
        for x, y, w in ((0.86, 0.81, 0.067), (0.85, 0.86, 0.074), (0.86, 0.84, 0.072)):
            with self.subTest(x=x, y=y):
                self.assertTrue(SA.ada_facecam(Plan([(x, y, w, 1.0)])))

    def test_facecam_kiri_atas_juga_terbaca(self):
        """Aturannya tentang POJOK, bukan tentang kanan bawah saja."""
        self.assertTrue(SA.ada_facecam(Plan([(0.14, 0.18, 0.07, 0.95)])))

    def test_facecam_terbaca_walau_ada_wajah_gambar_di_tengah(self):
        """Wajah di dalam permainan tidak boleh menutupi kamera pemainnya."""
        plan = Plan([(0.86, 0.82, 0.07, 1.0),      # kamera pemain
                     (0.43, 0.27, 0.07, 0.92),     # wajah gambar di tengah
                     (0.58, 0.49, 0.03, 0.18)])    # dan satu yang sekejap
        self.assertTrue(SA.ada_facecam(plan))


class PodcastBukanKameraPemain(unittest.TestCase):
    """
    Pembeda yang dipakai HARUS menahan podcast, kalau tidak wajah di luar
    "panel" dibuang oleh WAJAH_LUAR_PANEL_MIN dan wawancara dibingkai sebagai
    gameplay. Terukur 9 Oktober 2026: tanpa penahan ini, 5 dari 6 jendela
    podcast digolongkan "klip game".
    """

    def test_penutur_podcast_bukan_kamera_pemain(self):
        """Letak median sebenarnya dari tiga podcast di penyimpanan pemiliknya."""
        for x, y, w in ((0.13, 0.40, 0.074), (0.73, 0.36, 0.083), (0.31, 0.35, 0.074),
                        (0.71, 0.40, 0.076), (0.52, 0.34, 0.094), (0.70, 0.32, 0.087)):
            with self.subTest(x=x, y=y):
                self.assertFalse(SA.ada_facecam(Plan([(x, y, w, 0.9)])))

    def test_wajah_besar_di_pojok_bukan_kamera(self):
        """Orang yang duduk di tepi layar wajahnya jauh lebih lebar."""
        self.assertFalse(SA.ada_facecam(Plan([(0.86, 0.82, 0.20, 1.0)])))

    def test_wajah_pojok_yang_sekejap_bukan_kamera(self):
        """Kamera pemain menyala sepanjang klip; wajah gambar muncul sebentar."""
        self.assertFalse(SA.ada_facecam(Plan([(0.86, 0.12, 0.051, 0.22)])))

    def test_tanpa_wajah_sama_sekali(self):
        self.assertFalse(SA.ada_facecam(Plan([])))
        self.assertFalse(SA.ada_facecam(None))


class PanelHanyaGeometri(unittest.TestCase):
    """
    `panel_kecil_pada` tidak boleh memutuskan ADA-tidaknya kamera pemain.

    Dua pembeda dari pemindai panel sudah diukur dan ditolak: jumlah
    perpindahan per menit (gameplay 0,4-36,4 vs podcast 17-44) dan sebaran
    letaknya (gameplay 0,00-1,10 vs podcast 0,35-0,83). Keduanya bertumpuk.
    """

    def test_panel_yang_berpindah_pindah_tetap_diberikan(self):
        waktu = [{"t": float(i), "facecam": {"x": 10.0 + i, "y": 70.0,
                                             "w": 18.0, "h": 24.0}}
                 for i in range(20)]
        self.assertIsNotNone(SA.panel_kecil_pada(waktu))

    def test_panel_besar_tetap_ditolak(self):
        """Yang masih dinilai di sini cuma luasnya: panel selayar bukan pojok."""
        waktu = [{"t": 0.0, "facecam": {"x": 10.0, "y": 10.0, "w": 60.0, "h": 60.0}}]
        panel = SA.panel_kecil_pada(waktu)
        self.assertIsNone(panel(0.0))

    def test_tanpa_data_tidak_ada_panel(self):
        self.assertIsNone(SA.panel_kecil_pada([]))
        self.assertIsNone(SA.panel_kecil_pada(None))
