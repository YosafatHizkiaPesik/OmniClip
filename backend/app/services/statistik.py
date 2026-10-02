"""
Tayangan klip yang sudah diunggah ke YouTube.

Clipper menagih berdasarkan tayangan, dan sampai sekarang angkanya harus
dicari sendiri satu per satu di YouTube Studio — padahal OmniClip sudah tahu
persis video mana yang ia unggah (`uploads.remote_id`).

DIBACA DENGAN KUNCI API, BUKAN DENGAN IZIN AKUN.

`videos.list` menolak token unggah yang dipegang OmniClip — diuji 2 Oktober
2026, jawabannya 403 "insufficient authentication scopes". Dua jalan keluar,
dan pemiliknya memilih yang pertama:

  1. Kunci API biasa. Dibuat sekali di project Google yang sama, tidak menyentuh
     izin akun mana pun, jadi tidak ada satu pun akun tersambung yang harus
     menyambung ulang. Harganya: hanya video PUBLIK yang terbaca.
  2. Izin `youtube.readonly`. Membaca semua video termasuk yang privat, tapi
     menuntut scope baru di Cloud Console DAN persetujuan ulang dari setiap
     akun — termasuk akun yang sedang dipakai orang lain.

Jadi video yang privat atau unlisted akan menjawab "tidak ada datanya", dan itu
dikatakan apa adanya di antarmuka, bukan ditampilkan sebagai nol tayangan.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

log = logging.getLogger("omniclip.statistik")

# Satu permintaan `videos.list` menerima paling banyak lima puluh id.
SEKALI = 50

# Berapa lama angka tayangan dianggap masih segar.
#
# Lima belas menit. Tayangan tidak berubah secepat itu, dan yang dihemat bukan
# hanya waktu: kuota YouTube Data API 10.000 unit per hari, dan satu
# `videos.list` memakan satu unit per permintaan. Membuka halaman Klip jadi
# sepuluh kali semenit tidak boleh menghabiskan jatah sehari.
TTL = 15 * 60


def kunci_api() -> str:
    """Kunci YouTube Data API milik pemiliknya, atau teks kosong."""
    try:
        from ..repos import settings as settings_repo
        return (settings_repo.get("youtube.api_key") or "").strip()
    except Exception:                                    # noqa: BLE001
        return ""


def _kunci_simpanan(ids: list[str]) -> str:
    import hashlib
    sidik = hashlib.sha1("|".join(sorted(ids)).encode()).hexdigest()[:16]
    return f"statistik:{sidik}"


def tayangan(ids: Iterable[str], *, kunci: Optional[str] = None) -> dict[str, dict]:
    """
    {id_video: {"tayangan", "suka", "komentar"}} untuk id yang terbaca.

    Id yang tidak terbaca — video privat, unlisted, dihapus, atau milik kanal
    lain — TIDAK muncul di hasilnya. Memberinya nol akan berbohong, dan angka
    nol pada klip yang sebenarnya ditonton ribuan orang adalah kebohongan yang
    langsung dipakai orang untuk mengambil keputusan.
    """
    bersih = [str(v).strip() for v in ids if str(v or "").strip()]
    bersih = list(dict.fromkeys(bersih))
    if not bersih:
        return {}
    kunci = (kunci if kunci is not None else kunci_api()).strip()
    if not kunci:
        return {}

    from ..repos import cache as cache_repo

    simpanan = _kunci_simpanan(bersih)
    tersimpan = cache_repo.ambil(simpanan, ttl=TTL)
    if isinstance(tersimpan, dict):
        return tersimpan

    import requests

    hasil: dict[str, dict] = {}
    for i in range(0, len(bersih), SEKALI):
        potong = bersih[i:i + SEKALI]
        try:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "statistics", "id": ",".join(potong), "key": kunci},
                timeout=20,
            )
        except Exception as e:                           # noqa: BLE001
            log.info("Statistik tidak terbaca: %s", str(e)[:160])
            return hasil
        if not r.ok:
            # Kunci yang salah atau kuota habis bukan alasan menggagalkan
            # halaman yang memanggilnya; yang hilang hanya angkanya.
            log.info("videos.list menjawab %s: %s", r.status_code, r.text[:160])
            return hasil
        for item in (r.json().get("items") or []):
            s = item.get("statistics") or {}
            hasil[str(item.get("id"))] = {
                "tayangan": _angka(s.get("viewCount")),
                "suka": _angka(s.get("likeCount")),
                "komentar": _angka(s.get("commentCount")),
            }

    cache_repo.simpan(simpanan, hasil)
    return hasil


def _angka(v) -> Optional[int]:
    """YouTube menyembunyikan sebagian hitungan; yang disembunyikan jadi None."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
