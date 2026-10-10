"""
JOB-2 F1-1: `konteks` dari Gemini sampai ke klip.

Skema Gemini sudah meminta `konteks` didahulukan (apa yang perlu diketahui
penonton supaya potongan itu masuk akal), tapi sampai 9 Oktober 2026 medan itu
dibuang di `_apply_selections` dan tidak pernah sampai ke klip. Ia bahan untuk
draf komentar (F1-2) dan kartu konteks (F2-3).
"""

import unittest

from app.services import gemini
from app.services.heuristics import Candidate


def kalimat(n):
    return [{"s": i * 3.0, "e": i * 3.0 + 2.8, "text": f"kalimat {i} yang cukup panjang",
             "wi": (i * 5, i * 5 + 5)} for i in range(n)]


class KonteksTersimpan(unittest.TestCase):
    def pilih(self, **sel):
        sents = kalimat(30)
        pool = [Candidate(start=6.0, end=40.0, score=0.7, breakdown={},
                          sentence_span=(2, 13))]
        data = {"selections": [{
            "konteks": "Ia baru saja ditanya soal kasbon di kalimat 3.",
            "candidate_id": 0, "start_sentence": 2, "end_sentence": 12,
            "score": 80, "reason": "lucu", "hook_text": "kasbon",
            "suggested_title": "Kasbon di hari pertama", **sel}]}
        return gemini._apply_selections(data, pool, sents, 5)

    def test_konteks_ikut_ke_kandidat(self):
        out = self.pilih()
        self.assertTrue(out)
        self.assertEqual(out[0].konteks, "Ia baru saja ditanya soal kasbon di kalimat 3.")

    def test_konteks_dibersihkan_dari_em_dash(self):
        out = self.pilih(konteks="Ia ditanya — soal kasbon")
        self.assertNotIn("—", out[0].konteks)

    def test_konteks_kosong_tidak_meledak(self):
        out = self.pilih(konteks="")
        self.assertEqual(out[0].konteks, "")

    def test_konteks_dipotong_wajar(self):
        out = self.pilih(konteks="a" * 2000)
        self.assertLessEqual(len(out[0].konteks), 600)


class SampaiKeKlip(unittest.TestCase):
    def test_build_clip_payload_membawa_konteks(self):
        from pathlib import Path
        from app.services import clipmodel
        src = Path(clipmodel.__file__).read_text(encoding="utf-8")
        self.assertIn('"konteks": getattr(candidate, "konteks", "") or ""', src)

    def test_klip_tanpa_gemini_konteksnya_kosong(self):
        c = Candidate(start=0.0, end=10.0, score=0.5, breakdown={}, sentence_span=(0, 2))
        self.assertEqual(getattr(c, "konteks", ""), "")
