"""
Isi beranda: video yang sedang ramai, dan video yang sesuai yang dicari.

Dilaporkan pemiliknya 6 Oktober 2026 sambil menunjukkan layarnya: "entah
mengapa selalu saja video video ini yang tampil, kemudian video tersebut tidak
menarik sama sekali, satu videonya tentang vlog orang random dan satu lagi
teknik wawancara apalah itu yang tidak akan pernah saya tonton atau klip".

DUA VIDEO ITU MENUNJUKKAN PERSIS APA YANG RUSAK, dan keduanya terbaca dari
kartunya sendiri:

  - vlog 23 detik, 3 tayangan, diunggah hari ini;
  - kuliah teknik wawancara 9 menit, 216 tayangan, enam tahun lalu.

Tidak ada satu pun saringan yang menahan keduanya. Beranda memanggil pencarian
YouTube dengan kueri umum seperti "wawancara mendalam indonesia", mengambil
urutan RELEVANSI apa adanya, lalu menampilkannya. Relevansi menjawab "paling
cocok dengan katanya", bukan "layak dijadikan klip", dan kedua video itu
memang sangat cocok dengan katanya.

Jadi berkas ini menambahkan dua hal yang sebelumnya tidak ada.

PERTAMA, sumber "sedang ramai" yang sungguhan. `videos.list?chart=mostPopular`
dengan `regionCode=ID` adalah daftar populer milik YouTube sendiri untuk
Indonesia, bukan tebakan dari kata kunci. Ia memakai kunci YouTube Data API
yang sudah dipasang pemiliknya untuk membaca tayangan, memakan satu unit kuota
per panggilan, dan disimpan tiga jam. Tanpa kunci, beranda tetap bekerja dari
pencarian saja.

KEDUA, saringan mutu yang berlaku untuk SEMUA sumber: panjang minimal, tayangan
minimal, tanpa siaran langsung, tanpa klip musik. Saringannya BERTAHAP, dan itu
disengaja: kueri sempit yang hasilnya sedikit tidak boleh menghasilkan beranda
kosong, jadi ambangnya diturunkan selangkah demi selangkah sampai layarnya
cukup terisi. Lebih baik menampilkan video yang kurang ramai daripada
menampilkan halaman kosong.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("omniclip.beranda")

# Daftar populer YouTube untuk negara pengguna, disimpan tiga jam.
#
# Daftarnya sendiri hanya berganti beberapa kali sehari, dan satu panggilan
# memakan satu unit dari 10.000 unit per hari. Tiga jam berarti paling banyak
# delapan putaran sehari dikali jumlah kategori: masih di bawah empat puluh
# unit, sementara membaca tayangan klip memakai sisanya.
RAMAI_TTL = 3 * 3600

# Kategori yang diminta, dan DAFTAR UMUMNYA TIDAK DIPAKAI.
#
# Diuji pada daftar populer Indonesia hari itu: daftar umum berisi klip musik,
# trailer sinetron 25 detik, dan video kartun truk untuk anak-anak. Semuanya
# memang sedang ramai, dan tidak satu pun bisa dijadikan klip oleh aplikasi
# yang mencari orang berbicara.
#
#   20 Gaming, 24 Hiburan, 23 Komedi
KATEGORI_RAMAI = ("20", "24", "23")

# Musik dibuang. Klip musik tidak punya yang dicari aplikasi ini — orang yang
# berbicara — dan tiap hari ia memenuhi daftar populer Indonesia.
KATEGORI_BUANG = {"10"}

# Panjang sumber yang masuk akal untuk diklip.
#
# Di bawah tiga menit hampir tidak ada yang bisa dipotong jadi klip pendek yang
# berdiri sendiri; di atas empat jam yang ada di sana siaran langsung, dan
# mengunduhnya saja menghabiskan ruang cakram berjam-jam.
DURASI_MIN = 180
DURASI_MAKS = 4 * 3600

# Ambang tayangan, dari yang paling ketat ke yang paling longgar.
#
# Dipakai bertahap: saringan pertama yang menyisakan cukup video yang dipakai.
# Angka 0 di ujungnya bukan kelalaian melainkan janji bahwa beranda tidak
# pernah kosong hanya karena ambang yang kita sendiri yang memilih.
AMBANG_TAYANGAN = (10_000, 2_000, 500, 0)


# Ciri video musik, untuk yang lolos dari kategori.
#
# Kategori 10 (Musik) sudah dibuang, tapi klip musik, kompilasi lagu, dan
# karaoke sering diunggah ke kategori Hiburan, dan pencarian pun membawanya.
# Tidak ada yang bisa diklip dari video tanpa orang berbicara, jadi ciri yang
# paling jelas dibuang di sini: nama kanal "… - Topic" buatan YouTube sendiri,
# dan kata-kata yang hampir selalu berarti musik.
_MUSIK = re.compile(
    r"\b(official (music )?video|lirik|lyrics?|full album|kumpulan lagu|"
    r"lagu[- ]lagu|karaoke|cover|ost|instrumental|piano mix|dj remix)\b", re.I)


def _musik(v: dict) -> bool:
    kanal = (v.get("channel") or "").strip().lower()
    if kanal.endswith("- topic"):
        return True
    return bool(_MUSIK.search(v.get("title") or ""))


def _detik(iso: str) -> int:
    """Lama video dari bentuk ISO-8601 milik YouTube (PT1H2M3S)."""
    m = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    jam, menit, detik = (int(x or 0) for x in m.groups())
    return jam * 3600 + menit * 60 + detik


def _tanggal(publishedAt: str) -> str:
    """'2026-10-06T...' jadi '20261006', bentuk yang dipakai kartu video."""
    try:
        t = datetime.fromisoformat((publishedAt or "").replace("Z", "+00:00"))
        return t.astimezone(timezone.utc).strftime("%Y%m%d")
    except (TypeError, ValueError):
        return ""


def _kartu(item: dict, buang_musik: bool = True) -> Optional[dict]:
    s = item.get("snippet") or {}
    st = item.get("statistics") or {}
    cd = item.get("contentDetails") or {}
    vid = str(item.get("id") or "").strip()
    if not vid:
        return None
    # Topik Musik memang meminta musik; hanya beranda yang membuangnya.
    if buang_musik and (s.get("categoryId") or "") in KATEGORI_BUANG:
        return None
    # Siaran langsung yang sedang berjalan belum punya akhir, dan mengunduh
    # video yang masih bertambah panjang tidak pernah selesai.
    if (s.get("liveBroadcastContent") or "none") != "none":
        return None
    durasi = _detik(cd.get("duration") or "")
    gambar = ((s.get("thumbnails") or {}).get("high")
              or (s.get("thumbnails") or {}).get("medium") or {})
    try:
        tayangan = int(st.get("viewCount") or 0)
    except (TypeError, ValueError):
        tayangan = 0
    return {
        "id": vid,
        "title": s.get("title") or "",
        "url": f"https://www.youtube.com/watch?v={vid}",
        "duration": durasi,
        "channel": s.get("channelTitle") or "",
        "channel_id": s.get("channelId") or "",
        "views": tayangan,
        "thumbnail": gambar.get("url") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        "description": "",
        "upload_date": _tanggal(s.get("publishedAt") or ""),
        # Dibawa sampai ke kartunya: orang berhak tahu kenapa sebuah video ada
        # di berandanya. Tanpa ini, isi beranda terasa seperti nasib.
        "sebab": "ramai",
    }


def _minta(kunci: str, kategori: Optional[str], maks: int, wilayah: str = "ID",
           halaman: Optional[str] = None, buang_musik: bool = True) -> tuple[list[dict], Optional[str]]:
    """Satu halaman daftar populer: (kartu, token halaman berikutnya)."""
    import requests

    params = {
        "part": "snippet,statistics,contentDetails",
        "chart": "mostPopular", "regionCode": wilayah_sah(wilayah),
        "maxResults": min(max(maks, 1), 50), "key": kunci,
    }
    if kategori:
        params["videoCategoryId"] = kategori
    if halaman:
        params["pageToken"] = halaman
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/videos",
                         params=params, timeout=20)
    except Exception as e:                               # noqa: BLE001
        log.info("Daftar ramai tidak terbaca: %s", str(e)[:160])
        return [], None
    if not r.ok:
        # Kuota habis atau kunci dibatasi bukan alasan menggagalkan beranda;
        # yang hilang hanya lapis "sedang ramai".
        log.info("mostPopular menjawab %s: %s", r.status_code, r.text[:160])
        return [], None
    data = r.json()
    kartu = [_kartu(it, buang_musik) for it in (data.get("items") or [])]
    return [k for k in kartu if k], data.get("nextPageToken")


def wilayah_sah(kode: Optional[str]) -> str:
    """Kode negara dua huruf (ISO 3166), atau ID bila tidak terbaca."""
    kode = (kode or "").strip().upper()
    return kode if re.fullmatch(r"[A-Z]{2}", kode) else "ID"


def ramai(*, kunci: Optional[str] = None, maks: int = 50, wilayah: str = "ID") -> list[dict]:
    """
    Video yang sedang ramai di negara pengguna, menurut YouTube sendiri.

    Daftar kosong bila kunci API belum dipasang, kuotanya habis, atau
    jaringannya mati. Itu keadaan yang sah: beranda masih punya lapis
    pencarian, dan memaksakan daftar palsu lebih buruk daripada tidak ada.
    """
    from . import statistik

    kunci = (kunci if kunci is not None else statistik.kunci_api()).strip()
    if not kunci:
        return []

    from ..repos import cache as cache_repo

    wilayah = wilayah_sah(wilayah)
    simpanan = cache_repo.ambil(f"beranda:ramai:{wilayah}", ttl=RAMAI_TTL)
    if isinstance(simpanan, list) and simpanan:
        return simpanan[:maks]

    hasil: list[dict] = []
    terlihat: set[str] = set()
    for kategori in KATEGORI_RAMAI:
        for v in _minta(kunci, kategori, 25, wilayah)[0]:
            if v["id"] in terlihat:
                continue
            terlihat.add(v["id"])
            hasil.append(v)
    if hasil:
        cache_repo.simpan(f"beranda:ramai:{wilayah}", hasil)
    return hasil[:maks]


# Topik di Beranda = kategori resmi YouTube (JOB-3, diminta pemilik 15 Oktober
# 2026: "buat saja topiknya mengikuti YouTube, jangan membuat sendiri dengan
# manipulasi search bar"). Sebelumnya tiap topik adalah kueri buatan kita
# ("komedi lucu indonesia", "gameplay walkthrough funny") yang dikirim ke kotak
# cari: kuerinya terlihat di kotak cari, terikat ke Indonesia, dan "gameplay
# walkthrough funny" mengembalikan video kartun yang bukan gaming.
#
# Sekarang isinya `chart=mostPopular` per kategori untuk negara pengguna,
# daftar yang sama yang disusun YouTube sendiri. Diuji 15 Oktober 2026 untuk
# ID, US, GB, IN: semua kategori di bawah tersedia; Pendidikan (27) dan Wisata
# (19) menjawab 404 sehingga tidak ditawarkan.
#
# kunci topik -> id kategori YouTube ("" = semua kategori, "Sedang tren").
TOPIK = {
    "tren": "", "gaming": "20", "musik": "10", "hiburan": "24", "komedi": "23",
    "orang": "22", "olahraga": "17", "berita": "25", "sains": "28",
    "gaya": "26", "film": "1", "hewan": "15", "otomotif": "2",
}

# Nama kategori dalam bahasa Inggris, untuk pencarian cadangan saat kunci API
# belum dipasang. Kata ini tidak pernah ditulis ke kotak cari.
TOPIK_CADANGAN = {
    "tren": "trending", "gaming": "gaming", "musik": "music",
    "hiburan": "entertainment", "komedi": "comedy", "orang": "vlog",
    "olahraga": "sports", "berita": "news", "sains": "science technology",
    "gaya": "how to", "film": "animation", "hewan": "animals", "otomotif": "cars",
}

# Daftar populer satu kategori paling banyak sekitar 200 video (Gaming US hari
# itu: 127), empat halaman berisi 50.
TOPIK_MAKS = 200


def topik(nama: str, wilayah: str, maks: int, *, kunci: Optional[str] = None) -> Optional[list[dict]]:
    """
    Video populer satu kategori YouTube di satu negara.

    None bila kunci API tidak ada atau YouTube menolak: pemanggil lalu memakai
    pencarian cadangan. Disimpan tiga jam, seperti daftar ramai beranda.
    """
    from . import statistik

    if nama not in TOPIK:
        return None
    kunci = (kunci if kunci is not None else statistik.kunci_api()).strip()
    if not kunci:
        return None

    from ..repos import cache as cache_repo

    wilayah = wilayah_sah(wilayah)
    maks = max(1, min(maks, TOPIK_MAKS))
    kunci_simpan = f"topik:{nama}:{wilayah}"
    simpanan = cache_repo.ambil(kunci_simpan, ttl=RAMAI_TTL)
    simpanan = simpanan if isinstance(simpanan, dict) else {}
    hasil = list(simpanan.get("items") or [])
    token = simpanan.get("token")
    selesai = bool(simpanan.get("selesai"))
    if len(hasil) >= maks or selesai:
        return hasil[:maks]

    terlihat = {v["id"] for v in hasil}
    while len(hasil) < maks:
        kartu, token = _minta(kunci, TOPIK[nama], 50, wilayah, token,
                              buang_musik=(nama != "musik"))
        if not kartu and not hasil:
            return None
        for v in kartu:
            if v["id"] not in terlihat:
                terlihat.add(v["id"])
                v["sebab"] = "topik"
                hasil.append(v)
        if not token:
            selesai = True
            break
    cache_repo.simpan(kunci_simpan, {"items": hasil, "token": token, "selesai": selesai})
    return hasil[:maks]


def layak(v: dict, ambang: int) -> bool:
    """Apakah video ini pantas ditawarkan sebagai bahan klip."""
    durasi = float(v.get("duration") or 0)
    if durasi and not (DURASI_MIN <= durasi <= DURASI_MAKS):
        return False
    if _musik(v):
        return False
    return int(v.get("views") or 0) >= ambang


def saring(videos: list[dict], cukup: int) -> list[dict]:
    """
    Saringan mutu yang mengalah sebelum berandanya jadi kosong.

    Ambang paling ketat dicoba lebih dulu; kalau yang lolos belum sebanyak
    satu layar, ambangnya diturunkan. Yang TIDAK pernah dilonggarkan batas
    panjangnya: video 23 detik tetap tidak bisa dijadikan klip berapa pun
    ramainya.
    """
    for ambang in AMBANG_TAYANGAN:
        lolos = [v for v in videos if layak(v, ambang)]
        if len(lolos) >= cukup or ambang == 0:
            if ambang != AMBANG_TAYANGAN[0]:
                log.info("Saringan beranda turun ke %d tayangan: %d video lolos",
                         ambang, len(lolos))
            return lolos
    return []


# Satu dari setiap `SELA` kartu diambil dari daftar "sedang ramai".
#
# Sepertiga, bukan separuh: yang dicari pemiliknya sendiri tetap harus jadi
# isi utama berandanya, dan daftar populer Indonesia memang tidak seluruhnya
# cocok untuk kanal mana pun.
SELA = 3


def gabung(ramai_list: list[dict], cari_list: list[dict], want: int,
           maks_per_kanal: int = 3) -> list[dict]:
    """
    Menyisipkan video yang sedang ramai di antara hasil pencarian.

    Satu dari setiap `SELA` kartu diambil dari daftar ramai SELAMA masih ada.
    Begitu satu sumber habis, giliran berikutnya langsung diambil dari sumber
    yang satu lagi: tiap putaran harus memasang tepat satu video atau berhenti,
    tidak boleh ada putaran yang tidak menghasilkan apa-apa.
    """
    hasil: list[dict] = []
    dipakai: set = set()
    per_kanal: dict = {}
    maju = {"ramai": 0, "cari": 0}
    sumber = {"ramai": ramai_list, "cari": cari_list}

    def boleh(v: dict) -> bool:
        vid = v.get("id") or v.get("url")
        if vid in dipakai:
            return False
        kanal = (v.get("channel") or "").strip().lower()
        return not (kanal and per_kanal.get(kanal, 0) >= maks_per_kanal)

    def ambil(nama: str):
        """Video berikutnya dari satu sumber, melewati yang tidak boleh."""
        i = maju[nama]
        daftar = sumber[nama]
        while i < len(daftar) and not boleh(daftar[i]):
            i += 1
        maju[nama] = i
        if i >= len(daftar):
            return None
        maju[nama] = i + 1
        return daftar[i]

    while len(hasil) < want:
        urutan = ("ramai", "cari") if len(hasil) % SELA == 1 else ("cari", "ramai")
        v = None
        for nama in urutan:
            v = ambil(nama)
            if v is not None:
                break
        if v is None:
            break
        vid = v.get("id") or v.get("url")
        kanal = (v.get("channel") or "").strip().lower()
        dipakai.add(vid)
        per_kanal[kanal] = per_kanal.get(kanal, 0) + 1
        hasil.append(v)
    return hasil


def _kata(teks: str) -> set[str]:
    """Kata bermakna dari sepotong teks, huruf kecil, tanpa kata sambung."""
    buang = {"dan", "yang", "di", "ke", "dari", "untuk", "dengan", "ini", "itu",
             "the", "a", "of", "in", "video", "indonesia", "terbaru", "full"}
    return {w for w in re.findall(r"[a-z0-9]+", (teks or "").lower())
            if len(w) > 2 and w not in buang}


def urut_dekat(videos: list[dict], kolam: list[str]) -> list[dict]:
    """
    Yang sedang ramai, didahulukan yang paling dekat dengan yang dicari.

    Daftar populer Indonesia tidak dibuat untuk satu kanal pun, jadi sebagian
    isinya memang tidak akan pernah diklip pemiliknya. Urutannya tidak membuang
    apa-apa — yang tidak nyambung turun ke bawah, bukan hilang — supaya beranda
    tetap bisa memperkenalkan sesuatu yang belum pernah dicari.
    """
    minat = set()
    for q in kolam or []:
        minat |= _kata(q)
    if not minat:
        return list(videos)
    bernilai = [(len(_kata(f"{v.get('title')} {v.get('channel')}") & minat), i, v)
                for i, v in enumerate(videos)]
    bernilai.sort(key=lambda t: (-t[0], t[1]))
    return [v for _, _, v in bernilai]
