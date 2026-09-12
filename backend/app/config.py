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
# Pembacaan judul yang sudah disintesis. Disimpan supaya menekan "dengarkan"
# dua kali tidak berarti menjalankan model dua kali, dan supaya berkasnya bisa
# disajikan lewat /api/media seperti media lain — bukan lewat jalur baru yang
# aturan keamanannya harus dipikirkan ulang.
VOICE_DIR = STORAGE_DIR / "title_voice"
MODELS_DIR = BACKEND_DIR / "models"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

DB_PATH = STORAGE_DIR / "omniclip.db"

# Kategori media yang boleh disajikan lewat /api/media dan /api/file.
MEDIA_DIRS = {
    "local_downloads": DOWNLOAD_DIR,
    "edited_clips": CLIPS_DIR,
    "thumbnails": THUMBS_DIR,
    "title_voice": VOICE_DIR,
}

for _d in (DOWNLOAD_DIR, CLIPS_DIR, THUMBS_DIR, LOGS_DIR, MODELS_DIR, VOICE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# --- Job queue ----------------------------------------------------------------
# Batas sebenarnya di mesin ini adalah RAM, bukan CPU. Lane `cpu` sengaja 1
# supaya model Whisper (300-900 MB) dan encode x264 tidak pernah hidup bersamaan.
LANE_LIMITS = {
    "net": int(os.getenv("OMNICLIP_LANE_NET", "2")),
    "cpu": int(os.getenv("OMNICLIP_LANE_CPU", "1")),
    # Unggahan punya jalurnya sendiri, dan lebarnya SATU. Bukan karena memori —
    # unggahan hampir tidak memakainya — melainkan karena mengirim selusin klip
    # ke satu kanal dalam satu ledakan adalah persis pola yang membuat YouTube
    # menandai sebuah kanal. Satu per satu, berurutan, selalu.
    "upload": 1,
}

# Jeda minimum antara dua unggahan YouTube yang berhasil. Nol berarti langsung
# menyambung; bawaannya sengaja tidak nol.
UPLOAD_GAP_SECONDS = int(os.getenv("OMNICLIP_UPLOAD_GAP", "90"))
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


# --- Jaringan -----------------------------------------------------------------
# Bawaannya tetap 127.0.0.1. Membukanya adalah keputusan yang harus diketik
# sendiri, bukan sesuatu yang terjadi karena sebuah berkas konfigurasi berubah.
#
# Untuk Cloudflare Tunnel, HOST tidak perlu diubah sama sekali: `cloudflared`
# menyambung dari DALAM mesin ke 127.0.0.1, sehingga tidak ada satu port pun
# yang terbuka ke jaringan. Lihat PANDUAN-AKSES-JARAK-JAUH.md.
HOST = os.getenv("OMNICLIP_HOST", "127.0.0.1").strip()
PORT = int(os.getenv("OMNICLIP_PORT", "8000"))

# Asal yang boleh memanggil API dari peramban.
#
# Setelah frontend disajikan oleh backend yang sama (lihat app/main.py), asal
# permintaan sama dengan asal halaman dan CORS tidak lagi ikut bermain — itulah
# sebabnya jalur Cloudflare tidak butuh tambahan apa pun di sini. Daftar ini
# tinggal untuk mode pengembangan, saat UI masih hidup di Vite port 5173.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    *[o.strip() for o in os.getenv("OMNICLIP_ORIGINS", "").split(",") if o.strip()],
]

# Direktori hasil `npm run build`. Bila ada, backend menyajikannya di "/" dan
# seluruh aplikasi hidup di satu port — satu asal, satu terowongan.
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"


def get_api_key() -> str:
    """
    Kunci AI yang berlaku.

    Basis data lebih dulu, `.env` sebagai cadangan. Urutannya begitu karena
    basis data adalah satu-satunya dari keduanya yang bisa diisi dari HP —
    dan ketika keduanya terisi, yang dimasukkan lewat antarmuka adalah yang
    lebih baru dan lebih disengaja.
    """
    try:
        from .repos import settings as settings_repo
        value = settings_repo.get("ai.api_key").strip()
        if value:
            return value
    except Exception:  # basis data belum siap saat impor paling awal
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()


# Nama lama. Sudah bukan "env" saja, tapi dipakai di beberapa tempat.
get_env_api_key = get_api_key


def get_api_key_source() -> str:
    """`db` | `env` | `` — supaya antarmuka bisa mengatakan dari mana asalnya."""
    try:
        from .repos import settings as settings_repo
        if settings_repo.get("ai.api_key").strip():
            return "db"
    except Exception:
        pass
    return "env" if os.environ.get("GEMINI_API_KEY", "").strip() else ""


def get_model_override() -> str:
    """Model yang dipilih pengguna, tersimpan di server agar ikut ke HP."""
    try:
        from .repos import settings as settings_repo
        return settings_repo.get("ai.model").strip()
    except Exception:
        return ""


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
