"""
Pengaturan aplikasi.

Yang berubah sejak aplikasi ini bisa dibuka dari HP: kunci AI dan pilihan model
sekarang tinggal di basis data, bukan di `os.environ` proses. Versi lama
menuliskannya ke lingkungan proses, jadi ia hilang setiap backend dimulai ulang
dan satu-satunya penyimpanan sebenarnya adalah `backend/.env` — berkas yang
hanya bisa diedit dari terminal komputer ini.
"""

import asyncio
import logging
import re
import os
import sys
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from typing import List

from pydantic import BaseModel, Field

from ..config import (
    CAPTION_LANGS, GEMINI_MODELS, get_api_key, get_api_key_source,
    get_caption_langs, get_model_override,
)
from ..errors import AppError
from ..repos import settings as settings_repo

def _cookies_aktif() -> bool:
    """Apakah cookies sedang dipakai. Tidak menyentuh jaringan."""
    try:
        from ..services import cookies as ck
        return ck.aktif()
    except Exception:
        return False


log = logging.getLogger("omniclip.settings")
router = APIRouter(prefix="/api/settings", tags=["settings"])

# Penyedia yang benar-benar punya jalur di dalam kode. Daftar ini sengaja bukan
# teks bebas: menyimpan "openai" di sini tidak akan membuat OmniClip memanggil
# OpenAI, dan pengaturan yang berpura-pura berlaku lebih buruk daripada
# pengaturan yang tidak ada.
PROVIDERS = {
    "gemini": {
        "id": "gemini",
        "label": "Google Gemini",
        "key_url": "https://aistudio.google.com/app/apikey",
        "note": "Tingkat gratis tersedia. Dipakai untuk memilih klip dan menulis judul.",
    },
}


class ApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=400)
    provider: str = "gemini"


class ModelRequest(BaseModel):
    model: str = Field(default="", max_length=120)


@router.get("")
async def get_settings():
    key = get_api_key()
    return {
        "providers": list(PROVIDERS.values()),
        "ai_provider": settings_repo.get("ai.provider", "gemini"),
        # Hanya 4 karakter terakhir: cukup untuk mengenali kunci, tidak cukup
        # untuk membocorkannya. Versi lama mengembalikan 8 karakter PERTAMA.
        "gemini_api_key_set": bool(key),
        "gemini_api_key_last4": key[-4:] if len(key) >= 4 else "",
        # Kunci yang datang dari .env tidak bisa dihapus lewat antarmuka, dan
        # antarmuka harus mengatakannya alih-alih menyediakan tombol yang diam-
        # diam tidak berpengaruh.
        "gemini_api_key_source": get_api_key_source(),
        "ai_model": get_model_override(),
        "cookies_aktif": _cookies_aktif(),
        "gemini_models": GEMINI_MODELS,
        **_openrouter_ringkas(),
    }


# --- OpenRouter: cadangan saat kuota Gemini habis -----------------------------
def _openrouter_ringkas() -> dict:
    from ..services import openrouter
    from ..services.pipeline import bingkai_otomatis
    k = openrouter.kunci()
    return {"openrouter_key_set": bool(k),
            "openrouter_key_last4": k[-4:] if len(k) >= 4 else "",
            "openrouter_model": openrouter.model_pilihan(),
            "bingkai_otomatis": bingkai_otomatis()}


@router.get("/openrouter-models")
async def openrouter_models():
    """
    Model OpenRouter gratis yang bisa menonton klip.

    Bukan daftar tetap: model gratis datang dan pergi tiap beberapa minggu, dan
    daftar tangan akan menunjuk model yang sudah tidak ada.
    """
    from ..services import openrouter
    try:
        semua = await asyncio.to_thread(openrouter.daftar)
    except Exception as e:
        return {"tersedia": [], "galat": str(e)[:200], **_openrouter_ringkas()}
    urut = await asyncio.to_thread(openrouter.rantai, None)
    pilihan = [{"id": m["id"], "nama": m["nama"], "video": m["video"],
                "suara": m["suara"], "json": m["json"]}
               for m in openrouter.urutkan(semua)]
    return {"tersedia": pilihan, "terkuat": (urut or [{}])[0].get("id"),
            **_openrouter_ringkas()}


@router.post("/openrouter-key")
async def set_openrouter_key(req: ApiKeyRequest):
    """
    Kunci diuji ke OpenRouter sebelum disimpan, sama seperti kunci Gemini.

    Yang ditanyakan `/api/v1/key`: ia mengembalikan sisa jatah kunci ini tanpa
    memakai satu pun permintaan model, jadi menguji kunci tidak berbiaya.
    """
    import json
    import urllib.error
    import urllib.request

    from ..services import openrouter

    key = req.api_key.strip()
    if any(c.isspace() for c in key):
        raise AppError("Kunci tidak boleh memuat spasi atau baris baru.",
                       code="AI_KEY_INVALID", status=422)

    def _uji() -> str | None:
        permintaan = urllib.request.Request(
            f"{openrouter.ALAMAT}/key", headers={"Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(permintaan, timeout=25) as r:
                json.loads(r.read().decode("utf-8"))
            return None
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return ("OpenRouter tidak mengenali kunci ini. Periksa apakah "
                        "seluruhnya tersalin, tanpa spasi di ujung.")
            return f"OpenRouter menolak kunci ini (kode {e.code})."
        except Exception as e:
            # Tanpa kode status: jaringan, bukan kuncinya. Sama seperti Gemini,
            # wifi yang sedang mati tidak boleh membatalkan penyimpanan.
            log.warning("Kunci OpenRouter tidak bisa diuji: %s", str(e)[:200])
            return None

    galat = await asyncio.to_thread(_uji)
    if galat:
        raise AppError(galat, code="AI_KEY_INVALID", status=422)
    settings_repo.set_value(openrouter.NAMA_KUNCI, key)
    log.info("Kunci OpenRouter dipasang (berakhiran %s).", key[-4:])
    return {"status": "ok", **_openrouter_ringkas(),
            "message": "Kunci OpenRouter tersimpan. Dipakai saat kuota Gemini habis."}


@router.delete("/openrouter-key")
async def delete_openrouter_key():
    from ..services import openrouter
    if not settings_repo.get(openrouter.NAMA_KUNCI) and openrouter.kunci():
        raise AppError(
            "Kunci ini datang dari variabel lingkungan OPENROUTER_API_KEY, jadi "
            "tidak bisa dihapus dari sini.", code="AI_KEY_FROM_ENV", status=409)
    settings_repo.delete(openrouter.NAMA_KUNCI)
    return {"status": "ok", **_openrouter_ringkas()}


class SakelarRequest(BaseModel):
    aktif: bool


@router.post("/bingkai-otomatis")
async def set_bingkai_otomatis(req: SakelarRequest):
    """
    Sutradara bingkai berjalan sendiri sesudah auto-klip.

    Bawaannya mati, dan itu disengaja: tiap klip berarti satu panggilan model,
    dan kuota harian yang sama dipakai untuk MEMILIH klip video berikutnya.
    Menyalakannya adalah pertukaran yang harus dilakukan pemiliknya sendiri,
    bukan diam-diam oleh program.
    """
    from ..services.pipeline import NAMA_BINGKAI_OTOMATIS
    settings_repo.set_value(NAMA_BINGKAI_OTOMATIS, "1" if req.aktif else "0")
    return {"status": "ok", "aktif": req.aktif}


@router.post("/openrouter-model")
async def set_openrouter_model(req: ModelRequest):
    from ..services import openrouter
    nilai = req.model.strip()
    if nilai:
        settings_repo.set_value(openrouter.NAMA_MODEL, nilai)
    else:
        settings_repo.delete(openrouter.NAMA_MODEL)
    return {"status": "ok", "model": nilai}


@router.get("/models")
async def list_models():
    """
    Model Gemini yang benar-benar bisa dipakai oleh API key ini.

    Bukan daftar tetap: model dipensiunkan tanpa pemberitahuan, dan itulah yang
    membuat seluruh penajaman AI diam-diam gagal — dua model yang di-pin sudah
    menjawab 404 selama berminggu-minggu sementara UI tetap menulis "Gemini".
    """
    import asyncio

    key = get_api_key()
    if not key:
        return {"available": [], "configured": False, "default": GEMINI_MODELS}

    def _fetch() -> list[str]:
        from google import genai
        client = genai.Client(api_key=key)
        names = []
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if "generateContent" not in actions:
                continue
            name = m.name.replace("models/", "")
            # Hanya model teks serba guna. Varian gambar/suara/TTS tidak bisa
            # mengerjakan tugas ini dan hanya membuat daftarnya sulit dibaca.
            if any(x in name for x in ("image", "tts", "embedding", "robotics",
                                       "computer-use", "lyria", "banana",
                                       "transcribe", "omni")):
                continue
            names.append(name)
        return sorted(names)

    try:
        available = await asyncio.to_thread(_fetch)
    except Exception as e:
        return {"available": [], "configured": True, "error": str(e)[:200],
                "default": GEMINI_MODELS}
    # `cocok`: yang layak memilih klip, dari yang terkuat. Agen (deep-research,
    # antigravity), Gemma, dan varian lite ikut terdaftar di kunci tapi tidak
    # sanggup membaca transkrip sejam lalu menjawab dalam JSON yang benar.
    # `terkuat`: yang akan dicoba pertama bila pengguna memilih "Otomatis" —
    # sudah melewati model yang kuotanya nol untuk kunci ini.
    from ..services.peringkat_model import rantai, tanpa_kuota, urutkan
    cocok = urutkan(available)
    try:
        urutan = await asyncio.to_thread(rantai, key)
    except Exception:
        urutan = cocok
    return {"available": available, "configured": True, "default": GEMINI_MODELS,
            "cocok": cocok, "terkuat": (urutan or [None])[0],
            "tanpa_kuota": [m for m in cocok if tanpa_kuota(m)]}


@router.post("/api-key")
async def set_api_key(req: ApiKeyRequest):
    provider = req.provider.strip().lower() or "gemini"
    if provider not in PROVIDERS:
        raise AppError(f"Penyedia AI '{provider}' belum didukung.",
                       code="AI_PROVIDER_UNKNOWN", status=422)

    key = req.api_key.strip()
    if any(c.isspace() for c in key):
        raise AppError("API key tidak boleh memuat spasi atau baris baru.",
                       code="AI_KEY_INVALID", status=422)

    # Kuncinya DICOBA, bukan ditebak bentuknya.
    #
    # Versi pertama menolak apa pun yang tidak diawali "AIza", karena itulah
    # bentuk kunci AI Studio yang saya kenal. Google menerbitkan format lain —
    # ada kunci sah yang diawali "AQ." — dan pemeriksaan itu menolaknya mentah
    # mentah sambil menuduh penggunanya salah menempel. Menebak bentuk rahasia
    # milik layanan lain memang selalu menua buruk: bentuknya bisa berubah kapan
    # saja tanpa memberi tahu siapa pun.
    #
    # Yang benar adalah bertanya kepada Google. Sekali panggilan daftar model
    # sudah cukup, dan bonusnya: kunci yang sah tapi kuotanya mati atau API-nya
    # belum diaktifkan ikut ketahuan di sini, bukan nanti saat analisis pertama.
    galat = await _uji_kunci(key)
    if galat:
        raise AppError(galat, code="AI_KEY_INVALID", status=422)

    settings_repo.set_value("ai.provider", provider)
    settings_repo.set_value("ai.api_key", key)
    log.info("API key %s dipasang (berakhiran %s).", provider, key[-4:])
    return {"status": "ok",
            "message": "API key diuji ke Google dan tersimpan. Tetap ada setelah "
                       "aplikasi ditutup."}


async def _uji_kunci(key: str) -> str | None:
    """
    Menanyakan kunci ini ke Google. None berarti dipakai.

    Diklasifikasi dari KODE STATUS, bukan dari teks galatnya. Versi pertama
    mencocokkan teks, dan itu langsung meleset: kunci "AIza" yang keliru dijawab
    Google dengan 400 "API key not valid", sedangkan kunci "AQ." yang keliru
    dijawab 401 "invalid authentication credentials" — kalimat yang sama sekali
    berbeda untuk kesalahan yang sama. Kunci palsu pun lolos tersimpan.

    Kegagalan tanpa kode status sengaja TIDAK menolak kunci. Aplikasi ini
    berjalan di komputer orang, sering tanpa sambungan yang bisa diandalkan,
    dan menolak menyimpan kunci yang benar hanya karena wifi sedang mati adalah
    kegagalan yang lebih menjengkelkan daripada kunci keliru yang baru ketahuan
    saat analisis pertama.
    """
    import asyncio

    def _coba() -> str | None:
        from google import genai
        # Klien dipegang di variabel selama pemanggilan: dilepas terlalu cepat,
        # ia menutup dirinya sendiri dan galatnya menyamar jadi "client closed".
        client = genai.Client(api_key=key)
        next(iter(client.models.list()), None)
        return None

    try:
        return await asyncio.to_thread(_coba)
    except Exception as e:
        kode = getattr(e, "code", None)
        if kode in (400, 401):
            return ("Google tidak mengenali kunci ini. Periksa apakah seluruhnya "
                    "tersalin, tanpa spasi atau baris terpotong di ujung.")
        if kode == 403:
            return ("Kunci ini dikenali Google tapi belum diizinkan memakai "
                    "Gemini API. Buka aistudio.google.com dan pastikan kuncinya "
                    "dibuat untuk Generative Language API.")
        if kode == 429:
            return ("Kunci ini sah tapi kuotanya sedang habis. Coba lagi nanti, "
                    "atau pakai kunci lain.")
        if kode is not None:
            return f"Google menolak kunci ini (kode {kode}). Coba lagi sebentar lagi."
        # Tidak ada kode status sama sekali: jaringan, DNS, proxy, sertifikat.
        # Bukan urusan kuncinya.
        log.warning("Kunci tidak bisa diuji, tidak ada kode status dari Google: %s",
                    str(e)[:200])
        return None


@router.delete("/api-key")
async def delete_api_key():
    if get_api_key_source() == "env":
        raise AppError(
            "Kunci ini datang dari backend/.env, jadi tidak bisa dihapus dari sini. "
            "Hapus barisnya di berkas itu lalu mulai ulang backend.",
            code="AI_KEY_FROM_ENV", status=409)
    settings_repo.delete("ai.api_key")
    log.info("API key dihapus; pemilihan klip kembali ke heuristik lokal.")
    return {"status": "ok", "message": "API key dihapus. Mode heuristik lokal aktif."}


@router.post("/model")
async def set_model(req: ModelRequest):
    """
    Model pilihan, disimpan di server.

    Dulu ini hanya ada di localStorage peramban — yang berarti memilih model di
    laptop tidak berpengaruh apa pun saat aplikasi yang sama dibuka dari HP.
    """
    value = req.model.strip()
    if value:
        settings_repo.set_value("ai.model", value)
    else:
        settings_repo.delete("ai.model")
    return {"status": "ok", "model": value}


# --- Bahasa subtitle ----------------------------------------------------------

# Yang dipajang di antarmuka. Bukan daftar tertutup — kolom isian bebas ada di
# bawahnya, dan apa pun yang tidak ada di sini tetap bisa diketik.
BAHASA_UMUM = [
    ("id", "Indonesia"), ("en", "Inggris"), ("ms", "Melayu"),
    ("ja", "Jepang"), ("ko", "Korea"), ("zh", "Mandarin"),
    ("ar", "Arab"), ("es", "Spanyol"), ("pt", "Portugis"),
    ("fr", "Prancis"), ("de", "Jerman"), ("hi", "Hindi"),
    ("th", "Thai"), ("vi", "Vietnam"), ("tr", "Turki"), ("ru", "Rusia"),
]

_KODE = re.compile(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})?$")


class BahasaRequest(BaseModel):
    langs: List[str] = Field(default_factory=list)


class TerjemahOtomatisRequest(BaseModel):
    bahasa: str = Field("", max_length=12, pattern=r"^[A-Za-z-]*$")


@router.get("/terjemah-otomatis")
async def lihat_terjemah_otomatis():
    """Bahasa terjemahan otomatis untuk video berbahasa asing ("" = mati)."""
    from ..services.terjemah import bahasa_otomatis
    return {"bahasa": bahasa_otomatis()}


@router.post("/terjemah-otomatis")
async def atur_terjemah_otomatis(req: TerjemahOtomatisRequest):
    settings_repo.set_value("terjemah.otomatis", req.bahasa.strip() or "mati")
    from ..services.terjemah import bahasa_otomatis
    return {"bahasa": bahasa_otomatis()}


@router.get("/languages")
async def daftar_bahasa():
    """Bahasa pilihan yang berlaku, plus daftar yang ditawarkan antarmuka."""
    return {
        "langs": list(get_caption_langs()),
        "default": list(CAPTION_LANGS),
        "common": [{"code": k, "label": v} for k, v in BAHASA_UMUM],
    }


@router.post("/languages")
async def set_bahasa(req: BahasaRequest):
    """
    Urutan bahasa caption yang dicoba lebih dulu.

    Kosong = kembali ke bawaan. Dan apa pun isinya, ini BUKAN batas: kalau tidak
    satu pun bahasa di daftar ini dimiliki videonya, sistem tetap memakai bahasa
    yang benar-benar ada di video itu. Daftar ini hanya menyatakan urutan pilihan.
    """
    bersih: list[str] = []
    for kode in req.langs:
        kode = (kode or "").strip()
        if not kode:
            continue
        if not _KODE.match(kode):
            raise AppError(f"Kode bahasa tidak dikenal: {kode!r}. "
                           "Contoh yang benar: id, en, ja, pt-BR.",
                           code="BAHASA_TIDAK_SAH", status=422)
        if kode not in bersih:
            bersih.append(kode)

    if bersih:
        settings_repo.set_value("transcript.langs", ",".join(bersih))
    else:
        settings_repo.delete("transcript.langs")
    return {"status": "ok", "langs": list(get_caption_langs())}


# --- Kesehatan sistem -----------------------------------------------------------
@router.get("/kesehatan")
async def kesehatan():
    """
    Satu layar untuk "apakah semuanya baik-baik saja".

    Sebelum ini, semua yang dilaporkan di sini hanya terlihat di log: encoder
    mana yang dipakai, apakah server PO Token menyala, cookies masih hidup atau
    tidak. Artinya satu-satunya cara pemiliknya tahu ada yang rusak adalah
    dengan menemukan hasil yang salah — dan itu selalu terjadi di tengah
    pekerjaan.

    Tiap baris menyebut keadaan DAN akibatnya bila ia mati, karena "POT: mati"
    tidak berarti apa-apa bagi yang tidak menulis kodenya.
    """
    import asyncio

    from ..services import cookies as ck
    from ..services import alat_yt, enkoder, fonts, google_upload, sosial
    from ..version import __version__

    def _kumpul() -> dict:
        baris = []

        enc = enkoder.pilih()
        baris.append({
            "nama": "Encoder video",
            "nilai": f"{enc['nama']} ({enc.get('ffmpeg', '')})",
            "baik": enc["nama"] != "x264",
            "akibat": "Render tetap jalan memakai prosesor, sekitar 1,6 kali lebih lambat.",
        })

        alat = dict(getattr(alat_yt, "_status", {}) or {})
        pot = str(alat.get("pot") or "belum disiapkan")
        baris.append({
            "nama": "PO Token YouTube",
            "nilai": pot,
            "baik": pot.startswith("http"),
            "akibat": "Tanpa ini YouTube bisa menolak unduhan dengan "
                      "\"Sign in to confirm you're not a bot\".",
        })
        deno = str(alat.get("deno") or "belum disiapkan")
        baris.append({
            "nama": "Runtime JavaScript (Deno)",
            "nilai": "terpasang" if deno.startswith("/") or ":\\" in deno else deno,
            "baik": deno.startswith("/") or ":\\" in deno,
            "akibat": "Sama seperti PO Token: unduhan YouTube bisa ditolak.",
        })

        aktif = ck.aktif()
        baris.append({
            "nama": "Cookies YouTube",
            "nilai": "dipakai" if aktif else "tidak dipakai",
            "baik": aktif,
            "akibat": "Video berumur dan video yang dibatasi wilayah bisa gagal diunduh.",
        })

        g = google_upload.status()
        baris.append({
            "nama": "Akun Google profil ini",
            "nilai": g.get("email") or ("tersambung" if g.get("connected") else "belum tersambung"),
            "baik": bool(g.get("connected")),
            "akibat": "Unggah ke YouTube dan Drive tidak bisa jalan.",
        })

        for pf in sosial.PLATFORM:
            st = sosial.status(pf)
            baris.append({
                "nama": f"Akun {st['label']}",
                "nilai": (st["akun"] or "tersambung") if st["tersambung"]
                         else ("aplikasi siap, akun belum disambung" if st["siap"]
                               else "kunci aplikasi belum diisi"),
                "baik": st["tersambung"],
                "akibat": f"Unggah ke {st['label']} tidak bisa jalan.",
            })

        kunci_ai = bool(get_api_key())
        from ..services import openrouter
        baris.append({
            "nama": "Kunci AI",
            "nilai": ("Gemini" + (" + OpenRouter" if openrouter.aktif() else "")) if kunci_ai
                     else ("OpenRouter saja" if openrouter.aktif() else "belum diisi"),
            "baik": kunci_ai or openrouter.aktif(),
            "akibat": "Pemilihan klip dan sutradara bingkai memakai mesin lokal.",
        })

        ada_font = [f for f in fonts.terpasang() if f["ada"]]
        baris.append({
            "nama": "Font aksara non-Latin",
            "nilai": ", ".join(f["keluarga"] for f in ada_font) or "belum ada (diunduh saat dipakai)",
            "baik": True,
            "akibat": "Diunduh sendiri saat pertama kali ada subtitle Jepang, Korea, "
                      "Mandarin, atau Arab.",
        })

        import shutil as _sh
        from .. import config as cfg
        try:
            _, _, sisa = _sh.disk_usage(cfg.STORAGE_DIR)
        except OSError:
            sisa = 0
        baris.append({
            "nama": "Sisa ruang cakram",
            "nilai": f"{sisa / 1e9:.0f} GB",
            "baik": sisa > 15e9,
            "akibat": "Render dan unduhan gagal di tengah jalan bila ruangnya habis.",
        })
        return {"versi": __version__, "baris": baris}

    return await asyncio.to_thread(_kumpul)


# --- Ruang cakram dan cadangan --------------------------------------------------
class BuangRequest(BaseModel):
    folder: str
    berkas: List[str]


class PulihRequest(BaseModel):
    berkas: str


@router.get("/ruang")
async def ruang():
    """Pemakaian cakram per folder, dan video sumber terbesar."""
    from ..services.pemeliharaan import rinci
    return await asyncio.to_thread(rinci)


@router.post("/ruang/buang")
async def ruang_buang(req: BuangRequest):
    from ..services.pemeliharaan import buang
    return await asyncio.to_thread(buang, req.folder, req.berkas)


@router.get("/cadangan")
async def cadangan_daftar():
    from ..services.pemeliharaan import daftar_cadangan
    return {"cadangan": await asyncio.to_thread(daftar_cadangan)}


@router.post("/cadangan")
async def cadangan_buat():
    from ..services.pemeliharaan import cadangkan
    return await asyncio.to_thread(cadangkan)


@router.post("/cadangan/pulihkan")
async def cadangan_pulihkan(req: PulihRequest):
    from ..services.pemeliharaan import siapkan_pulih
    return await asyncio.to_thread(siapkan_pulih, req.berkas)


@router.delete("/cadangan/pulihkan")
async def cadangan_batal():
    from ..services.pemeliharaan import batalkan_pulih
    batalkan_pulih()
    return {"status": "ok"}


# --- Lokasi penyimpanan -------------------------------------------------------

class PenyimpananRequest(BaseModel):
    folder: str = Field(..., description="Folder tujuan penyimpanan")


def _ringkas_penyimpanan() -> dict:
    import shutil as _sh
    from .. import config as cfg

    sekarang = cfg.STORAGE_DIR
    try:
        _, _, sisa = _sh.disk_usage(sekarang)
    except OSError:
        sisa = 0

    # Saran hanya diberikan saat terbungkus: dari kode sumber, penyimpanan
    # memang sudah berada di dalam repositori dan tidak ada yang perlu pindah.
    saran = ""
    if cfg.FROZEN:
        calon = Path(sys.executable).resolve().parent.parent / "OmniClip-Data"
        if calon.resolve() != sekarang.resolve():
            saran = str(calon)

    def _isi(d: Path) -> dict:
        """Ukuran dan jumlah berkas satu folder — supaya bisa dibersihkan sadar."""
        total = jumlah = 0
        try:
            for f in d.iterdir():
                if f.is_file():
                    jumlah += 1
                    total += f.stat().st_size
        except OSError:
            pass
        return {"folder": str(d), "ukuran": total, "jumlah": jumlah}

    return {
        "folder": str(sekarang),
        "sisa_ruang": sisa,
        "dari_sumber": not cfg.FROZEN,
        "saran": saran,
        "dikunci_env": bool(os.getenv("OMNICLIP_STORAGE", "").strip()),
        "menunggu_pindah": (cfg._user_data_dir() / "pindah-dari.txt").is_file(),
        # Dua folder yang isinya paling besar dan paling sering dibuka sendiri.
        "unduhan": _isi(cfg.DOWNLOAD_DIR),
        "klip": _isi(cfg.CLIPS_DIR),
    }


@router.get("/penyimpanan")
async def lihat_penyimpanan():
    """Di mana klip dan unduhan disimpan sekarang."""
    return await asyncio.to_thread(_ringkas_penyimpanan)


@router.post("/penyimpanan")
async def pindah_penyimpanan(req: PenyimpananRequest):
    """
    Menunjuk folder penyimpanan yang baru.

    Pemindahannya TIDAK dikerjakan di sini. Basis data sedang terbuka oleh
    proses ini, dan memindahkan berkas SQLite yang sedang dipakai adalah cara
    yang rapi untuk merusaknya. Yang ditulis di sini hanya dua berkas penunjuk;
    perpindahannya terjadi saat aplikasi dijalankan berikutnya, sebelum satu
    koneksi pun dibuka.
    """
    from .. import config as cfg

    if os.getenv("OMNICLIP_STORAGE", "").strip():
        raise AppError("Lokasi penyimpanan sedang dipaksa lewat OMNICLIP_STORAGE.",
                       code="STORAGE_LOCKED", status=409)
    if not cfg.FROZEN:
        raise AppError("Dijalankan dari kode sumber — penyimpanan mengikuti folder proyek.",
                       code="STORAGE_FROM_SOURCE", status=409)

    tujuan = Path(req.folder.strip()).expanduser()
    if not str(tujuan).strip():
        raise AppError("Folder tujuan kosong.", code="STORAGE_EMPTY", status=422)
    if not cfg._bisa_ditulis(tujuan):
        raise AppError(f"Folder {tujuan} tidak bisa ditulis.",
                       code="STORAGE_NOT_WRITABLE", status=422)
    if tujuan.resolve() == cfg.STORAGE_DIR.resolve():
        return {"status": "ok", "folder": str(tujuan), "perlu_restart": False}

    data = cfg._user_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    (data / "lokasi-penyimpanan.txt").write_text(str(tujuan.resolve()), encoding="utf-8")
    (data / "pindah-dari.txt").write_text(str(cfg.STORAGE_DIR.resolve()), encoding="utf-8")
    log.info("Penyimpanan akan dipindahkan ke %s saat aplikasi dijalankan lagi.", tujuan)
    return {"status": "ok", "folder": str(tujuan.resolve()), "perlu_restart": True}


@router.post("/penyimpanan/buka")
async def buka_penyimpanan():
    """Membuka folder penyimpanan di pengelola berkas sistem."""
    import subprocess
    from .. import config as cfg

    folder = str(cfg.STORAGE_DIR)
    try:
        if sys.platform == "win32":
            os.startfile(folder)                     # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder], close_fds=True)
        else:
            subprocess.Popen(["xdg-open", folder], close_fds=True)
    except OSError as e:
        raise AppError(f"Tidak bisa membuka folder: {e}",
                       code="STORAGE_OPEN_FAILED", status=500) from e
    return {"status": "ok", "folder": folder}


class FolderRequest(BaseModel):
    jenis: str = Field(..., description="unduhan | klip")
    folder: str = Field("", description="Kosongkan untuk kembali ke bawaan")


_JENIS = {"unduhan", "klip"}


@router.post("/penyimpanan/folder")
async def atur_folder(req: FolderRequest):
    """
    Menunjuk folder untuk unduhan atau klip jadi.

    Berkas yang SUDAH ada tidak ikut pindah. Itu disengaja: memindahkan
    puluhan gigabita di dalam sebuah permintaan HTTP berarti permintaan yang
    menggantung bermenit-menit tanpa ada yang bisa membatalkannya, dan
    kegagalan di tengah jalan meninggalkan berkas terbelah di dua tempat.
    Yang lama tetap bisa dibuka dari halaman Unduhan sampai dipindahkan
    sendiri — dan foldernya ditunjukkan di sini supaya bisa.
    """
    from .. import config as cfg

    if req.jenis not in _JENIS:
        raise AppError("Jenis folder tidak dikenal.", code="FOLDER_UNKNOWN", status=422)

    data = cfg._user_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    penunjuk = data / f"lokasi-{req.jenis}.txt"

    pilihan = req.folder.strip()
    if not pilihan:
        penunjuk.unlink(missing_ok=True)
        return {"status": "ok", "kembali_ke_bawaan": True, "perlu_restart": True}

    tujuan = Path(pilihan).expanduser()
    if not cfg._bisa_ditulis(tujuan):
        raise AppError(f"Folder {tujuan} tidak bisa ditulis.",
                       code="FOLDER_NOT_WRITABLE", status=422)
    penunjuk.write_text(str(tujuan.resolve()), encoding="utf-8")
    log.info("Folder %s diarahkan ke %s", req.jenis, tujuan)
    return {"status": "ok", "folder": str(tujuan.resolve()), "perlu_restart": True}


@router.post("/penyimpanan/folder/buka")
async def buka_folder(req: FolderRequest):
    """Membuka salah satu folder di pengelola berkas sistem."""
    import subprocess
    from .. import config as cfg

    if req.jenis not in _JENIS:
        raise AppError("Jenis folder tidak dikenal.", code="FOLDER_UNKNOWN", status=422)
    folder = str(cfg.DOWNLOAD_DIR if req.jenis == "unduhan" else cfg.CLIPS_DIR)
    try:
        if sys.platform == "win32":
            os.startfile(folder)                     # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder], close_fds=True)
        else:
            subprocess.Popen(["xdg-open", folder], close_fds=True)
    except OSError as e:
        raise AppError(f"Tidak bisa membuka folder: {e}",
                       code="FOLDER_OPEN_FAILED", status=500) from e
    return {"status": "ok", "folder": folder}


# ---------------------------------------------------------------------------
# Cookies YouTube
#
# Diletakkan di sini dan bukan di variabel lingkungan karena pesan yang
# meminta cookies muncul di dalam aplikasi, sementara `OMNICLIP_COOKIES_FILE`
# hanya bisa disetel SEBELUM aplikasi dijalankan. Untuk exe yang diklik dua
# kali, saran itu tidak bisa dituruti sama sekali.
# ---------------------------------------------------------------------------
class CookiesRequest(BaseModel):
    mode: str = Field("mati", description="mati | browser | berkas")
    browser: str = ""
    profil: str = ""


@router.get("/cookies")
async def lihat_cookies():
    from ..services import cookies as ck

    def baca():
        s = ck.sumber()
        return {**s, "browser_tersedia": ck.daftar_browser()}

    return await asyncio.to_thread(baca)


@router.post("/cookies")
async def atur_cookies(req: CookiesRequest):
    from ..services import cookies as ck

    try:
        return await asyncio.to_thread(
            ck.simpan, req.mode, browser=req.browser, profil=req.profil)
    except ValueError as e:
        raise AppError(str(e), code="COOKIES_INVALID", status=422) from e


@router.post("/cookies/berkas")
async def unggah_cookies(berkas: UploadFile = File(...)):
    """Menerima cookies.txt format Netscape."""
    from .. import config as cfg
    from ..services import cookies as ck

    isi = await berkas.read()
    if len(isi) > 8 * 1024 * 1024:
        raise AppError("Berkas cookies terlalu besar (maksimal 8 MB).",
                       code="COOKIES_TOO_BIG", status=413)
    try:
        jalur = await asyncio.to_thread(
            ck.simpan_berkas_unggahan, isi, Path(cfg.STORAGE_DIR) / "cookies")
        return await asyncio.to_thread(ck.simpan, "berkas", berkas=jalur)
    except ValueError as e:
        raise AppError(str(e), code="COOKIES_INVALID", status=422) from e


@router.post("/cookies/uji")
async def uji_cookies():
    """
    Menguji cookies dengan permintaan sungguhan ke YouTube, dan
    membandingkannya dengan permintaan tanpa cookies.

    Perbandingannya yang penting, bukan angka tunggalnya: cookies yang "bisa
    dibaca" tetap bisa menghasilkan nol format yang bisa diunduh, dan satu-
    satunya cara mengetahuinya adalah meminta keduanya berdampingan.
    """
    from ..services import cookies as ck

    return await asyncio.to_thread(ck.uji)


@router.delete("/cookies")
async def matikan_cookies():
    from ..services import cookies as ck

    return await asyncio.to_thread(ck.simpan, "mati")


# ---------------------------------------------------------------------------
# Pustaka yang memperbarui dirinya sendiri
# ---------------------------------------------------------------------------
@router.get("/pustaka")
async def lihat_pustaka():
    from ..services import pustaka as P

    def baca():
        return {
            "paket": [
                {
                    "nama": nama,
                    "versi": P.versi_terpasang(nama),
                    "dari_pembaruan": bool(P.versi_aktif(nama)),
                    "alasan": alasan,
                }
                for nama, (_, alasan) in P.OTOMATIS.items()
            ],
            "folder": str(P.folder_overlay()),
        }

    return await asyncio.to_thread(baca)


@router.post("/pustaka/periksa")
async def periksa_pustaka():
    """Memeriksa PyPI sekarang juga, melewati jeda dua belas jam."""
    from ..services import pustaka as P

    hasil = await asyncio.to_thread(P.perbarui_semua, paksa=True)
    return {"hasil": hasil,
            "perlu_restart": any(h.get("dipasang") for h in hasil)}


# ---------------------------------------------------------------------------
# Penjelajah folder
#
# Menggantikan `window.prompt` yang meminta jalur diketik penuh. Itu hampir
# mustahil dilakukan benar — jalur seperti
# "/media/ynot/744E3DDC4E3D97B6/Projek Coding/OmniClip" harus disalin dari
# tempat lain, dan satu salah ketik berarti folder yang tidak ada.
#
# Kenapa dijelajahi lewat backend, bukan dengan pemilih folder peramban:
# peramban TIDAK PERNAH memberi halaman web jalur berkas sungguhan.
# `<input webkitdirectory>` memberi nama berkas di dalam folder, bukan letak
# folder itu di cakram, dan `showDirectoryPicker()` memberi pegangan yang hanya
# berlaku di dalam peramban — ffmpeg tidak bisa memakainya. Dialog milik sistem
# operasi juga bukan jawaban: ia akan muncul di komputer yang menjalankan
# backend, bukan di perangkat yang sedang dipakai.
#
# Endpoint ini hanya mendaftar NAMA folder; isi berkas tidak pernah dibuka. Ia
# berada di balik gerbang kata sandi yang sama dengan seluruh API.
# ---------------------------------------------------------------------------
def _tempat_umum() -> list[dict]:
    """Titik awal yang masuk akal, supaya jarang perlu menyusur jauh."""
    rumah = Path.home()
    calon: list[tuple[str, Path]] = [("Home", rumah)]
    for nama, sub in (("Desktop", "Desktop"), ("Unduhan", "Downloads"),
                      ("Video", "Videos"), ("Dokumen", "Documents")):
        calon.append((nama, rumah / sub))

    # Cakram dan media yang terpasang — di situlah ruang besar biasanya berada,
    # dan justru itu yang dicari saat memindahkan folder unduhan.
    akar: list[Path] = []
    if sys.platform == "win32":
        akar = [Path(f"{huruf}:\\") for huruf in "CDEFGHIJKLMNOPQRSTUVWXYZ"]
    elif sys.platform == "darwin":
        akar = list(Path("/Volumes").glob("*"))
    else:
        akar = list(Path("/media").glob("*/*")) + list(Path("/mnt").glob("*"))
    for d in akar[:12]:
        calon.append((f"Cakram: {d.name or str(d)}", d))

    keluar = []
    terlihat = set()
    for nama, d in calon:
        try:
            if d.is_dir() and str(d) not in terlihat:
                terlihat.add(str(d))
                keluar.append({"nama": nama, "jalur": str(d)})
        except OSError:
            continue
    return keluar


_VIDEO_JELAJAH = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".mpg", ".mpeg", ".ts"}


@router.get("/jelajah")
async def jelajah(jalur: str = "", video: bool = False):
    """Isi sebuah folder: sub-folder, dan berkas video bila `video` benar."""
    def baca():
        d = Path(jalur).expanduser() if jalur.strip() else Path.home()
        try:
            d = d.resolve()
        except OSError:
            d = Path.home()
        if not d.is_dir():
            raise AppError(f"Folder tidak ditemukan: {d}",
                           code="FOLDER_NOT_FOUND", status=404)

        anak = []
        berkas = []
        try:
            for masuk in sorted(d.iterdir(), key=lambda x: x.name.lower()):
                # Folder tersembunyi disembunyikan: ia bukan tempat menaruh
                # video, dan menampilkannya membuat daftar Home tidak terbaca.
                if masuk.name.startswith("."):
                    continue
                try:
                    if masuk.is_dir():
                        anak.append({"nama": masuk.name, "jalur": str(masuk)})
                    elif video and masuk.suffix.lower() in _VIDEO_JELAJAH and masuk.is_file():
                        berkas.append({"nama": masuk.name, "jalur": str(masuk),
                                       "mb": round(masuk.stat().st_size / 1e6)})
                except OSError:
                    continue
        except PermissionError:
            raise AppError("Folder ini tidak bisa dibuka (izin ditolak).",
                           code="FOLDER_DENIED", status=403) from None

        induk = str(d.parent) if d.parent != d else ""
        return {
            "jalur": str(d),
            "induk": induk,
            "bisa_ditulis": os.access(d, os.W_OK),
            "folder": anak[:500],
            "berkas": berkas[:500],
            "tempat_umum": _tempat_umum(),
        }

    return await asyncio.to_thread(baca)


class FolderBaruRequest(BaseModel):
    induk: str
    nama: str


@router.post("/jelajah/buat")
async def buat_folder(req: FolderBaruRequest):
    """Membuat sub-folder baru dari dalam dialog pemilih."""
    def kerja():
        nama = req.nama.strip()
        # Nama yang mengandung pemisah jalur bukan "nama folder baru", melainkan
        # cara menulis di tempat lain.
        if not nama or nama in (".", "..") or "/" in nama or "\\" in nama:
            raise AppError("Nama folder tidak sah.", code="FOLDER_NAME", status=422)
        induk = Path(req.induk).expanduser().resolve()
        if not induk.is_dir():
            raise AppError("Folder induk tidak ditemukan.",
                           code="FOLDER_NOT_FOUND", status=404)
        baru = induk / nama
        try:
            baru.mkdir(exist_ok=True)
        except OSError as e:
            raise AppError(f"Tidak bisa membuat folder: {e}",
                           code="FOLDER_CREATE_FAILED", status=500) from e
        return {"jalur": str(baru)}

    return await asyncio.to_thread(kerja)
