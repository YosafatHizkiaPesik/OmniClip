"""
Seluruh video di kanal YouTube, bukan hanya yang diunggah lewat OmniClip.

Dilaporkan pemiliknya 9 Oktober 2026: "disana tidak memuat seluruh video yang
kita upload dan juga tidak ada grafik views atau apapun".

Ia benar, dan sebabnya ada di rancangan lamanya: `analitik.kumpulkan` membaca
tabel `uploads`, yaitu riwayat unggahan OmniClip sendiri. Video yang diunggah
dari ponsel atau dari peramban tidak pernah lewat tabel itu, jadi tidak pernah
terlihat. Pada kanal pemiliknya saat ini: 4 video di kanal, 1 yang diunggah
OmniClip. Tiga perempat datanya hilang dari halaman yang seharusnya menjawab
"video saya harus seperti apa".

TIDAK BUTUH IZIN BARU. Semuanya lewat kunci YouTube Data API v3 yang sudah
terpasang: `channels.list` memberi playlist unggahan kanal, `playlistItems`
memberi daftar id-nya, `videos.list` memberi tayangan, durasi, dan tanggal
terbitnya. Terbukti pada kanal pemiliknya: 4 video terbaca, termasuk tiga yang
tidak pernah disentuh OmniClip.

Batasnya dikatakan apa adanya: kunci API hanya melihat apa yang bisa dilihat
publik. Video yang berstatus pribadi tidak muncul di playlist unggahan, dan
itulah sebabnya jumlah video di sini bisa lebih kecil daripada yang Anda tahu
ada di kanal. Membaca yang pribadi menuntut izin `youtube.readonly` dan
persetujuan ulang dari setiap akun, dan itu keputusan pemiliknya, bukan
keputusan berkas ini.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger("omniclip.kanal")

API = "https://www.googleapis.com/youtube/v3"

# Berapa lama daftar video kanal disimpan sebelum ditanyakan lagi.
#
# Tayangan tidak berubah tiap detik, dan tiap pembukaan halaman yang memanggil
# API adalah kuota yang terpakai. Lima belas menit sama dengan TTL statistik
# yang sudah ada, supaya dua angka di layar yang sama tidak pernah berasal dari
# dua waktu yang berbeda.
TTL = 15 * 60

# Satu halaman playlist, dan satu permintaan videos.list, masing-masing 50.
SEKALI = 50

# Berapa video yang ditarik paling banyak. Kuota hariannya 10.000 unit dan ini
# memakai 1 unit per 50 video, jadi batasnya bukan soal kuota melainkan soal
# halaman yang tidak ada gunanya memuat dua ribu baris.
MAKS = 500


def _angka(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def durasi_detik(iso: str) -> Optional[float]:
    """`PT2M39S` jadi 159. Durasi dipakai membandingkan klip pendek dan panjang."""
    m = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", iso or "")
    if not m:
        return None
    hari, jam, menit, detik = (float(x) if x else 0.0 for x in m.groups())
    return hari * 86400 + jam * 3600 + menit * 60 + detik


def id_dari_tautan(teks: str) -> str:
    """
    Nomor kanal dari apa pun yang ditempel orang: tautan, @nama, atau nomornya.

    Diterima apa adanya karena yang menempelkannya sedang menyalin dari bilah
    alamat peramban, bukan membaca dokumentasi API.
    """
    t = (teks or "").strip()
    if not t:
        return ""
    if re.fullmatch(r"UC[\w-]{20,}", t):
        return t
    m = re.search(r"/channel/(UC[\w-]{20,})", t)
    return m.group(1) if m else ""


def _handle_dari_tautan(teks: str) -> str:
    """`@nama` dari tautan atau dari teks yang ditempel."""
    t = (teks or "").strip()
    m = re.search(r"(?:youtube\.com/)?@([\w.\-]{3,30})", t)
    return m.group(1) if m else ""


def _minta(jalan: str, params: dict) -> Optional[dict]:
    import requests

    from . import statistik as stat_svc

    kunci = stat_svc.kunci_api()
    if not kunci:
        return None
    try:
        r = requests.get(f"{API}/{jalan}", params={**params, "key": kunci}, timeout=25)
    except Exception as e:                           # noqa: BLE001
        log.info("%s tidak terjawab: %s", jalan, str(e)[:160])
        return None
    if not r.ok:
        # Kuota habis atau kunci salah bukan alasan menggagalkan halaman yang
        # memanggilnya; yang hilang hanya angkanya.
        log.info("%s menjawab %s: %s", jalan, r.status_code, r.text[:200])
        return None
    try:
        return r.json()
    except ValueError:
        return None


def cari_id_kanal(profil_id: int) -> str:
    """
    Nomor kanal akun ini: dari setelannya, atau ditebak dari video yang pernah
    diunggah OmniClip.

    Ditebak, bukan ditanyakan, selama masih bisa. Satu video yang pernah naik
    lewat OmniClip sudah membawa `snippet.channelId` miliknya sendiri, dan
    menanyakannya kepada orang yang baru saja mengunggah ke kanalnya sendiri
    adalah pertanyaan yang jawabannya sudah kita punya.
    """
    from ..repos import profil as profil_repo
    from ..repos import uploads as uploads_repo

    tersimpan = (profil_repo.setelan(profil_id, "kanal") or {}).get("id") or ""
    if id_dari_tautan(tersimpan):
        return id_dari_tautan(tersimpan)

    naik = [u for u in uploads_repo.list_recent(50, None, profil_id=profil_id)
            if u.get("target") == "youtube" and (u.get("remote_id") or "").strip()]
    if not naik:
        return ""
    data = _minta("videos", {"part": "snippet", "id": naik[0]["remote_id"].strip()})
    for item in ((data or {}).get("items") or []):
        cid = ((item.get("snippet") or {}).get("channelId") or "").strip()
        if cid:
            try:
                profil_repo.simpan_setelan(profil_id, "kanal", {"id": cid})
            except Exception:                        # noqa: BLE001
                pass
            return cid
    return ""


def id_dari_handle(handle: str) -> str:
    """Nomor kanal dari `@nama`, untuk yang belum pernah mengunggah lewat OmniClip."""
    nama = _handle_dari_tautan(handle) or (handle or "").lstrip("@").strip()
    if not nama:
        return ""
    data = _minta("channels", {"part": "id", "forHandle": f"@{nama}"})
    for item in ((data or {}).get("items") or []):
        if item.get("id"):
            return str(item["id"])
    return ""


def kanal(channel_id: str) -> dict:
    """Nama, jumlah pelanggan, jumlah video, dan playlist unggahannya."""
    data = _minta("channels", {"part": "snippet,statistics,contentDetails",
                               "id": channel_id})
    item = ((data or {}).get("items") or [None])[0]
    if not item:
        return {}
    s = item.get("statistics") or {}
    sn = item.get("snippet") or {}
    return {
        "id": channel_id,
        "nama": sn.get("title") or "",
        "pelanggan": _angka(s.get("subscriberCount")),
        "pelanggan_disembunyikan": bool(s.get("hiddenSubscriberCount")),
        "jumlah_video": _angka(s.get("videoCount")),
        "total_tayangan": _angka(s.get("viewCount")),
        "playlist_unggahan": ((item.get("contentDetails") or {})
                              .get("relatedPlaylists") or {}).get("uploads") or "",
    }


def _id_video(playlist: str, batas: int) -> list:
    out: list = []
    halaman = ""
    while len(out) < batas:
        p = {"part": "contentDetails", "playlistId": playlist, "maxResults": SEKALI}
        if halaman:
            p["pageToken"] = halaman
        data = _minta("playlistItems", p)
        if not data:
            break
        for item in (data.get("items") or []):
            vid = ((item.get("contentDetails") or {}).get("videoId") or "").strip()
            if vid:
                out.append(vid)
        halaman = data.get("nextPageToken") or ""
        if not halaman:
            break
    return out[:batas]


def video(ids: list) -> list:
    """Tayangan, suka, komentar, durasi, dan tanggal terbit tiap video."""
    hasil = []
    for i in range(0, len(ids), SEKALI):
        data = _minta("videos", {"part": "snippet,statistics,contentDetails",
                                 "id": ",".join(ids[i:i + SEKALI])})
        for v in ((data or {}).get("items") or []):
            sn = v.get("snippet") or {}
            s = v.get("statistics") or {}
            cd = v.get("contentDetails") or {}
            hasil.append({
                "id": str(v.get("id") or ""),
                "judul": sn.get("title") or "",
                "terbit": sn.get("publishedAt") or "",
                "sampul": (((sn.get("thumbnails") or {}).get("medium") or {})
                           .get("url") or ""),
                "tayangan": _angka(s.get("viewCount")),
                "suka": _angka(s.get("likeCount")),
                "komentar": _angka(s.get("commentCount")),
                "durasi": durasi_detik(cd.get("duration") or ""),
                "tag": sn.get("tags") or [],
                "deskripsi": (sn.get("description") or "")[:600],
            })
    return hasil


def semua(profil_id: int, *, batas: int = MAKS, segar: bool = False) -> dict:
    """
    Seluruh video kanal akun ini, dengan angkanya masing-masing.

    Disimpan `TTL` detik. Tanpa itu, tiap kali halaman Analitik dibuka ia
    memakai kuota lagi untuk angka yang sama persis.
    """
    from ..repos import cache as cache_repo

    cid = cari_id_kanal(profil_id)
    if not cid:
        return {"ada": False, "alasan": "kanal_belum_dikenali", "video": []}

    simpanan = f"kanal:{cid}:v1"
    if not segar:
        tersimpan = cache_repo.ambil(simpanan, ttl=TTL)
        if isinstance(tersimpan, dict) and tersimpan.get("video"):
            return tersimpan

    info = kanal(cid)
    if not info or not info.get("playlist_unggahan"):
        return {"ada": False, "alasan": "kanal_tidak_terbaca", "kanal": info,
                "video": []}
    ids = _id_video(info["playlist_unggahan"], batas)
    daftar = video(ids)
    daftar.sort(key=lambda v: v.get("terbit") or "", reverse=True)
    hasil = {"ada": True, "kanal": info, "video": daftar,
             "jumlah": len(daftar)}
    try:
        cache_repo.simpan(simpanan, hasil)
    except Exception:                                # noqa: BLE001
        pass
    return hasil
