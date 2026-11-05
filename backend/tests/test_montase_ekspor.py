"""
JOB-4 M1.9: ekspor proyek Montase ke Klip jadi.

Bagian pertama tanpa mesin: nama berkas, isi sidecar, dan penolakan yang
jelas (linimasa kosong, berkas bahan hilang). Bagian kedua mengekspor sungguhan
lewat Mesin Montase bila mesin dan Chrome tersedia di komputer ini (lewat
`OMNICLIP_MONTASE_BROWSER` atau unduhan `siapkan`), dan dilewati bila tidak.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.db import get_conn, run_migrations
from app.montase import bahan as bahan_svc
from app.montase import ekspor, mesin, router, uji
from app.services import aset as aset_svc
from app.services import profil

PID = 987_611


def _bersihkan():
    c = get_conn()
    c.execute("DELETE FROM montase_proyek WHERE profil_id = ?", (PID,))
    c.execute("DELETE FROM montase_bahan WHERE profil_id = ?", (PID,))


class Dasar(unittest.TestCase):
    def setUp(self):
        run_migrations()
        _bersihkan()
        self.addCleanup(_bersihkan)
        tanda = profil.setel(PID)
        self.addCleanup(profil.pulihkan, tanda)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder_klip = Path(self._tmp.name) / "klip"
        p = mock.patch.object(profil, "folder_klip",
                              side_effect=lambda pid, buat=False: self._folder(buat))
        p.start()
        self.addCleanup(p.stop)

    def _folder(self, buat):
        if buat:
            self.folder_klip.mkdir(parents=True, exist_ok=True)
        return self.folder_klip

    def proyek(self):
        return router.buat_proyek(router.ProyekBaru(nama="Top 5: Momen Lucu!", preset="shorts"))


class TanpaMesin(Dasar):
    def test_nama_berkas_aman(self):
        nama = ekspor.nama_berkas("Top 5: Momen Lucu! / bagian 2", 0)
        self.assertRegex(nama, r"^Top-5-Momen-Lucu-bagian-2_montase_\d{4}-\d\d-\d\d_\d{4}\.mp4$")
        self.assertTrue(ekspor.nama_berkas("???").startswith("Montase_montase_"))

    def test_sidecar_dikenali_klip_jadi(self):
        dok = router.ambil_proyek(self.proyek()["id"])["dokumen"]
        s = ekspor.sidecar(dok, pid=PID, berkas="x.mp4", detik=12.5)
        for kunci in ("jenis", "montase_id", "file_name", "title", "hashtags", "duration",
                      "aspect_ratio", "subtitles", "sumber_banyak", "suara_sintetis", "created_at"):
            self.assertIn(kunci, s)
        self.assertEqual((s["jenis"], s["aspect_ratio"], s["duration"]), ("montase", "9:16", 12.5))
        self.assertEqual((s["subtitles"], s["suara_sintetis"]), ([], False))

    def test_sidecar_membawa_tulisan_dan_narasi(self):
        dok = router.ambil_proyek(self.proyek()["id"])["dokumen"]
        lajur = {l["jenis"]: l for l in dok["lajur"]}
        lajur["motion"]["item"].append({"id": "m1", "jenis": "motion", "komponen": "ko_hitung_mundur",
                                        "mulai": 0, "durasi": 60, "props": {"angka": 5, "judul": "Kucing jatuh"}})
        lajur["audio"]["item"].append({"id": "a1", "jenis": "audio", "bahan": "bh_x", "mulai": 0, "durasi": 45,
                                       "narasi": {"teks": "Nomor 5. Kucing jatuh.", "suara": "edge-ardi"}})
        lajur["teks"]["item"].append({"id": "t1", "jenis": "teks", "mulai": 90, "durasi": 30, "teks": "Ikuti!"})
        s = ekspor.sidecar(dok, pid=PID, berkas="x.mp4", detik=4)
        self.assertEqual([b["text"] for b in s["subtitles"]], ["Kucing jatuh", "Ikuti!"])
        self.assertEqual(s["subtitles"][1]["start"], 3.0)
        self.assertEqual(s["hook_text"], "Kucing jatuh")
        self.assertTrue(s["suara_sintetis"])
        # Narasi yang sudah direkam pemiliknya (teleprompter, JOB-5 O2): bukan sintetis.
        lajur["audio"]["item"][0]["narasi"]["direkam"] = True
        s = ekspor.sidecar(dok, pid=PID, berkas="x.mp4", detik=4)
        self.assertFalse(s["suara_sintetis"])
        self.assertEqual([x["jenis"] for x in s["lapisan"] if x["t"] == 0 and x["d"] == 1.5], ["rekam"])
        self.assertEqual([b["text"] for b in s["subtitles"]], ["Kucing jatuh", "Ikuti!"])

    def test_linimasa_kosong_ditolak(self):
        with self.assertRaisesRegex(ekspor.GagalEkspor, "kosong"):
            ekspor.ekspor(PID, self.proyek()["id"])

    def test_proyek_tidak_ada(self):
        with self.assertRaisesRegex(ekspor.GagalEkspor, "tidak ditemukan"):
            ekspor.ekspor(PID, "mt_tidakada")

    def test_bahan_hilang_disebut_namanya(self):
        p = self.proyek()
        dok = router.ambil_proyek(p["id"])["dokumen"]
        from app.repos import montase as repo
        b = repo.catat_bahan(PID, {"asal": "aset", "rujukan": "0" * 16, "nama": "Video Hilang",
                                   "rel_path": "/tidak/ada.mp4", "jenis": "video", "durasi": 2})
        dok["bahan"] = {b["id"]: {"jenis": "video", "nama": "Video Hilang", "durasi": 2}}
        dok["lajur"][0]["item"] = [{"id": "i1", "jenis": "video", "bahan": b["id"],
                                    "mulai": 0, "durasi": 60}]
        router.simpan_proyek(p["id"], router.SimpanProyek(dokumen=dok, revisi=1))
        with self.assertRaisesRegex(ekspor.GagalEkspor, "Video Hilang"):
            ekspor.ekspor(PID, p["id"])


def _ada_chrome() -> bool:
    if not (mesin.status()["siap"] and shutil.which("ffmpeg")):
        return False
    return bool(mesin.jalur_browser() or mesin._browser_terunduh())


@unittest.skipUnless(_ada_chrome(), "Mesin Montase atau Chrome belum siap di komputer ini")
class EksporSungguhan(Dasar):
    def test_tiga_video_berurutan_jadi_satu_mp4_di_klip_jadi(self):
        bahan = []
        for i, warna in enumerate(("red", "green", "blue")):
            berkas = Path(self._tmp.name) / f"warna{i}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            f"color=c={warna}:size=540x960:rate=30:duration=1", "-f", "lavfi",
                            "-i", "sine=frequency=440:duration=1", "-c:v", "libx264", "-pix_fmt",
                            "yuv420p", "-c:a", "aac", "-shortest", str(berkas)], check=True)
            a = aset_svc.simpan_unggahan(berkas, f"warna{i}.mp4")
            self.addCleanup(aset_svc.hapus, a["id"])
            b = bahan_svc.rujuk("impor", a["id"])
            self.addCleanup(shutil.rmtree, bahan_svc.folder(b["id"]), True)
            bahan.append(b)

        p = self.proyek()
        dok = router.ambil_proyek(p["id"])["dokumen"]
        for n, b in enumerate(bahan):
            dok["bahan"][b["id"]] = {"jenis": "video", "nama": b["nama"], "durasi": 1}
            dok["lajur"][0]["item"].append({"id": f"i{n}", "jenis": "video", "bahan": b["id"],
                                            "mulai": n * 30, "durasi": 30, "isi": "cover"})
        router.simpan_proyek(p["id"], router.SimpanProyek(dokumen=dok, revisi=1))

        with uji.server_sementara() as dasar:
            hasil = ekspor.ekspor(PID, p["id"], dasar_url=dasar)
        mp4 = self.folder_klip / hasil["berkas"]
        self.assertTrue(mp4.is_file())
        meta = json.loads(mp4.with_suffix(".json").read_text())
        self.assertEqual((meta["jenis"], meta["montase_id"]), ("montase", p["id"]))
        info = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,nb_frames",
             "-of", "json", str(mp4)], capture_output=True, text=True).stdout)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        self.assertEqual((v["width"], v["height"]), (1080, 1920))
        self.assertEqual(int(v["nb_frames"]), 90)
        # Bingkai tengah tiap potongan berwarna sesuai urutannya.
        for detik, warna in ((0.5, (255, 0, 0)), (1.5, (0, 128, 0)), (2.5, (0, 0, 255))):
            px = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(detik), "-i", str(mp4),
                                 "-frames:v", "1", "-vf", "crop=2:2:540:960,scale=1:1",
                                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                capture_output=True).stdout
            for nyata, harap in zip(px, warna):
                self.assertLess(abs(nyata - harap), 40, (detik, list(px), warna))


if __name__ == "__main__":
    unittest.main()
