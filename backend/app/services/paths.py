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
# Berkas perantara yt-dlp: satu aliran (video SAJA atau audio saja) yang
# belum digabung, mis. "Judul_ID.f623.mp4". Tertinggal bila penggabungan
# gagal — terukur satu berkas 17 GB berisi video tanpa suara. Dipakai sebagai
# sumber, klipnya bisu.
PERANTARA_RE = re.compile(r"\.f\d+(-\d+)?\.[A-Za-z0-9]+$")


def berkas_perantara(nama: str) -> bool:
    return bool(PERANTARA_RE.search(nama))
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
    if base_dir is None and category.startswith("klip_") and category[5:].isdigit():
        # Folder klip satu profil (services/profil.py).
        from ..repos import profil as profil_repo
        from .profil import folder_klip
        if profil_repo.ambil(int(category[5:])):
            base_dir = folder_klip(int(category[5:]))
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


KANAL_IMPOR = "Impor lokal"


def adalah_impor(video_id: str) -> bool:
    """
    Video dari komputer pengguna, bukan dari YouTube.

    Tidak cukup dari bentuk id-nya: id impor ("L" + 10 heks) sengaja
    berbentuk seperti id YouTube supaya mengalir lewat jalur yang sama, dan
    id YouTube sungguhan juga bisa diawali "L". Penandanya baris videonya.
    """
    if not (video_id or "").startswith("L"):
        return False
    try:
        from ..repos import media as media_repo
        row = media_repo.get_video(video_id) or {}
    except Exception:
        return False
    return row.get("channel") == KANAL_IMPOR


def jalur_luar(video_id: str) -> Path | None:
    """
    Berkas impor yang dibaca DI TEMPATNYA (tidak disalin): jalurnya tersimpan
    di metadata videonya. None bila impor ini salinan, atau berkasnya hilang.
    """
    if not adalah_impor(video_id):
        return None
    try:
        import json
        from ..repos import media as media_repo
        meta = json.loads((media_repo.get_video(video_id) or {}).get("meta_json") or "{}")
        p = Path(meta.get("jalur") or "")
    except Exception:
        return None
    return p if str(p) not in ("", ".") and p.is_file() else None


def _cari_di(folder: Path, video_id: str) -> Path | None:
    if not folder.is_dir():
        return None
    for entry in sorted(folder.iterdir()):
        if (entry.is_file() and video_id in entry.name and entry.suffix.lower() in VIDEO_EXTS
                and not berkas_perantara(entry.name)):
            return entry
    return None


def find_local_video(video_id: str) -> Path | None:
    """Berkas video untuk sebuah id: unduhan YouTube, atau video impor."""
    if not YT_ID_RE.match(video_id or ""):
        return None
    from ..config import IMPOR_DIR
    return (_cari_di(DOWNLOAD_DIR, video_id) or _cari_di(IMPOR_DIR, video_id)
            or (jalur_luar(video_id) if video_id.startswith("L") else None))


def url_sumber(video_id: str, path: Path) -> str:
    """URL pemutar untuk berkas sumber, termasuk impor yang ada di luar folder OmniClip."""
    from ..config import DOWNLOAD_DIR as _D, IMPOR_DIR
    try:
        induk = Path(path).resolve().parent
        if induk not in (_D.resolve(), IMPOR_DIR.resolve()):
            return f"/api/impor/{video_id}/berkas"
    except OSError:
        pass
    return f"/api/media/{kategori_berkas(path)}/{Path(path).name}"


def kategori_berkas(path: Path) -> str:
    """Kategori media (/api/media/<kategori>/…) untuk berkas sumber."""
    from ..config import IMPOR_DIR
    try:
        if Path(path).resolve().parent == IMPOR_DIR.resolve():
            return "impor"
    except OSError:
        pass
    return "local_downloads"


def pindahkan_impor_lama() -> int:
    """Impor dari versi sebelumnya (di local_downloads) dipindah ke folder impor."""
    import shutil
    from ..config import IMPOR_DIR
    pindah = 0
    if not DOWNLOAD_DIR.is_dir():
        return 0
    for entry in list(DOWNLOAD_DIR.iterdir()):
        m = re.search(r"_(L[0-9a-f]{10})\.[A-Za-z0-9]+$", entry.name)
        if not (entry.is_file() and m and adalah_impor(m.group(1))):
            continue
        try:
            IMPOR_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(IMPOR_DIR / entry.name))
            pindah += 1
        except OSError:
            pass
    return pindah


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


def ffpath(path) -> str:
    r"""
    Menyiapkan sebuah path untuk dipakai DI DALAM filtergraph ffmpeg.

    Parser filtergraph memperlakukan ":" sebagai pemisah opsi dan "\" sebagai
    escape, dan path Windows penuh keduanya: C:\Users\nama\... . Tanpa
    penyiapan ini, titik dua setelah huruf diska mengakhiri opsinya dan sisanya
    dibaca sebagai opsi lain yang tidak dikenal.

    Kesalahannya tidak selalu berupa galat. Untuk `fontsdir`, ffmpeg yang tidak
    bisa membaca nilainya meneruskan tanpa fontsdir sama sekali — libass lalu
    jatuh ke font teks badan lewat fontconfig, dan hasil render berhenti cocok
    dengan pratinjau. Diam, dan baru terlihat setelah videonya jadi.

    Dulu ini disalin di tiga tempat dengan tiga salinan yang tidak sama; satu di
    antaranya, `fontsdir`, tidak pernah mendapat perlakuan ini sama sekali. Di
    Linux ketiganya tampak benar, karena path Linux tidak punya ":" maupun "\".
    """
    return str(path).replace("\\", "/").replace(":", r"\:")


def buang_salinan_impor(video_id: str) -> bool:
    """
    Membuang SALINAN impor milik OmniClip (folder impor). Berkas yang dibaca di
    tempatnya (impor lewat jalur) tidak pernah disentuh — itu milik pengguna.
    """
    from ..config import IMPOR_DIR
    if not adalah_impor(video_id):
        return False
    berkas = _cari_di(IMPOR_DIR, video_id)
    if berkas is None:
        return False
    try:
        berkas.unlink()
        return True
    except OSError:
        return False


def bersihkan_impor_yatim(umur_min: float = 24 * 3600) -> int:
    """Salinan impor tanpa analisis dan tanpa pekerjaan (kartunya sudah dihapus)."""
    import time
    from ..config import IMPOR_DIR
    from ..db import get_conn
    if not IMPOR_DIR.is_dir():
        return 0
    conn = get_conn()
    dibuang = 0
    for entry in list(IMPOR_DIR.iterdir()):
        m = re.search(r"_(L[0-9a-f]{10})\.[A-Za-z0-9]+$", entry.name)
        if not (entry.is_file() and m) or time.time() - entry.stat().st_mtime < umur_min:
            continue
        vid = m.group(1)
        ada = conn.execute("SELECT 1 FROM analyses WHERE video_id = ? UNION ALL "
                           "SELECT 1 FROM jobs WHERE video_id = ? LIMIT 1", (vid, vid)).fetchone()
        if ada is None:
            try:
                entry.unlink()
                dibuang += 1
            except OSError:
                pass
    return dibuang
