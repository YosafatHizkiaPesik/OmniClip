"""
Pengaturan aplikasi.

Yang berubah sejak aplikasi ini bisa dibuka dari HP: kunci AI dan pilihan model
sekarang tinggal di basis data, bukan di `os.environ` proses. Versi lama
menuliskannya ke lingkungan proses, jadi ia hilang setiap backend dimulai ulang
dan satu-satunya penyimpanan sebenarnya adalah `backend/.env` — berkas yang
hanya bisa diedit dari terminal komputer ini.
"""

import logging

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
        "key_prefix": "AIza",
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

    prefix = PROVIDERS[provider]["key_prefix"]
    if prefix and not key.startswith(prefix):
        # Menolak lebih awal, bukan membiarkan setiap analisis gagal nanti
        # dengan pesan dari Google yang tidak menunjuk ke ladang isian ini.
        raise AppError(
            f"Sepertinya bukan API key {PROVIDERS[provider]['label']} — "
            f"kunci yang benar diawali \"{prefix}\".",
            code="AI_KEY_INVALID", status=422)

    settings_repo.set_value("ai.provider", provider)
    settings_repo.set_value("ai.api_key", key)
    log.info("API key %s dipasang (berakhiran %s).", provider, key[-4:])
    return {"status": "ok",
            "message": "API key tersimpan dan tetap ada setelah backend dimulai ulang."}


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
