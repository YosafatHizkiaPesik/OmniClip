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


@router.post("/api-key")
async def set_api_key(req: ApiKeyRequest):
    os.environ["GEMINI_API_KEY"] = req.api_key.strip()
    return {"status": "ok", "message": "API Key Gemini tersimpan untuk sesi ini."}
