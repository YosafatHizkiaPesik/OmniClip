"""
Momen kandidat di dalam satu klip, dari bukti yang terukur secara lokal.

Ini lapis pertama sutradara bingkai. Tugasnya BUKAN memutuskan — itu pekerjaan
model yang menonton klipnya — melainkan memberi jangkar waktu yang tepat dan
bukti yang jujur. Model bahasa menonton dengan dua sampai empat bingkai per
detik dan menyebut waktu dengan kasar; waktu yang dipakai untuk memotong
diambil dari sini.

Empat jenis bukti, semuanya dalam waktu KLIP (detik sejak awal klip):

- ``kejut``        lonjakan suara mendadak jauh di atas kebiasaan klip itu
                   (`sutradara.cari_kejutan`). Jumpscare, teriakan, gebrakan.
- ``tanpa_kata``   suara keras yang tidak menghasilkan satu kata pun di
                   transkrip. Pengenal suara tidak menulis tawa, sorak, atau
                   tepuk tangan — caption otomatis YouTube berbahasa Indonesia
                   bahkan tidak pernah memberi penanda "[Tertawa]": di 19
                   transkrip yang tersimpan hanya ada "[Musik]". Jadi celah kata
                   yang bersuara keras adalah tanda paling jujur untuk tawa.
- ``mulut_bersama`` dua orang atau lebih menggerakkan mulut bersamaan jauh di
                   atas kebiasaannya masing-masing. Orang bicara bergantian;
                   yang bergerak BERSAMAAN biasanya tertawa atau bereaksi.
- ``potong``       kamera berpindah (`ReframePlan.cut_times`).
- ``tawa`` / ``sorak`` / ``teriak``  didengar langsung oleh YAMNet
                   (`peristiwa_suara`). Inilah sinyal tawa yang paling andal:
                   ia tidak bergantung pada transkrip maupun pada berapa wajah
                   yang kebetulan terlihat.

Bukti yang berdekatan (±1,2 dtk) disatukan menjadi satu momen.
"""

import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("omniclip.momen")

LANGKAH = 0.05              # resolusi jejak energi, sama dengan sutradara.py
# Suara tanpa kata: minimal sekian detik, dan sekeras apa dibanding ucapan
# biasa di klip itu (median energi saat ADA kata).
TANPA_KATA_MIN = 0.5
TANPA_KATA_DB = -4.0        # relatif terhadap median energi ucapan
KATA_TEPI = 0.12            # kata dianggap menempati sedikit di luar batasnya
# Mulut bersama: gerak mulut di atas persentil ini (per orang), untuk minimal
# sekian detik, oleh minimal dua orang yang terlihat.
MULUT_PERSENTIL = 80
MULUT_MIN_DETIK = 0.5
GABUNG_DETIK = 1.2


def _rentang_bersuara(energi: list[float], kata: list[tuple[float, float]]
                      ) -> list[dict]:
    """Rentang suara keras yang tidak ditempati kata mana pun."""
    import numpy as np

    e = np.asarray(energi, dtype=np.float64)
    if len(e) < 20:
        return []
    ditempati = np.zeros(len(e), dtype=bool)
    for s, t in kata:
        a = max(0, int((s - KATA_TEPI) / LANGKAH))
        b = min(len(e), int((t + KATA_TEPI) / LANGKAH) + 1)
        ditempati[a:b] = True
    if ditempati.sum() < 20:
        return []            # tanpa transkrip, "tanpa kata" tidak berarti apa-apa
    ucapan = float(np.median(e[ditempati]))
    keras = (e > ucapan + TANPA_KATA_DB) & ~ditempati

    out: list[dict] = []
    i = 0
    while i < len(e):
        if not keras[i]:
            i += 1
            continue
        j = i
        # Celah sangat pendek (<0,15 dtk) di tengah tawa tetap satu rentang.
        while j < len(e) and (keras[j] or (j + 3 < len(e) and keras[j:j + 3].any()
                                            and not ditempati[j])):
            j += 1
        dur = (j - i) * LANGKAH
        if dur >= TANPA_KATA_MIN:
            puncak = i + int(np.argmax(e[i:j]))
            out.append({"t": round(puncak * LANGKAH, 2), "mulai": round(i * LANGKAH, 2),
                        "akhir": round(j * LANGKAH, 2),
                        "di_atas_ucapan_db": round(float(e[i:j].max()) - ucapan, 1)})
        i = j
    return out


def _mulut_bersama(plan) -> list[dict]:
    """Rentang ketika dua orang atau lebih menggerakkan mulut bersamaan."""
    from .reframe import SAMPLE_FPS

    gerak = getattr(plan, "people_motion", None) or []
    terlihat = getattr(plan, "people_seen", None) or []
    if len(gerak) < 2:
        return []
    ambang = []
    for p, g in enumerate(gerak):
        nilai = sorted(v for v, s in zip(g, terlihat[p] if p < len(terlihat) else [])
                       if s and v > 0)
        if len(nilai) < 10:
            ambang.append(None)
            continue
        ambang.append(nilai[min(len(nilai) - 1, int(len(nilai) * MULUT_PERSENTIL / 100))])

    n = min(len(g) for g in gerak)
    aktif: list[list[int]] = []
    for i in range(n):
        siapa = [p for p, g in enumerate(gerak)
                 if ambang[p] is not None and p < len(terlihat) and i < len(terlihat[p])
                 and terlihat[p][i] and g[i] > ambang[p]]
        aktif.append(siapa)

    out: list[dict] = []
    min_n = max(1, int(MULUT_MIN_DETIK * SAMPLE_FPS))
    i = 0
    while i < n:
        if len(aktif[i]) < 2:
            i += 1
            continue
        j = i
        orang: set[int] = set()
        while j < n and len(aktif[j]) >= 2:
            orang.update(aktif[j])
            j += 1
        if j - i >= min_n:
            out.append({"t": round((i + (j - i) / 2) / SAMPLE_FPS, 2),
                        "mulai": round(i / SAMPLE_FPS, 2), "akhir": round(j / SAMPLE_FPS, 2),
                        "orang": sorted(orang)})
        i = j
    return out


def cari_momen(src: Path, segments: list[dict], *, plan=None,
               words: Optional[list] = None, energi: Optional[list] = None,
               dengar: bool = True) -> list[dict]:
    """
    Daftar momen kandidat: [{id, t, mulai, akhir, jenis:[...], kuat, orang, bukti}].

    `words` adalah kata-kata di DALAM klip dalam waktu klip ({"s","e"} atau
    {"start","end"}). `energi` boleh diberikan bila sudah dihitung.
    """
    from .sutradara import _energi_klip, cari_kejutan

    if energi is None:
        try:
            energi = _energi_klip(Path(src), segments)
        except Exception as e:
            log.warning("Energi klip tidak terbaca: %s", str(e)[:160])
            energi = []

    kata = []
    for w in words or []:
        s = w.get("s", w.get("start"))
        t = w.get("e", w.get("end"))
        if s is not None and t is not None:
            kata.append((float(s), float(t)))

    bukti: list[dict] = []
    for k in cari_kejutan(energi) if energi else []:
        bukti.append({"jenis": "kejut", "t": k["t"], "mulai": k["t"], "akhir": k["t"] + 0.5,
                      "kuat": min(1.0, k["naik_db"] / 24.0), "rinci": k})
    for r in _rentang_bersuara(energi, kata) if energi else []:
        bukti.append({"jenis": "tanpa_kata", "t": r["t"], "mulai": r["mulai"],
                      "akhir": r["akhir"],
                      "kuat": min(1.0, 0.4 + (r["akhir"] - r["mulai"]) / 4.0
                                  + max(0.0, r["di_atas_ucapan_db"]) / 20.0),
                      "rinci": r})
    if dengar:
        from .peristiwa_suara import peristiwa, skor_klip
        try:
            skor = skor_klip(Path(src), segments)
        except Exception as e:
            log.warning("Peristiwa suara tidak terbaca: %s", str(e)[:160])
            skor = None
        for p in peristiwa(skor) if skor else []:
            bukti.append({"jenis": p["jenis"], "t": p["t"], "mulai": p["mulai"],
                          "akhir": p["akhir"],
                          "kuat": min(1.0, 0.45 + 2.0 * p["skor"]
                                      + 0.05 * (p["akhir"] - p["mulai"])),
                          "rinci": p})
    if plan is not None:
        for r in _mulut_bersama(plan):
            bukti.append({"jenis": "mulut_bersama", "t": r["t"], "mulai": r["mulai"],
                          "akhir": r["akhir"], "orang": r["orang"],
                          "kuat": min(1.0, 0.3 + 0.2 * len(r["orang"])
                                      + (r["akhir"] - r["mulai"]) / 5.0),
                          "rinci": r})
        for t in getattr(plan, "cut_times", None) or []:
            bukti.append({"jenis": "potong", "t": t, "mulai": t, "akhir": t, "kuat": 0.2})

    # Satukan bukti yang berdekatan menjadi satu momen.
    bukti.sort(key=lambda b: b["mulai"])
    kelompok: list[list[dict]] = []
    for b in bukti:
        if kelompok and b["mulai"] <= max(x["akhir"] for x in kelompok[-1]) + GABUNG_DETIK:
            kelompok[-1].append(b)
        else:
            kelompok.append([b])

    momen: list[dict] = []
    for g in kelompok:
        jenis = sorted({b["jenis"] for b in g})
        if jenis == ["potong"]:
            continue            # perpindahan kamera saja bukan momen
        inti = max((b for b in g if b["jenis"] != "potong"), key=lambda b: b["kuat"])
        orang = sorted({p for b in g for p in b.get("orang", [])})
        kuat = min(1.0, inti["kuat"] + 0.15 * (len(jenis) - 1))
        momen.append({
            "t": inti["t"],
            "mulai": round(min(b["mulai"] for b in g), 2),
            "akhir": round(max(b["akhir"] for b in g), 2),
            "jenis": jenis, "kuat": round(kuat, 2), "orang": orang,
            "bukti": [{k: v for k, v in b.items() if k != "rinci"} for b in g],
        })
    for i, m in enumerate(momen):
        m["id"] = i
    return momen


def jangkar_terdekat(momen: list[dict], t: float, jarak: float = 1.0) -> Optional[dict]:
    """Momen kandidat terdekat dari waktu `t`, bila dalam `jarak` detik."""
    terbaik = None
    for m in momen:
        d = 0.0 if m["mulai"] <= t <= m["akhir"] else min(abs(t - m["mulai"]), abs(t - m["akhir"]))
        if d <= jarak and (terbaik is None or d < terbaik[0]):
            terbaik = (d, m)
    return terbaik[1] if terbaik else None


def ringkas(momen: list[dict]) -> str:
    """Satu baris per momen, untuk dikirim ke model."""
    nama = {"kejut": "lonjakan suara mendadak", "tanpa_kata": "suara keras tanpa kata",
            "tawa": "terdengar tawa", "sorak": "terdengar sorak/tepuk tangan",
            "teriak": "terdengar teriakan/kaget",
            "mulut_bersama": "beberapa mulut bergerak bersamaan", "potong": "kamera berpindah"}
    baris = []
    for m in momen:
        orang = f"; orang {', '.join(f'P{p}' for p in m['orang'])}" if m["orang"] else ""
        baris.append(f"momen_id={m['id']} | {m['mulai']:.1f}-{m['akhir']:.1f} dtk "
                     f"(puncak {m['t']:.1f}) | {', '.join(nama.get(j, j) for j in m['jenis'])}"
                     f"{orang} | kekuatan {m['kuat']:.2f}")
    return "\n".join(baris) if baris else "(tidak ada momen kandidat yang terukur)"

