"""
Bingkai ulang otomatis ke kanvas tegak (JOB-4 M5.5), sebagai USULAN.

Klip mendatar di kanvas 9:16 diperbesar sampai menutup tinggi kanvas, lalu
digeser mengikuti subjek: jejak wajah dari `reframe.plan_reframe` (YuNet,
fungsi publik yang sama dengan Studio Klip), atau pusat gerakan bila wajah
tidak terlihat atau modelnya tidak ada. Jejak itu menjadi keyframe `x`
item (piksel kanvas) dan `skala` dasar, jadi hasilnya bisa dikoreksi tangan
seperti keyframe lain (M3.7).

Jejak reframe rapat (laju sampel analisis); di sini diringkas menjadi titik
tiap SELANG_DETIK lalu titik tengah yang bisa ditebak dari tetangganya
(galat < TOLERANSI_PX) dibuang, supaya linimasa tidak penuh wajik.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..repos import montase as repo
from ..services import profil

log = logging.getLogger("omniclip.montase.bingkai")

SELANG_DETIK = 0.5
TOLERANSI_PX = 10.0


def ukuran_tampak(sw: int, sh: int, W: int, H: int) -> tuple[float, float]:
    """(skala, lebar tampak) supaya kotak 'muat' bahan menutup seluruh kanvas."""
    s0 = min(W / sw, H / sh)
    bw, bh = sw * s0, sh * s0
    skala = max(W / bw, H / bh)
    return skala, bw * skala


def _ringkas(titik: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Membuang titik yang bisa ditebak garis lurus dari titik yang dipertahankan."""
    if len(titik) <= 2:
        return titik
    hasil = [titik[0]]
    for i in range(1, len(titik) - 1):
        a, b = hasil[-1], titik[i + 1]
        t, v = titik[i]
        tebak = a[1] + (b[1] - a[1]) * (t - a[0]) / max(1, b[0] - a[0])
        if abs(v - tebak) > TOLERANSI_PX:
            hasil.append(titik[i])
    hasil.append(titik[-1])
    return hasil


def keyframe_x(centers: list[tuple[float, float]], *, sw: int, sh: int, W: int, H: int,
               fps: int, kecepatan: float = 1.0) -> tuple[float, list[dict]]:
    """
    `centers` = [(detik sejak awal rentang, x tengah subjek dalam piksel bahan)].
    Mengembalikan (skala, keyframe x [{t, v, kurva}]) dengan t dalam bingkai item.
    """
    skala, lebar = ukuran_tampak(sw, sh, W, H)
    maks = max(0.0, (lebar - W) / 2)
    sampel: list[tuple[int, float]] = []
    terakhir = None
    for t, cx in centers:
        if cx is None:
            continue
        if terakhir is not None and t - terakhir < SELANG_DETIK - 1e-6:
            continue
        terakhir = t
        x = min(maks, max(-maks, (0.5 - float(cx) / sw) * lebar))
        sampel.append((round(t * fps / kecepatan), round(x, 1)))
    if not sampel:
        return skala, []
    sampel = _ringkas(sampel)
    return round(skala, 4), [{"t": t, "v": v, "kurva": "masuk-keluar"} for t, v in sampel]


def _jejak(jalur, s0: float, s1: float) -> tuple[Optional[list], str, float]:
    from ..services import reframe
    for subjek in ("wajah", "gerak"):
        try:
            plan = reframe.plan_reframe(str(jalur), [{"start": s0, "end": s1}], aspect_ratio="9:16",
                                        track_only=True, subjek=subjek)
        except Exception as e:      # noqa: BLE001 - OpenCV/berkas aneh: coba cara berikutnya
            log.info("Jejak %s gagal: %s", subjek, str(e)[:160])
            plan = None
        if plan is not None and plan.centers:
            return plan.centers, subjek, float(plan.face_coverage or 0)
    return None, "", 0.0


def run_bingkai(ctx):
    """Pekerjaan `montase_bingkai`: usulan keyframe bingkai ulang untuk satu item video."""
    from ..errors import InvalidInput
    from . import bahan as bahan_svc

    p = ctx.payload
    pid = int(p.get("profil_id") or profil.kini())
    proyek = repo.ambil_proyek(pid, p["proyek_id"])
    if proyek is None:
        raise InvalidInput("Proyek tidak ditemukan.")
    dokumen = proyek["dokumen"]
    k = dokumen["kanvas"]
    W, H, fps = k["lebar"], k["tinggi"], k["fps"]
    item = next((i for l in dokumen["lajur"] for i in l["item"] if i["id"] == p.get("item")), None)
    if item is None or item.get("jenis") != "video" or not item.get("bahan"):
        raise InvalidInput("Pilih satu klip video.")
    b = repo.ambil_bahan(pid, item["bahan"]) or {}
    sw, sh = b.get("lebar") or 0, b.get("tinggi") or 0
    if not sw or not sh or sw / sh <= W / H + 0.01:
        raise InvalidInput("Klip ini sudah setegak kanvasnya; tidak ada yang perlu dibingkai ulang.")
    jalur = bahan_svc.jalur_asli(pid, item["bahan"])
    if jalur is None:
        raise InvalidInput("Berkas bahan tidak ditemukan.")
    kec = float(item.get("kecepatan") or 1)
    s0 = (item.get("potong_awal") or 0) / fps
    s1 = s0 + item["durasi"] * kec / fps
    ctx.progress(0.1, stage="jejak", message="Mencari wajah")
    centers, subjek, cakupan = _jejak(jalur, s0, s1)
    if not centers:
        raise InvalidInput("Wajah maupun gerakan tidak terbaca di klip ini.")
    skala, kf = keyframe_x(centers, sw=sw, sh=sh, W=W, H=H, fps=fps, kecepatan=kec)
    keyframe = {s: v for s, v in (item.get("keyframe") or {}).items() if s not in ("x", "skala")}
    if len(kf) > 1:
        keyframe["x"] = kf
    ubah = {**(item.get("ubah") or {}), "skala": skala, "x": kf[0]["v"] if kf else 0}
    if subjek == "wajah":
        alasan = f"Mengikuti wajah (terlihat {round(cakupan * 100)}% waktu), {len(kf)} keyframe."
    else:
        alasan = f"Wajah tidak terbaca; mengikuti pusat gerakan, {len(kf)} keyframe."
    op = {"id": "b1", "jenis": "ubah", "kelompok": "bingkai", "label": "9:16",
          "alasan": alasan, "item": item["id"], "ubah": ubah, "keyframe": keyframe or None}
    return {"operasi": [op], "sumber": "lokal", "peringatan": [], "model": ""}


def mulai(proyek_id: str, item_id: str) -> str:
    from ..services.jobs import queue
    pid = profil.kini()
    job_id, _ = queue.enqueue("montase_bingkai", {"proyek_id": proyek_id, "item": item_id, "profil_id": pid},
                              lane="cpu")
    return job_id
