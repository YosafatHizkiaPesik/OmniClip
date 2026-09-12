"""
Peluncur aplikasi OmniClip.

Inilah titik masuk saat OmniClip dijalankan sebagai aplikasi terbungkus — satu
berkas yang diklik, bukan dua terminal. Ia menyalakan server di dalam dirinya
sendiri, lalu membuka peramban ke alamat lokalnya.

Bentuk ini dipilih karena antarmuka OmniClip adalah halaman web yang sudah
matang; membungkusnya lagi dengan kerangka desktop hanya akan menambah puluhan
megabita dan satu lapis yang bisa rusak sendiri. Peramban yang sudah ada di
komputer pengguna mengerjakannya lebih baik.

Jendela konsol sengaja dibiarkan terlihat. Render bisa berjalan bermenit-menit,
dan aplikasi yang tidak menunjukkan apa pun selama itu terlihat seperti
aplikasi yang menggantung.
"""

import logging
import os
import socket
import sys
import threading
import time
import webbrowser

PORT_AWAL = 8000
PORT_DICOBA = 20


def _port_kosong(mulai: int, banyak: int) -> int:
    """
    Port pertama yang benar-benar bisa diikat.

    Bukan kemewahan: 8000 adalah port yang sangat ramai, dan aplikasi yang mati
    dengan "Address already in use" tidak memberi tahu penggunanya apa yang
    harus dilakukan.
    """
    for port in range(mulai, mulai + banyak):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit(
        f"Tidak ada port kosong antara {mulai} dan {mulai + banyak - 1}. "
        "Tutup aplikasi lain yang memakainya, lalu coba lagi."
    )


def _buka_peramban(url: str, siap: threading.Event) -> None:
    """Menunggu server benar-benar menjawab sebelum membuka peramban."""
    if siap.wait(timeout=90):
        time.sleep(0.4)
        try:
            webbrowser.open(url)
        except Exception:
            pass  # tanpa peramban pun alamatnya sudah tercetak di layar


# --- Pemeriksaan mandiri -------------------------------------------------------
#
# Sebuah bundel bisa terbangun mulus dan tetap kehilangan sesuatu: satu pustaka
# biner yang dimuat lewat nama saat berjalan, satu berkas font, satu model.
# Kehilangan seperti itu tidak muncul saat membangun — ia muncul di mesin
# pengguna, berminggu-minggu kemudian, sebagai satu fitur yang diam-diam tidak
# bekerja.
#
# Karena itu bundel memeriksa dirinya sendiri, dan pemeriksaannya dijalankan di
# SISTEM YANG SAMA dengan yang akan memakainya. Build Windows diperiksa di
# Windows; tidak ada yang ditebak dari mesin pengembang.

MODUL_WAJIB = [
    ("fastapi", "kerangka web"),
    ("uvicorn", "server"),
    ("pydantic", "validasi permintaan"),
    ("numpy", "hitungan bingkai dan audio"),
    ("yt_dlp", "pencarian dan unduhan YouTube"),
    ("faster_whisper", "transkripsi lokal"),
    ("ctranslate2", "mesin di balik faster-whisper"),
    ("av", "pembaca audio/video faster-whisper"),
    ("cv2", "deteksi wajah"),
    ("onnxruntime", "pengenal wajah dan suara"),
    ("piper", "pembacaan judul"),
    ("edge_tts", "pembacaan judul lewat jaringan"),
    ("googleapiclient.discovery", "unggah ke YouTube dan Drive"),
    ("google_auth_oauthlib.flow", "izin akun Google"),
    ("google.genai", "penajaman klip oleh Gemini"),
    ("cryptography.hazmat.primitives.asymmetric.rsa", "identitas Cloudflare Access"),
]

FILTER_WAJIB = ("ass", "sendcmd", "crop", "loudnorm", "scdet",
                "silencedetect", "astats")
ENCODER_WAJIB = ("libx264", "aac")


def periksa() -> int:
    """Memeriksa setiap bagian yang bisa hilang dari bundel. 0 = lengkap."""
    import importlib
    import shutil
    import subprocess
    from pathlib import Path

    gagal: list[str] = []

    def lapor(nama: str, ok: bool, ket: str = "") -> None:
        print(f"  {'OK   ' if ok else 'KURANG'} {nama:<46} {ket}")
        if not ok:
            gagal.append(nama)

    print("=" * 74)
    print(f"  Pemeriksaan OmniClip — {sys.platform}, Python {sys.version.split()[0]}")
    print("=" * 74)

    print("\n  Pustaka")
    for modul, guna in MODUL_WAJIB:
        try:
            importlib.import_module(modul)
            lapor(modul, True, guna)
        except Exception as e:
            lapor(modul, False, f"{guna} — {type(e).__name__}: {e}")

    print("\n  Berkas yang dibundel")
    from app.config import (
        FONTS_DIR, FRONTEND_DIST, MODELS_DIR, STORAGE_DIR, use_bundled_ffmpeg,
    )
    lapor("antarmuka (frontend_dist/index.html)",
          (FRONTEND_DIST / "index.html").is_file(), str(FRONTEND_DIST))
    font = sorted(FONTS_DIR.glob("*.ttf")) if FONTS_DIR.is_dir() else []
    lapor("font subtitle", len(font) > 0, f"{len(font)} berkas di {FONTS_DIR}")
    yunet = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
    lapor("model wajah YuNet", yunet.is_file(), str(yunet))

    print("\n  ffmpeg")
    folder = use_bundled_ffmpeg()
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    lapor("ffmpeg ditemukan", bool(ffmpeg),
          f"{'bundelan' if folder else 'dari sistem'}: {ffmpeg}")
    lapor("ffprobe ditemukan", bool(ffprobe), str(ffprobe))
    if ffmpeg:
        def punya(argumen: str, nama: str) -> bool:
            out = subprocess.run([ffmpeg, "-hide_banner", argumen],
                                 capture_output=True, text=True).stdout
            return any(b.split()[1:2] == [nama]
                       for b in out.splitlines() if len(b.split()) > 1)
        for f in FILTER_WAJIB:
            lapor(f"filter {f}", punya("-filters", f))
        for e in ENCODER_WAJIB:
            lapor(f"encoder {e}", punya("-encoders", e))

    print("\n  Bagian yang bergerak")
    try:
        import cv2
        d = cv2.FaceDetectorYN.create(str(yunet), "", (320, 320))
        lapor("detektor wajah bisa dibuat", d is not None)
    except Exception as e:
        lapor("detektor wajah bisa dibuat", False, f"{type(e).__name__}: {e}")
    try:
        import onnxruntime
        lapor("onnxruntime punya penyedia", True,
              ", ".join(onnxruntime.get_available_providers()))
    except Exception as e:
        lapor("onnxruntime punya penyedia", False, str(e))
    # Subtitle sungguhan, lewat ffmpeg sungguhan, dengan path sungguhan.
    #
    # Di Windows FONTS_DIR dimulai dengan "C:\", dan parser filtergraph ffmpeg
    # memperlakukan titik dua sebagai pemisah opsi. Salah menyiapkannya bukan
    # menghasilkan font yang keliru melainkan render yang GAGAL — dan gagalnya
    # hanya di Windows, di mesin pengguna. Karena itu diuji di sini, di sistem
    # yang sama dengan yang akan memakainya.
    if ffmpeg:
        import tempfile
        from app.services.paths import ffpath
        try:
            with tempfile.TemporaryDirectory(prefix="omniclip_periksa_") as d:
                ass = Path(d) / "uji.ass"
                ass.write_text(
                    "[Script Info]\nScriptType: v4.00+\nPlayResX: 640\nPlayResY: 360\n"
                    "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, "
                    "OutlineColour, BorderStyle, Outline, Alignment, MarginV, Encoding\n"
                    "Style: C,Anton,60,&H00FFFFFF,&H00000000,1,4,2,40,1\n"
                    "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, "
                    "MarginR, MarginV, Effect, Text\n"
                    "Dialogue: 0,0:00:00.00,0:00:02.00,C,,0,0,0,,UJI\n",
                    encoding="utf-8")
                keluar = Path(d) / "uji.png"
                vf = (f"ass=filename='{ffpath(ass)}'"
                      f":fontsdir='{ffpath(FONTS_DIR)}'")
                r = subprocess.run(
                    [ffmpeg, "-v", "error", "-f", "lavfi",
                     "-i", "color=black:s=640x360:d=1", "-vf", vf,
                     "-frames:v", "1", "-y", str(keluar)],
                    capture_output=True, text=True)
                jadi = keluar.is_file() and keluar.stat().st_size > 500
                lapor("subtitle terbakar (path + font bundelan)", jadi,
                      (r.stderr or "").strip()[:90] if not jadi else
                      f"{keluar.stat().st_size} bita")
        except Exception as e:
            lapor("subtitle terbakar (path + font bundelan)", False,
                  f"{type(e).__name__}: {e}")

    try:
        from app.db import run_migrations
        run_migrations()
        lapor("basis data & migrasi", True, str(STORAGE_DIR))
    except Exception as e:
        lapor("basis data & migrasi", False, f"{type(e).__name__}: {e}")
    try:
        from app.main import app as _app
        lapor("aplikasi FastAPI terbentuk", True,
              f"{len(_app.routes)} rute terdaftar")
    except Exception as e:
        lapor("aplikasi FastAPI terbentuk", False, f"{type(e).__name__}: {e}")

    print("\n" + "=" * 74)
    if gagal:
        print(f"  TIDAK LENGKAP — {len(gagal)} bagian hilang:")
        for g in gagal:
            print(f"    - {g}")
        print("  Bundel ini jangan dibagikan.")
        return 1
    print("  Lengkap. Semua bagian ada dan bisa dipakai.")
    return 0


def main() -> int:
    # Impor ditunda sampai di sini supaya pesan galat konfigurasi muncul setelah
    # sambutan di bawah, bukan sebagai tumpukan traceback sebelum apa pun.
    from app.config import STORAGE_DIR, use_bundled_ffmpeg

    host = os.getenv("OMNICLIP_HOST", "127.0.0.1").strip()
    port = int(os.getenv("OMNICLIP_PORT", "0")) or _port_kosong(PORT_AWAL, PORT_DICOBA)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}"

    bundled = use_bundled_ffmpeg()

    print("=" * 62)
    print("  OmniClip")
    print("=" * 62)
    print(f"  Alamat       : {url}")
    print(f"  Penyimpanan  : {STORAGE_DIR}")
    print(f"  ffmpeg       : {'bundelan' if bundled else 'dari sistem'}")
    if host not in ("127.0.0.1", "::1", "localhost"):
        print(f"  Terbuka di jaringan ({host}) — pastikan kata sandi sudah dipasang.")
    print()
    print("  Tutup jendela ini untuk mematikan OmniClip.")
    print("  Saat pertama dipakai, beberapa model akan diunduh (± 150 MB).")
    print("=" * 62, flush=True)

    siap = threading.Event()
    threading.Thread(target=_buka_peramban, args=(url, siap), daemon=True).start()

    import uvicorn
    from app.main import app

    config = uvicorn.Config(app, host=host, port=port, log_level="info",
                            proxy_headers=True, forwarded_allow_ips="127.0.0.1")
    server = uvicorn.Server(config)

    # Menandai "siap" hanya setelah uvicorn benar-benar menerima sambungan.
    # Membuka peramban lebih awal memberi halaman galat, dan pengguna yang
    # melihat halaman galat akan menutup aplikasinya.
    def _pantau() -> None:
        while not server.started:
            if getattr(server, "should_exit", False):
                return
            time.sleep(0.15)
        siap.set()

    threading.Thread(target=_pantau, daemon=True).start()

    try:
        server.run()
    except KeyboardInterrupt:
        pass
    print("\nOmniClip berhenti.")
    return 0


if __name__ == "__main__":
    if "--periksa" in sys.argv:
        raise SystemExit(periksa())

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    raise SystemExit(main())
