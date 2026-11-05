"""
JOB-4 bagian 15: batas modul Montase.

Montase boleh memakai layanan bersama OmniClip, tapi tidak boleh menyentuh isi
Studio Klip. Kalau sesuatu di Studio Klip dibutuhkan, ia dipindah ke tempat
bersama lebih dulu, bukan diimpor dari tempatnya sekarang.
"""

import re
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
BACKEND_MONTASE = AKAR / "backend" / "app" / "montase"
FRONTEND_MONTASE = AKAR / "frontend" / "src" / "features" / "montase"

# Paket tambahan untuk komponen animasi AI (JOB-4 bagian 21).
TAMBAHAN_AI = {"@remotion/shapes", "@remotion/paths", "@remotion/noise", "@remotion/zod-types",
               "@remotion/transitions"}

DILARANG_PY = (
    "services.pipeline", "services.render", "services.sutradara", "services.sutradara_ai",
    "routers.clips", "routers.projects", "services import pipeline", "services import render",
    "services import sutradara",
)


def _impor_js(teks: str) -> list[str]:
    return re.findall(r"""(?:from\s+|import\s*\(\s*|^import\s+)['"]([^'"]+)['"]""", teks, re.M)


class BatasBackend(unittest.TestCase):
    def test_tidak_mengimpor_studio_klip(self):
        for berkas in BACKEND_MONTASE.rglob("*.py"):
            teks = berkas.read_text(encoding="utf-8")
            for dilarang in DILARANG_PY:
                self.assertNotIn(dilarang, teks, f"{berkas.name} mengimpor {dilarang}")


class BatasFrontend(unittest.TestCase):
    def test_tidak_mengimpor_features_studio(self):
        for berkas in FRONTEND_MONTASE.rglob("*.js*"):
            for impor in _impor_js(berkas.read_text(encoding="utf-8")):
                self.assertNotIn("studio", impor.split("/"), f"{berkas.name}: {impor}")

    def test_komposisi_hanya_paket_yang_ada_di_mesin(self):
        """
        Mesin membundel komposisi dengan alias ke node_modules miliknya, dan
        hanya paket-paket ini yang dipaksa ke sana (montase-mesin/src/bundel.mjs).
        """
        boleh = {"react", "react/jsx-runtime", "remotion", "@remotion/media", "zod", *TAMBAHAN_AI}
        komposisi = FRONTEND_MONTASE / "komposisi"
        for berkas in komposisi.rglob("*.js*"):
            if ".test." in berkas.name:
                continue
            for impor in _impor_js(berkas.read_text(encoding="utf-8")):
                if impor.startswith("."):
                    tujuan = (berkas.parent / impor).resolve()
                    self.assertTrue(tujuan.is_relative_to(komposisi.resolve()),
                                    f"{berkas.name} keluar dari komposisi/: {impor}")
                else:
                    self.assertIn(impor, boleh, f"{berkas.name}: {impor}")

    def test_paket_dipaksa_mesin_sama_dengan_daftar(self):
        teks = (AKAR / "montase-mesin" / "src" / "bundel.mjs").read_text(encoding="utf-8")
        cocok = re.search(r"const DIPAKSA = \[([^\]]+)\]", teks)
        dipaksa = set(re.findall(r"'([^']+)'", cocok.group(1)))
        self.assertEqual(dipaksa, {"react", "react-dom", "remotion", "@remotion/media", "zod", *TAMBAHAN_AI})

    def test_impor_komponen_ai_sama_di_peramban_dan_mesin(self):
        """Yang lolos pemeriksa mesin harus bisa dimuat pratinjau, dan sebaliknya."""
        mesin = (AKAR / "montase-mesin" / "src" / "kompilasi.mjs").read_text(encoding="utf-8")
        cocok = re.search(r"IMPOR_DIIZINKAN = new Set\(\[([^\]]+)\]", mesin)
        di_mesin = set(re.findall(r"'([^']+)'", cocok.group(1)))
        peramban = (FRONTEND_MONTASE / "komposisi" / "muatKomponen.js").read_text(encoding="utf-8")
        blok = re.search(r"MODUL_DIIZINKAN = Object.freeze\(\{(.+?)\}\)", peramban, re.S).group(1)
        di_peramban = set(re.findall(r"'([^']+)'\s*:", blok))
        self.assertEqual(di_mesin, di_peramban)


class VersiRemotionSama(unittest.TestCase):
    """Aturan Remotion: semua paket remotion/@remotion/* versi yang SAMA PERSIS."""

    def test_frontend_dan_mesin(self):
        import json
        versi = {}
        for berkas in (AKAR / "frontend" / "package.json", AKAR / "montase-mesin" / "package.json"):
            data = json.loads(berkas.read_text(encoding="utf-8"))
            for bagian in ("dependencies", "devDependencies"):
                for nama, v in data.get(bagian, {}).items():
                    if nama == "remotion" or nama.startswith("@remotion/"):
                        versi[f"{berkas.parent.name}:{nama}"] = v
        self.assertTrue(versi)
        self.assertEqual(len(set(versi.values())), 1, versi)
        self.assertRegex(next(iter(versi.values())), r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
