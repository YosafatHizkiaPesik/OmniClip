"""Konfigurasi terpusat: path, batas sumber daya, dan pengaturan dari .env."""

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")

# --- Path ---------------------------------------------------------------------
STORAGE_DIR = PROJECT_DIR / "OmniClip_Storage"
DOWNLOAD_DIR = STORAGE_DIR / "local_downloads"
CLIPS_DIR = STORAGE_DIR / "edited_clips"
THUMBS_DIR = STORAGE_DIR / "thumbnails"
LOGS_DIR = STORAGE_DIR / "logs"
MODELS_DIR = BACKEND_DIR / "models"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

DB_PATH = STORAGE_DIR / "omniclip.db"

# Kategori media yang boleh disajikan lewat /api/media dan /api/file.
MEDIA_DIRS = {
    "local_downloads": DOWNLOAD_DIR,
    "edited_clips": CLIPS_DIR,
    "thumbnails": THUMBS_DIR,
}

for _d in (DOWNLOAD_DIR, CLIPS_DIR, THUMBS_DIR, LOGS_DIR, MODELS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# --- Job queue ----------------------------------------------------------------
# Batas sebenarnya di mesin ini adalah RAM, bukan CPU. Lane `cpu` sengaja 1
# supaya model Whisper (300-900 MB) dan encode x264 tidak pernah hidup bersamaan.
LANE_LIMITS = {
    "net": int(os.getenv("OMNICLIP_LANE_NET", "2")),
    "cpu": int(os.getenv("OMNICLIP_LANE_CPU", "1")),
}
JOB_PROGRESS_MIN_INTERVAL = 0.25  # detik antar tulisan progress ke DB


# --- Transkrip ----------------------------------------------------------------
WHISPER_MODEL_DEFAULT = os.getenv("OMNICLIP_WHISPER_MODEL", "base")
WHISPER_IDLE_UNLOAD_SECONDS = 600
CAPTION_LANGS = ("id", "id-ID", "en", "en-US")


# --- Gemini -------------------------------------------------------------------
# Dua model pertama di-pin, bukan alias bergerak: kualitas alias bisa berubah
# semalam tanpa perubahan kode. Rantainya diperiksa dari kiri; model yang sudah
# dipensiunkan menjawab 404 dan pemanggil lanjut ke berikutnya.
#
# gemini-2.0-flash dan gemini-2.5-flash dihapus dari rantai: keduanya menjawab
# "no longer available to new users", jadi keduanya hanya menambah satu bulatan
# gagal sebelum sistem menyerah ke heuristik. Penutup rantai sekarang
# gemini-flash-latest — alias memang bisa berubah diam-diam, tapi sebagai
# cadangan TERAKHIR ia selalu lebih baik daripada model yang sudah pasti mati.
GEMINI_MODELS = [
    m.strip() for m in
    os.getenv("OMNICLIP_GEMINI_MODELS",
              "gemini-3.6-flash,gemini-3.5-flash,gemini-flash-latest").split(",")
    if m.strip()
]
MAX_TRANSCRIPT_CHARS = int(os.getenv("OMNICLIP_MAX_TRANSCRIPT_CHARS", "350000"))


# --- CORS ---------------------------------------------------------------------
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def get_env_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def get_cookies_file() -> str:
    path = os.environ.get("OMNICLIP_COOKIES_FILE", "").strip()
    return path if path and os.path.exists(path) else ""


def require_ffmpeg() -> None:
    """Gagal cepat saat startup, bukan di tengah render pertama."""
    missing = [b for b in ("ffmpeg", "ffprobe") if not shutil.which(b)]
    if missing:
        raise RuntimeError(
            f"{' dan '.join(missing)} tidak ditemukan di PATH. "
            "OmniClip membutuhkannya untuk memproses video. "
            "Ubuntu/Debian: sudo apt install ffmpeg"
        )
