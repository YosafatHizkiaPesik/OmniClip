"""
Tayangan tiap video per hari, dicatat OmniClip sendiri.

YouTube Data API v3 hanya memberi angka SAAT INI. Riwayat sungguhan ada di
YouTube Analytics API, yang menuntut izin baru dan persetujuan ulang dari
setiap akun. Jadi yang dikerjakan di sini sederhana dan jujur: sekali sehari,
angka hari ini disimpan. Grafiknya tidak bisa memberi masa lalu, tapi mulai
hari pertama ia tumbuh dari angka yang benar-benar diamati.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Optional

from ..db import get_conn, tx


def hari_ini() -> str:
    return date.today().isoformat()


def catat(baris: list[dict], tanggal: Optional[str] = None) -> int:
    """
    Menyimpan angka hari ini. Satu baris per video per hari, ditimpa bila
    dicatat dua kali pada hari yang sama.

    Ditimpa, bukan diabaikan: angka sore hari lebih benar daripada angka pagi,
    dan yang dibandingkan antar hari memang angka pada akhir hari itu.
    """
    t = tanggal or hari_ini()
    sekarang = time.time()
    isi = [(str(b.get("id") or b.get("video_id") or ""), t,
            b.get("tayangan"), b.get("suka"), b.get("komentar"), sekarang)
           for b in baris if (b.get("id") or b.get("video_id"))]
    if not isi:
        return 0
    with tx() as c:
        c.executemany(
            "INSERT INTO statistik_harian "
            "(video_id, tanggal, tayangan, suka, komentar, dicatat_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(video_id, tanggal) DO UPDATE SET "
            "tayangan = excluded.tayangan, suka = excluded.suka, "
            "komentar = excluded.komentar, dicatat_at = excluded.dicatat_at",
            isi)
    return len(isi)


def sudah_dicatat(tanggal: Optional[str] = None) -> bool:
    t = tanggal or hari_ini()
    r = get_conn().execute(
        "SELECT 1 FROM statistik_harian WHERE tanggal = ? LIMIT 1", (t,)).fetchone()
    return r is not None


def deret(video_ids: list, hari: int = 90) -> dict:
    """
    {video_id: [{tanggal, tayangan, suka, komentar}]}, urut tanggal menaik.
    """
    if not video_ids:
        return {}
    tanda = ",".join("?" for _ in video_ids)
    rows = get_conn().execute(
        f"SELECT video_id, tanggal, tayangan, suka, komentar "
        f"FROM statistik_harian WHERE video_id IN ({tanda}) "
        f"ORDER BY tanggal ASC", list(video_ids)).fetchall()
    out: dict[str, list] = {}
    for r in rows:
        out.setdefault(r["video_id"], []).append({
            "tanggal": r["tanggal"], "tayangan": r["tayangan"],
            "suka": r["suka"], "komentar": r["komentar"]})
    if hari:
        for k, v in out.items():
            out[k] = v[-hari:]
    return out


def harian_kanal(video_ids: list, hari: int = 90) -> list[dict]:
    """
    Total tayangan kanal per hari, plus TAMBAHANNYA dibanding hari sebelumnya.

    Tambahan harian yang paling menjawab "video saya jalan atau tidak": total
    kumulatif selalu naik, jadi grafiknya selalu terlihat bagus walau tidak ada
    yang menonton sejak minggu lalu.

    Hari yang tidak tercatat dilewati, bukan dianggap nol. Aplikasi yang tidak
    dibuka dua hari bukan dua hari tanpa penonton.
    """
    per_video = deret(video_ids, hari=0)
    per_hari: dict[str, int] = {}
    for baris in per_video.values():
        for b in baris:
            if isinstance(b.get("tayangan"), int):
                per_hari[b["tanggal"]] = per_hari.get(b["tanggal"], 0) + b["tayangan"]
    urut = sorted(per_hari.items())[-hari:] if hari else sorted(per_hari.items())
    keluar = []
    sebelum = None
    for tanggal, total in urut:
        keluar.append({"tanggal": tanggal, "total": total,
                       "tambahan": (total - sebelum) if sebelum is not None else None})
        sebelum = total
    return keluar
