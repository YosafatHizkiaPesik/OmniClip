"""
Asisten penyunting Montase (JOB-4 M5.1-M5.3).

Satu perintah tingkat proyek ("susun Top 5 momen paling lucu dari klip-klip
ini") menjadi DAFTAR OPERASI usulan. Asisten tidak pernah menulis dokumen
proyek: operasinya dijalankan editor dengan fungsi `model/` yang sama dengan
tangan manusia (frontend `model/usulan.js`), ditampilkan bergaris putus, dan
pemilik memilih untuk menerima semua, sebagian, atau menolak.

Alurnya:
  1. ringkas bahan terpilih: nama, durasi, judul/hook Klip jadi, transkrip
     bertimestamp, momen (tawa/sorak/kejut, `momen.py`);
  2. rencana: AI menyusun urutan segmen {bahan, dari, sampai, peringkat,
     judul, narasi, alasan}; tanpa AI (atau bila AI gagal) rencana dibuat
     lokal dari skor momen, sesuai kebiasaan OmniClip bahwa setiap fitur AI
     punya jalur lokal;
  3. narasi per peringkat dibacakan dengan suara pilihan (narasi.py, M3.3);
  4. rencana dikompilasi menjadi operasi berbingkai (`susun_operasi`).

AI hanya menulis RENCANA, bukan operasi mentah: rencana kecil dan mudah
diperiksa (id bahan harus ada, rentang harus di dalam durasi), sedangkan
letak bingkai dihitung di sini supaya tidak mungkin tumpang tindih.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Callable, Optional

from ..repos import montase as repo
from ..services import profil

log = logging.getLogger("omniclip.montase.asisten")

BATAS_BAHAN = 12
DETIK_KLIP = 20.0          # panjang segmen paling lama, bisa diubah pengguna
DETIK_KLIP_MIN = 2.0
DETIK_KARTU = 2.0          # kartu peringkat tanpa narasi
JEDA_NARASI = 0.4          # sisa kartu sesudah narasi selesai
KATA_TRANSKRIP = 260       # kata per bahan yang dikirim ke AI
WARNA = ["#FF3355", "#FFB800", "#22C55E", "#3B82F6", "#A855F7"]

# Kata di perintah -> jenis momen yang dicari. Jenis dari momen.py.
MINAT = (
    (("lucu", "tawa", "ngakak", "kocak", "funny", "laugh", "hilarious"), {"tawa", "tanpa_kata", "mulut_bersama"}),
    (("kaget", "seram", "horor", "jumpscare", "takut", "scary", "shock"), {"kejut", "teriak"}),
    (("seru", "sorak", "epik", "hype", "epic", "keren", "cheer"), {"sorak", "kejut", "teriak"}),
)


class GagalAsisten(Exception):
    pass


# --- 1. ringkas bahan -------------------------------------------------------------

def _sidecar(pid: int, b: dict) -> dict:
    """Sidecar Klip jadi (judul, hook, subtitle). Kosong untuk asal lain."""
    if b.get("asal") != "klip_jadi":
        return {}
    from . import bahan as bahan_svc
    jalur = bahan_svc.jalur_asli(pid, b["id"])
    if jalur is None:
        return {}
    try:
        return json.loads(jalur.with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _kata(pid: int, b: dict, meta: dict, *, kabar=None, batal=None) -> list[dict]:
    """Kata {w, s, e} dalam detik bahan: subtitle Klip jadi, kata.json, atau Whisper."""
    baris = [s for s in meta.get("subtitles") or [] if isinstance(s, dict) and s.get("text")]
    if baris:
        kata = []
        for s in baris:
            try:
                a, z = float(s.get("start", 0)), float(s.get("end", 0))
            except (TypeError, ValueError):
                continue
            pecah = str(s["text"]).split()
            langkah = max(0.01, (z - a) / max(1, len(pecah)))
            kata += [{"w": w, "s": round(a + i * langkah, 2), "e": round(a + (i + 1) * langkah, 2)}
                     for i, w in enumerate(pecah)]
        return kata
    if not b.get("ada_suara"):
        return []
    from . import subtitle
    try:
        return [{"w": k["w"], "s": k["s"], "e": k["e"]}
                for k in subtitle.kata_bahan(pid, b["id"], kabar=kabar, batal=batal)]
    except Exception as e:      # noqa: BLE001 - tanpa transkrip pun rencana tetap bisa dibuat
        log.info("Transkrip %s tidak ada: %s", b["id"], str(e)[:160])
        return []


def _transkrip(kata: list[dict]) -> str:
    """Kata dikelompokkan per ±8 dengan penanda detik, dipotong KATA_TRANSKRIP."""
    potong = kata[:KATA_TRANSKRIP]
    baris = []
    for i in range(0, len(potong), 8):
        g = potong[i:i + 8]
        baris.append(f"[{g[0]['s']:.1f}] " + " ".join(k["w"] for k in g))
    if len(kata) > KATA_TRANSKRIP:
        baris.append("...")
    return "\n".join(baris)


def _momen(pid: int, b: dict, kata: list[dict]) -> list[dict]:
    from . import bahan as bahan_svc
    jalur = bahan_svc.jalur_asli(pid, b["id"])
    if jalur is None or b.get("jenis") != "video" or not b.get("durasi"):
        return []
    try:
        from ..services import momen
        hasil = momen.cari_momen(jalur, [{"start": 0.0, "end": float(b["durasi"])}], words=kata, dengar=True)
    except Exception as e:      # noqa: BLE001 - model suara tidak ada, berkas aneh
        log.info("Momen %s tidak terhitung: %s", b["id"], str(e)[:160])
        return []
    return [{"t": round(float(m["t"]), 2), "jenis": list(m["jenis"]), "kuat": float(m["kuat"])} for m in hasil]


def ringkas_bahan(pid: int, bahan_ids: list[str], *, kabar: Optional[Callable[[float, str], None]] = None,
                  batal=None) -> list[dict]:
    hasil = []
    ids = list(dict.fromkeys(bahan_ids))[:BATAS_BAHAN]
    for n, bid in enumerate(ids):
        if batal and batal():
            break
        b = repo.ambil_bahan(pid, bid)
        if b is None or b.get("jenis") != "video":
            continue
        if kabar:
            kabar(n / max(1, len(ids)), b.get("nama") or bid)
        meta = _sidecar(pid, b)
        kata = _kata(pid, b, meta, batal=batal)
        hasil.append({
            "id": b["id"], "nama": b.get("nama") or bid, "durasi": float(b.get("durasi") or 0),
            "judul": str(meta.get("title") or "")[:120], "hook": str(meta.get("hook_text") or "")[:160],
            "kata": kata, "transkrip": _transkrip(kata), "momen": _momen(pid, b, kata),
            "info": {k: b.get(k) for k in ("jenis", "nama", "durasi", "lebar", "tinggi", "fps", "ada_suara")},
        })
    return hasil


# --- 2. rencana ---------------------------------------------------------------

def jumlah_diminta(perintah: str) -> Optional[int]:
    m = re.search(r"\b(?:top|peringkat|ranking|best|terbaik)\s*(\d{1,2})\b", perintah, re.I) \
        or re.search(r"\b(\d{1,2})\s*(?:momen|klip|moment|clip|terbaik|best)", perintah, re.I)
    return int(m.group(1)) if m else None


def minat(perintah: str) -> set[str]:
    p = perintah.lower()
    hasil: set[str] = set()
    for kata, jenis in MINAT:
        if any(k in p for k in kata):
            hasil |= jenis
    return hasil


def skor(r: dict, dicari: set[str]) -> float:
    """Jumlah kekuatan momen, dibobot dua kali lipat bila jenisnya yang dicari."""
    return round(sum(m["kuat"] * (2.0 if dicari & set(m["jenis"]) else 1.0) for m in r["momen"]), 3)


def _judul_lokal(r: dict) -> str:
    for teks in (r["hook"], r["judul"]):
        if teks:
            return " ".join(teks.split()[:7])[:60]
    if r["kata"]:
        return " ".join(k["w"] for k in r["kata"][:6])[:60]
    return r["nama"][:60]


def _rentang(r: dict, maks: float, pusat: Optional[float]) -> tuple[float, float]:
    durasi = r["durasi"]
    if durasi <= maks:
        return 0.0, round(durasi, 2)
    t = pusat if pusat is not None else 0.0
    dari = min(max(0.0, t - maks * 0.4), durasi - maks)
    return round(dari, 2), round(dari + maks, 2)


def _narasi_lokal(peringkat: Optional[int], judul: str, bahasa: str) -> str:
    if peringkat is None:
        return judul
    return f"Number {peringkat}. {judul}." if bahasa == "en" else f"Nomor {peringkat}. {judul}."


def rencana_lokal(perintah: str, ringkasan: list[dict], *, maks: float, bahasa: str) -> dict:
    dicari = minat(perintah)
    n = min(jumlah_diminta(perintah) or len(ringkasan), len(ringkasan))
    berperingkat = jumlah_diminta(perintah) is not None or bool(dicari)
    urut = sorted(enumerate(ringkasan), key=lambda x: (-skor(x[1], dicari), x[0]))[:n]
    segmen = []
    for rank, (_i, r) in enumerate(urut, start=1):
        kuat = max(r["momen"], key=lambda m: m["kuat"] * (2 if dicari & set(m["jenis"]) else 1), default=None)
        dari, sampai = _rentang(r, maks, kuat["t"] if kuat else None)
        judul = _judul_lokal(r)
        if kuat:
            alasan = (f"Skor momen {skor(r, dicari):.2f}; terkuat {'+'.join(kuat['jenis'])} "
                      f"({kuat['kuat']:.2f}) di detik {kuat['t']:.1f}.")
        else:
            alasan = "Tidak ada momen terdeteksi; diurutkan seperti pilihan bahan."
        segmen.append({"bahan": r["id"], "dari": dari, "sampai": sampai,
                       "peringkat": rank if berperingkat else None, "judul": judul,
                       "narasi": _narasi_lokal(rank if berperingkat else None, judul, bahasa),
                       "alasan": alasan})
    if berperingkat:
        segmen.reverse()        # hitung mundur: peringkat terbesar dulu, #1 terakhir
    return {"judul": perintah.strip()[:80], "urutan": segmen, "penutup": ""}


SKEMA_RENCANA = {
    "type": "OBJECT",
    "properties": {
        "judul": {"type": "STRING"},
        "urutan": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "bahan": {"type": "STRING"}, "dari": {"type": "NUMBER"}, "sampai": {"type": "NUMBER"},
            "peringkat": {"type": "INTEGER"}, "judul": {"type": "STRING"},
            "narasi": {"type": "STRING"}, "alasan": {"type": "STRING"},
        }, "required": ["bahan", "dari", "sampai", "judul", "alasan"]}},
        "penutup": {"type": "STRING"},
    },
    "required": ["judul", "urutan"],
}


def _sistem(bahasa: str, maks: float, narasi: bool) -> str:
    from ..services import bahasa_ai
    return "\n".join([
        "Kamu penyunting video pendek. Dari daftar bahan (klip) beserta transkrip dan momennya, "
        "susun rencana video sesuai perintah pengguna.",
        "Aturan:",
        "- Pakai HANYA id bahan yang diberikan. Satu bahan boleh dipakai sekali.",
        f"- Setiap segmen {DETIK_KLIP_MIN:.0f}-{maks:.0f} detik, di dalam durasi bahannya; mulai dan "
        "akhiri di batas kalimat bila transkripnya ada.",
        "- Untuk daftar peringkat (Top N), isi `peringkat` dan urutkan hitung mundur: peringkat "
        "terbesar dulu, peringkat 1 terakhir. Peringkat 1 = momen terkuat sesuai perintah.",
        "- `judul` paling banyak 6 kata, menarik, tanpa tagar.",
        ("- `narasi` 1-2 kalimat pendek (paling banyak 25 kata) yang dibacakan sebelum segmennya, "
         "menyebut peringkatnya." if narasi else "- Kosongkan `narasi`."),
        "- `alasan` menyebut buktinya: kutipan transkrip atau momen (jenis dan detiknya).",
        "- `penutup`: ajakan singkat di akhir video, boleh kosong.",
        bahasa_ai.perintah(bahasa),
    ])


def _pesan(perintah: str, ringkasan: list[dict]) -> str:
    bagian = [f"Perintah: {perintah.strip()}", ""]
    for r in ringkasan:
        bagian.append(f"## Bahan {r['id']}: {r['nama']} ({r['durasi']:.1f} detik)")
        if r["judul"]:
            bagian.append(f"Judul klip: {r['judul']}")
        if r["hook"]:
            bagian.append(f"Hook: {r['hook']}")
        if r["momen"]:
            bagian.append("Momen: " + ", ".join(f"{m['t']:.1f}s {'+'.join(m['jenis'])} ({m['kuat']:.2f})"
                                                 for m in r["momen"][:12]))
        bagian.append("Transkrip:\n" + (r["transkrip"] or "(tidak ada)"))
        bagian.append("")
    return "\n".join(bagian)


def bersihkan_rencana(rencana: dict, ringkasan: list[dict], *, maks: float) -> dict:
    """Membuang segmen yang tidak sah: bahan asing, ganda, atau rentang di luar durasi."""
    durasi = {r["id"]: r["durasi"] for r in ringkasan}
    sudah: set[str] = set()
    segmen = []
    for s in rencana.get("urutan") or []:
        bid = str(s.get("bahan") or "")
        if bid not in durasi or bid in sudah:
            continue
        try:
            dari = max(0.0, float(s.get("dari") or 0))
            sampai = min(durasi[bid], float(s.get("sampai") or durasi[bid]))
        except (TypeError, ValueError):
            continue
        if sampai - dari > maks:
            sampai = dari + maks
        if sampai - dari < min(DETIK_KLIP_MIN, durasi[bid]) - 0.01:
            continue
        sudah.add(bid)
        p = s.get("peringkat")
        segmen.append({
            "bahan": bid, "dari": round(dari, 2), "sampai": round(sampai, 2),
            "peringkat": int(p) if isinstance(p, (int, float)) and 0 < p < 100 else None,
            "judul": " ".join(str(s.get("judul") or "").split())[:60],
            "narasi": " ".join(str(s.get("narasi") or "").split())[:300],
            "alasan": " ".join(str(s.get("alasan") or "").split())[:300],
        })
    return {"judul": str(rencana.get("judul") or "")[:80], "urutan": segmen,
            "penutup": " ".join(str(rencana.get("penutup") or "").split())[:120]}


def rencana_ai(perintah: str, ringkasan: list[dict], *, maks: float, bahasa: str, narasi: bool,
               utamakan: Optional[str] = None, batal=None) -> tuple[dict, str]:
    from ..services import penyedia_ai
    with penyedia_ai.pekerjaan("montase_asisten"):
        data, model, _pakai = penyedia_ai.tanya(
            [{"teks": _pesan(perintah, ringkasan)}], schema=SKEMA_RENCANA,
            sistem=_sistem(bahasa, maks, narasi), api_key="", models=[], suhu=0.3,
            maks_keluaran=4000, batal=batal, utamakan=utamakan)
    return bersihkan_rencana(data or {}, ringkasan, maks=maks), model


# --- 4. rencana -> operasi ------------------------------------------------------

def _ujung_video(dokumen: dict) -> int:
    for l in dokumen["lajur"]:
        if l["jenis"] == "video" and not l.get("kunci"):
            return max((i["mulai"] + i["durasi"] for i in l["item"]), default=0)
    return 0


def susun_operasi(dokumen: dict, rencana: dict, ringkasan: list[dict], *,
                  narasi_bahan: Optional[dict[int, dict]] = None, suara: str = "") -> list[dict]:
    """
    Operasi berbingkai, diletakkan sesudah isi lajur video yang sudah ada:
      [kartu peringkat (+ narasi)] [klip] [kartu] [klip] ... [penutup]
    Setiap operasi membawa `kelompok` (satu per segmen) supaya bisa diterima
    atau ditolak per peringkat.
    """
    fps = dokumen["kanvas"]["fps"]
    info = {r["id"]: r for r in ringkasan}
    narasi_bahan = narasi_bahan or {}
    t = _ujung_video(dokumen)
    ops: list[dict] = []

    def op(**isi):
        ops.append({"id": f"u{len(ops) + 1}", **isi})

    for k, s in enumerate(rencana["urutan"]):
        r = info[s["bahan"]]
        kel = f"#{s['peringkat']}" if s.get("peringkat") else f"{k + 1}"
        nar = narasi_bahan.get(k)
        kartu = 0
        if s.get("peringkat") or nar:
            detik = max(DETIK_KARTU, (float(nar["durasi"] or 0) + JEDA_NARASI) if nar else 0)
            kartu = round(detik * fps)
        if s.get("peringkat"):
            op(jenis="animasi", kelompok=kel, label=f"Kartu {kel}", alasan=s["alasan"],
               komponen="ko_hitung_mundur", mulai=t, durasi=kartu,
               props={"angka": s["peringkat"], "judul": s["judul"] or r["nama"][:60],
                      "warna": WARNA[(s["peringkat"] - 1) % len(WARNA)]})
        elif kartu:
            op(jenis="teks", kelompok=kel, label=s["judul"] or r["nama"], alasan=s["alasan"],
               teks=s["judul"] or r["nama"][:60], mulai=t, durasi=kartu)
        if nar:
            op(jenis="audio", kelompok=kel, label="Narasi", alasan=s["narasi"], bahan=nar["id"],
               bahan_info={k2: nar.get(k2) for k2 in ("jenis", "nama", "durasi", "ada_suara")},
               mulai=t, narasi={"teks": s["narasi"], "suara": suara, "kecepatan": 1})
        t += kartu
        durasi = max(1, round((s["sampai"] - s["dari"]) * fps))
        op(jenis="klip", kelompok=kel, label=f"{r['nama']} ({s['dari']:.1f}-{s['sampai']:.1f} dtk)",
           alasan=s["alasan"], bahan=r["id"], bahan_info=r["info"], mulai=t,
           potong_awal=round(s["dari"] * fps), durasi=durasi)
        if not s.get("peringkat") and not kartu and s["judul"]:
            op(jenis="teks", kelompok=kel, label=s["judul"], alasan=s["alasan"], teks=s["judul"],
               mulai=t, durasi=min(durasi, round(3 * fps)))
        t += durasi
    if rencana.get("penutup"):
        op(jenis="animasi", kelompok="penutup", label="Ajakan berlangganan", alasan=rencana["penutup"],
           komponen="ko_ajakan_langganan", mulai=max(0, t - 90), durasi=90,
           props={"kanal": rencana["penutup"][:40], "tombol": "SUBSCRIBE", "sudah": "SUBSCRIBED",
                  "warna": "#E11D2E"})
    return ops


# --- pekerjaan antrean --------------------------------------------------------

def _suara_bawaan() -> str:
    from . import narasi
    daftar = narasi.daftar_suara()
    siap = [s for s in daftar if s.get("siap", True)]
    return (siap or daftar or [{"id": ""}])[0]["id"]


def run_asisten(ctx):
    """Pekerjaan `montase_asisten`: ringkas bahan -> rencana -> narasi -> operasi."""
    from ..errors import InvalidInput
    from ..services import bahasa_ai, penyedia_ai
    from . import komponen, narasi

    p = ctx.payload
    pid = int(p.get("profil_id") or profil.kini())
    proyek = repo.ambil_proyek(pid, p["proyek_id"])
    if proyek is None:
        raise InvalidInput("Proyek tidak ditemukan.")
    dokumen = proyek["dokumen"]
    perintah = str(p.get("perintah") or "").strip()
    maks = min(120.0, max(DETIK_KLIP_MIN + 1, float(p.get("maks_detik") or DETIK_KLIP)))
    pakai_narasi = bool(p.get("narasi"))
    bahasa = bahasa_ai.kode()
    peringatan: list[str] = []

    ctx.progress(0.03, stage="bahan", message="Membaca klip")
    ringkasan = ringkas_bahan(pid, list(p.get("bahan") or []), batal=lambda: ctx.cancelled,
                              kabar=lambda f, n: ctx.progress(0.03 + 0.4 * f, stage="bahan",
                                                              message=f"Membaca {n}"))
    if not ringkasan:
        raise InvalidInput("Pilih paling sedikit satu klip video di Bahan saya.")

    sumber, model = "lokal", ""
    rencana = None
    if penyedia_ai.ada_ai() and p.get("pakai_ai", True):
        ctx.progress(0.5, stage="ai", message="AI menyusun urutan")
        try:
            rencana, model = rencana_ai(perintah, ringkasan, maks=maks, bahasa=bahasa, narasi=pakai_narasi,
                                        utamakan=komponen.setelan_koneksi() or None,
                                        batal=lambda: ctx.cancelled)
            sumber = "ai"
            if not rencana["urutan"]:
                peringatan.append("Rencana AI tidak berisi segmen yang sah; dipakai susunan lokal.")
                rencana, sumber = None, "lokal"
        except Exception as e:      # noqa: BLE001 - AI pelengkap; susunan lokal selalu ada
            log.warning("Rencana AI gagal: %s", str(e)[:200])
            peringatan.append("AI tidak menjawab; dipakai susunan lokal dari momen klip.")
    if rencana is None:
        rencana = rencana_lokal(perintah, ringkasan, maks=maks, bahasa=bahasa)
        if not pakai_narasi:
            for s in rencana["urutan"]:
                s["narasi"] = ""

    suara = str(p.get("suara") or "") or _suara_bawaan()
    narasi_bahan: dict[int, dict] = {}
    if pakai_narasi:
        segmen = rencana["urutan"]
        for k, s in enumerate(segmen):
            if ctx.cancelled or not s.get("narasi"):
                continue
            ctx.progress(0.75 + 0.2 * k / max(1, len(segmen)), stage="narasi", message="Membacakan narasi")
            try:
                narasi_bahan[k] = narasi.buat_narasi(pid, s["narasi"], suara)
            except narasi.GagalNarasi as e:
                peringatan.append(str(e))
                break
    operasi = susun_operasi(dokumen, rencana, ringkasan, narasi_bahan=narasi_bahan, suara=suara)
    return {"operasi": operasi, "rencana": rencana, "sumber": sumber, "model": model,
            "peringatan": list(dict.fromkeys(peringatan)), "bahasa": bahasa}


def mulai(proyek_id: str, payload: dict) -> str:
    from ..services.jobs import queue
    pid = profil.kini()
    job_id, _ = queue.enqueue("montase_asisten", {**payload, "proyek_id": proyek_id, "profil_id": pid},
                              lane="net")
    return job_id

