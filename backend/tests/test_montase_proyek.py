"""
JOB-4 M1.1-M1.3 dan M1.6: skema dokumen, proyek per profil dengan revisi,
setelan beta, dan bahan (rujuk, persiapan, token).

Memakai basis data pengembangan seperti tes lain di repo ini, dengan nomor
profil khusus tes supaya tidak bercampur dengan data pemilik, dan semua yang
dibuat dibersihkan sesudahnya.
"""

import asyncio
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.db import get_conn, run_migrations
from app.errors import AppError, InvalidInput, NotFound
from app.montase import bahan as bahan_svc
from app.montase import router, skema
from app.montase import token as token_svc
from app.services import aset as aset_svc
from app.services import profil

PID_UJI = 987_601
PID_LAIN = 987_602


def _bersihkan_db():
    c = get_conn()
    for pid in (PID_UJI, PID_LAIN):
        c.execute("DELETE FROM montase_proyek WHERE profil_id = ?", (pid,))
        c.execute("DELETE FROM montase_bahan WHERE profil_id = ?", (pid,))


class DenganProfil(unittest.TestCase):
    pid = PID_UJI

    def setUp(self):
        run_migrations()
        _bersihkan_db()
        self.addCleanup(_bersihkan_db)
        tanda = profil.setel(self.pid)
        self.addCleanup(profil.pulihkan, tanda)


class Skema(unittest.TestCase):
    def dok(self, **ubah):
        d = skema.dokumen_baru("mt_uji", "Uji", lebar=1080, tinggi=1920, fps=30)
        d.update(ubah)
        return d

    def test_proyek_baru_sah_dengan_empat_lajur(self):
        d = self.dok()
        self.assertEqual([l["jenis"] for l in d["lajur"]], ["video", "motion", "teks", "audio"])
        self.assertEqual(d["durasi"], 1)

    def test_ukuran_ganjil_dan_fps_aneh_ditolak(self):
        for kanvas in ({"lebar": 1081, "tinggi": 1920, "fps": 30},
                       {"lebar": 1080, "tinggi": 1920, "fps": 29}):
            with self.assertRaises(skema.GagalSkema):
                skema.periksa(self.dok(kanvas=kanvas))

    def test_rujukan_dan_id_diperiksa(self):
        d = self.dok()
        d["lajur"][0]["item"] = [
            {"id": "a", "jenis": "video", "mulai": 0, "durasi": 30, "bahan": "bh_tidakada"},
            {"id": "a", "jenis": "teks", "mulai": 0, "durasi": 30, "teks": "x"},
        ]
        with self.assertRaises(skema.GagalSkema) as k:
            skema.periksa(d)
        teks = " ".join(k.exception.pesan)
        self.assertIn("tidak ada di dokumen.bahan", teks)
        self.assertIn("dipakai dua kali", teks)
        self.assertIn("tidak boleh di lajur video", teks)

    def test_versi_lebih_baru_ditolak(self):
        with self.assertRaisesRegex(skema.GagalSkema, "lebih baru"):
            skema.periksa(self.dok(versi=skema.VERSI_DOKUMEN + 1))

    def test_kolom_tak_dikenal_dipertahankan_dan_durasi_dihitung_ulang(self):
        d = self.dok(kolom_masa_depan={"a": 1}, durasi=99999)
        d["bahan"] = {"bh_1": {"jenis": "video", "durasi": 5}}
        d["lajur"][0]["item"] = [{"id": "i1", "jenis": "video", "mulai": 30, "durasi": 60,
                                  "bahan": "bh_1", "filter_baru": "x"}]
        hasil = skema.periksa(d)
        self.assertEqual(hasil["kolom_masa_depan"], {"a": 1})
        self.assertEqual(hasil["lajur"][0]["item"][0]["filter_baru"], "x")
        self.assertEqual(hasil["durasi"], 90)

    def test_dokumen_raksasa_ditolak(self):
        with self.assertRaisesRegex(skema.GagalSkema, "MB"):
            skema.periksa(self.dok(sampah="x" * (skema.BATAS_BITA + 1)))


class Proyek(DenganProfil):
    def buat(self, **kw):
        return router.buat_proyek(router.ProyekBaru(**{"nama": "Top 5", "preset": "shorts", **kw}))

    def test_buat_ambil_daftar(self):
        p = self.buat()
        self.assertEqual(p["kanvas"]["lebar"], 1080)
        self.assertEqual(p["revisi"], 1)
        self.assertEqual(router.ambil_proyek(p["id"])["dokumen"]["nama"], "Top 5")
        self.assertEqual([x["id"] for x in router.daftar_proyek()["proyek"]], [p["id"]])

    def test_preset_youtube_dan_preset_asing(self):
        self.assertEqual(self.buat(preset="youtube")["kanvas"]["lebar"], 1920)
        with self.assertRaises(InvalidInput):
            self.buat(preset="bioskop")

    def test_simpan_menaikkan_revisi_dan_menolak_revisi_basi(self):
        p = self.buat()
        dok = p["dokumen"] if "dokumen" in p else router.ambil_proyek(p["id"])["dokumen"]
        dok["nama"] = "Top 5 baru"
        r = router.simpan_proyek(p["id"], router.SimpanProyek(dokumen=dok, revisi=1))
        self.assertEqual(r["revisi"], 2)
        with self.assertRaises(AppError) as k:
            router.simpan_proyek(p["id"], router.SimpanProyek(dokumen=dok, revisi=1))
        self.assertEqual((k.exception.status, k.exception.code), (409, "REVISI_BENTROK"))
        self.assertEqual(router.ambil_proyek(p["id"])["nama"], "Top 5 baru")

    def test_dokumen_tidak_sah_ditolak_422(self):
        p = self.buat()
        dok = router.ambil_proyek(p["id"])["dokumen"]
        dok["kanvas"]["fps"] = 7
        with self.assertRaises(AppError) as k:
            router.simpan_proyek(p["id"], router.SimpanProyek(dokumen=dok, revisi=1))
        self.assertEqual(k.exception.status, 422)

    def test_bahan_profil_lain_ditolak(self):
        p = self.buat()
        dok = router.ambil_proyek(p["id"])["dokumen"]
        dok["bahan"] = {"bh_milikorang": {"jenis": "video", "durasi": 3}}
        with self.assertRaisesRegex(InvalidInput, "tidak ada di pustaka"):
            router.simpan_proyek(p["id"], router.SimpanProyek(dokumen=dok, revisi=1))

    def test_proyek_profil_lain_tidak_terlihat(self):
        p = self.buat()
        tanda = profil.setel(PID_LAIN)
        try:
            self.assertEqual(router.daftar_proyek()["proyek"], [])
            with self.assertRaises(NotFound):
                router.ambil_proyek(p["id"])
        finally:
            profil.pulihkan(tanda)

    def test_gandakan_dan_hapus(self):
        p = self.buat()
        salinan = router.gandakan_proyek(p["id"])
        self.assertNotEqual(salinan["id"], p["id"])
        self.assertIn("(salinan)", salinan["nama"])
        self.assertEqual(router.ambil_proyek(salinan["id"])["dokumen"]["id"], salinan["id"])
        router.hapus_proyek(p["id"])
        with self.assertRaises(NotFound):
            router.ambil_proyek(p["id"])


class Setelan(unittest.TestCase):
    def setUp(self):
        run_migrations()
        from app.repos import settings as s
        lama = s.get(router.KUNCI_AKTIF, "")
        self.addCleanup(lambda: s.set_value(router.KUNCI_AKTIF, lama) if lama
                        else s.delete(router.KUNCI_AKTIF))

    def test_bawaan_aktif_dan_bisa_dimatikan(self):
        from app.repos import settings as s
        s.delete(router.KUNCI_AKTIF)
        self.assertTrue(router.ambil_setelan()["aktif"])
        router.simpan_setelan(router.Setelan(aktif=False))
        self.assertFalse(router.ambil_setelan()["aktif"])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg tidak ada")
class Bahan(DenganProfil):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        video = Path(self._tmp.name) / "uji bahan.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=1080x1920:rate=30:duration=3", "-f", "lavfi", "-i",
                        "sine=frequency=330:duration=3", "-c:v", "libx264", "-preset",
                        "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                        str(video)], check=True)
        self.aset = aset_svc.simpan_unggahan(video, "uji bahan.mp4")
        self.addCleanup(aset_svc.hapus, self.aset["id"])

    def rujuk(self):
        b = bahan_svc.rujuk("impor", self.aset["id"])
        self.addCleanup(shutil.rmtree, bahan_svc.folder(b["id"]), True)
        return b

    def test_rujuk_membaca_metadata_tanpa_jalur(self):
        b = self.rujuk()
        self.assertEqual((b["jenis"], b["lebar"], b["tinggi"], b["ada_suara"]),
                         ("video", 1080, 1920, True))
        self.assertAlmostEqual(b["durasi"], 3.0, delta=0.2)
        self.assertNotIn("rel_path", b)
        self.assertEqual(bahan_svc.rujuk("impor", self.aset["id"])["id"], b["id"])

    def test_persiapan_membuat_turunan_dan_salinan_sunting(self):
        b = self.rujuk()
        hasil = bahan_svc.siapkan(b["id"], PID_UJI)
        d = bahan_svc.folder(b["id"])
        for nama in ("sampul.jpg", "strip.jpg", "gelombang.json", "sunting.mp4"):
            self.assertTrue((d / nama).is_file(), (nama, hasil))
        info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                               "-show_entries", "stream=width,height", "-of", "json",
                               str(d / "sunting.mp4")], capture_output=True, text=True)
        s = json.loads(info.stdout)["streams"][0]
        self.assertEqual(min(s["width"], s["height"]), bahan_svc.SUNTING_SISI)
        gel = json.loads((d / "gelombang.json").read_text())
        self.assertGreater(len(gel["puncak"]), 30)
        self.assertTrue(router.daftar_bahan()["bahan"][0]["siap"])

    def test_token_hanya_untuk_profilnya(self):
        b = self.rujuk()
        sah = token_svc.buat(router.lingkup_bahan(PID_UJI))
        r = router.berkas_bahan(sah, b["id"])
        self.assertTrue(Path(r.path).is_file())
        for tkn in (token_svc.buat(router.lingkup_bahan(PID_LAIN)), token_svc.buat("uji"),
                    "palsu.x"):
            with self.assertRaises(NotFound):
                router.berkas_bahan(tkn, b["id"])

    def test_bahan_yang_dipakai_tidak_bisa_dihapus(self):
        b = self.rujuk()
        p = router.buat_proyek(router.ProyekBaru(nama="Pakai", preset="shorts"))
        dok = router.ambil_proyek(p["id"])["dokumen"]
        dok["bahan"] = {b["id"]: {"jenis": "video", "durasi": 3}}
        dok["lajur"][0]["item"] = [{"id": "i1", "jenis": "video", "mulai": 0,
                                    "durasi": 90, "bahan": b["id"]}]
        router.simpan_proyek(p["id"], router.SimpanProyek(dokumen=dok, revisi=1))
        self.assertEqual(router.ambil_proyek(p["id"])["sampul"], b["id"])
        with self.assertRaises(AppError) as k:
            router.hapus_bahan(b["id"])
        self.assertEqual(k.exception.code, "BAHAN_DIPAKAI")
        router.hapus_proyek(p["id"])
        self.assertTrue(router.hapus_bahan(b["id"])["ok"])

    def test_asal_dan_berkas_tak_dikenal(self):
        with self.assertRaises(bahan_svc.BahanTidakSah):
            bahan_svc.rujuk("rahasia", "x")
        with self.assertRaises(bahan_svc.BahanTidakSah):
            bahan_svc.rujuk("aset", "0123456789abcdef")
        with self.assertRaises(InvalidInput):
            asyncio.run(router.sumber_bahan("rahasia"))


if __name__ == "__main__":
    unittest.main()
