"""JOB-2 F2-4: sambungan antar potongan tanpa mengubah panjang klip."""

import unittest

from app.services.render import _build_segment_graph

DUA = [{"start": 10.0, "end": 14.0}, {"start": 50.0, "end": 54.0}]


class Transisi(unittest.TestCase):
    def test_potong_hanya_fade_audio_kecil(self):
        _, graf, _ = _build_segment_graph(DUA, 30, "potong")
        self.assertNotIn("fade=t=in:st=0:d=0.120", graf)
        self.assertIn("afade=t=out", graf)
        self.assertIn("afade=t=in", graf)

    def test_celup_meredup_di_sambungan_saja(self):
        _, graf, _ = _build_segment_graph(DUA, 30, "celup")
        # Potongan pertama hanya keluar, potongan kedua hanya masuk.
        v0 = graf.split(";")[0]
        self.assertIn("fade=t=out:st=3.880:d=0.120:color=black", v0)
        self.assertNotIn("fade=t=in", v0)
        self.assertIn("fade=t=in:st=0:d=0.120:color=black", graf)
        # Tidak ada xfade: panjang klip tidak boleh berubah.
        self.assertNotIn("xfade", graf)
        self.assertIn("concat=n=2", graf)

    def test_satu_potongan_tanpa_efek(self):
        _, graf, _ = _build_segment_graph(DUA[:1], 30, "kilat")
        self.assertNotIn("fade", graf)


if __name__ == "__main__":
    unittest.main()
