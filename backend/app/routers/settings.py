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
import os
import sys
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import (
    GEMINI_MODELS, get_api_key, get_api_key_source, get_cookies_file,
    get_model_override,
)
from ..errors import AppError
from ..repos import settings as settings_repo

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
        "cookies_file_set": bool(get_cookies_file()),
        "gemini_models": GEMINI_MODELS,
    }


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
    return {"available": available, "configured": True, "default": GEMINI_MODELS}


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

    return {
        "folder": str(sekarang),
        "sisa_ruang": sisa,
        "dari_sumber": not cfg.FROZEN,
        "saran": saran,
        "dikunci_env": bool(os.getenv("OMNICLIP_STORAGE", "").strip()),
        "menunggu_pindah": (cfg._user_data_dir() / "pindah-dari.txt").is_file(),
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
