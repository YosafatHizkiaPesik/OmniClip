"""
Ekspor proyek Montase menjadi MP4 di Klip jadi (JOB-4 M1.9, bagian 22).

Alurnya:
  1. dokumen proyek dibaca dan DIPERIKSA ULANG (skema.periksa): dokumen yang
     tersimpan bisa saja dibuat versi lama;
  2. setiap bahan harus masih ada berkasnya, kalau tidak gagal dengan nama
     bahannya, bukan dengan galat Chrome yang tidak bisa dibaca;
  3. Mesin Montase merender dari BERKAS ASLI (bukan salinan sunting) lewat
     alamat bertoken ke server OmniClip sendiri;
  4. hasilnya dipindah ke folder klip profil bersama sidecar `.json`, jadi
     Klip jadi, unggah, dan pembersihan mengenalinya seperti klip biasa.

Lajur `cpu` antrean sudah memegang giliran CPU, sama dengan render klip.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from ..config import PORT, STORAGE_DIR
from ..repos import media as media_repo
from ..repos import montase as repo
from ..services import profil
from . import bahan as bahan_svc
from . import kekerasan, mesin, skema, teks
from . import token as token_svc

log = logging.getLogger("omniclip.montase.ekspor")

RASIO = {(1080, 1920): "9:16", (1920, 1080): "16:9", (1080, 1080): "1:1", (1080, 1350): "4:5"}


class GagalEkspor(RuntimeError):
    pass


def _rasio(lebar: int, tinggi: int) -> str:
    return RASIO.get((lebar, tinggi), f"{lebar}:{tinggi}")


def nama_berkas(nama: str, waktu: Optional[float] = None) -> str:
    """'Top 5 Momen!' -> 'Top-5-Momen_montase_2026-11-03_1015.mp4'."""
    dasar = re.sub(r"[^\w]+", "-", nama, flags=re.UNICODE).strip("-")[:60] or "Montase"
    cap = time.strftime("%Y-%m-%d_%H%M", time.localtime(waktu or time.time()))
    return f"{dasar}_montase_{cap}.mp4"


def _sumber_kredit(pid: int, dokumen: dict) -> list[dict]:
    """Video sumber tiap bahan, untuk kredit di deskripsi unggahan (JOB-2 F0-1)."""
    hasil, sudah = [], set()
    for bahan_id in dokumen.get("bahan", {}):
        b = repo.ambil_bahan(pid, bahan_id)
        if b is None:
            continue
        sumber = None
        if b["asal"] == "unduhan":
            sumber = media_repo.sumber_video(b["rujukan"])
        elif b["asal"] == "klip_jadi":
            try:
                sidecar = profil.folder_klip(pid) / Path(b["rujukan"]).with_suffix(".json").name
                sumber = json.loads(sidecar.read_text(encoding="utf-8")).get("sumber")
            except (OSError, ValueError):
                sumber = None
        if sumber and sumber.get("video_id") and sumber["video_id"] not in sudah:
            sudah.add(sumber["video_id"])
            hasil.append(sumber)
    return hasil


_AWALAN_PERINGKAT = re.compile(r"^\s*(nomor|number|peringkat|rank)\s*\d+\s*[.:,!-]?\s*", re.I)


def baris_teks(dokumen: dict) -> list[dict]:
    """
    Tulisan dan ucapan yang ADA di video, dalam detik: item teks (termasuk
    subtitle), teks narasi, dan judul animasi. Masuk ke `subtitles` sidecar
    supaya saran caption dan tagar (keterangan.py, M5.6) membaca isi videonya,
    bukan hanya nama proyek.
    """
    fps = dokumen["kanvas"]["fps"]
    hasil = []
    for lajur in dokumen["lajur"]:
        if lajur.get("sembunyi"):
            continue
        for i in lajur["item"]:
            teks_item = ""
            if i["jenis"] == "teks":
                teks_item = i.get("teks") or ""
            elif i["jenis"] == "audio":
                # "Nomor 5." di awal narasi peringkat bukan isi videonya: tanpa
                # dibuang, tagar lokal yang terpilih malah #nomor.
                teks_item = _AWALAN_PERINGKAT.sub("", (i.get("narasi") or {}).get("teks") or "")
            elif i["jenis"] == "motion":
                props = i.get("props") or {}
                teks_item = " ".join(str(props[k]) for k in ("judul", "teks", "nama", "label")
                                     if isinstance(props.get(k), str) and props[k].strip())
            teks_item = " ".join(teks_item.split())
            if teks_item:
                hasil.append({"start": round(i["mulai"] / fps, 2),
                              "end": round((i["mulai"] + i["durasi"]) / fps, 2), "text": teks_item[:500]})
    hasil.sort(key=lambda b: b["start"])
    # Narasi peringkat biasanya mengulang judul kartunya; baris yang sama
    # (abaikan huruf besar dan tanda baca) cukup sekali, kalau tidak caption
    # lokal memuat kalimat yang sama dua kali.
    sudah, unik = set(), []
    for b in hasil:
        kunci = re.sub(r"[^\w]+", " ", b["text"].lower()).strip()
        if kunci and kunci not in sudah:
            sudah.add(kunci)
            unik.append(b)
    return unik


def _bersuara_sintetis(pid: int, dokumen: dict) -> bool:
    """Ada narasi TTS di linimasa: label konten sintetis saat diunggah (JOB-2 F0-7)."""
    for lajur in dokumen["lajur"]:
        if lajur.get("bisu") or lajur.get("sembunyi"):
            continue
        for i in lajur["item"]:
            if i["jenis"] != "audio":
                continue
            if i.get("narasi"):
                return True
            b = repo.ambil_bahan(pid, i.get("bahan") or "")
            if b and b.get("asal") == "tts":
                return True
    return False


def sidecar(dokumen: dict, *, pid: int, berkas: str, detik: float) -> dict:
    k = dokumen["kanvas"]
    ada_ai = any(i.get("asal") == "ai" for lajur in dokumen["lajur"] for i in lajur["item"])
    baris = baris_teks(dokumen)
    return {
        "jenis": "montase",
        "montase_id": dokumen["id"],
        "file_name": berkas,
        "title": dokumen["nama"],
        "hashtags": [],
        "duration": round(detik, 3),
        "aspect_ratio": _rasio(k["lebar"], k["tinggi"]),
        "subtitles": baris,
        "hook_text": baris[0]["text"][:160] if baris else "",
        "sumber_banyak": _sumber_kredit(pid, dokumen),
        "suara_sintetis": _bersuara_sintetis(pid, dokumen),
        "motion_ai": ada_ai,
        "created_at": time.time(),
    }


def mulai(proyek_id: str) -> str:
    from ..services.jobs import queue
    pid = profil.kini()
    if repo.ambil_proyek(pid, proyek_id) is None:
        raise KeyError(proyek_id)
    job_id, _ = queue.enqueue("montase_render", {"proyek_id": proyek_id, "profil_id": pid},
                              lane="cpu", dedupe_key=f"montase_render:{pid}:{proyek_id}")
    return job_id


def ekspor(pid: int, proyek_id: str, *, kabar=None, batal=None, dasar_url: Optional[str] = None) -> dict:
    p = repo.ambil_proyek(pid, proyek_id)
    if p is None:
        raise GagalEkspor("Proyek tidak ditemukan.")
    try:
        dokumen = skema.periksa(p["dokumen"])
    except skema.GagalSkema as e:
        raise GagalEkspor("Dokumen proyek tidak sah: " + "; ".join(e.pesan[:3])) from e
    if not any(lajur["item"] for lajur in dokumen["lajur"]):
        raise GagalEkspor("Linimasa masih kosong.")
    hilang = [meta.get("nama") or bahan_id for bahan_id, meta in dokumen["bahan"].items()
              if bahan_svc.jalur_asli(pid, bahan_id) is None]
    if hilang:
        raise GagalEkspor("Berkas bahan tidak ditemukan lagi: " + ", ".join(hilang[:5]))

    tkn = token_svc.buat(f"bahan:{pid}", berlaku_detik=12 * 3600)
    dasar = (dasar_url or f"http://127.0.0.1:{PORT}").rstrip("/")
    sumber = {"bahan": {b: f"{dasar}/api/montase/t/{tkn}/bahan/{b}" for b in dokumen["bahan"]},
              "font": {f: f"{dasar}/api/montase/t/{tkn}/font/{quote(f)}"
                       for f in teks.font_dipakai(dokumen)},
              "komponen": {f"{i['komponen']}@{i.get('versi') or 1}":
                           f"{dasar}/api/montase/t/{tkn}/komponen/{i['komponen']}/{i.get('versi') or 1}/kode.js"
                           for l in dokumen["lajur"] for i in l["item"]
                           if i["jenis"] == "motion" and not str(i.get("komponen", "")).startswith("ko_")}}
    sementara = STORAGE_DIR / "montase" / "render" / f"{proyek_id}.mp4"
    mulai_t = time.monotonic()
    hasil = mesin.render(dokumen, sumber, sementara, kabar=kabar, batal=batal)
    if kabar:
        kabar({"tahap": "suara"})
    suara = kekerasan.ratakan(sementara)

    folder = profil.folder_klip(pid, buat=True)
    berkas = nama_berkas(dokumen["nama"])
    tujuan = folder / berkas
    sementara.replace(tujuan)
    detik_video = dokumen["durasi"] / dokumen["kanvas"]["fps"]
    tujuan.with_suffix(".json").write_text(
        json.dumps(sidecar(dokumen, pid=pid, berkas=berkas, detik=detik_video),
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "berkas": berkas,
        "detik_video": round(detik_video, 2),
        "detik_render": round(time.monotonic() - mulai_t, 1),
        "ukuran_mb": round(tujuan.stat().st_size / 1e6, 1),
        "bingkai": hasil.get("bingkai"),
        "suara": suara,
    }


def run_ekspor(ctx):
    """Pekerjaan antrean `montase_render` (lajur cpu)."""
    p = ctx.payload
    pid = int(p.get("profil_id") or profil.kini())

    def kabar(baris):
        if "kemajuan" in baris:
            ctx.progress(float(baris["kemajuan"]), stage="render",
                         message=f"Bingkai {baris.get('bingkai', 0)} dari {baris.get('total', '?')}")
        elif baris.get("tahap") == "suara":
            ctx.progress(0.99, stage="suara", message="Menyamakan kekerasan suara")
        elif baris.get("tahap"):
            ctx.progress(0.0, stage="render", message="Menyiapkan render")

    from ..errors import JobCancelled, RenderError
    try:
        return ekspor(pid, p["proyek_id"], kabar=kabar, batal=lambda: ctx.cancelled)
    except mesin.Dibatalkan as e:
        raise JobCancelled() from e
    except (GagalEkspor, mesin.GagalMesin) as e:
        raise RenderError(str(e)[:500]) from e
