"""
Pembaruan yang tahan koneksi putus, dan yang memeriksa keaslian berkasnya.

Keluhan pengguna: "saat update versi omniclip gagal dan ketika dibuka tidak ada
versi terbaru yang bisa didownload". Arsip rilis 260-320 MB, dan sebelum ini:

  - satu putusan berarti mulai dari nol lagi;
  - tidak ada percobaan ulang, orangnya harus menekan tombol lagi;
  - berkas `.sha256` diterbitkan bersama tiap arsip tapi TIDAK PERNAH dibaca —
    yang diperiksa hanya ukuran, dengan kelonggaran 4 KB.

Terukur di GitHub pada rilis 1.1.0: masing-masing arsip baru SATU kali berhasil
diunduh. Uji ini menjalankan unduhan sungguhan terhadap server lokal yang
sengaja memutus sambungan di tengah jalan.
"""

import hashlib
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.services import updater as U


def _server(data: bytes, putus_sekali: bool, abaikan_range: bool = False):
    sha = hashlib.sha256(data).hexdigest()
    catat = {"permintaan": [], "putus": putus_sekali}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.endswith(".sha256"):
                b = f"{sha}  arsip.tar.gz\n".encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            mulai = 0
            rg = self.headers.get("Range")
            if rg and not abaikan_range:
                mulai = int(rg.split("=")[1].split("-")[0])
                self.send_response(206)
                self.send_header("Content-Range",
                                 f"bytes {mulai}-{len(data) - 1}/{len(data)}")
            else:
                self.send_response(200)
            sisa = data[mulai:]
            self.send_header("Content-Length", str(len(sisa)))
            self.end_headers()
            catat["permintaan"].append(mulai)
            if catat["putus"] and mulai == 0:
                catat["putus"] = False
                self.wfile.write(sisa[: len(sisa) // 2])
                self.wfile.flush()
                self.connection.shutdown(2)
                return
            self.wfile.write(sisa)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/arsip.tar.gz", sha, catat


class _Ctx:
    def check_cancelled(self):
        pass

    def progress(self, *a, **k):
        pass


class PembaruTangguh(unittest.TestCase):
    def setUp(self):
        self._jeda = U.UNDUH_JEDA
        U.UNDUH_JEDA = (0, 0, 0, 0)
        self.data = os.urandom(3 * 1024 * 1024)
        self.arsip = Path(tempfile.mkdtemp()) / "arsip.tar.gz"

    def tearDown(self):
        U.UNDUH_JEDA = self._jeda

    def test_melanjutkan_dari_titik_putus(self):
        srv, url, sha, catat = _server(self.data, putus_sekali=True)
        try:
            U._unduh_berlanjut(_Ctx(), url, self.arsip, len(self.data))
        finally:
            srv.shutdown()
        self.assertEqual(self.arsip.read_bytes(), self.data)
        # Permintaan kedua dimulai dari tengah, bukan dari nol.
        self.assertEqual(len(catat["permintaan"]), 2)
        self.assertEqual(catat["permintaan"][0], 0)
        self.assertGreater(catat["permintaan"][1], 0)

    def test_server_yang_mengabaikan_range_tidak_menyambung_dua_salinan(self):
        """
        Bila server menjawab 200 alih-alih 206, menulis di ujung berkas akan
        menyambung dua salinan jadi satu arsip rusak. Harus mulai dari awal.
        """
        srv, url, sha, _ = _server(self.data, putus_sekali=True, abaikan_range=True)
        try:
            U._unduh_berlanjut(_Ctx(), url, self.arsip, len(self.data))
        finally:
            srv.shutdown()
        self.assertEqual(self.arsip.read_bytes(), self.data)

    def test_sidik_resmi_dibaca_dan_berkas_rusak_ditolak(self):
        srv, url, sha, _ = _server(self.data, putus_sekali=False)
        try:
            self.assertEqual(U._sha256_resmi(url), sha)
        finally:
            srv.shutdown()
        rusak = bytearray(self.data)
        rusak[1000] ^= 0xFF
        self.arsip.write_bytes(bytes(rusak))
        # Ukurannya sama persis — pemeriksaan ukuran lama meloloskannya.
        self.assertEqual(self.arsip.stat().st_size, len(self.data))
        self.assertNotEqual(U._sha256_berkas(self.arsip), sha)

    def test_berkas_yang_ditarik_tidak_dicoba_berulang(self):
        """404 berarti rilisnya ditarik; lima kali mencoba tidak mengubah itu."""
        class H(BaseHTTPRequestHandler):
            n = 0
            def log_message(self, *a): pass
            def do_GET(self):
                H.n += 1
                self.send_response(404); self.end_headers()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with self.assertRaises(RuntimeError) as ctx:
                U._unduh_berlanjut(_Ctx(), f"http://127.0.0.1:{srv.server_port}/x",
                                   self.arsip, 1000)
        finally:
            srv.shutdown()
        self.assertEqual(H.n, 1)
        self.assertIn("404", str(ctx.exception))

    def test_tanpa_berkas_sha256_tidak_menolak(self):
        """Rilis lama belum punya .sha256; ketiadaannya bukan alasan menolak."""
        self.assertIsNone(U._sha256_resmi("http://127.0.0.1:9/tidak-ada"))

    def test_sidik_diperiksa_sebelum_dibongkar(self):
        sumber = (Path(__file__).resolve().parents[1] / "app" / "services"
                  / "updater.py").read_text(encoding="utf-8")
        badan = sumber.split("def _unduh_dan_bongkar")[1].split("\ndef ")[0]
        self.assertLess(badan.index("_sha256_resmi"), badan.index("_bongkar("))


if __name__ == "__main__":
    unittest.main()
