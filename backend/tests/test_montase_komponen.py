"""
JOB-4 M4.3-M4.10: pemeriksa komponen animasi, revisi berversi, pustaka, dan
jalur salin-tempel. Render sungguhan lewat Mesin Montase (dilewati bila Node
atau Chrome tidak ada); AI digantikan tiruan.
"""

import shutil
import unittest
from unittest import mock

from app.db import get_conn, run_migrations
from app.montase import komponen, mesin, motion_ai, periksa
from app.repos import montase as repo
from app.services import profil

PID = 987_631

BAGUS = """
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { z } from "zod";
import { zColor } from "@remotion/zod-types";
export const skema = z.object({ teks: z.string().max(30), warna: zColor() });
export const contohProps = { teks: "Halo", warna: "#FF3355" };
export const durasiBawaan = 30;
export const kategori = "judul";
export default function A({ teks, warna }) {
  const f = useCurrentFrame();
  const x = interpolate(f, [0, 30], [0, 600], { extrapolateRight: "clamp" });
  return <AbsoluteFill><div style={{ position: "absolute", left: x, top: 800, fontSize: 160,
    color: warna, fontFamily: "sans-serif" }}>{teks}</div></AbsoluteFill>;
}
"""
DIAM = BAGUS.replace("[0, 600]", "[300, 300]")
PROPS_SALAH = BAGUS.replace('contohProps = { teks: "Halo"', 'contohProps = { teks: 5')
CSS = BAGUS.replace("fontSize: 160,", "fontSize: 160, transition: 'all 1s',")
# Dua animasi sah yang dulu salah ditolak (uji M4.9): kilat layar penuh (tiap
# bingkai satu warna, tetapi kecerahannya berubah) dan label yang masuk lalu
# diam (tidak bergerak sama sekali di 10-90% durasinya).
KILAT = BAGUS.replace(
    '<AbsoluteFill><div style={{ position: "absolute", left: x, top: 800, fontSize: 160,\n'
    '    color: warna, fontFamily: "sans-serif" }}>{teks}</div></AbsoluteFill>',
    '<AbsoluteFill style={{ background: warna, opacity: interpolate(f, [0, 12, 29], [0, 1, 0]) }} />')
MASUK_LALU_DIAM = BAGUS.replace("[0, 30], [0, 600]", "[0, 4], [0, 600]")


def _bersihkan():
    for (kid,) in get_conn().execute("SELECT DISTINCT id FROM montase_komponen WHERE profil_id = ?", (PID,)):
        shutil.rmtree(periksa.folder_gambar(kid, 1).parent, ignore_errors=True)
    get_conn().execute("DELETE FROM montase_komponen WHERE profil_id = ?", (PID,))


ADA_MESIN = bool(mesin.jalur_node() and mesin.jalur_browser() and mesin.folder_bundel())
KANVAS = {"lebar": 540, "tinggi": 960, "fps": 30}


class Uraikan(unittest.TestCase):
    def test_balasan_claude_dengan_teks_pembuka(self):
        j = motion_ai.uraikan("Tentu! Ini komponennya:\n```tsx\n" + BAGUS + "```\n\n```json\n"
                              '{"nama": "Geser halo", "alasan": "masuk dari kiri", "durasi": 45}\n```\nSemoga membantu.')
        self.assertIn("export default", j["kode"])
        self.assertEqual((j["nama"], j["durasi"]), ("Geser halo", 45))

    def test_tanpa_kode_ditolak(self):
        with self.assertRaises(motion_ai.GagalAi):
            motion_ai.uraikan("Maaf, saya tidak bisa.")

    def test_prompt_berisi_kontrak_contoh_dan_galat(self):
        s = motion_ai.sistem(KANVAS)
        self.assertIn("useCurrentFrame", s)
        self.assertIn("HitungMundur.jsx", s)
        p = motion_ai.pesan("judul neon", kanvas=KANVAS, durasi=60, galat=["Baris 3: x"])
        self.assertIn("DITOLAK", p)
        self.assertIn("540x960", p)


@unittest.skipUnless(ADA_MESIN, "Mesin Montase (Node + Chrome) tidak tersedia")
class Pemeriksa(unittest.TestCase):
    def setUp(self):
        run_migrations()
        _bersihkan()
        self.addCleanup(_bersihkan)
        tanda = profil.setel(PID)
        self.addCleanup(profil.pulihkan, tanda)

    def _cek(self, kode):
        return komponen.catat_dan_periksa(PID, kode=kode, nama="Uji", permintaan="uji", asal="ai",
                                          kanvas=KANVAS, durasi=30)

    def test_bagus_lolos_dengan_lima_gambar(self):
        v = self._cek(BAGUS)
        self.assertEqual(v["status"], "lolos", v["catatan"])
        self.assertEqual(komponen.jumlah_gambar(v), 5)
        self.assertIn("exports", repo.ambil_komponen(PID, v["id"], 1, dengan_kode=True)["hasil_js"])

    def test_kilat_dan_masuk_lalu_diam_lolos(self):
        self.assertIn("opacity: interpolate", KILAT)
        for kode in (KILAT, MASUK_LALU_DIAM):
            v = self._cek(kode)
            self.assertEqual(v["status"], "lolos", v["catatan"])

    def test_diam_props_salah_dan_css_ditolak_dengan_alasan(self):
        for kode, tahap, kata in ((DIAM, "gerak", "tidak bergerak"), (PROPS_SALAH, "render", "skema"),
                                  (CSS, "kompilasi", "transition")):
            v = self._cek(kode)
            self.assertEqual(v["status"], "gagal")
            self.assertEqual(v["catatan"]["tahap"], tahap, v["catatan"])
            self.assertIn(kata, " ".join(v["catatan"]["masalah"]))

    def test_ai_diperbaiki_sekali_lalu_lolos_dan_revisi_menambah_versi(self):
        jawaban = [{"kode": DIAM, "nama": "A", "alasan": "x", "durasi": 30, "taruh_di": None},
                   {"kode": BAGUS, "nama": "A", "alasan": "x", "durasi": 30, "taruh_di": None}]
        pesan = []

        def tiruan(sistem, teks, **kw):
            pesan.append(teks)
            return jawaban.pop(0), "tiruan:model", {}
        with mock.patch.object(motion_ai, "tanya", side_effect=tiruan), \
             mock.patch.object(motion_ai, "nilai_bingkai", return_value=None):
            v = komponen.buat_lewat_ai(PID, "judul bergeser", dokumen={"kanvas": KANVAS}, durasi=30)
        self.assertEqual((v["status"], v["versi"]), ("lolos", 2))
        self.assertIn("tidak bergerak", pesan[1])
        jawaban.append({"kode": BAGUS.replace("#FF3355", "#00FF00"), "nama": "A", "alasan": "hijau",
                        "durasi": 30, "taruh_di": None})
        with mock.patch.object(motion_ai, "tanya", side_effect=tiruan), \
             mock.patch.object(motion_ai, "nilai_bingkai", return_value=None):
            r = komponen.buat_lewat_ai(PID, "jadikan hijau", dokumen={"kanvas": KANVAS}, durasi=30,
                                       komponen_id=v["id"])
        self.assertEqual((r["id"], r["versi"]), (v["id"], 3))
        self.assertIn("Kode versi sekarang", pesan[-1])
        self.assertEqual(len(repo.versi_komponen(PID, v["id"])), 3)

    def test_pustaka_hanya_yang_lolos_dan_tempelan_gagal_memberi_pesan_perbaikan(self):
        gagal = komponen.dari_tempelan(PID, "```tsx\n" + DIAM + "```", permintaan="x",
                                       dokumen={"kanvas": KANVAS}, durasi=30)
        self.assertIn("Perbaiki semua masalah", gagal["pesan_perbaikan"])
        self.assertFalse(repo.tandai_simpan(PID, gagal["id"], gagal["versi"], "Gagal"))
        baik = komponen.dari_tempelan(PID, "```tsx\n" + BAGUS + "```\n```json\n{\"nama\": \"Baik\"}\n```",
                                      permintaan="x", dokumen={"kanvas": KANVAS}, durasi=30)
        self.assertTrue(repo.tandai_simpan(PID, baik["id"], baik["versi"], "Judul geser"))
        self.assertEqual([k["nama"] for k in repo.daftar_komponen(PID, hanya_disimpan=True)], ["Judul geser"])


if __name__ == "__main__":
    unittest.main()
