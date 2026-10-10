"""
Skor nilai tambah per klip (JOB-2 F3-1).

Kebijakan konten yang digunakan ulang YouTube tidak menanyakan "berapa lama
klip ini", melainkan "apa yang ditambahkan orang ini di atas karya orang
lain". Skor ini menjawab pertanyaan itu dengan angka yang bisa dibaca: berapa
detik dari klip jadinya yang berisi lapisan buatan pemilik kanal, dibagi
panjang klipnya.

Yang dihitung, dan kenapa hanya ini:

  komentar  pendapat pemilik kanal (F1-3..F1-6). Bobot penuh; inilah yang
            disebut kebijakan itu sebagai komentar dan kritik.
  sisipan   cuplikan, gambar, atau teks yang ditaruh orangnya sendiri. Setengah
            bobot: menambah konteks, tapi bukan pendapat.

Yang TIDAK dihitung: subtitle, bingkai, tema, kartu judul. Semuanya dibuat
otomatis dan sama di setiap klip, dan itu persis "produksi massal" yang sedang
dihindari, bukan nilai tambah.

Gerbang tinjau (`gerbang.nilai`) memakai `cukup`: ada komentar paling sedikit
`KOMENTAR_MIN` detik, atau skornya paling sedikit `SKOR_MIN`. Angkanya sengaja
rendah: satu kalimat pembuka yang jujur sudah mengubah klip dari potongan
ulang menjadi komentar atas potongan itu.
"""

from __future__ import annotations

from typing import Optional

KOMENTAR_MIN = 2.0          # detik
SKOR_MIN = 0.08
BOBOT_SISIPAN = 0.5


def _gabung(rentang: list[tuple[float, float]]) -> float:
    """Panjang gabungan rentang yang mungkin bertumpuk."""
    total, ujung = 0.0, None
    for a, b in sorted(r for r in rentang if r[1] > r[0]):
        if ujung is None or a > ujung:
            total += b - a
            ujung = b
        elif b > ujung:
            total += b - ujung
            ujung = b
    return total


def hitung(meta: Optional[dict]) -> dict:
    """{skor, detik_komentar, detik_sisipan, cukup, rincian} dari sidecar klip."""
    meta = meta or {}
    durasi = float(meta.get("duration") or 0.0)
    komentar = [k for k in (meta.get("komentar") or []) if isinstance(k, dict)]
    detik_komentar = sum(float(k.get("d") or 0.0) for k in komentar
                         if k.get("bersuara") or k.get("kartu"))
    rentang = []
    for l in meta.get("media_layers") or []:
        if not isinstance(l, dict):
            continue
        try:
            t = float(l.get("t") or 0.0)
            d = float(l["dur"]) if l.get("dur") not in (None, "") else 0.0
        except (TypeError, ValueError):
            continue
        if d > 0:
            rentang.append((t, t + d))
    detik_sisipan = _gabung(rentang)
    berlapis = detik_komentar + BOBOT_SISIPAN * detik_sisipan
    skor = min(1.0, berlapis / durasi) if durasi > 0 else 0.0
    cukup = detik_komentar >= KOMENTAR_MIN or skor >= SKOR_MIN

    rincian = []
    if komentar:
        suara = sum(1 for k in komentar if k.get("bersuara") and not k.get("sintetis"))
        rincian.append(f"{len(komentar)} komentar, {detik_komentar:.1f} detik"
                       + (f", {suara} dengan suara Anda" if suara else ""))
    if detik_sisipan:
        rincian.append(f"sisipan {detik_sisipan:.1f} detik")
    return {"skor": round(skor, 3), "persen": int(round(skor * 100)),
            "detik_komentar": round(detik_komentar, 2),
            "detik_sisipan": round(detik_sisipan, 2),
            "cukup": cukup, "rincian": rincian}
