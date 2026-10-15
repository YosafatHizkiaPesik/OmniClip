"""
Channel YouTube seperti di YouTube sendiri (JOB-3 J3-3..J3-7).

- `avatar(ids)`: foto channel untuk kartu video. Dengan kunci YouTube Data
  API, 50 channel dalam satu panggilan (1 unit kuota); tanpa kunci, halaman
  channel dibaca yt-dlp satu per satu. Disimpan seminggu.
- `halaman(ref, tab, urut)`: banner, avatar, nama, @handle, subscriber,
  deskripsi, dan daftar video tab Video / Shorts / Live.
- Ikuti channel, feed langganan, dan riwayat tontonan disimpan per akun
  OmniClip (setelan profil), bukan di akun YouTube siapa pun.
"""

from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

log = logging.getLogger("omniclip.channel")

TTL_AVATAR = 7 * 24 * 3600
TTL_HALAMAN = 30 * 60
TAB = ("videos", "shorts", "streams")
MAKS_IKUTI = 200
MAKS_RIWAYAT = 300
_POLA_ID = re.compile(r"UC[\w-]{22}")


def _cache():
    from ..repos import cache as cache_repo
    return cache_repo


def _thumb(info: dict, kunci: str) -> str:
    for t in info.get("thumbnails") or []:
        if t.get("id") == kunci and t.get("url"):
            return t["url"]
    return ""


def _avatar_dari_thumbs(info: dict) -> str:
    """Avatar = gambar persegi; banner = gambar lebar. yt-dlp menandai keduanya."""
    a = _thumb(info, "avatar_uncropped")
    if a:
        return a
    persegi = [t for t in info.get("thumbnails") or []
               if t.get("width") and t.get("height") and t["width"] == t["height"]]
    return persegi[-1]["url"] if persegi else ""


def _ytdl_tab(url: str, batas: int) -> Optional[dict]:
    import yt_dlp

    from .ytdlp import _base_opts

    opts = _base_opts()
    opts.update({"extract_flat": "in_playlist", "skip_download": True,
                 "playlistend": max(1, batas), "quiet": True, "no_warnings": True})
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:                            # noqa: BLE001
        log.info("Channel %s tidak terbaca: %s", url, str(e)[:160])
        return None


# --- Avatar ------------------------------------------------------------------

def _avatar_api(ids: list[str]) -> dict:
    from .kanal import _angka, _minta

    hasil: dict = {}
    for i in range(0, len(ids), 50):
        data = _minta("channels", {"part": "snippet,statistics", "id": ",".join(ids[i:i + 50])})
        for it in ((data or {}).get("items") or []):
            sn = it.get("snippet") or {}
            th = sn.get("thumbnails") or {}
            url = ((th.get("medium") or th.get("default") or {}).get("url")) or ""
            hasil[it.get("id")] = {"avatar": url, "nama": sn.get("title") or "",
                                   "handle": sn.get("customUrl") or "",
                                   "pelanggan": _angka((it.get("statistics") or {}).get("subscriberCount"))}
    return hasil


def _avatar_ytdl(cid: str) -> Optional[dict]:
    info = _ytdl_tab(f"https://www.youtube.com/channel/{cid}/videos", 1)
    if not info:
        return None
    return {"avatar": _avatar_dari_thumbs(info), "nama": info.get("channel") or "",
            "handle": info.get("uploader_id") or "", "pelanggan": info.get("channel_follower_count")}


def avatar(ids: list[str]) -> dict:
    """{channel_id: {avatar, nama, handle, pelanggan}} untuk channel yang dikenal."""
    from . import statistik as stat_svc

    ids = [i for i in dict.fromkeys(ids or []) if _POLA_ID.fullmatch(i or "")][:100]
    cache = _cache()
    hasil, kurang = {}, []
    for cid in ids:
        ada = cache.ambil(f"channel.avatar:{cid}", ttl=TTL_AVATAR)
        if ada:
            hasil[cid] = ada
        else:
            kurang.append(cid)
    if kurang and stat_svc.kunci_api():
        for cid, data in _avatar_api(kurang).items():
            hasil[cid] = data
            cache.simpan(f"channel.avatar:{cid}", data)
        kurang = [c for c in kurang if c not in hasil]
    if kurang:
        # Tanpa kunci API: halaman channel dibaca langsung, empat sekaligus,
        # maksimal 24 per permintaan supaya beranda tidak menunggu lama.
        with ThreadPoolExecutor(max_workers=4) as ex:
            for cid, data in zip(kurang[:24], ex.map(_avatar_ytdl, kurang[:24])):
                if data:
                    hasil[cid] = data
                    cache.simpan(f"channel.avatar:{cid}", data)
    return hasil


# --- Halaman channel -------------------------------------------------------------

def _ref_ke_url(ref: str, tab: str) -> str:
    ref = (ref or "").strip()
    if _POLA_ID.fullmatch(ref):
        return f"https://www.youtube.com/channel/{ref}/{tab}"
    nama = ref.lstrip("@")
    if not re.fullmatch(r"[\w.\-]{2,40}", nama):
        raise ValueError("Channel tidak dikenali.")
    return f"https://www.youtube.com/@{nama}/{tab}"


def _video(e: dict, tab: str, info: dict) -> Optional[dict]:
    vid = (e or {}).get("id")
    if not vid or len(vid) != 11:
        return None
    return {
        "id": vid,
        "title": e.get("title") or "",
        "url": f"https://www.youtube.com/watch?v={vid}",
        "duration": e.get("duration") or 0,
        "views": e.get("view_count") or 0,
        "channel": info.get("channel") or "",
        "channel_id": info.get("channel_id") or "",
        "thumbnail": (f"https://i.ytimg.com/vi/{vid}/oardefault.jpg" if tab == "shorts"
                      else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"),
        "jenis": {"shorts": "short", "streams": "live"}.get(tab, "video"),
        "live": e.get("live_status") == "is_live",
    }


def halaman(ref: str, tab: str = "videos", urut: str = "terbaru", batas: int = 60) -> dict:
    tab = tab if tab in TAB else "videos"
    batas = max(1, min(120, int(batas or 60)))
    kunci = f"channel.halaman:{ref}:{tab}:{batas}"
    cache = _cache()
    data = cache.ambil(kunci, ttl=TTL_HALAMAN)
    if not data:
        info = _ytdl_tab(_ref_ke_url(ref, tab), batas)
        if info is None and tab != "videos":
            # Tab yang tidak dimiliki channel (banyak channel tanpa Live):
            # infonya tetap diambil dari tab Video, daftarnya kosong.
            info = _ytdl_tab(_ref_ke_url(ref, "videos"), 1)
            entries = []
        else:
            entries = (info or {}).get("entries") or []
        if info is None:
            raise LookupError("Channel ini tidak bisa dibuka sekarang.")
        data = {
            "info": {
                "id": info.get("channel_id") or "",
                "nama": info.get("channel") or info.get("uploader") or "",
                "handle": info.get("uploader_id") or "",
                "url": info.get("channel_url") or info.get("uploader_url") or "",
                "avatar": _avatar_dari_thumbs(info),
                "banner": _thumb(info, "banner_uncropped"),
                "pelanggan": info.get("channel_follower_count"),
                "terverifikasi": bool(info.get("channel_is_verified")),
                "deskripsi": (info.get("description") or "")[:2000],
            },
            "video": [v for v in (_video(e, tab, info) for e in entries) if v],
        }
        cache.simpan(kunci, data)
        if data["info"]["id"] and data["info"]["avatar"]:
            cache.simpan(f"channel.avatar:{data['info']['id']}",
                         {"avatar": data["info"]["avatar"], "nama": data["info"]["nama"],
                          "handle": data["info"]["handle"], "pelanggan": data["info"]["pelanggan"]})
    video = list(data["video"])
    if urut == "populer":
        video.sort(key=lambda v: v.get("views") or 0, reverse=True)
    return {"info": data["info"], "tab": tab, "urut": urut, "video": video}


# --- Ikuti, feed langganan, riwayat --------------------------------------------

def _setelan(pid: int, kelompok: str) -> dict:
    from ..repos import profil as profil_repo
    return dict(profil_repo.setelan(pid, kelompok) or {})


def _simpan(pid: int, kelompok: str, daftar: list) -> None:
    from ..repos import profil as profil_repo
    profil_repo.simpan_setelan(pid, kelompok, {"daftar": daftar})


def diikuti(pid: int) -> list:
    return list(_setelan(pid, "ikuti").get("daftar") or [])


def ikuti(pid: int, channel_id: str, nama: str = "", avatar_: str = "") -> list:
    if not _POLA_ID.fullmatch(channel_id or ""):
        raise ValueError("Nomor channel tidak sah.")
    daftar = [c for c in diikuti(pid) if c.get("channel_id") != channel_id]
    daftar.insert(0, {"channel_id": channel_id, "nama": (nama or "")[:100],
                      "avatar": (avatar_ or "")[:500], "sejak": time.time()})
    _simpan(pid, "ikuti", daftar[:MAKS_IKUTI])
    return daftar


def berhenti_ikuti(pid: int, channel_id: str) -> list:
    daftar = [c for c in diikuti(pid) if c.get("channel_id") != channel_id]
    _simpan(pid, "ikuti", daftar)
    return daftar


def feed_langganan(pid: int, per_channel: int = 8) -> list:
    """
    Video terbaru dari channel yang diikuti.

    Daftar datar yt-dlp tidak membawa tanggal unggah, jadi urutannya
    bergiliran: video terbaru tiap channel lebih dulu, lalu yang kedua, dst.
    """
    daftar = diikuti(pid)[:40]
    if not daftar:
        return []

    def satu(c):
        try:
            return halaman(c["channel_id"], "videos", "terbaru", 30)["video"][:per_channel]
        except Exception:                              # noqa: BLE001
            return []

    with ThreadPoolExecutor(max_workers=4) as ex:
        per = list(ex.map(satu, daftar))
    out = []
    for k in range(per_channel):
        for vs in per:
            if k < len(vs):
                out.append(vs[k])
    return out


def riwayat(pid: int) -> list:
    return list(_setelan(pid, "riwayat_tonton").get("daftar") or [])


def catat_tonton(pid: int, video: dict) -> list:
    vid = (video or {}).get("id") or ""
    if not re.fullmatch(r"[\w-]{11}", vid):
        raise ValueError("Video tidak sah.")
    bersih = {k: video.get(k) for k in ("id", "title", "channel", "channel_id",
                                         "thumbnail", "duration", "views")}
    bersih["ditonton"] = time.time()
    daftar = [v for v in riwayat(pid) if v.get("id") != vid]
    daftar.insert(0, bersih)
    _simpan(pid, "riwayat_tonton", daftar[:MAKS_RIWAYAT])
    return daftar


def hapus_riwayat(pid: int, video_id: str = "") -> list:
    daftar = [v for v in riwayat(pid) if video_id and v.get("id") != video_id]
    _simpan(pid, "riwayat_tonton", daftar)
    return daftar
