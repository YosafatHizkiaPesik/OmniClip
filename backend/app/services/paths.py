"""
Satu-satunya pintu dari input klien ke filesystem.

Semua akses file media melewati modul ini. Tidak ada endpoint yang boleh
menyusun path dari string milik klien secara langsung.
"""

import os
import re
from pathlib import Path

from ..config import DOWNLOAD_DIR, MEDIA_DIRS
from ..errors import InvalidInput, NotFound

VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".mov")
YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YT_URL_RE = re.compile(
    r"(?:v=|/embed/|/v/|youtu\.be/|/shorts/|/live/)([A-Za-z0-9_-]{11})"
)


def extract_youtube_id(url_or_id: str) -> str:
    """Mengambil ID YouTube 11 karakter dari URL atau ID telanjang."""
    if not url_or_id:
        return ""
    s = url_or_id.strip()
    if YT_ID_RE.match(s):
        return s
    m = YT_URL_RE.search(s)
    return m.group(1) if m else ""


def extract_id_from_filename(filename: str) -> str:
    """
    Mengambil ID YouTube dari nama file unduhan.

    Template yt-dlp adalah '%(title).60s_%(id)s.%(ext)s', jadi ID selalu berada
    tepat sebelum ekstensi dan didahului garis bawah.
    """
    stem = Path(filename).stem
    m = re.search(r"[_-]([A-Za-z0-9_-]{11})$", stem)
    if m:
        return m.group(1)
    return stem if YT_ID_RE.match(stem) else ""


def safe_media_path(category: str, filename: str) -> Path:
    """
    Menyelesaikan file media di dalam kategori yang diizinkan.

    Menggantikan mount StaticFiles("/storage") lama yang membuka seluruh pohon
    storage — termasuk token dan file database — tanpa autentikasi.
    """
    base_dir = MEDIA_DIRS.get(category)
    if base_dir is None:
        raise InvalidInput("Kategori media tidak valid.")

    name = os.path.basename(filename)
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise InvalidInput("Nama file tidak valid.")

    base = base_dir.resolve()
    candidate = (base / name).resolve()
    if not candidate.is_relative_to(base):
        raise InvalidInput("Nama file tidak valid.")
    if not candidate.is_file():
        raise NotFound("File tidak ditemukan.")
    return candidate


def find_local_video(video_id: str) -> Path | None:
    """Mencari file video yang sudah diunduh untuk sebuah ID YouTube."""
    if not YT_ID_RE.match(video_id or ""):
        return None
    if not DOWNLOAD_DIR.is_dir():
        return None
    for entry in sorted(DOWNLOAD_DIR.iterdir()):
        if entry.is_file() and video_id in entry.name and entry.suffix.lower() in VIDEO_EXTS:
            return entry
    return None


def resolve_source_reference(source: str) -> tuple[str | None, Path | None]:
    """
    Menerjemahkan referensi sumber dari klien.

    Hanya menerima ID/URL YouTube atau nama file yang sudah ada di
    local_downloads/. Mengembalikan (video_id, path_lokal_bila_ada).

    Path filesystem sembarang ditolak: versi lama meneruskan nilai apa pun dari
    klien ke `ffmpeg -i`, sehingga file mana pun di disk bisa dibaca dan
    disajikan kembali lewat storage.
    """
    if not source or not source.strip():
        raise InvalidInput("Referensi video wajib diisi.")
    source = source.strip()

    # Nama file yang sudah ada di local_downloads.
    name = os.path.basename(source)
    if name and Path(name).suffix.lower() in VIDEO_EXTS:
        base = DOWNLOAD_DIR.resolve()
        candidate = (base / name).resolve()
        if candidate.is_relative_to(base) and candidate.is_file():
            return extract_youtube_id(name) or None, candidate

    video_id = extract_youtube_id(source)
    if not video_id:
        raise InvalidInput(
            "Referensi video harus berupa ID/URL YouTube atau nama file yang sudah diunduh."
        )
    return video_id, find_local_video(video_id)
