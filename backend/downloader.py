import os
import json
import yt_dlp

STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "OmniClip_Storage"))
DOWNLOAD_DIR = os.path.join(STORAGE_DIR, "local_downloads")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def search_youtube_videos(query: str, limit: int = 20):
    """
    Melakukan pencarian video YouTube menggunakan yt-dlp tanpa YouTube API Key.
    """
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
    }

    results = []
    search_target = f"ytsearch{limit}:{query}" if not (query.startswith("http://") or query.startswith("https://")) else query

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
            print(f"Error during YouTube search: {e}")

    return results

def get_video_info(url_or_id: str):
    """
    Mendapatkan detail metadata video YouTube.
    """
    url = url_or_id if url_or_id.startswith("http") else f"https://www.youtube.com/watch?v={url_or_id}"
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
                "available_resolutions": ["360p", "480p", "720p", "1080p", "Audio MP3"]
            }
        except Exception as e:
            return {"error": str(e)}

def download_youtube_media(url_or_id: str, resolution: str = "720p"):
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
        out_ext = ".mp3"
    else:
        res_height = resolution.replace("p", "")
        # Prefer single-file format to avoid merging issues
        fmt = f"best[height<={res_height}][ext=mp4]/best[height<={res_height}]/best[ext=mp4]/best"
        postprocessors = []
        out_ext = ".mp4"

    # Sanitize output template (use safe ASCII title)
    out_template = os.path.join(DOWNLOAD_DIR, '%(title).60s_%(id)s.%(ext)s')

    ydl_opts = {
        'format': fmt,
        'outtmpl': out_template,
        'postprocessors': postprocessors if postprocessors else None,
        'quiet': False,
        'no_warnings': True,
        'nopart': True,           # Tidak buat .part file — langsung tulis ke file final
        'continuedl': False,      # Jangan lanjutkan download yang incomplete
        'retries': 3,
        'fragment_retries': 3,
        'socket_timeout': 30,
        'merge_output_format': 'mp4',
        'restrictfilenames': True, # Hindari karakter spesial di nama file
    }

    if postprocessors:
        ydl_opts['postprocessors'] = postprocessors
    else:
        del ydl_opts['postprocessors']

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

            return {
                "success": True,
                "file_path": filename,
                "file_name": os.path.basename(filename),
                "title": info.get('title'),
                "duration": info.get('duration'),
                "resolution": resolution,
                "file_size": os.path.getsize(filename) if os.path.exists(filename) else 0
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

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
        # Skip incomplete .part files
        if fname.endswith('.part'):
            continue
        fpath = os.path.join(DOWNLOAD_DIR, fname)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            is_audio = fname.endswith(".mp3") or fname.endswith(".m4a")
            files.append({
                "file_name": fname,
                "file_path": fpath,
                "file_size": stat.st_size,
                "created_at": stat.st_ctime,
                "type": "audio" if is_audio else "video"
            })
    files.sort(key=lambda x: x['created_at'], reverse=True)
    return files
