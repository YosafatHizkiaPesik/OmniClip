"""
Pemeriksa kemiripan antar video Montase (JOB-5 O3).

Kebijakan "konten tidak autentik" YouTube (Juli 2025) menolak konten yang
diproduksi massal, bertemplat, atau berulang dengan sedikit perbedaan antar
video, dan menilainya per KANAL: video yang masing-masing tampak wajar tetap
bermasalah bila sepuluh di antaranya bersusun, bersuara, dan bertemplat sama.
Asisten Top N (JOB-4 M5) justru memudahkan pola seperti itu.

Setiap ekspor menyimpan SIDIK di sidecarnya (`sidik`); video yang sedang
disunting dibandingkan dengan sidik ekspor Montase sebelumnya di profil yang
sama (ekspor ulang proyek yang sama tidak dihitung). Dimensi dan bobotnya:

  struktur  pola tiga langkah urutan item (kartu, narasi, klip, teks) 0,25
  animasi   komponen animasi yang dipakai                              0,15
  suara     suara narasi (id TTS, atau "sendiri" untuk rekaman)        0,15
  musik     bahan musik                                                0,10
  gaya      font dan warna teks                                        0,10
  irama     pola panjang klip (dibulatkan ke 2 detik)                  0,10
  judul     kata judul tanpa angka                                     0,15

Dua video dianggap mirip bila skornya >= AMBANG_MIRIP, ATAU bila tiga atau
lebih dimensi inti (struktur, animasi, suara, musik, gaya) sama persis: itulah
templatnya, walau judul dan panjang klipnya berbeda.

Yang dikembalikan menyebut DIMENSI mana yang sama, supaya yang diubah jelas
("ganti suara narasi", "susunan sama persis"), bukan sekadar angka. Bukan alat
mengelabui deteksi: yang disarankan selalu perubahan isi.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Optional

from ..services import profil

BOBOT = {"struktur": 0.25, "animasi": 0.15, "suara": 0.15, "musik": 0.10, "gaya": 0.10,
         "irama": 0.10, "judul": 0.15}
AMBANG_MIRIP = 0.75          # dua video dianggap "bertemplat sama"
INTI = {"struktur", "animasi", "suara", "musik", "gaya"}
INTI_MIN = 3                 # ...atau sebanyak ini dimensi inti sama persis
AMBANG_DIMENSI = 0.8         # satu dimensi dianggap "sama"
BANDINGKAN_MAKS = 30         # ekspor terakhir yang dibandingkan
POLA_MIN = 3                 # sebanyak ini yang mirip = pola kanal


def _kata_judul(judul: str) -> list[str]:
    return [w for w in re.findall(r"[^\W\d_]+", (judul or "").lower()) if len(w) > 2]


def sidik(dokumen: dict) -> dict:
    """Sidik isi satu dokumen proyek, cukup kecil untuk disimpan di sidecar."""
    fps = dokumen["kanvas"]["fps"]
    item = sorted(((l, i) for l in dokumen["lajur"] if not l.get("sembunyi") and not l.get("subtitle")
                   for i in l["item"]), key=lambda x: x[1]["mulai"])
    struktur: list[str] = []
    animasi, suara, musik, gaya = set(), set(), set(), set()
    irama: list[int] = []
    for l, i in item:
        j = i["jenis"]
        if j == "motion":
            token = "kartu"
            animasi.add(str(i.get("komponen") or ""))
        elif j == "audio":
            n = i.get("narasi") or {}
            if n:
                token = "narasi"
                suara.add("sendiri" if n.get("direkam") else str(n.get("suara") or "tts"))
            else:
                token = "musik"
                musik.add(str(i.get("bahan") or ""))
        elif j == "teks":
            token = "teks"
            g = i.get("gaya") or {}
            gaya.add(f"{g.get('font', '')}|{g.get('warna', '')}|{g.get('latar', '')}")
        elif j in ("video", "gambar"):
            token = "klip"
            irama.append(int(round(i["durasi"] / fps / 2)) * 2)
        else:
            token = j
        if not struktur or struktur[-1] != token:
            struktur.append(token)
    return {
        "versi": 1, "struktur": struktur[:200], "animasi": sorted(animasi), "suara": sorted(suara),
        "musik": sorted(musik), "gaya": sorted(gaya), "irama": irama[:100],
        "judul": _kata_judul(dokumen.get("nama") or ""),
    }


def _jaccard(a, b) -> Optional[float]:
    a, b = set(a or []), set(b or [])
    if not a and not b:
        return None                  # dimensi kosong di keduanya: tidak dinilai
    return len(a & b) / len(a | b)


def _pola(token: list[str]) -> set[str]:
    """Pola tiga langkah (trigram). Top 2 dan Top 10 dengan susunan kartu-narasi-klip
    yang sama punya pola yang sama, walau panjang urutannya jauh berbeda."""
    if len(token) < 3:
        return {"|".join(token)} if token else set()
    return {"|".join(token[i:i + 3]) for i in range(len(token) - 2)}


def _urutan(a, b) -> Optional[float]:
    if not a and not b:
        return None
    return SequenceMatcher(None, list(a or []), list(b or []), autojunk=False).ratio()


def banding(a: dict, b: dict) -> dict:
    """{skor 0..1, dimensi: {nama: skor}, sama: [dimensi yang >= AMBANG_DIMENSI]}."""
    nilai = {
        "struktur": _jaccard(_pola(a.get("struktur") or []), _pola(b.get("struktur") or [])),
        "animasi": _jaccard(a.get("animasi"), b.get("animasi")),
        "suara": _jaccard(a.get("suara"), b.get("suara")),
        "musik": _jaccard(a.get("musik"), b.get("musik")),
        "gaya": _jaccard(a.get("gaya"), b.get("gaya")),
        "irama": _urutan(a.get("irama"), b.get("irama")),
        "judul": _jaccard(a.get("judul"), b.get("judul")),
    }
    dinilai = {k: v for k, v in nilai.items() if v is not None}
    bobot = sum(BOBOT[k] for k in dinilai) or 1.0
    skor = sum(BOBOT[k] * v for k, v in dinilai.items()) / bobot
    sama = [k for k, v in dinilai.items() if v >= AMBANG_DIMENSI]
    # Templat = inti yang sama, walau judul dan panjang klipnya berbeda.
    templat = len(set(sama) & INTI) >= INTI_MIN
    return {"skor": round(skor, 3), "dimensi": {k: round(v, 3) for k, v in dinilai.items()},
            "sama": sama, "templat": templat}


def _ekspor_sebelumnya(pid: int, kecuali: str) -> list[dict]:
    folder = profil.folder_klip(pid)
    if not folder.is_dir():
        return []
    hasil = []
    for p in sorted(folder.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if m.get("jenis") != "montase" or not m.get("sidik") or m.get("montase_id") == kecuali:
            continue
        hasil.append({"berkas": m.get("file_name") or p.with_suffix(".mp4").name,
                      "judul": m.get("title") or "", "sidik": m["sidik"],
                      "waktu": m.get("created_at") or p.stat().st_mtime})
        if len(hasil) >= BANDINGKAN_MAKS:
            break
    return hasil


SARAN = {
    "struktur": "Susunannya sama: ubah urutan, panjang pembuka, atau bentuk ceritanya (tidak selalu hitung mundur).",
    "animasi": "Animasinya sama: pakai animasi lain atau buat yang baru untuk video ini.",
    "suara": "Suara narasinya sama: rekam dengan suara Anda sendiri, atau ganti suaranya.",
    "musik": "Musiknya sama: pilih musik lain yang cocok dengan isi video ini.",
    "gaya": "Gaya teksnya sama: ganti tema teks sesuai isi video.",
    "irama": "Panjang setiap klip sama: biarkan panjang klip mengikuti momennya.",
    "judul": "Judulnya mirip video sebelumnya: tulis judul yang menyebut isi khas video ini.",
}


def periksa(pid: int, dokumen: dict) -> dict:
    """
    Video yang sedang disunting lawan ekspor Montase sebelumnya di profil ini.
    {mirip: [...], jumlah_banding, tingkat: aman|waspada|pola, sama_sering: [...], saran: [...]}.
    """
    ini = sidik(dokumen)
    lalu = _ekspor_sebelumnya(pid, dokumen.get("id") or "")
    hasil = []
    for e in lalu:
        b = banding(ini, e["sidik"])
        hasil.append({"berkas": e["berkas"], "judul": e["judul"], "waktu": e["waktu"], **b})
    mirip = sorted((h for h in hasil if h["skor"] >= AMBANG_MIRIP or h["templat"]), key=lambda h: -h["skor"])
    hitung: dict[str, int] = {}
    for h in mirip:
        for k in h["sama"]:
            hitung[k] = hitung.get(k, 0) + 1
    sama_sering = sorted(hitung, key=lambda k: -hitung[k])
    tingkat = "pola" if len(mirip) >= POLA_MIN else ("waspada" if mirip else "aman")
    return {
        "jumlah_banding": len(lalu), "tingkat": tingkat, "mirip": mirip[:10],
        "sama_sering": sama_sering, "saran": [SARAN[k] for k in sama_sering[:4]],
    }
