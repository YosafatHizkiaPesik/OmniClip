"""
Buang jeda sunyi dan kata isian (JOB-4 M5.4), sebagai USULAN potongan.

Dihitung dari waktu per kata (kata.json bahan, transkrip Unduhan, atau
Whisper; sama dengan subtitle M3.2), tanpa AI:
  - jeda: celah antarkata lebih dari JEDA_MIN detik. Yang dipotong celahnya
    dikurangi SISA di kedua sisi, supaya napas sebelum dan sesudah kalimat
    tetap ada dan potongannya tidak terdengar seperti lompatan;
  - kata isian ("eh", "em", "uh", "um", ...): katanya sendiri, ditambah
    sedikit ruang di kedua sisi, digabung dengan jeda yang bersebelahan.
Hasilnya operasi `potong` {item, dari, sampai} dalam bingkai linimasa yang
dijalankan editor dengan `belah` + `hapusBeriak` (model/usulan.js).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from ..repos import montase as repo
from ..services import profil

log = logging.getLogger("omniclip.montase.jeda")

JEDA_MIN = 0.6         # detik; celah di bawah ini adalah irama bicara biasa
SISA = 0.15            # detik yang disisakan di tiap sisi jeda
RUANG_ISIAN = 0.04     # detik di kiri-kanan kata isian
POTONG_MIN = 0.25      # potongan lebih pendek dari ini tidak sepadan dengan sambungannya
ISIAN = {"eh", "ehm", "em", "emm", "hmm", "hm", "mm", "uh", "uhm", "um", "umm", "erm", "er", "ah", "eee", "ee"}


def _bersih(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower())


def cari_potongan(kata: list[dict], item: dict, fps: int) -> list[dict]:
    """
    Potongan {dari, sampai, jenis, kata?} dalam bingkai linimasa untuk satu
    item. `kata` dalam detik bahan ({w, s, e}).
    """
    k = float(item.get("kecepatan") or 1)
    awal = (item.get("potong_awal") or 0) / fps                 # detik bahan
    akhir = awal + item["durasi"] * k / fps
    dalam = sorted((w for w in kata if w["e"] > awal and w["s"] < akhir), key=lambda w: w["s"])
    if not dalam:
        return []
    # Kata isian dianggap diam saat mencari jeda: "semua ... eh ... hari"
    # menjadi satu potongan, bukan potongan isian dan jeda yang berdempetan.
    isi = [w for w in dalam if _bersih(w["w"]) not in ISIAN]
    isian = [w for w in dalam if _bersih(w["w"]) in ISIAN]
    mentah: list[tuple[float, float, str, str]] = []
    terserap: set[int] = set()
    batas = [(awal, awal)] + [(w["s"], w["e"]) for w in isi] + [(akhir, akhir)]
    for (_s0, e0), (s1, _e1) in zip(batas, batas[1:]):
        if s1 - e0 > JEDA_MIN:
            kiri = e0 + (SISA if e0 > awal else 0)
            kanan = s1 - (SISA if s1 < akhir else 0)
            di_dalam = [w for w in isian if w["s"] >= e0 and w["e"] <= s1]
            terserap.update(id(w) for w in di_dalam)
            if di_dalam:    # kata isian di tepi jeda ikut terpotong seluruhnya
                kiri = max(e0 + 0.05, min(kiri, di_dalam[0]["s"] - RUANG_ISIAN))
                kanan = min(s1 - 0.05, max(kanan, di_dalam[-1]["e"] + RUANG_ISIAN))
            mentah.append((kiri, kanan, "isian" if di_dalam else "jeda", " ".join(w["w"] for w in di_dalam)))
    for w in isian:
        if id(w) not in terserap:
            mentah.append((w["s"] - RUANG_ISIAN, w["e"] + RUANG_ISIAN, "isian", w["w"]))
    mentah.sort()
    gabung: list[list] = []
    for a, b, jenis, w in mentah:
        a, b = max(awal, a), min(akhir, b)
        if gabung and a <= gabung[-1][1] + 0.05:
            g = gabung[-1]
            g[1] = max(g[1], b)
            if jenis == "isian":
                g[2], g[3] = "isian", (g[3] + " " + w).strip()
        else:
            gabung.append([a, b, jenis, w])
    hasil = []
    for a, b, jenis, w in gabung:
        if b - a < POTONG_MIN:
            continue
        dari = item["mulai"] + round((a - awal) * fps / k)
        sampai = item["mulai"] + round((b - awal) * fps / k)
        if sampai - dari >= 1:
            hasil.append({"dari": dari, "sampai": sampai, "jenis": jenis, "kata": w})
    return hasil


def operasi(potongan: list[dict], item_id: str, fps: int) -> list[dict]:
    ops = []
    for n, p in enumerate(potongan, start=1):
        detik = (p["sampai"] - p["dari"]) / fps
        if p["jenis"] == "isian":
            label = f'"{p["kata"]}"'
            alasan = f"Kata isian, {detik:.1f} detik."
        else:
            label = f"{detik:.1f} s"
            alasan = f"Diam {detik:.1f} detik."
        ops.append({"id": f"p{n}", "jenis": "potong", "kelompok": p["jenis"], "label": label,
                    "alasan": alasan, "item": item_id, "dari": p["dari"], "sampai": p["sampai"]})
    return ops


def run_jeda(ctx):
    """Pekerjaan `montase_jeda`: usulan potongan untuk satu item."""
    from ..errors import InvalidInput
    from . import subtitle

    p = ctx.payload
    pid = int(p.get("profil_id") or profil.kini())
    proyek = repo.ambil_proyek(pid, p["proyek_id"])
    if proyek is None:
        raise InvalidInput("Proyek tidak ditemukan.")
    dokumen = proyek["dokumen"]
    fps = dokumen["kanvas"]["fps"]
    item: Optional[dict] = None
    for l in dokumen["lajur"]:
        item = next((i for i in l["item"] if i["id"] == p.get("item")), None)
        if item:
            break
    if item is None or item.get("jenis") not in ("video", "audio") or not item.get("bahan"):
        raise InvalidInput("Pilih satu klip video atau suara.")
    ctx.progress(0.1, stage="kata", message="Membaca ucapan")
    try:
        kata = subtitle.kata_bahan(pid, item["bahan"], batal=lambda: ctx.cancelled,
                                   kabar=lambda f: ctx.progress(0.1 + 0.8 * f, stage="kata",
                                                                message="Mentranskrip"))
    except subtitle.GagalSubtitle as e:
        raise InvalidInput(str(e)) from e
    peringatan = [] if kata else ["Tidak ada ucapan yang terbaca di klip ini."]
    ops = operasi(cari_potongan(kata, item, fps), item["id"], fps)
    return {"operasi": ops, "sumber": "lokal", "peringatan": peringatan, "model": ""}


def mulai(proyek_id: str, item_id: str) -> str:
    from ..services.jobs import queue
    pid = profil.kini()
    job_id, _ = queue.enqueue("montase_jeda", {"proyek_id": proyek_id, "item": item_id, "profil_id": pid},
                              lane="cpu")
    return job_id
