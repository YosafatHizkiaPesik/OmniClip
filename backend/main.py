import os
import uvicorn

# Auto-load .env file jika ada (untuk GEMINI_API_KEY dll)
_env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_file):
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                key = key.strip()
                val = val.strip()
                if key and val and key not in os.environ:
                    os.environ[key] = val
    print(f"[OmniClip] Loaded config from .env — GEMINI_API_KEY: {'SET ✓' if os.environ.get('GEMINI_API_KEY') else 'NOT SET'}")

from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from downloader import search_youtube_videos, get_video_info, download_youtube_media, list_local_downloads, delete_local_download
from analyzer import analyze_video_for_clips
from clipper import render_clip_with_ffmpeg, list_local_clips
from drive_manager import (
    list_connected_accounts,
    set_active_account,
    add_new_account,
    upload_clip_to_google_drive,
    get_drive_uploads
)

STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "OmniClip_Storage"))

app = FastAPI(
    title="OmniClip AI Backend Engine",
    version="3.0",
    description="Backend API untuk In-App YouTube Search/Download, AI Clipping Gemini, FFmpeg Renderer & Multi-Account Google Drive Manager"
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount OmniClip_Storage for direct video/audio playback
app.mount("/storage", StaticFiles(directory=STORAGE_DIR), name="storage")

# Pydantic Schemas
class DownloadRequest(BaseModel):
    url: str
    resolution: str = "720p"

class AnalyzeRequest(BaseModel):
    video_info: Dict[str, Any]
    api_key: Optional[str] = None

class RenderClipRequest(BaseModel):
    source_path: str
    start_seconds: float
    end_seconds: float
    subtitles: Optional[List[Dict[str, Any]]] = None
    aspect_ratio: str = "9:16"
    font_color: str = "yellow"
    font_size: int = 24
    position: str = "bottom"
    hook_text: str = ""

class SwitchAccountRequest(BaseModel):
    account_id: str

class AddAccountRequest(BaseModel):
    name: str
    email: str

class DriveUploadRequest(BaseModel):
    file_path: str
    account_id: Optional[str] = None

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "OmniClip AI Engine v3.0"}

# --- SETTINGS / API KEY ---
_runtime_api_key = {"key": ""}

class ApiKeyRequest(BaseModel):
    api_key: str

@app.post("/api/settings/api-key")
def set_api_key(req: ApiKeyRequest):
    _runtime_api_key["key"] = req.api_key.strip()
    os.environ["GEMINI_API_KEY"] = req.api_key.strip()
    return {"message": "API Key Gemini berhasil disimpan untuk sesi ini", "status": "ok"}

@app.get("/api/settings")
def get_settings():
    key = os.environ.get("GEMINI_API_KEY", "")
    return {
        "gemini_api_key_set": bool(key),
        "gemini_api_key_preview": f"{key[:8]}..." if len(key) > 8 else ("TIDAK DIKONFIGURASI" if not key else key)
    }

# --- SEARCH & DOWNLOAD ENDPOINTS ---
@app.get("/api/search")
def search_videos(q: str = Query(..., description="Kata kunci pencarian YouTube"), limit: int = 20):
    if not q.strip():
        return []
    return search_youtube_videos(q, limit)

@app.get("/api/trending")
def get_trending(limit: int = 20):
    """Ambil video trending / rekomendasi untuk homepage YouTube-style"""
    return search_youtube_videos("trending viral indonesia 2024", limit)

@app.get("/api/video-info")
def video_info(url: str = Query(...)):
    return get_video_info(url)

@app.post("/api/download")
def download_media(req: DownloadRequest):
    result = download_youtube_media(req.url, req.resolution)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Pengunduhan gagal"))
    # Return URL for web playback
    file_name = result["file_name"]
    result["web_url"] = f"/storage/local_downloads/{file_name}"
    return result

@app.get("/api/downloads")
def get_downloads():
    files = list_local_downloads()
    for f in files:
        f["web_url"] = f"/storage/local_downloads/{f['file_name']}"
    return files

@app.delete("/api/downloads/{filename}")
def delete_download(filename: str):
    result = delete_local_download(filename)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Gagal menghapus file"))
    return result

# --- GEMINI AI AUTO-CLIP ENDPOINTS ---
@app.post("/api/analyze-clips")
def analyze_clips(req: AnalyzeRequest):
    return analyze_video_for_clips(req.video_info, req.api_key)

# --- FFMPEG CLIPPER ENDPOINTS ---
@app.post("/api/render-clip")
def render_clip(req: RenderClipRequest):
    res = render_clip_with_ffmpeg(
        source_video_path=req.source_path,
        start_seconds=req.start_seconds,
        end_seconds=req.end_seconds,
        subtitles=req.subtitles,
        aspect_ratio=req.aspect_ratio,
        font_color=req.font_color,
        font_size=req.font_size,
        position=req.position,
        hook_text=req.hook_text
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Rendering klip gagal"))
    res["web_url"] = f"/storage/edited_clips/{res['clip_name']}"
    return res

@app.get("/api/clips")
def get_clips():
    clips = list_local_clips()
    for c in clips:
        c["web_url"] = f"/storage/edited_clips/{c['file_name']}"
    
    drive_uploads = get_drive_uploads()
    return {
        "local_clips": clips,
        "drive_clips": drive_uploads
    }

# --- MULTI-ACCOUNT GOOGLE DRIVE ENDPOINTS ---
@app.get("/api/accounts")
def get_accounts():
    return list_connected_accounts()

@app.post("/api/accounts/switch")
def switch_account(req: SwitchAccountRequest):
    ok = set_active_account(req.account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    return {"message": "Berhasil berganti akun aktif", "accounts": list_connected_accounts()}

@app.post("/api/accounts/add")
def add_account(req: AddAccountRequest):
    new_acc = add_new_account(req.name, req.email)
    return {"message": "Berhasil menambahkan akun Google baru", "account": new_acc, "accounts": list_connected_accounts()}

@app.post("/api/drive/upload")
def upload_drive(req: DriveUploadRequest):
    res = upload_clip_to_google_drive(req.file_path, req.account_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Gagal mengunggah ke Drive"))
    return res

# --- FILE DOWNLOAD PROXY (hindari CORS error pada browser) ---
@app.get("/api/file/{category}/{filename}")
def download_file_proxy(category: str, filename: str):
    """
    Endpoint proxy download file lokal untuk menghindari CORS error.
    category: 'local_downloads' atau 'edited_clips'
    """
    allowed_categories = ["local_downloads", "edited_clips"]
    if category not in allowed_categories:
        raise HTTPException(status_code=400, detail="Kategori tidak valid")
    
    safe_filename = os.path.basename(filename)  # Cegah path traversal
    file_path = os.path.join(STORAGE_DIR, category, safe_filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File '{safe_filename}' tidak ditemukan")
    
    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'}
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
