"""
JOB-4 M0.3 dan M0.5: Python menjalankan Mesin Montase.

Bagian pertama memakai skrip Node palsu, jadi menguji `mesin.jalankan` sendiri:
kemajuan sampai ke pemanggil, galat jadi GagalMesin, pembatalan dan batas
waktu benar-benar mematikan prosesnya. Bagian kedua memakai mesin sungguhan
(kompilasi.mjs) bila `montase-mesin/` sudah dipasang (`npm ci`), dan dilewati
bila belum.
"""

import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from app.montase import mesin

NODE = shutil.which("node")

SKRIP_GEMA = r"""
import process from 'node:process';
const potong = []; for await (const p of process.stdin) potong.push(p);
const m = JSON.parse(Buffer.concat(potong).toString() || '{}');
const tulis = (o) => process.stdout.write(JSON.stringify(o) + '\n');
if (m.mode === 'galat') { tulis({ galat: 'sengaja gagal' }); process.exit(1); }
if (m.mode === 'mati') { process.stderr.write('jejak tumpukan palsu\n'); process.exit(3); }
if (m.mode === 'lama') { tulis({ tahap: 'menunggu' }); await new Promise((r) => setTimeout(r, 60000)); }
for (let i = 1; i <= 3; i++) tulis({ kemajuan: i / 3, bingkai: i });
process.stdout.write('baris bukan json\n');
tulis({ selesai: true, gema: m.isi ?? null, cwd: process.cwd() });
"""


@unittest.skipUnless(NODE, "node tidak ada di PATH")
class Jalankan(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        paket = Path(self._tmp.name)
        (paket / "src").mkdir()
        (paket / "src" / "gema.mjs").write_text(SKRIP_GEMA, encoding="utf-8")
        self.data = paket / "data"
        self._p = [mock.patch.object(mesin, "folder_paket", return_value=paket),
                   mock.patch.object(mesin, "jalur_node", return_value=NODE),
                   mock.patch.object(mesin, "STORAGE_DIR", self.data)]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()
        self._tmp.cleanup()

    def test_kemajuan_dan_hasil(self):
        kabar = []
        hasil = mesin.jalankan("gema", {"isi": "halo é"}, kabar=kabar.append)
        self.assertEqual((hasil["selesai"], hasil["gema"]), (True, "halo é"))
        self.assertEqual([k["bingkai"] for k in kabar], [1, 2, 3])

    def test_berjalan_di_folder_kerja_data(self):
        """
        Chrome diunduh Remotion ke node_modules/.remotion milik package.json
        terdekat dari CWD. CWD harus folder kerja di folder data, bukan folder
        paket (yang di aplikasi terbungkus ada di dalam folder aplikasi).
        """
        hasil = mesin.jalankan("gema", {})
        kerja = self.data / "mesin_montase" / "kerja"
        self.assertEqual(Path(hasil["cwd"]).resolve(), kerja.resolve())
        self.assertTrue((kerja / "package.json").is_file())

    def test_baris_galat_jadi_gagal_mesin(self):
        with self.assertRaisesRegex(mesin.GagalMesin, "sengaja gagal"):
            mesin.jalankan("gema", {"mode": "galat"})

    def test_kode_keluar_bukan_nol_membawa_stderr(self):
        with self.assertRaisesRegex(mesin.GagalMesin, "jejak tumpukan palsu"):
            mesin.jalankan("gema", {"mode": "mati"})

    def test_batal_mematikan_proses(self):
        mulai = time.monotonic()
        with self.assertRaises(mesin.Dibatalkan):
            mesin.jalankan("gema", {"mode": "lama"}, batal=lambda: time.monotonic() - mulai > 0.5)
        self.assertLess(time.monotonic() - mulai, 15)

    def test_batas_waktu(self):
        mulai = time.monotonic()
        with self.assertRaisesRegex(mesin.GagalMesin, "batas"):
            mesin.jalankan("gema", {"mode": "lama"}, batas_detik=1)
        self.assertLess(time.monotonic() - mulai, 15)


class TanpaMesin(unittest.TestCase):
    def test_pesan_jelas_bila_belum_terpasang(self):
        with mock.patch.object(mesin, "folder_paket", return_value=None):
            with self.assertRaisesRegex(mesin.GagalMesin, "belum terpasang"):
                mesin.jalankan("render", {})

    def test_status_lengkap(self):
        s = mesin.status()
        for kunci in ("node", "versi_node", "paket", "bundel", "browser", "siap"):
            self.assertIn(kunci, s)
        self.assertEqual(s["siap"], bool(s["node"] and s["paket"] and s["bundel"]))

    def test_node_lama_ditolak(self):
        self.assertFalse(mesin._cukup_baru("20.11.0"))
        self.assertTrue(mesin._cukup_baru("22.23.4"))
        self.assertFalse(mesin._cukup_baru(None))


BAIK = (Path(__file__).resolve().parents[2] / "montase-mesin" / "uji" / "komponen_ai.jsx")


@unittest.skipUnless(NODE and mesin.folder_paket(), "montase-mesin belum dipasang (npm ci)")
class KompilasiSungguhan(unittest.TestCase):
    def test_komponen_uji_lolos(self):
        hasil = mesin.kompilasi(BAIK.read_text(encoding="utf-8"))
        self.assertTrue(hasil["lolos"], hasil)
        self.assertEqual(sorted(hasil["ekspor"]),
                         ["contohProps", "durasiBawaan", "kategori", "skema"])
        self.assertRegex(hasil["js"], r"""require\(['"]remotion['"]\)""")

    def test_kode_berbahaya_ditolak_dengan_alasan(self):
        jahat = (
            'import fs from "fs";\n'
            "export default function A() {\n"
            '  fetch("/api/settings"); fs.readFileSync("x");\n'
            "  const w = window.parent; const t = Date.now();\n"
            '  const f = ({}).constructor.constructor("return 1");\n'
            "  return Math.random();\n"
            "}\n"
        )
        hasil = mesin.kompilasi(jahat)
        self.assertFalse(hasil["lolos"])
        teks = json.dumps(hasil["masalah"])
        for harus in ('fs', 'fetch', 'window', 'Date', 'constructor', 'Math.random'):
            self.assertIn(harus, teks)

    def test_tanpa_ekspor_bawaan_ditolak(self):
        hasil = mesin.kompilasi("export const a = 1;")
        self.assertFalse(hasil["lolos"])
        self.assertIn("export default", json.dumps(hasil["masalah"]))

    def test_sintaks_rusak_tidak_melempar(self):
        hasil = mesin.kompilasi("export default function ( {")
        self.assertFalse(hasil["lolos"])


if __name__ == "__main__":
    unittest.main()
