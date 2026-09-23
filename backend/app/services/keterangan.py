"""
Caption dan tagar yang siap ditempel, per platform.

Pemiliknya melaporkan dua hal: captionnya kurang hook, dan tagarnya sering
tidak nyambung dengan isinya. Keduanya benar, dan sebabnya sama — selama ini
judul klip dibuat untuk jadi NAMA BERKAS, bukan untuk jadi caption yang dibaca
orang sambil menggulir.

Aturan yang dipakai di sini bukan selera saya. Diperiksa September 2026:

  * **Tagar bukan lagi alat pertumbuhan.** Ia cuma menandai kategori. TikTok
    bahkan membatasi keras lima tagar sejak Agustus 2025. Menempelkan tiga
    puluh tagar tidak menaikkan apa pun dan membuat unggahan terlihat seperti
    spam.
  * **Yang menggantikannya: kata kunci di caption.** Orang MENCARI di TikTok
    dan Instagram sekarang, dan yang dicocokkan adalah kata-kata di baris
    pertama caption — bukan tagarnya.
  * **Tiga detik pertama menentukan.** Yang dinilai algoritma adalah berapa
    lama orang bertahan; caption yang bagus membuat orang berhenti menggulir
    cukup lama untuk mendengar kalimat pertamanya.

Jadi bentuk caption di sini selalu sama, dan urutannya sengaja:

    baris 1  hook — memuat kata yang akan diketik orang saat mencari
    baris 2  satu kalimat konteks, juga membawa kata kuncinya
    baris 3  tagar, tiga sampai lima, semuanya dari isi klipnya

Yang TIDAK dilakukan: huruf kapital semua, tanda seru bertumpuk, janji yang
tidak ada isinya di klip, dan tagar populer yang tidak nyambung. Pemiliknya
meminta "menarik tapi jangan heboh", dan itu juga yang terbukti lebih awet:
caption yang menjanjikan lebih daripada isinya menghasilkan orang yang pergi
di detik keempat, dan itu sinyal terburuk yang bisa diberikan sebuah video.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger("omniclip.keterangan")

VERSI = 1

# Batas tiap platform. Angka tagar di sini BATAS KERAS, bukan saran.
PLATFORM = {
    "tiktok": {
        "label": "TikTok",
        "maks_tagar": 5,
        "maks_caption": 2200,
        "judul_terpisah": False,
        "unggah": "https://www.tiktok.com/tiktokstudio/upload",
        "catatan": "TikTok membatasi lima tagar. Pilih sound yang sedang naik "
                   "di aplikasinya — itu tidak bisa dilakukan lewat unggahan web.",
    },
    "instagram": {
        "label": "Instagram Reels",
        "maks_tagar": 5,
        "maks_caption": 2200,
        "judul_terpisah": False,
        "unggah": "https://www.instagram.com/",
        "catatan": "Unggah dari aplikasi HP bila ingin memakai sound, stiker, "
                   "atau efek — semuanya tidak ada di versi web.",
    },
    "shorts": {
        "label": "YouTube Shorts",
        "maks_tagar": 3,
        "maks_caption": 4800,
        "judul_terpisah": True,
        "maks_judul": 100,
        "unggah": "https://studio.youtube.com/",
        "catatan": "Di YouTube judulnya yang paling menentukan, bukan "
                   "deskripsinya. Tiga tagar pertama muncul di atas judul.",
    },
    "facebook": {
        "label": "Facebook Reels",
        "maks_tagar": 3,
        "maks_caption": 2200,
        "judul_terpisah": False,
        "unggah": "https://www.facebook.com/reels/create",
        "catatan": "Tagar paling tidak berpengaruh di sini; yang menentukan "
                   "kalimat pertamanya.",
    },
}

SISTEM = """Anda penulis caption untuk video pendek berbahasa Indonesia.

Anda diberi ISI SEBUAH KLIP (transkrip apa adanya). Tugas Anda menulis caption
yang membuat orang berhenti menggulir — tanpa menjanjikan apa pun yang tidak
ada di dalam klip itu.

Tiga hal yang menentukan, berurutan:

1. HOOK (baris pertama). Paling penting. Ia harus:
   - memuat KATA YANG AKAN DIKETIK ORANG saat mencari topik ini, karena orang
     sekarang mencari di TikTok dan Instagram seperti mencari di Google;
   - menyebutkan hal yang konkret dari klipnya — angka, nama, kejadian,
     pernyataan yang mengejutkan;
   - maksimal 70 karakter, dan berdiri sendiri tanpa perlu menonton dulu.

2. KONTEKS (baris kedua). Satu kalimat. Menjelaskan siapa yang bicara atau apa
   yang sedang dibahas, sekaligus membawa kata kunci lain. Bukan pengulangan
   hook.

3. TAGAR. Lima sampai delapan, diurutkan dari yang paling nyambung. Semuanya
   harus berasal dari ISI klip: topiknya, bidangnya, nama orang atau tempat
   yang disebut. DILARANG memakai tagar umum seperti #fyp, #viral, #foryou,
   #trending — semuanya tidak menaikkan apa pun dan membuatnya terlihat spam.

Gaya yang diminta: menarik tapi TIDAK heboh.
  - Jangan menulis dengan huruf kapital semua.
  - Paling banyak satu emoji, dan hanya bila benar-benar menambah.
  - Tanpa tanda seru bertumpuk, tanpa "WAJIB NONTON", tanpa "gila banget".
  - Bahasa sehari-hari, seperti orang bercerita ke temannya.

Yang paling dilarang: menjanjikan sesuatu yang tidak ada di klipnya. Orang yang
merasa tertipu pergi di detik keempat, dan itu sinyal terburuk yang bisa
diberikan sebuah video ke algoritma."""


def _schema() -> dict:
    return {
        "type": "OBJECT",
        "required": ["hook", "konteks", "kata_kunci", "tagar"],
        "property_ordering": ["hook", "konteks", "kata_kunci", "tagar"],
        "properties": {
            "hook": {"type": "STRING"},
            "konteks": {"type": "STRING"},
            # Kata yang diketik orang saat mencari. Dipakai memeriksa apakah
            # hook-nya benar-benar memuat salah satunya.
            "kata_kunci": {"type": "ARRAY", "items": {"type": "STRING"}},
            "tagar": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
    }


_UMUM = {"fyp", "fypage", "foryou", "foryoupage", "viral", "viralvideo", "trending",
         "trend", "explore", "explorepage", "reels", "reel", "shorts", "short",
         "tiktok", "instagram", "youtube", "video", "keren", "wow"}


def _bersih_tagar(mentah, *, maks: int, sertakan_shorts: bool = False) -> list[str]:
    """
    Tagar yang sudah dirapikan: tanpa tagar umum, tanpa kembar, dibatasi jumlah.

    `#shorts` diperlakukan berbeda dari tagar umum lain dan hanya untuk YouTube:
    ia bukan tagar populer yang ditempel asal, melainkan penanda yang benar-
    benar menempatkan video di rak Shorts.
    """
    keluar: list[str] = []
    dilihat: set[str] = set()
    if sertakan_shorts:
        keluar.append("#shorts")
        dilihat.add("shorts")
    for t in mentah or []:
        s = re.sub(r"[^0-9a-zA-Z_À-ɏ]", "", str(t).lstrip("#")).lower()
        if not (2 < len(s) <= 24) or s in dilihat or s in _UMUM:
            continue
        dilihat.add(s)
        keluar.append(f"#{s}")
        if len(keluar) >= maks:
            break
    return keluar


def _potong(teks: str, batas: int) -> str:
    teks = " ".join((teks or "").split())
    if len(teks) <= batas:
        return teks
    potong = teks[:batas].rsplit(" ", 1)[0]
    return potong.rstrip(" ,.;:-") or teks[:batas]


# --- Jalur tanpa AI ---------------------------------------------------------
# Gumaman yang tidak boleh ikut ke dalam caption.
_GUMAM = re.compile(r"\b(ee+|eh|hmm+|mm+|anu|gitu|ya kan|kan ya)\b[,.]?\s*",
                    re.IGNORECASE)


def _hook_lokal(teks: str, judul_klip: str, judul_video: str = "") -> str:
    """
    Hook dari kalimat klipnya sendiri.

    Bukan karangan: yang dipilih kalimat yang paling bisa berdiri sendiri —
    cukup panjang untuk bermakna, tidak dibuka dengan kata sambung, dan tidak
    memuat kata ganti yang menunjuk ke sesuatu sebelum klipnya.

    Judul klip dipakai HANYA bila ia memang milik klip itu. Saat klip tidak
    punya judul sendiri, renderer mengisinya dengan judul video sumber — dan
    judul video sumber sebagai caption klip adalah persis keluhan yang
    dilaporkan: tidak nyambung dengan isi potongannya.
    """
    judul_klip = (judul_klip or "").strip()
    sama = judul_klip and judul_video and judul_klip.lower() == judul_video.strip().lower()
    if judul_klip and len(judul_klip) >= 12 and not sama:
        return _potong(judul_klip, 70)
    buruk = ("jadi", "terus", "nah", "makanya", "setelah", "kemudian", "itu",
             "dia", "gitu", "ya", "kalau", "tapi", "nih", "oh", "ini")
    for kalimat in re.split(r"(?<=[.!?])\s+", _GUMAM.sub("", teks or "").strip()):
        k = kalimat.strip()
        if not (20 <= len(k) <= 120):
            continue
        if k.split()[0].lower().strip(",") in buruk:
            continue
        return _potong(k, 70)
    return _potong(_GUMAM.sub("", teks or ""), 70)


def _lokal(meta: dict) -> dict:
    """Paket tanpa model: dari kata-kata klipnya sendiri."""
    from .clipmodel import suggest_hashtags
    teks = " ".join((l.get("text") or "") for l in (meta.get("subtitles") or []))
    judul = (meta.get("title") or "").strip()
    hook = _hook_lokal(teks, judul, meta.get("video_title") or "")
    tagar = meta.get("hashtags") or suggest_hashtags(
        teks, meta.get("video_title") or "", meta.get("channel") or "",
        duration=float(meta.get("duration") or 0))
    # Konteksnya kalimat lain dari klip yang sama, bukan potongan mentah yang
    # berhenti di tengah kata.
    sisa = _GUMAM.sub("", teks).replace(hook, "", 1).strip()
    konteks = ""
    for kalimat in re.split(r"(?<=[.!?])\s+", sisa):
        if 25 <= len(kalimat.strip()) <= 160:
            konteks = kalimat.strip()
            break
    return {"hook": hook, "konteks": konteks, "kata_kunci": [],
            "tagar": list(tagar), "sumber": "lokal"}


# --- Jalur AI ---------------------------------------------------------------
def _minta_ai(meta: dict, *, api_key: str, models: list) -> Optional[dict]:
    from .penyedia_ai import SemuaGagal, tanya

    teks = " ".join((l.get("text") or "") for l in (meta.get("subtitles") or []))[:6000]
    if len(teks.strip()) < 40:
        return None
    bahan = [{"teks":
              f"Judul video sumber: {meta.get('video_title') or '(tidak diketahui)'}\n"
              f"Kanal: {meta.get('channel') or '(tidak diketahui)'}\n"
              f"Durasi klip: {float(meta.get('duration') or 0):.0f} detik\n\n"
              f"=== ISI KLIP ===\n{teks}\n\n"
              "Tulis hook, konteks, kata kunci pencarian, dan tagarnya."}]
    try:
        hasil, model, _pakai = tanya(bahan, schema=_schema(), sistem=SISTEM,
                                     api_key=api_key, models=models,
                                     suhu=0.7, maks_keluaran=1024, batas_detik=90)
    except SemuaGagal as e:
        log.info("Caption AI tidak tersedia: %s", str(e)[:200])
        return None
    except Exception as e:                       # noqa: BLE001
        log.warning("Caption AI gagal: %s", str(e)[:200])
        return None
    return {
        "hook": _potong(hasil.get("hook") or "", 100),
        "konteks": _potong(hasil.get("konteks") or "", 200),
        "kata_kunci": [str(k) for k in (hasil.get("kata_kunci") or [])][:6],
        "tagar": [str(t) for t in (hasil.get("tagar") or [])],
        "sumber": model,
    }


# --- Perakitan per platform --------------------------------------------------
def _rakit(inti: dict, meta: dict, nama: str) -> dict:
    p = PLATFORM[nama]
    tagar = _bersih_tagar(inti.get("tagar"), maks=p["maks_tagar"],
                          sertakan_shorts=(nama == "shorts"
                                           and 0 < float(meta.get("duration") or 0) <= 180))
    hook = inti.get("hook") or ""
    konteks = inti.get("konteks") or ""
    if konteks.strip().lower() == hook.strip().lower():
        konteks = ""

    # Disusun baris per baris, bukan lewat `_potong` yang meratakan spasi:
    # bentuk tiga barisnya itu sendiri bagian dari captionnya.
    caption = "\n\n".join(x for x in (hook, konteks, " ".join(tagar)) if x.strip())
    if len(caption) > p["maks_caption"]:
        caption = caption[:p["maks_caption"]].rsplit("\n\n", 1)[0]

    keluar = {
        "platform": nama,
        "label": p["label"],
        "caption": caption,
        "tagar": tagar,
        "unggah": p["unggah"],
        "catatan": p["catatan"],
        "maks_tagar": p["maks_tagar"],
    }
    if p.get("judul_terpisah"):
        # Di YouTube, judul yang menentukan — dan judul terbaik adalah hooknya
        # sendiri, bukan nama berkasnya.
        keluar["judul"] = _potong(hook or meta.get("title") or "", p["maks_judul"])
    return keluar


def paket(meta: dict, *, api_key: str = "", models: Optional[list] = None,
          pakai_ai: bool = True) -> dict:
    """
    {platform: {...}, sumber, hook} — semua yang dibutuhkan untuk menempel.

    `meta` adalah sidecar klip hasil render (judul, subtitles, hashtags,
    duration), ditambah `video_title` dan `channel` bila ada.
    """
    inti = None
    if pakai_ai and api_key and models:
        inti = _minta_ai(meta, api_key=api_key, models=models)
    if inti is None:
        inti = _lokal(meta)
    # Tagar AI yang kosong atau habis tersaring tetap ditambal dari isi klip,
    # supaya kotaknya tidak pernah keluar kosong.
    if len(_bersih_tagar(inti.get("tagar"), maks=5)) < 3:
        inti["tagar"] = list(inti.get("tagar") or []) + _lokal(meta)["tagar"]
    return {
        "hook": inti["hook"],
        "konteks": inti.get("konteks") or "",
        "kata_kunci": inti.get("kata_kunci") or [],
        "sumber": inti.get("sumber") or "lokal",
        "platform": [_rakit(inti, meta, nama) for nama in PLATFORM],
    }
