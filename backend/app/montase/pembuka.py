"""
Cuplikan pembuka (JOB-5 O4), sebagai USULAN.

Di Shorts, sinyal pertama adalah "viewed vs swiped away": penonton memutuskan
menonton atau menggeser dalam detik-detik awal. Video Top N yang dibuka kartu
"#5" dan narasi pengantar memberi alasan yang lemah untuk berhenti menggeser.

Usulannya: cuplikan pendek (CUPLIKAN_DETIK) dari momen TERKUAT di video ini
ditaruh paling depan dengan tulisan pengait, dan seluruh isi lama digeser ke
belakang sepanjang cuplikan itu. Momennya dicari dengan pendengar momen yang
sama dengan asisten (`momen.cari_momen`, di rentang yang benar-benar dipakai
tiap klip). Tanpa momen terdeteksi, cuplikan diambil dari klip TERAKHIR
(peringkat #1 di susunan hitung mundur).
"""

from __future__ import annotations

import logging
from typing import Optional

from ..repos import montase as repo
from ..services import profil

log = logging.getLogger("omniclip.montase.pembuka")

CUPLIKAN_DETIK = 2.0
SEBELUM_PUNCAK = 0.7         # cuplikan mulai sedikit sebelum puncak momennya
PENGAIT = {"id": "Tunggu momen ini!", "en": "Wait for this moment!"}


def _klip(dokumen: dict) -> list[dict]:
    lajur = [l for l in dokumen["lajur"] if l["jenis"] == "video" and not l.get("sembunyi")]
    return sorted((i for l in lajur[:1] for i in l["item"] if i["jenis"] == "video" and i.get("bahan")),
                  key=lambda i: i["mulai"])


def pilih_momen(pid: int, dokumen: dict, *, batal=None) -> Optional[dict]:
    """{item, detik_bahan, kuat, jenis} momen terkuat di klip-klip lajur utama, atau None."""
    from . import bahan as bahan_svc
    fps = dokumen["kanvas"]["fps"]
    terbaik = None
    for item in _klip(dokumen):
        if batal and batal():
            break
        jalur = bahan_svc.jalur_asli(pid, item["bahan"])
        if jalur is None:
            continue
        k = float(item.get("kecepatan") or 1)
        s0 = (item.get("potong_awal") or 0) / fps
        s1 = s0 + item["durasi"] * k / fps
        # Seluruh bahan dianalisis, lalu disaring ke rentang yang dipakai: pendeteksi
        # lonjakan membutuhkan suara SEBELUM lonjakan sebagai pembanding, dan
        # rentang yang dimulai 4 detik sebelum puncak tidak menemukan apa pun
        # (terukur pada klip uji: lonjakan di detik 11 hilang bila mulai di detik 7).
        b = repo.ambil_bahan(pid, item["bahan"]) or {}
        durasi_bahan = float(b.get("durasi") or s1)
        try:
            from ..services import momen
            hasil = momen.cari_momen(jalur, [{"start": 0.0, "end": durasi_bahan}], dengar=True)
        except Exception as e:      # noqa: BLE001 - model suara tidak ada, berkas aneh
            log.info("Momen %s tidak terhitung: %s", item["id"], str(e)[:160])
            continue
        for m in hasil:
            t = float(m["t"])
            if s0 <= t <= s1 and (terbaik is None or m["kuat"] > terbaik["kuat"]):
                terbaik = {"item": item, "detik_bahan": t, "kuat": float(m["kuat"]), "jenis": list(m["jenis"])}
    return terbaik


def susun_operasi(dokumen: dict, momen: Optional[dict], *, bahan_info: dict, bahasa: str = "id") -> list[dict]:
    fps = dokumen["kanvas"]["fps"]
    klip = _klip(dokumen)
    if not klip:
        return []
    panjang = round(CUPLIKAN_DETIK * fps)
    if momen:
        item = momen["item"]
        mulai_bahan = max(0.0, momen["detik_bahan"] - SEBELUM_PUNCAK)
        alasan = (f"Momen terkuat ({'+'.join(momen['jenis'])}, {momen['kuat']:.2f}) "
                  f"di detik {momen['detik_bahan']:.1f} bahannya.")
    else:
        item = klip[-1]
        mulai_bahan = (item.get("potong_awal") or 0) / fps
        alasan = "Tidak ada momen terdeteksi; diambil dari awal klip terakhir (peringkat teratas)."
    info = bahan_info.get(item["bahan"]) or (dokumen.get("bahan") or {}).get(item["bahan"]) or {"jenis": "video"}
    return [
        {"id": "c1", "jenis": "geser_semua", "kelompok": "pembuka", "label": f"+{CUPLIKAN_DETIK:.0f} s",
         "alasan": "Isi lama digeser ke belakang sepanjang cuplikan.", "delta": panjang},
        {"id": "c2", "jenis": "klip", "kelompok": "pembuka", "label": "Cuplikan pembuka", "alasan": alasan,
         "bahan": item["bahan"], "bahan_info": info, "mulai": 0, "potong_awal": round(mulai_bahan * fps),
         "durasi": panjang},
        {"id": "c3", "jenis": "teks", "kelompok": "pembuka", "label": PENGAIT.get(bahasa, PENGAIT["id"]),
         "alasan": "Tulisan pengait di detik pertama.", "teks": PENGAIT.get(bahasa, PENGAIT["id"]),
         "mulai": 0, "durasi": panjang},
    ]


def run_pembuka(ctx):
    """Pekerjaan `montase_pembuka`: usulan cuplikan pembuka dari momen terkuat."""
    from ..errors import InvalidInput
    from ..services import bahasa_ai

    p = ctx.payload
    pid = int(p.get("profil_id") or profil.kini())
    proyek = repo.ambil_proyek(pid, p["proyek_id"])
    if proyek is None:
        raise InvalidInput("Proyek tidak ditemukan.")
    dokumen = proyek["dokumen"]
    if not _klip(dokumen):
        raise InvalidInput("Belum ada klip video di lajur utama.")
    ctx.progress(0.1, stage="momen", message="Mencari momen terkuat")
    momen = pilih_momen(pid, dokumen, batal=lambda: ctx.cancelled)
    info = {}
    for b in repo.daftar_bahan(pid):
        info[b["id"]] = {k: b.get(k) for k in ("jenis", "nama", "durasi", "lebar", "tinggi", "fps", "ada_suara")}
    ops = susun_operasi(dokumen, momen, bahan_info=info, bahasa=bahasa_ai.kode())
    return {"operasi": ops, "sumber": "lokal", "peringatan": [], "model": ""}


def mulai(proyek_id: str) -> str:
    from ..services.jobs import queue
    pid = profil.kini()
    job_id, _ = queue.enqueue("montase_pembuka", {"proyek_id": proyek_id, "profil_id": pid}, lane="cpu")
    return job_id
