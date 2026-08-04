import os
import re
import subprocess
import tempfile
import json
from typing import List, Dict, Any, Optional

STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "OmniClip_Storage"))
CLIPS_DIR = os.path.join(STORAGE_DIR, "edited_clips")
DOWNLOAD_DIR = os.path.join(STORAGE_DIR, "local_downloads")

os.makedirs(CLIPS_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def extract_youtube_id(url_or_id: str) -> str:
    """Ekstraksi YouTube Video ID 11 karakter dari URL atau ID"""
    if not url_or_id:
        return ""
    if len(url_or_id) == 11 and "/" not in url_or_id and "." not in url_or_id:
        return url_or_id
    match = re.search(r'(?:v=|\/embed\/|\/v\/|https:\/\/youtu\.be\/|\/shorts\/)([a-zA-Z0-9_-]{11})', url_or_id)
    return match.group(1) if match else url_or_id

def seconds_to_srt_time(seconds: float) -> str:
    """Mengubah detik (float) ke format SRT timestamp (HH:MM:SS,mmm)"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def create_srt_file(subtitles: List[Dict[str, Any]], offset_seconds: float = 0.0) -> str:
    """
    Membuat file SRT sementara dari list subtitle.
    """
    temp_srt = tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w", encoding="utf-8")
    for idx, sub in enumerate(subtitles, 1):
        start = max(0.0, float(sub.get("start", 0.0)) - offset_seconds)
        end = max(start + 0.5, float(sub.get("end", start + 2.0)) - offset_seconds)
        text = sub.get("text", "").strip()

        temp_srt.write(f"{idx}\n")
        temp_srt.write(f"{seconds_to_srt_time(start)} --> {seconds_to_srt_time(end)}\n")
        temp_srt.write(f"{text}\n\n")

    temp_srt.close()
    return temp_srt.name

def render_clip_with_ffmpeg(
    source_video_path: str,
    start_seconds: float,
    end_seconds: float,
    subtitles: Optional[List[Dict[str, Any]]] = None,
    aspect_ratio: str = "9:16",
    font_color: str = "yellow",
    font_size: int = 24,
    position: str = "bottom",
    hook_text: str = "",
    clip_name_prefix: str = "clip"
) -> Dict[str, Any]:
    """
    Memotong video dan merender klip vertikal 9:16 atau 16:9 / 1:1 / 4:5 dengan subtitle burned-in & hook overlay.
    """
    # Check if source_video_path is URL or non-existent file
    if not os.path.exists(source_video_path) or source_video_path.startswith("http"):
        print(f"[FFmpeg Clipper] Source video '{source_video_path}' not found locally. Resolving...")
        from downloader import download_youtube_media

        yt_id = extract_youtube_id(source_video_path)
        existing_file = None
        if os.path.exists(DOWNLOAD_DIR):
            for fname in os.listdir(DOWNLOAD_DIR):
                if yt_id and yt_id in fname and (fname.endswith(".mp4") or fname.endswith(".mkv") or fname.endswith(".webm")):
                    existing_file = os.path.join(DOWNLOAD_DIR, fname)
                    break

        if existing_file and os.path.exists(existing_file):
            source_video_path = existing_file
            print(f"[FFmpeg Clipper] Found existing local video: {source_video_path}")
        else:
            print(f"[FFmpeg Clipper] Downloading video from YouTube ({source_video_path})...")
            dl_res = download_youtube_media(source_video_path, resolution="720p")
            if dl_res.get("success") and os.path.exists(dl_res["file_path"]):
                source_video_path = dl_res["file_path"]
                print(f"[FFmpeg Clipper] Successfully downloaded source: {source_video_path}")
            else:
                return {"success": False, "error": f"Gagal mengunduh video sumber dari YouTube: {dl_res.get('error')}"}

    duration = max(1.0, end_seconds - start_seconds)
    output_filename = f"{clip_name_prefix}_{int(start_seconds)}_{int(end_seconds)}.mp4"
    output_path = os.path.join(CLIPS_DIR, output_filename)

    srt_path = None
    if subtitles:
        srt_path = create_srt_file(subtitles, offset_seconds=start_seconds)

    # Build FFmpeg Video Filters (-vf)
    vf_parts = []

    # 1. Aspect Ratio Filters
    if aspect_ratio == "9:16":
        # CapCut Style: Blur background padding + Center scaled video foreground
        vf_parts.append(
            "split[v1][v2];"
            "[v1]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
            "[v2]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
    elif aspect_ratio == "1:1":
        vf_parts.append("crop=ih:ih,scale=1080:1080")
    elif aspect_ratio == "4:5":
        vf_parts.append("crop=w=ih*4/5:h=ih,scale=1080:1350")

    # 2. Subtitle Overlay Filter
    if srt_path:
        # Determine PrimaryColour (ASS BGR format)
        if font_color in ["yellow", "kuning"]:
            color_code = "&H00FFFF&" # Yellow
            border_style = "1"
        elif font_color in ["cyan", "syan"]:
            color_code = "&HFFFF00&" # Cyan
            border_style = "1"
        elif font_color in ["black_box", "box"]:
            color_code = "&H00FFFFFF&" # White text inside dark box
            border_style = "3"
        else:
            color_code = "&H00FFFFFF&" # White default
            border_style = "1"

        # Determine Alignment & Margin
        if position == "top":
            align_code = "6"
            margin_v = "140"
        elif position == "middle":
            align_code = "10"
            margin_v = "0"
        else:
            align_code = "2" # Bottom center
            margin_v = "120"

        escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")
        sub_filter = f"subtitles='{escaped_srt}':force_style='FontSize={font_size},PrimaryColour={color_code},OutlineColour=&H000000&,BorderStyle={border_style},Outline=2,Alignment={align_code},MarginV={margin_v}'"
        vf_parts.append(sub_filter)

    vf_str = ", ".join(vf_parts) if vf_parts else ""

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_seconds),
        "-i", source_video_path,
        "-t", str(duration),
    ]

    if vf_str:
        cmd.extend(["-vf", vf_str])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ])

    print(f"[FFmpeg Command] {' '.join(cmd)}")

    try:
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if srt_path and os.path.exists(srt_path):
            os.remove(srt_path)

        if process.returncode != 0:
            print(f"FFmpeg Error: {process.stderr}")
            return {"success": False, "error": process.stderr}

        meta_filename = output_filename.replace(".mp4", ".json")
        meta_path = os.path.join(CLIPS_DIR, meta_filename)
        clip_meta = {
            "file_name": output_filename,
            "file_path": output_path,
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "subtitles": subtitles or [],
            "hook_text": hook_text,
            "created_at": os.path.getctime(output_path) if os.path.exists(output_path) else 0
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(clip_meta, f, indent=2)

        return {
            "success": True,
            "clip_path": output_path,
            "clip_name": output_filename,
            "metadata_path": meta_path,
            "duration": duration
        }
    except Exception as e:
        if srt_path and os.path.exists(srt_path):
            os.remove(srt_path)
        return {"success": False, "error": str(e)}

def list_local_clips():
    """
    Mendaftar semua file klip (.mp4) yang tersimpan di OmniClip_Storage/edited_clips/
    """
    clips = []
    if not os.path.exists(CLIPS_DIR):
        return clips

    for fname in os.listdir(CLIPS_DIR):
        if fname.endswith(".mp4"):
            fpath = os.path.join(CLIPS_DIR, fname)
            meta_path = os.path.join(CLIPS_DIR, fname.replace(".mp4", ".json"))
            meta = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    pass
            stat = os.stat(fpath)
            clips.append({
                "file_name": fname,
                "file_path": fpath,
                "file_size": stat.st_size,
                "created_at": stat.st_ctime,
                "metadata": meta
            })
    clips.sort(key=lambda x: x['created_at'], reverse=True)
    return clips
