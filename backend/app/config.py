"""Konfigurasi terpusat: path, batas sumber daya, dan pengaturan dari .env."""

import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

# --- Dijalankan dari sumber, atau sebagai aplikasi terbungkus? ----------------
#
# Perbedaannya bukan kosmetik. Saat dibungkus, folder aplikasi bisa berada di
# tempat yang tidak boleh ditulis (Program Files), dan yang lebih penting: ia
# DITIMPA setiap kali aplikasi diperbarui. Menyimpan klip di sana berarti
# memperbarui aplikasi menghapus pekerjaan penggunanya.

FROZEN = bool(getattr(sys, "frozen", False))
# PyInstaller menaruh berkas data di sini; saat dijalankan dari sumber, tidak ada.
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BACKEND_DIR))


def _user_data_dir() -> Path:
    """Tempat data pengguna menurut kebiasaan tiap sistem."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "OmniClip"


# --- Path ---------------------------------------------------------------------
# OMNICLIP_STORAGE menang atas keduanya: satu-satunya cara memindahkan seluruh
# penyimpanan ke diska lain tanpa menyentuh kode.
_storage_env = os.getenv("OMNICLIP_STORAGE", "").strip()
if _storage_env:
    STORAGE_DIR = Path(_storage_env).expanduser().resolve()
elif FROZEN:
    STORAGE_DIR = _user_data_dir()
else:
    STORAGE_DIR = PROJECT_DIR / "OmniClip_Storage"

# .env dibaca dari penyimpanan pengguna saat terbungkus — folder aplikasi bukan
# tempat yang bisa ditulis, dan isinya hilang saat aplikasi diperbarui.
load_dotenv(STORAGE_DIR / ".env" if FROZEN else BACKEND_DIR / ".env")
DOWNLOAD_DIR = STORAGE_DIR / "local_downloads"
CLIPS_DIR = STORAGE_DIR / "edited_clips"
THUMBS_DIR = STORAGE_DIR / "thumbnails"
LOGS_DIR = STORAGE_DIR / "logs"
# Pembacaan judul yang sudah disintesis. Disimpan supaya menekan "dengarkan"
# dua kali tidak berarti menjalankan model dua kali, dan supaya berkasnya bisa
# disajikan lewat /api/media seperti media lain — bukan lewat jalur baru yang
# aturan keamanannya harus dipikirkan ulang.
VOICE_DIR = STORAGE_DIR / "title_voice"
# Model diunduh saat pertama dipakai, jadi foldernya harus bisa ditulis. Saat
# terbungkus itu berarti penyimpanan pengguna, bukan folder aplikasi.
MODELS_DIR = (STORAGE_DIR / "models") if FROZEN else (BACKEND_DIR / "models")
# Font dan aset lain hanya dibaca, jadi ia tinggal di dalam bundel.
ASSETS_DIR = (BUNDLE_DIR / "app" / "assets") if FROZEN \
    else (Path(__file__).resolve().parent / "assets")
FONTS_DIR = ASSETS_DIR / "fonts"
# Model kecil yang ikut dibundel (YuNet, 232 KB) disalin sekali ke folder yang
# bisa ditulis, supaya seluruh kode hanya perlu tahu satu tempat mencari model.
BUNDLED_MODELS_DIR = (BUNDLE_DIR / "models") if FROZEN else None

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

if BUNDLED_MODELS_DIR and BUNDLED_MODELS_DIR.is_dir():
    for _m in BUNDLED_MODELS_DIR.glob("*.onnx"):
        _target = MODELS_DIR / _m.name
        if not _target.exists():
            shutil.copy2(_m, _target)


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
FRONTEND_DIST = (BUNDLE_DIR / "frontend_dist") if FROZEN \
    else (PROJECT_DIR / "frontend" / "dist")


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


def use_bundled_ffmpeg() -> Path | None:
    """
    Menaruh ffmpeg bundelan di depan PATH.

    Dilakukan lewat PATH, bukan dengan mengganti string "ffmpeg" di sebelas
    tempat pemanggilan: cara ini juga membuat yt-dlp menemukannya, dan yt-dlp
    mencari ffmpeg dengan caranya sendiri yang tidak bisa kita arahkan.
    """
    folder = BUNDLE_DIR / "bin"
    exe = folder / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if not exe.is_file():
        return None
    os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
    return folder


def require_ffmpeg() -> None:
    """Gagal cepat saat startup, bukan di tengah render pertama."""
    use_bundled_ffmpeg()
    missing = [b for b in ("ffmpeg", "ffprobe") if not shutil.which(b)]
    if missing:
        raise RuntimeError(
            f"{' dan '.join(missing)} tidak ditemukan di PATH. "
            "OmniClip membutuhkannya untuk memproses video. "
            "Ubuntu/Debian: sudo apt install ffmpeg"
        )
