"""
Subtitle otomatis Montase (JOB-4 M3.2).

Suara di linimasa (item video bersuara dan item audio, di lajur yang tidak
dibisukan, bukan bingkai beku) diubah jadi potongan teks berwaktu per kata.

Kata per bahan diambil dengan urutan termurah dulu:
  1. simpanan `<data>/montase/bahan/<id>/kata.json` (sekali per bahan);
  2. transkrip yang sudah ada, untuk bahan dari Unduhan (`transcripts` per
     video_id: caption YouTube atau hasil Whisper sebelumnya);
  3. Whisper lokal atas suara bahannya.
Waktu kata dalam DETIK BAHAN; baru dipetakan ke bingkai linimasa per item,
dengan potong_awal dan kecepatannya, jadi satu bahan yang dipakai di tiga
potongan cukup ditranskrip sekali.

Hasilnya USULAN (prinsip "AI mengusulkan" di CLAUDE.md): pekerjaan hanya
mengembalikan potongan, editor yang menaruhnya di lajur teks baru bertanda
`asal: ai` dengan alasannya, satu langkah batal, dan setiap potongan bisa
diubah atau dihapus sendiri.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional

from ..repos import montase as repo
from ..services import profil
from . import bahan as bahan_svc
from . import skema

log = logging.getLogger("omniclip.montase.subtitle")

# Potongan subtitle gaya klip pendek: sedikit kata, berganti cepat. Angka yang
# sama dengan Studio Klip (3-5 kata, ±26 huruf), jeda 0,6 detik memutus
# potongan supaya kalimat baru tidak menempel ke ekor kalimat lama.
KATA_MAKS = 4
HURUF_MAKS = 26
JEDA_PUTUS = 0.6
TANDA_AKHIR = (".", "!", "?", "…")


class GagalSubtitle(Exception):
    pass


def _berkas_kata(bahan_id: str) -> Path:
    return bahan_svc.folder(bahan_id) / "kata.json"


def _rapikan(kata: list[dict]) -> list[dict]:
    hasil = []
    for k in kata:
        w = str(k.get("w") or k.get("word") or "").strip()
        try:
            s = float(k.get("s", k.get("start")))
            e = float(k.get("e", k.get("end")))
        except (TypeError, ValueError):
            continue
        if w and e > s >= 0:
            hasil.append({"w": w, "s": round(s, 3), "e": round(e, 3)})
    return hasil


def _whisper(jalur: Path, *, kabar, batal) -> tuple[list[dict], str]:
    from ..services.whisper import transcribe_audio
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "suara.wav"
        r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(jalur),
                            "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                           capture_output=True, text=True, timeout=1800)
        if r.returncode != 0 or not wav.is_file():
            raise GagalSubtitle("Suara bahan tidak bisa dibaca.")
        return transcribe_audio(str(wav), on_progress=kabar, should_cancel=batal)


def kata_bahan(pid: int, bahan_id: str, *, kabar: Optional[Callable[[float], None]] = None,
               batal: Optional[Callable[[], bool]] = None) -> list[dict]:
    """Kata bertimestamp (detik bahan) untuk satu bahan, disimpan per bahan."""
    berkas = _berkas_kata(bahan_id)
    if berkas.is_file():
        try:
            return _rapikan(json.loads(berkas.read_text(encoding="utf-8")).get("kata", []))
        except (OSError, ValueError):
            pass
    b = repo.ambil_bahan(pid, bahan_id)
    if b is None:
        raise GagalSubtitle("Bahan tidak ditemukan.")
    kata, bahasa, asal = [], "", ""
    if b["asal"] == "unduhan" and b.get("rujukan"):
        from ..repos import transcripts as tx_repo
        tx = tx_repo.get_best(b["rujukan"])
        if tx and tx.get("words"):
            kata, bahasa, asal = _rapikan(tx["words"]), tx.get("language") or "", tx.get("source") or ""
    if not kata:
        jalur = bahan_svc.jalur_asli(pid, bahan_id)
        if jalur is None:
            raise GagalSubtitle("Berkas bahan tidak ditemukan.")
        mentah, bahasa = _whisper(jalur, kabar=kabar, batal=batal)
        kata, asal = _rapikan(mentah), "whisper"
    berkas.parent.mkdir(parents=True, exist_ok=True)
    berkas.write_text(json.dumps({"kata": kata, "bahasa": bahasa, "asal": asal}, ensure_ascii=False),
                      encoding="utf-8")
    return kata


def _bersuara(dokumen: dict) -> list[tuple[dict, dict]]:
    """
    Item bersuara, URUT PRIORITAS: lajur audio dulu (narasi, suara rekaman),
    lalu lajur video dari yang paling bawah (lajur utama). Saat dua sumber
    berbicara bersamaan, yang lebih tinggi prioritasnya yang disalin; ucapan
    dua sumber yang diselang-seling kata demi kata tidak terbaca.
    """
    hasil = []
    urut = sorted(dokumen["lajur"], key=lambda l: 0 if l["jenis"] == "audio" else 1)
    for lajur in urut:
        if lajur.get("bisu") or lajur["jenis"] not in ("video", "audio"):
            continue
        if lajur["jenis"] == "video" and lajur.get("sembunyi"):
            continue
        for item in lajur["item"]:
            meta = dokumen["bahan"].get(item.get("bahan") or "", {})
            if item.get("beku") or (item.get("volume", 1) <= 0):
                continue
            if item["jenis"] == "audio" or (item["jenis"] == "video" and meta.get("ada_suara")):
                hasil.append((item, lajur))
    return hasil


def ke_linimasa(kata: list[dict], item: dict, fps: int) -> list[dict]:
    """
    Kata (detik bahan) -> kata di linimasa (bingkai mutlak) untuk satu item.
    Kata yang mulainya di luar potongan item dibuang; yang ekornya melewati
    ujung item dipotong di ujungnya.
    """
    k = float(item.get("kecepatan") or 1)
    awal = int(item.get("potong_awal") or 0)
    akhir = awal + item["durasi"] * k
    mulai = item["mulai"]
    hasil = []
    for w in kata:
        s = w["s"] * fps
        if s < awal or s >= akhir:
            continue
        t0 = mulai + (s - awal) / k
        t1 = min(mulai + item["durasi"], mulai + (w["e"] * fps - awal) / k)
        t0 = int(round(t0))
        t1 = max(t0 + 1, int(round(t1)))
        hasil.append({"w": w["w"], "t": t0, "u": t1, "i": item.get("id")})
    return hasil


def potong(kata: list[dict], fps: int) -> list[dict]:
    """
    Kata linimasa -> potongan subtitle {mulai, durasi, teks, kata}. `kata` di
    potongan relatif ke awal potongan, dalam bingkai: {w, t, d}.
    """
    hasil: list[list[dict]] = []
    kini: list[dict] = []
    for w in sorted(kata, key=lambda x: x["t"]):
        if kini:
            teks = " ".join(x["w"] for x in kini + [w])
            jeda = (w["t"] - kini[-1]["u"]) / fps
            # Potongan tidak melewati sambungan klip: kalimat klip berikutnya
            # mulai di potongan baru, bersama gambarnya.
            if (len(kini) >= KATA_MAKS or len(teks) > HURUF_MAKS or jeda >= JEDA_PUTUS
                    or kini[-1]["w"].endswith(TANDA_AKHIR) or kini[-1].get("i") != w.get("i")):
                hasil.append(kini)
                kini = []
        kini.append(w)
    if kini:
        hasil.append(kini)
    potongan = []
    for i, p in enumerate(hasil):
        mulai = p[0]["t"]
        # Potongan bertahan sampai potongan berikutnya mulai (paling lama
        # +0,6 detik sesudah kata terakhirnya), jadi layar tidak berkedip
        # kosong di antara dua kata yang berdekatan.
        ujung = p[-1]["u"]
        if i + 1 < len(hasil):
            ujung = min(max(ujung, hasil[i + 1][0]["t"]), ujung + int(JEDA_PUTUS * fps))
        else:
            ujung += int(0.2 * fps)
        if potongan and mulai < potongan[-1]["mulai"] + potongan[-1]["durasi"]:
            potongan[-1]["durasi"] = max(1, mulai - potongan[-1]["mulai"])
        potongan.append({
            "mulai": mulai,
            "durasi": max(1, ujung - mulai),
            "teks": " ".join(x["w"] for x in p),
            "kata": [{"w": x["w"], "t": x["t"] - mulai, "d": max(1, x["u"] - x["t"])} for x in p],
        })
    return potongan


def buat(pid: int, dokumen: dict, *, kabar=None, batal=None) -> dict:
    """Potongan subtitle untuk seluruh suara di linimasa dokumen."""
    fps = dokumen["kanvas"]["fps"]
    sumber = _bersuara(dokumen)
    if not sumber:
        raise GagalSubtitle("Tidak ada suara di linimasa (lajur dibisukan atau tanpa klip bersuara).")
    bahan_ids = list(dict.fromkeys(item["bahan"] for item, _ in sumber))
    kata_per_bahan = {}
    for i, b in enumerate(bahan_ids):
        def maju(f, i=i):
            if kabar:
                kabar((i + max(0.0, min(1.0, f))) / len(bahan_ids))
        kata_per_bahan[b] = kata_bahan(pid, b, kabar=maju, batal=batal)
        maju(1.0)
    semua: list[dict] = []
    jarak = int(0.3 * fps)
    for item, _lajur in sumber:
        terisi = [(w["t"] - jarak, w["u"] + jarak) for w in semua]
        for w in ke_linimasa(kata_per_bahan[item["bahan"]], item, fps):
            if not any(a < w["u"] and w["t"] < b for a, b in terisi):
                semua.append(w)
    potongan = potong(semua, fps)
    return {"potongan": potongan, "jumlah_kata": len(semua)}


def mulai(proyek_id: str) -> str:
    from ..services.jobs import queue
    pid = profil.kini()
    if repo.ambil_proyek(pid, proyek_id) is None:
        raise KeyError(proyek_id)
    job_id, _ = queue.enqueue("montase_subtitle", {"proyek_id": proyek_id, "profil_id": pid},
                              lane="cpu", dedupe_key=f"montase_subtitle:{pid}:{proyek_id}")
    return job_id


def run_subtitle(ctx):
    """Pekerjaan antrean `montase_subtitle` (lajur cpu)."""
    from ..errors import InvalidInput, JobCancelled
    p = ctx.payload
    pid = int(p.get("profil_id") or profil.kini())
    proyek = repo.ambil_proyek(pid, p["proyek_id"])
    if proyek is None:
        raise InvalidInput("Proyek tidak ditemukan.")
    dokumen = skema.periksa(proyek["dokumen"])
    ctx.progress(0.02, stage="subtitle", message="Mencari ucapan di linimasa")
    try:
        return buat(pid, dokumen,
                    kabar=lambda f: ctx.progress(0.05 + 0.9 * f, stage="subtitle", message="Menyalin ucapan"),
                    batal=lambda: ctx.cancelled)
    except GagalSubtitle as e:
        raise InvalidInput(str(e)) from e
    except JobCancelled:
        raise
