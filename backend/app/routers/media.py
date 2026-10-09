"""Penyajian file media. Menggantikan mount StaticFiles('/storage')."""

import logging
import mimetypes
import os
import subprocess
import sys

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import FONTS_DIR
from ..errors import NotFound
from ..services.paths import safe_media_path
from ..services.subtitles import BUNDLED_FONTS, FONT_FILES

router = APIRouter(prefix="/api", tags=["media"])

log = logging.getLogger("omniclip.media")


@router.get("/fonts")
async def list_fonts():
    """
    Font display yang dibundel bersama aplikasi.

    Dipakai frontend untuk memasang @font-face, sehingga pratinjau memakai font
    yang PERSIS sama dengan yang dibakar libass ke dalam video. Tanpa ini,
    mengganti font tidak mengubah apa pun di layar sampai render selesai.
    """
    from ..services import fonts as fonts_svc
    d = fonts_svc.dir_font()
    daftar = [{**f, "url": f"/api/fonts/{f['file']}"}
              for f in BUNDLED_FONTS if (FONTS_DIR / f["file"]).is_file()]
    # Font aksara yang sudah diunduh ikut disajikan, supaya pratinjau memakai
    # berkas yang PERSIS sama dengan yang dipakai libass — bukan font Jepang
    # bawaan sistem, yang bentuknya berbeda dan lebarnya berbeda.
    daftar += [{"file": v[0], "family": v[1], "label": v[1],
                "note": "aksara non-Latin", "url": f"/api/fonts/{v[0]}"}
               for v in fonts_svc.NOTO.values() if (d / v[0]).is_file()]
    return {"fonts": daftar}


@router.get("/fonts/{filename}")
async def get_font(filename: str):
    """Berkas font. Hanya nama yang ada di daftar bundel yang dilayani."""
    from ..services import fonts as fonts_svc
    noto = {v[0] for v in fonts_svc.NOTO.values()}
    if filename not in FONT_FILES and filename not in noto:
        raise NotFound("Font tidak dikenali.")
    path = (fonts_svc.dir_font() if filename in noto else FONTS_DIR) / filename
    if not path.is_file():
        raise NotFound("Berkas font tidak ada.")
    return FileResponse(path=path, media_type="font/ttf",
                        headers={"Cache-Control": "public, max-age=604800"})


@router.get("/media/{category}/{filename}")
async def stream_media(category: str, filename: str):
    """
    Pemutaran inline. Starlette FileResponse menangani HTTP Range, jadi seeking
    pada elemen <video> tetap bekerja tanpa perlu mount statis.
    """
    path = safe_media_path(category, filename)
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(path=path, media_type=media_type or "application/octet-stream")


@router.get("/file/{category}/{filename}")
async def download_file(category: str, filename: str):
    """Unduh paksa (Content-Disposition: attachment)."""
    path = safe_media_path(category, filename)
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


class TunjukRequest(BaseModel):
    kategori: str
    nama: str


@router.post("/berkas/tunjuk")
async def tunjuk_berkas(req: TunjukRequest):
    """
    Membuka pengelola berkas dengan berkas ini SUDAH TERSOROT.

    Bukan sekadar membuka foldernya. Dilaporkan pemiliknya 9 Oktober 2026:
    "saat mengklik klip yang jadi disana hanya ada simpan berkas bukan membuka
    folder dan menunjuk video itu dimana, karena sering saat upload saya harus
    cari foldernya dahulu, jika tidak maka saya mendownload ulang hasil klip".

    Mengunduh ulang berkas yang sudah ada di cakram bukan cuma lambat: ia
    melahirkan salinan kedua dengan nama berbeda, dan dari situlah video
    tertukar saat diunggah. Menyorot berkasnya menghapus seluruh rantai itu.

    Perintah per sistem, dan semuanya memang berbeda:
      Windows  explorer /select,"jalur"
      macOS    open -R jalur
      Linux    FileManager1.ShowItems lewat D-Bus, mundur ke membuka foldernya
    """
    from ..errors import AppError

    path = safe_media_path(req.kategori, req.nama)
    if not path.is_file():
        raise NotFound("Berkas tidak ada lagi di folder itu.")
    jalur = str(path)
    try:
        if sys.platform == "win32":
            # Tanpa daftar argumen: explorer menuntut /select,"jalur" sebagai
            # SATU argumen, dan subprocess yang memecahnya membuat explorer
            # membuka Documents alih-alih menyorot apa pun.
            subprocess.Popen(f'explorer /select,"{jalur}"', close_fds=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", jalur], close_fds=True)
        else:
            tersorot = False
            if subprocess.run(
                    ["dbus-send", "--session", "--print-reply",
                     "--dest=org.freedesktop.FileManager1",
                     "/org/freedesktop/FileManager1",
                     "org.freedesktop.FileManager1.ShowItems",
                     f"array:string:file://{jalur}", "string:"],
                    capture_output=True, timeout=8).returncode == 0:
                tersorot = True
            if not tersorot:
                # Pengelola berkas yang tidak bicara D-Bus tetap dilayani:
                # foldernya dibuka, berkasnya tidak tersorot. Setengah jawaban
                # masih jauh lebih baik daripada mencarinya sendiri.
                subprocess.Popen(["xdg-open", str(path.parent)], close_fds=True)
            return {"status": "ok", "jalur": jalur, "tersorot": tersorot}
    except (OSError, subprocess.SubprocessError) as e:
        raise AppError(f"Tidak bisa membuka pengelola berkas: {e}",
                       code="REVEAL_FAILED", status=500) from e
    return {"status": "ok", "jalur": jalur, "tersorot": True}


@router.post("/berkas/salin")
async def salin_berkas_ke_papan(req: TunjukRequest):
    """
    Menaruh BERKAS videonya di papan klip sistem, bukan jalurnya sebagai teks.

    Dengan ini, kotak unggah TikTok, Facebook, atau Instagram di peramban bisa
    diisi dengan Ctrl+V, tanpa menelusuri folder sama sekali.

    Kenapa harus server yang melakukannya: halaman OmniClip berjalan di dalam
    peramban, dan peramban TIDAK BOLEH menaruh berkas sembarangan di papan klip
    maupun mengisi kotak unggah situs lain. Itu batas keamanan, bukan kekurangan
    yang bisa diakali. Yang bisa melakukannya adalah proses lokal ini.

    Gagal dengan jujur: bila alat papan klipnya tidak ada, pemanggilnya diberi
    tahu supaya ia menawarkan "tunjuk di folder" sebagai gantinya.
    """
    from ..errors import AppError

    path = safe_media_path(req.kategori, req.nama)
    if not path.is_file():
        raise NotFound("Berkas tidak ada lagi di folder itu.")
    jalur = str(path)
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f'Set-Clipboard -LiteralPath "{jalur}"'],
                capture_output=True, timeout=15, check=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        elif sys.platform == "darwin":
            subprocess.run(
                ["osascript", "-e",
                 f'set the clipboard to (POSIX file "{jalur}")'],
                capture_output=True, timeout=15, check=True)
        else:
            alat = None
            for calon in ("wl-copy", "xclip"):
                from shutil import which
                if which(calon):
                    alat = calon
                    break
            if alat is None:
                raise AppError(
                    "Papan klip tidak tersedia di sistem ini. Pasang "
                    "wl-clipboard atau xclip, atau pakai tombol tunjuk di folder.",
                    code="CLIPBOARD_MISSING", status=501)
            isi = f"file://{jalur}\n".encode()
            if alat == "wl-copy":
                subprocess.run(["wl-copy", "--type", "text/uri-list"],
                               input=isi, capture_output=True, timeout=15, check=True)
            else:
                subprocess.run(["xclip", "-selection", "clipboard",
                                "-t", "text/uri-list"],
                               input=isi, capture_output=True, timeout=15, check=True)
    except AppError:
        raise
    except (OSError, subprocess.SubprocessError) as e:
        raise AppError(f"Tidak bisa menyalin berkas ke papan klip: {e}",
                       code="CLIPBOARD_FAILED", status=500) from e
    return {"status": "ok", "jalur": jalur}
