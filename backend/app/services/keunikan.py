"""
Keunikan judul unggahan (JOB-5 O7).

Kebijakan konten tidak autentik YouTube menilai pola kanal, termasuk metadata
yang bertemplat: sepuluh video berjudul "Top 5 Momen Lucu Podcast" dengan angka
yang berbeda-beda adalah pola itu. Judul yang akan diunggah dibandingkan dengan
judul unggahan sebelumnya di profil ini dan judul Klip jadi lain di foldernya.

Pembandingnya kata, bukan huruf: angka dan kata pendek (<= 2 huruf) dibuang,
lalu kemiripan Jaccard. Deskripsi tidak dibandingkan: sebagian besar isinya
memang dari templat profil (kredit sumber, tagar tetap) dan itu bukan masalah.
Tidak memblokir apa pun; hanya memperingatkan beserta judul yang mirip.
"""

from __future__ import annotations

import json
import re

AMBANG = 0.7
BANDINGKAN_MAKS = 60


def kata(judul: str) -> set[str]:
    return {w for w in re.findall(r"[^\W\d_]+", (judul or "").lower()) if len(w) > 2}


def mirip(a: str, b: str) -> float:
    ka, kb = kata(a), kata(b)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / len(ka | kb)


def periksa(judul: str, *, clip_name: str, profil_id: int) -> dict:
    """{tingkat: aman|waspada|pola, mirip: [{judul, skor, asal}], jumlah_banding}."""
    from ..repos import uploads as uploads_repo
    from . import profil

    lain: list[tuple[str, str]] = []
    for u in uploads_repo.list_recent(BANDINGKAN_MAKS, profil_id=profil_id):
        if u.get("clip_name") != clip_name and u.get("title"):
            lain.append((u["title"], "unggahan"))
    folder = profil.folder_klip(profil_id)
    if folder.is_dir():
        for p in sorted(folder.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:BANDINGKAN_MAKS]:
            if p.with_suffix(".mp4").name == clip_name:
                continue
            try:
                t = json.loads(p.read_text(encoding="utf-8")).get("title")
            except (OSError, ValueError):
                continue
            if t:
                lain.append((t, "klip"))
    sudah: set[str] = set()
    hasil = []
    for t, asal in lain:
        if t in sudah:
            continue
        sudah.add(t)
        s = mirip(judul, t)
        if s >= AMBANG:
            hasil.append({"judul": t, "skor": round(s, 2), "asal": asal})
    hasil.sort(key=lambda x: -x["skor"])
    tingkat = "pola" if len(hasil) >= 3 else ("waspada" if hasil else "aman")
    return {"tingkat": tingkat, "mirip": hasil[:5], "jumlah_banding": len(sudah)}
