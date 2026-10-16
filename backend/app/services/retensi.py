"""
Retensi penonton dari YouTube Analytics API (JOB-2 F3-3).

Tayangan dan suka sudah dibaca lewat YouTube Data API dengan kunci API, tapi
yang paling menentukan jangkauan video pendek, berapa bagian videonya yang
ditonton, hanya ada di YouTube Analytics, dan itu butuh izin pemilik kanal
(`yt-analytics.readonly`, sambungan "analitik" di google_upload).

Satu permintaan untuk banyak video sekaligus (`dimensions=video`), disimpan
enam jam: angkanya sendiri baru diperbarui YouTube sekitar sekali sehari.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Iterable, Optional

log = logging.getLogger("omniclip.retensi")

TTL = 6 * 3600
API = "https://youtubeanalytics.googleapis.com/v2/reports"


def tersambung(pid: Optional[int] = None) -> bool:
    from . import google_upload
    try:
        return google_upload._load_credentials(pid, "analitik") is not None
    except Exception:                                     # noqa: BLE001
        return False


def baca(ids: Iterable[str], pid: Optional[int] = None) -> dict[str, dict]:
    """{video_id: {persen, detik, tayangan}}; kosong bila belum tersambung."""
    from google.auth.transport.requests import AuthorizedSession

    from ..repos import cache as cache_repo
    from . import google_upload

    ids = sorted({i for i in ids if i})
    if not ids:
        return {}
    creds = google_upload._load_credentials(pid, "analitik")
    if creds is None:
        return {}
    import hashlib
    kunci = "retensi:" + hashlib.sha1(",".join(ids).encode()).hexdigest()[:16]
    simpan = cache_repo.ambil(kunci, ttl=TTL)
    if isinstance(simpan, dict):
        return simpan

    hasil: dict[str, dict] = {}
    sesi = AuthorizedSession(creds)
    for i in range(0, len(ids), 200):
        potong = ids[i:i + 200]
        try:
            r = sesi.get(API, params={
                "ids": "channel==MINE",
                "startDate": "2015-01-01",
                "endDate": date.today().isoformat(),
                "metrics": "views,averageViewDuration,averageViewPercentage",
                "dimensions": "video",
                "filters": "video==" + ",".join(potong),
                "maxResults": 200,
            }, timeout=30)
        except Exception as e:                            # noqa: BLE001
            log.info("Retensi tidak terbaca: %s", str(e)[:160])
            return hasil
        if not r.ok:
            log.info("YouTube Analytics menjawab %s: %s", r.status_code, r.text[:200])
            return hasil
        data = r.json()
        kolom = [h.get("name") for h in data.get("columnHeaders") or []]
        for baris in data.get("rows") or []:
            d = dict(zip(kolom, baris))
            hasil[str(d.get("video"))] = {
                "tayangan": int(d.get("views") or 0),
                "detik": round(float(d.get("averageViewDuration") or 0), 1),
                "persen": round(float(d.get("averageViewPercentage") or 0), 1),
            }
    cache_repo.simpan(kunci, hasil)
    return hasil
