import os
import glob
import re
import tempfile
import yt_dlp
from typing import List, Dict, Any

def get_youtube_transcript(url_or_id: str) -> List[Dict[str, Any]]:
    """
    Mengambil transkrip/caption asli yang diucapkan di video YouTube menggunakan yt-dlp.
    Mendukung Bahasa Indonesia ('id') dan Bahasa Inggris ('en').
    """
    if not url_or_id:
        return []

    # Extract clean 11-char YT ID
    yt_id = url_or_id
    match = re.search(r'(?:v=|\/embed\/|\/v\/|https:\/\/youtu\.be\/|\/shorts\/)([a-zA-Z0-9_-]{11})', url_or_id)
    if match:
        yt_id = match.group(1)

    temp_dir = tempfile.gettempdir()
    out_prefix = os.path.join(temp_dir, f"omni_sub_{yt_id}")

    # Clean old sub files for this ID
    for old_file in glob.glob(f"{out_prefix}*"):
        try:
            os.remove(old_file)
        except Exception:
            pass

    ydl_opts = {
        'skip_download': True,
        'writeautosub': True,
        'writesubtitles': True,
        'subtitleslangs': ['id', 'id-ID', 'en', 'en-US'],
        'subtitlesformat': 'vtt/srv1/json3',
        'outtmpl': f"{out_prefix}.%(ext)s",
        'quiet': True,
        'no_warnings': True
    }

    url = f"https://www.youtube.com/watch?v={yt_id}" if len(yt_id) == 11 else url_or_id

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as e:
        print(f"[Transcript] yt-dlp warning/error: {e}")

    sub_files = glob.glob(f"{out_prefix}*")
    print(f"[Transcript] Found subtitle files: {sub_files}")

    lines = []
    if sub_files:
        # Sort so 'id' (Indonesian) or 'en' is prioritized
        target_file = sub_files[0]
        for f in sub_files:
            if '.id' in f:
                target_file = f
                break

        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = _parse_vtt_subtitles(content)
        except Exception as err:
            print(f"[Transcript] File read error: {err}")

        # Clean up temp sub files
        for f in sub_files:
            try:
                os.remove(f)
            except Exception:
                pass

    print(f"[Transcript ✓] Extracted {len(lines)} spoken lines for '{yt_id}'")
    return lines

def _parse_vtt_subtitles(content: str) -> List[Dict[str, Any]]:
    """
    Parser ringkas VTT subtitle file menjadi list {"start": float, "end": float, "text": str}
    """
    lines = []
    blocks = content.split('\n\n')
    seen_texts = set()

    for b in blocks:
        time_match = re.search(r'(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})', b)
        if time_match:
            start_str = time_match.group(1)
            end_str = time_match.group(2)

            start_sec = _parse_timestamp(start_str)
            end_sec = _parse_timestamp(end_str)

            # Get text (last non-empty line without tags)
            raw_lines = [l.strip() for l in b.split('\n') if l.strip()]
            text_lines = [l for l in raw_lines if not '-->' in l and not l.startswith('WEBVTT') and not l.startswith('Kind:') and not l.startswith('Language:')]

            if text_lines:
                raw_text = " ".join(text_lines)
                clean_text = re.sub(r'<[^>]+>', '', raw_text).strip()
                clean_text = re.sub(r'&gt;', '>', clean_text)
                clean_text = re.sub(r'&lt;', '<', clean_text)
                clean_text = re.sub(r'&amp;', '&', clean_text)

                if clean_text and clean_text not in seen_texts:
                    seen_texts.add(clean_text)
                    lines.append({
                        "start": round(start_sec, 1),
                        "end": round(end_sec, 1),
                        "text": clean_text
                    })

    return lines

def _parse_timestamp(ts: str) -> float:
    parts = ts.split(':')
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    return 0.0
