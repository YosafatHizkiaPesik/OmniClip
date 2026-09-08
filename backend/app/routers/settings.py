"""Pengaturan aplikasi."""

import os

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import GEMINI_MODELS, get_cookies_file, get_env_api_key

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ApiKeyRequest(BaseModel):
    api_key: str


@router.get("")
async def get_settings():
    key = get_env_api_key()
    return {
        # Hanya 4 karakter terakhir: cukup untuk mengenali kunci, tidak cukup
        # untuk membocorkannya. Versi lama mengembalikan 8 karakter PERTAMA.
        "gemini_api_key_set": bool(key),
        "gemini_api_key_last4": key[-4:] if len(key) >= 4 else "",
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

    key = get_env_api_key()
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
    os.environ["GEMINI_API_KEY"] = req.api_key.strip()
    return {"status": "ok", "message": "API Key Gemini tersimpan untuk sesi ini."}
