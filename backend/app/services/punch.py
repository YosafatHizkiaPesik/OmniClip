"""
Punch-in: gambar membesar sekejap di momen yang paling keras (JOB-2 F2-1).

Editor manusia memperbesar bidikan saat orang tertawa, berteriak, atau
menekankan sesuatu. Itu yang membuat klip terasa "disunting", bukan sekadar
dipotong, dan itu yang dimaksud kebijakan YouTube dengan modifikasi visual
yang substantif. Zoom statis yang sudah ada (`frame_zoom`) tidak melakukannya:
ia sama dari awal sampai akhir.

Momennya dicari dari kekerasan suara klip itu sendiri (`sutradara._energi_klip`,
per 50 ms), dengan pembanding SETEMPAT: lonjakan dibanding median 1,5 detik
sebelumnya, dan harus di atas kebiasaan klip itu. Lebih longgar daripada
`sutradara.cari_kejutan` (yang mencari jumpscare sesudah hening), karena di
podcast yang dicari adalah tawa dan penekanan di tengah obrolan.

Seperti sutradara, hasilnya USULAN: daftar titik yang tampil di Studio dan
bisa dihapus atau ditambah sendiri sebelum dirender.

Zoom-nya dipasang SESUDAH pembingkaian dan SEBELUM sisipan dan subtitle, jadi
yang membesar hanya gambarnya; tulisan tetap di tempat dan ukurannya.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("omniclip.punch")

LANGKAH = 0.05
LATAR_DETIK = 1.5
NAIK_MIN_DB = 7.0
DI_ATAS_KEBIASAAN_DB = 1.0       # di atas persentil 85 klip itu
JARAK_MIN = 5.0
PER_DETIK = 1 / 8.0              # paling banyak satu tiap 8 detik klip
MENDAHULUI = 0.08                # zoom mulai sedikit sebelum puncaknya

SKALA_BAWAAN = 1.15
SKALA_MAKS = 1.4
LAMA_BAWAAN = 1.0
NAIK = 0.12                      # detik menuju zoom penuh
TURUN = 0.35                     # detik kembali normal
MAKS_TITIK = 12


def cari(energi: list[float], durasi: Optional[float] = None) -> list[dict]:
    """[{t, naik_db, alasan}] dari jejak energi per LANGKAH, urut waktu."""
    import numpy as np

    e = np.asarray(energi, dtype=np.float64)
    bersuara = e[e > -60]
    if len(bersuara) < 20:
        return []
    kebiasaan = float(np.percentile(bersuara, 85))
    n_latar = int(LATAR_DETIK / LANGKAH)
    n_puncak = 4                                   # 200 ms
    kandidat = []
    for i in range(n_latar, len(e) - n_puncak):
        latar = float(np.median(e[i - n_latar:i]))
        keras = float(10 * np.log10(np.mean(10 ** (e[i:i + n_puncak] / 10)) + 1e-12))
        naik = keras - latar
        if naik >= NAIK_MIN_DB and keras - kebiasaan >= DI_ATAS_KEBIASAAN_DB:
            kandidat.append((naik, i * LANGKAH))
    durasi = float(durasi if durasi is not None else len(e) * LANGKAH)
    batas = max(1, min(MAKS_TITIK, int(durasi * PER_DETIK)))
    pilih: list[tuple[float, float]] = []
    for naik, t in sorted(kandidat, reverse=True):
        if all(abs(t - u) >= JARAK_MIN for _, u in pilih):
            pilih.append((naik, t))
        if len(pilih) >= batas:
            break
    return [{"t": round(max(0.0, t - MENDAHULUI), 2), "naik_db": round(naik, 1),
             "alasan": f"suara melonjak {naik:.0f} dB"}
            for naik, t in sorted(pilih, key=lambda x: x[1])]


def untuk_klip(src: Path, segments: list[dict]) -> list[dict]:
    from .sutradara import _energi_klip

    energi = _energi_klip(src, segments)
    durasi = sum(float(s["end"]) - float(s["start"]) for s in segments)
    return cari(energi, durasi)


def siapkan(titik, durasi: float) -> list[dict]:
    """Membersihkan daftar dari Studio: [{t, dur, skala}] yang masuk klip."""
    out = []
    for p in (titik or [])[:MAKS_TITIK]:
        if not isinstance(p, dict):
            continue
        try:
            t = float(p.get("t"))
            dur = float(p.get("dur") or LAMA_BAWAAN)
            skala = float(p.get("skala") or SKALA_BAWAAN)
        except (TypeError, ValueError):
            continue
        if not (0.0 <= t < durasi):
            continue
        dur = max(0.3, min(4.0, dur, durasi - t))
        skala = max(1.02, min(SKALA_MAKS, skala))
        out.append({"t": round(t, 3), "dur": round(dur, 3), "skala": round(skala, 3)})
    out.sort(key=lambda p: p["t"])
    return out


def rumus_zoom(titik: list[dict]) -> str:
    """Ungkapan zoom per bingkai untuk `zoompan` (variabel `it` = detik)."""
    bagian = []
    for p in titik:
        a, b, k = p["t"], p["t"] + p["dur"], p["skala"] - 1.0
        bagian.append(f"{k:.3f}*clip((it-{a:.3f})/{NAIK},0,1)"
                      f"*clip(({b + TURUN:.3f}-it)/{TURUN},0,1)")
    puncak = bagian[0]
    for x in bagian[1:]:
        puncak = f"max({puncak},{x})"
    return f"1+{puncak}"


def graf(titik: list[dict], vin: str, *, out_w: int, out_h: int, fps: int) -> str:
    """Satu `zoompan` yang membesar di titik-titiknya. Teks kosong bila tidak ada."""
    if not titik:
        return ""
    z = rumus_zoom(titik)
    # Pusat zoom sedikit di atas tengah: wajah di bingkai 9:16 hampir selalu di
    # sepertiga atas, dan zoom tepat di tengah memotong dahinya lebih dulu.
    return (f"{vin}zoompan=z='{z}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*0.42'"
            f":d=1:s={out_w}x{out_h}:fps={fps}[vpunch]")
