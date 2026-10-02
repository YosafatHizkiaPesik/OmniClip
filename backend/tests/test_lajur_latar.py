"""
Pemanasan bingkai tidak boleh menahan Render.

Sampai 2 Oktober 2026 keduanya berbagi lajur `cpu` yang lebarnya satu.
Pemanasan dua belas klip berjalan sembilan sampai dua belas menit, dan selama
itu menekan tombol Render berarti menunggu di belakang pekerjaan yang tidak
diminta siapa pun — pekerjaan yang justru sengaja dirancang mengalah.
"""

import unittest

from app.config import LANE_LIMITS


class LajurLatar(unittest.TestCase):
    def test_lajurnya_ada_dan_lebarnya_satu(self):
        self.assertIn("latar", LANE_LIMITS)
        self.assertEqual(LANE_LIMITS["latar"], 1)

    def test_pemanasan_bingkai_tidak_di_lajur_render(self):
        """Dibaca dari pendaftarannya, bukan dari niat."""
        from pathlib import Path
        main = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(
            encoding="utf-8")
        self.assertIn('queue.register("bingkai_awal", run_bingkai_awal, lane="latar")',
                      main)
        self.assertIn('queue.register("render", run_render, lane="cpu")', main)

    def test_pemanasan_tetap_minggir_di_sela_klip(self):
        """
        Lajur sendiri bukan izin menguasai mesin. Yang menjaga mesin tetap
        mengerjakan satu hal berat pada satu waktu adalah `gerbang_cpu`, dan
        pemanasan harus tetap melepaskannya di sela tiap klip — kalau tidak,
        lajur baru ini justru membuat dua pekerjaan berat berebut.
        """
        from pathlib import Path
        awal = (Path(__file__).resolve().parents[1] / "app" / "services"
                / "bingkai_awal.py").read_text(encoding="utf-8")
        self.assertIn("ctx.mengalah_cpu(", awal)

    def test_lajur_yang_dipakai_semuanya_dikenal(self):
        """Lajur yang tidak ada di LANE_LIMITS membuat pendaftarannya melempar."""
        from pathlib import Path
        import re
        main = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(
            encoding="utf-8")
        for lane in set(re.findall(r'lane="([a-z]+)"', main)):
            with self.subTest(lane=lane):
                self.assertIn(lane, LANE_LIMITS)


if __name__ == "__main__":
    unittest.main()
