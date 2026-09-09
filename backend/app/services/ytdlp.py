import os
import json
import subprocess
import yt_dlp
from urllib.parse import quote_plus

from ..config import DOWNLOAD_DIR as _DOWNLOAD_DIR, STORAGE_DIR as _STORAGE_DIR, get_cookies_file

STORAGE_DIR = str(_STORAGE_DIR)
DOWNLOAD_DIR = str(_DOWNLOAD_DIR)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Tinggi video yang ditawarkan ke user, dari kecil ke besar.
SUPPORTED_HEIGHTS = [360, 480, 720, 1080, 1440, 2160]

AUDIO_EXTS = {".mp3", ".m4a", ".opus", ".webm-audio", ".aac", ".wav"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov"}
MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS


class YtdlpError(Exception):
    """Kegagalan yt-dlp yang sudah diterjemahkan ke pesan yang berguna bagi user."""

    def __init__(self, code: str, message: str, original: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.original = original


def classify_ytdlp_error(exc: Exception) -> YtdlpError:
    """
    Menerjemahkan kegagalan yt-dlp jadi pesan Indonesia yang bisa ditindaklanjuti.

    Sebelumnya semua kegagalan ditelan (`except: return []`), sehingga blokir
    YouTube tampak identik dengan "tidak ada hasil" — user tidak punya cara tahu
    apa yang salah, apalagi cara memperbaikinya.
    """
    raw = str(exc)
    low = raw.lower()

    if "403" in raw or "forbidden" in low:
        return YtdlpError(
            "YTDLP_FORBIDDEN",
            "YouTube menolak unduhan ini (HTTP 403). Biasanya yt-dlp perlu "
            "diperbarui: jalankan `pip install -U yt-dlp` di venv backend. "
            "Kalau masih gagal, tambahkan file cookies lewat OMNICLIP_COOKIES_FILE.",
            raw,
        )
    if "sign in to confirm" in low or "not a bot" in low or "captcha" in low:
        return YtdlpError(
            "YTDLP_BOT_CHECK",
            "YouTube meminta verifikasi bot. Tambahkan file cookies browser lewat "
            "variabel OMNICLIP_COOKIES_FILE, lalu coba lagi.",
            raw,
        )
    if "429" in raw or "too many requests" in low or "rate" in low and "limit" in low:
        return YtdlpError(
            "YTDLP_RATE_LIMIT",
            "YouTube sedang membatasi permintaan. Tunggu beberapa menit lalu coba lagi.",
            raw,
        )
    if "private" in low or "members-only" in low or "members only" in low:
        return YtdlpError("YTDLP_PRIVATE", "Video ini privat atau khusus member.", raw)
    if "unavailable" in low or "removed" in low or "does not exist" in low:
        return YtdlpError("YTDLP_UNAVAILABLE", "Video tidak tersedia atau sudah dihapus.", raw)
    if "geo" in low and "restrict" in low:
        return YtdlpError("YTDLP_GEO", "Video dibatasi di wilayah ini.", raw)
    if "requested format is not available" in low:
        return YtdlpError(
            "YTDLP_NO_FORMAT",
            "Resolusi yang diminta tidak tersedia untuk video ini. Coba resolusi lebih rendah.",
            raw,
        )
    if "timed out" in low or "timeout" in low:
        return YtdlpError("YTDLP_TIMEOUT", "Koneksi ke YouTube timeout. Periksa jaringan Anda.", raw)

    return YtdlpError("YTDLP_ERROR", f"Gagal menghubungi YouTube: {raw[:200]}", raw)


def _base_opts() -> dict:
    """Opsi yt-dlp yang dipakai bersama semua pemanggilan."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 30,
        'retries': 3,
    }
    # Cookies opsional — jalan keluar utama ketika YouTube menuntut verifikasi bot.
    cookies = get_cookies_file()
    if cookies:
        opts['cookiefile'] = cookies
    return opts


def probe_media(path: str) -> dict:
    """
    Membaca dimensi/durasi/codec asli sebuah file media lewat ffprobe.
    Dipakai untuk melaporkan resolusi yang BENAR-BENAR diunduh, bukan yang diminta.
    """
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "stream=codec_type,codec_name,width,height",
                "-show_entries", "format=duration",
                "-of", "json", path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return {}
        data = json.loads(out.stdout or "{}")
        result = {"duration": float(data.get("format", {}).get("duration") or 0) or None}
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and "width" not in result:
                result["width"] = stream.get("width")
                result["height"] = stream.get("height")
                result["vcodec"] = stream.get("codec_name")
            elif stream.get("codec_type") == "audio" and "acodec" not in result:
                result["acodec"] = stream.get("codec_name")
        return result
    except Exception as e:
        print(f"[OmniClip] ffprobe gagal untuk {path}: {e}")
        return {}

# Parameter urutan hasil YouTube. Nilainya adalah protobuf terenkode yang
# dipakai halaman pencarian YouTube sendiri; yt-dlp meneruskan URL-nya apa
# adanya, jadi filternya benar-benar dikerjakan YouTube dan bukan diurutkan
# ulang di sini atas data yang tidak lengkap.
SEARCH_SORTS = {
    "relevan": None,
    "terbaru": "CAI%3D",
    "terpopuler": "CAM%3D",
    "rating": "CAE%3D",
}


def search_youtube_videos(query: str, limit: int = 20, sort: str = "relevan"):
    """
    Melakukan pencarian video YouTube menggunakan yt-dlp tanpa YouTube API Key.

    `sort` memakai parameter urutan milik YouTube sendiri. Mengurutkan di sisi
    kita mustahil: pencarian datar tidak mengembalikan tanggal unggah sama
    sekali (lihat `fetch_upload_dates`), jadi "terbaru" hanya bisa dijawab oleh
    YouTube.
    """
    ydl_opts = _base_opts()
    ydl_opts.update({
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'default_search': 'ytsearch',
    })

    results = []
    is_url = query.startswith("http://") or query.startswith("https://")
    sp = SEARCH_SORTS.get(sort)
    if is_url:
        search_target = query
    elif sp:
        # Lewat URL pencarian sungguhan supaya parameter urutannya ikut.
        ydl_opts['playlistend'] = limit
        search_target = ("https://www.youtube.com/results?search_query="
                         + quote_plus(query) + "&sp=" + sp)
    else:
        search_target = f"ytsearch{limit}:{query}"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(search_target, download=False)
            entries = info.get('entries', []) if 'entries' in info else [info]

            for entry in entries:
                if not entry:
                    continue
                video_id = entry.get('id', '')
                if not video_id:
                    continue
                title = entry.get('title', 'Untitled')
                url = entry.get('url') or entry.get('webpage_url') or f"https://www.youtube.com/watch?v={video_id}"
                duration = entry.get('duration', 0)
                uploader = entry.get('uploader') or entry.get('channel', 'Unknown Channel')
                view_count = entry.get('view_count', 0)
                thumbnail = (
                    entry.get('thumbnail') or
                    (entry.get('thumbnails', [{}])[-1].get('url') if entry.get('thumbnails') else None) or
                    f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                )

                results.append({
                    "id": video_id,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "duration": duration,
                    "channel": uploader,
                    "views": view_count,
                    "thumbnail": thumbnail,
                    "description": entry.get('description', '')
                })
        except Exception as e:
            # Jangan telan kegagalan jadi daftar kosong: user berhak tahu bedanya
            # antara "tidak ada hasil" dan "YouTube memblokir kita".
            raise classify_ytdlp_error(e) from e

    return results

def _available_resolutions(info: dict) -> list:
    """
    Menurunkan daftar resolusi dari format yang BENAR-BENAR ditawarkan YouTube
    untuk video ini. Sebelumnya daftar ini hardcoded, sehingga UI menjanjikan
    1080p pada video yang maksimal 480p.
    """
    heights = set()
    has_audio = False
    for f in info.get('formats') or []:
        if f.get('vcodec') and f.get('vcodec') != 'none':
            h = f.get('height')
            if h:
                heights.add(int(h))
        if f.get('acodec') and f.get('acodec') != 'none':
            has_audio = True

    if not heights:
        # Fallback konservatif kalau daftar format tidak terbaca.
        h = info.get('height')
        heights = {int(h)} if h else {360}

    max_h = max(heights)
    options = [f"{h}p" for h in SUPPORTED_HEIGHTS if h <= max_h]
    # Selalu tawarkan minimal satu pilihan video.
    if not options:
        options = [f"{max_h}p"]
    if has_audio:
        options.append("Audio MP3")
    return options


def _has_usable_captions(info: dict, langs=("id", "id-ID", "en", "en-US")) -> bool:
    """Apakah video punya caption dalam salah satu bahasa yang kita pakai."""
    available = set((info.get("subtitles") or {})) | set((info.get("automatic_captions") or {}))
    return any(l in available for l in langs)


def get_video_info(url_or_id: str):
    """
    Mendapatkan detail metadata video YouTube.
    """
    url = url_or_id if url_or_id.startswith("http") else f"https://www.youtube.com/watch?v={url_or_id}"
    with yt_dlp.YoutubeDL(_base_opts()) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return {
                "id": info.get('id'),
                "title": info.get('title'),
                "description": info.get('description', ''),
                "duration": info.get('duration', 0),
                "url": url,
                "thumbnail": info.get('thumbnail'),
                "channel": info.get('uploader'),
                "views": info.get('view_count', 0),
                "upload_date": info.get('upload_date'),
                "available_resolutions": _available_resolutions(info),
                # Ketersediaan caption menentukan apakah transkripsi lokal
                # (yang lambat) diperlukan. Frontend memakainya untuk memberi
                # perkiraan waktu yang jujur SEBELUM pengguna menunggu.
                "has_captions": _has_usable_captions(info),
                "caption_langs": sorted(
                    set((info.get("subtitles") or {}))
                    | set((info.get("automatic_captions") or {}))
                )[:12],
            }
        except Exception as e:
            raise classify_ytdlp_error(e) from e

def _make_progress_hook(on_progress):
    """
    Menjembatani progress_hooks yt-dlp ke callback job.

    yt-dlp melaporkan tiap stream secara terpisah, dan unduhan DASH punya dua
    stream (video lalu audio). Bobot 85%/15% membuat bar tidak melompat mundur
    ke 0 saat stream kedua dimulai.
    """
    state = {"stream": 0, "last": -1.0}

    def hook(d):
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            frac = (done / total) if total else 0.0
            base, span = (0.0, 0.85) if state["stream"] == 0 else (0.85, 0.15)
            overall = base + span * min(1.0, frac)
            if overall - state["last"] >= 0.005:
                state["last"] = overall
                speed = d.get("speed") or 0
                mb = f"{done / 1048576:.0f}/{total / 1048576:.0f} MB" if total else ""
                on_progress(overall, f"Mengunduh {mb} ({speed / 1048576:.1f} MB/s)" if speed else f"Mengunduh {mb}")
        elif status == "finished":
            state["stream"] += 1
            state["last"] = -1.0
            on_progress(0.85 if state["stream"] == 1 else 0.98, "Menggabungkan video dan audio…")

    return hook


def download_youtube_media(url_or_id: str, resolution: str = "720p", on_progress=None):
    """
    Mengunduh media dari YouTube berdasarkan opsi resolusi (360p, 480p, 720p, 1080p, Audio MP3).
    Format output disimpan ke OmniClip_Storage/local_downloads/
    """
    url = url_or_id if url_or_id.startswith("http") else f"https://www.youtube.com/watch?v={url_or_id}"

    # Setup format selector
    if resolution == "Audio MP3":
        fmt = "bestaudio[ext=m4a]/bestaudio/best"
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        try:
            res_height = int(resolution.rstrip("pP"))
        except ValueError:
            res_height = 720

        # PENTING: `best[...]` hanya cocok dengan format PROGRESSIVE (audio+video
        # dalam satu file), dan satu-satunya format progressive YouTube hari ini
        # adalah itag 18 = 360p. Selektor lama karenanya SELALU menghasilkan 360p
        # berapapun resolusi yang diminta. Kita harus memilih video-only (`bv*`)
        # lalu menggabungkannya dengan audio terbaik (`ba`).
        #
        # avc1 (H.264) didahulukan karena decode-nya jauh lebih murah di CPU
        # tanpa GPU dan langsung kompatibel dengan pipeline ffmpeg berikutnya.
        # `<=?` berarti "abaikan filter ini bila field height tidak ada".
        fmt = (
            f"bv*[height<=?{res_height}][vcodec^=avc1]+ba[ext=m4a]/"
            f"bv*[height<=?{res_height}]+ba/"
            f"b[height<=?{res_height}]/b"
        )
        postprocessors = []

    # Sanitize output template (use safe ASCII title)
    out_template = os.path.join(DOWNLOAD_DIR, '%(title).60s_%(id)s.%(ext)s')

    ydl_opts = _base_opts()
    ydl_opts.update({
        'format': fmt,
        'outtmpl': out_template,
        # Pakai file .part selama proses berlangsung: unduhan yang gagal di
        # tengah jalan tidak lagi menyisakan .mp4 rusak yang tampak valid di
        # daftar Downloads. list_local_downloads() sudah melewati file .part.
        'fragment_retries': 3,
        'merge_output_format': 'mp4',
        'restrictfilenames': True, # Hindari karakter spesial di nama file
    })

    if postprocessors:
        ydl_opts['postprocessors'] = postprocessors
    if on_progress is not None:
        ydl_opts['progress_hooks'] = [_make_progress_hook(on_progress)]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            
            # Get actual downloaded filename
            filename = ydl.prepare_filename(info)
            
            # Fix extension for merged/converted files
            if not os.path.exists(filename):
                # Try common extensions
                base = os.path.splitext(filename)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a']:
                    candidate = base + ext
                    if os.path.exists(candidate):
                        filename = candidate
                        break
            
            # For Audio MP3 conversion
            if resolution == "Audio MP3":
                base, _ = os.path.splitext(filename)
                mp3_path = base + ".mp3"
                if os.path.exists(mp3_path):
                    filename = mp3_path
            
            if not os.path.exists(filename):
                # Try to find the file by video ID
                vid_id = info.get('id', '')
                for fname in os.listdir(DOWNLOAD_DIR):
                    if vid_id in fname and not fname.endswith('.part'):
                        filename = os.path.join(DOWNLOAD_DIR, fname)
                        break

            if not os.path.exists(filename):
                return {"success": False, "error": f"File unduhan tidak ditemukan setelah proses selesai."}

            # Laporkan apa yang SUNGGUH diunduh, bukan apa yang diminta. Kalau
            # YouTube hanya menyediakan 480p untuk permintaan 1080p, user berhak
            # tahu — bukan diberi label "1080p" pada file 480p.
            probe = probe_media(filename) if resolution != "Audio MP3" else {}
            actual_height = probe.get("height")

            return {
                "success": True,
                "file_path": filename,
                "file_name": os.path.basename(filename),
                "video_id": info.get('id'),
                "title": info.get('title'),
                "duration": probe.get("duration") or info.get('duration'),
                "requested_resolution": resolution,
                "resolution": f"{actual_height}p" if actual_height else resolution,
                "width": probe.get("width"),
                "height": actual_height,
                "vcodec": probe.get("vcodec"),
                "acodec": probe.get("acodec"),
                "file_size": os.path.getsize(filename) if os.path.exists(filename) else 0
            }
        except Exception as e:
            err = classify_ytdlp_error(e)
            print(f"[OmniClip] Unduhan gagal ({err.code}): {err.original[:300]}")
            return {"success": False, "error": err.message, "code": err.code}

def delete_local_download(filename: str) -> dict:
    """Menghapus file unduhan lokal."""
    safe_name = os.path.basename(filename)
    file_path = os.path.join(DOWNLOAD_DIR, safe_name)
    if not os.path.exists(file_path):
        return {"success": False, "error": "File tidak ditemukan"}
    try:
        os.remove(file_path)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_local_downloads():
    """
    Mendaftar semua file yang ada di folder local_downloads/ (kecuali .part)
    """
    files = []
    if not os.path.exists(DOWNLOAD_DIR):
        return files

    for fname in os.listdir(DOWNLOAD_DIR):
        # Lewati unduhan yang belum selesai, dan apa pun yang bukan media —
        # tanpa filter ini `.gitkeep` ikut terdaftar sebagai video.
        ext = os.path.splitext(fname)[1].lower()
        if ext not in MEDIA_EXTS:
            continue
        fpath = os.path.join(DOWNLOAD_DIR, fname)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            is_audio = ext in AUDIO_EXTS
            files.append({
                "file_name": fname,
                "file_path": fpath,
                "file_size": stat.st_size,
                "created_at": stat.st_ctime,
                "type": "audio" if is_audio else "video"
            })
    files.sort(key=lambda x: x['created_at'], reverse=True)
    return files


# Tanggal unggah TIDAK ADA di hasil pencarian datar — bukan salah, memang tidak
# dikirim. Satu-satunya cara mendapatkannya adalah membuka tiap videonya, dan
# itu terlalu lambat untuk dijalankan sebelum daftar hasilnya muncul.
#
# Jadi ia diambil belakangan, bersamaan, dan hasilnya diisikan ke kartu yang
# sudah tampil. Sampai datang, kartunya tidak menuliskan tanggal apa pun —
# lebih baik kosong daripada menampilkan tanggal yang dikarang.
UPLOAD_DATE_WORKERS = 8


def fetch_upload_dates(video_ids: list[str]) -> dict:
    """Mengambil tanggal unggah beberapa video sekaligus."""
    from concurrent.futures import ThreadPoolExecutor

    ids = [v for v in dict.fromkeys(video_ids) if v][:50]
    if not ids:
        return {}

    def one(vid: str):
        opts = _base_opts()
        opts.update({'skip_download': True})
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                # process=False melewati penguraian format, yang merupakan
                # bagian termahal dan tidak dibutuhkan sama sekali di sini.
                info = ydl.extract_info(vid, download=False, process=False)
            return vid, {"upload_date": info.get("upload_date"),
                         "timestamp": info.get("timestamp"),
                         "views": info.get("view_count")}
        except Exception:
            # Satu video yang gagal tidak boleh mengosongkan seluruh baris.
            return vid, None

    out = {}
    with ThreadPoolExecutor(max_workers=UPLOAD_DATE_WORKERS) as ex:
        for vid, data in ex.map(one, ids):
            if data and data.get("upload_date"):
                out[vid] = data
    return out
