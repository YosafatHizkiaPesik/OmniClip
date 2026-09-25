"""Konfigurasi terpusat: path, batas sumber daya, dan pengaturan dari .env."""

import os
from typing import Optional
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
def _bisa_ditulis(d: Path) -> bool:
    """Apakah direktori ini benar-benar bisa ditulis? Dicoba, bukan ditebak."""
    try:
        d.mkdir(parents=True, exist_ok=True)
        uji = d / f".omniclip-uji-{os.getpid()}"
        uji.touch()
        uji.unlink()
        return True
    except OSError:
        return False


def _berkas_penunjuk() -> Path:
    """
    Tempat lokasi penyimpanan pilihan pengguna dicatat.

    Ia HARUS di luar penyimpanan itu sendiri — berkas yang menyebutkan di mana
    penyimpanan berada tidak bisa ikut tinggal di dalamnya. Folder data sistem
    adalah satu-satunya tempat yang selalu ada dan tidak ikut ditukar saat
    aplikasi diperbarui.
    """
    return _user_data_dir() / "lokasi-penyimpanan.txt"


def _storage_terpilih() -> Path:
    """
    Di mana klip, unduhan, dan basis data tinggal.

    Urutannya dipilih supaya tidak ada pengguna lama yang datanya tiba-tiba
    hilang dari pandangan:

    1. `OMNICLIP_STORAGE` — paksaan penuh, untuk pengujian dan pemasangan khusus.
    2. Berkas penunjuk — pilihan pengguna lewat Pengaturan.
    3. Penyimpanan lama yang SUDAH BERISI basis data — dipertahankan apa adanya.
       Tanpa aturan ini, mengubah bawaan akan membuat pengguna yang memperbarui
       aplikasinya membuka folder kosong dan mengira seluruh kerjanya lenyap.
    4. `OmniClip-Data` di sebelah folder aplikasi — bawaan untuk pemasangan baru.
       Di SEBELAH, bukan di dalam: folder aplikasi ditukar seluruhnya setiap kali
       aplikasi memperbarui dirinya, jadi apa pun di dalamnya akan ikut hilang.
    5. Folder data sistem, bila induk aplikasi ternyata tidak bisa ditulis
       (misalnya dipasang di Program Files).
    """
    env = os.getenv("OMNICLIP_STORAGE", "").strip()
    if env:
        return Path(env).expanduser().resolve()

    if not FROZEN:
        return PROJECT_DIR / "OmniClip_Storage"

    try:
        penunjuk = _berkas_penunjuk()
        if penunjuk.is_file():
            pilihan = Path(penunjuk.read_text(encoding="utf-8").strip()).expanduser()
            if str(pilihan) and _bisa_ditulis(pilihan):
                return pilihan.resolve()
    except OSError:
        pass

    lama = _user_data_dir()
    if (lama / "omniclip.db").is_file():
        return lama

    sebelah = Path(sys.executable).resolve().parent.parent / "OmniClip-Data"
    return sebelah.resolve() if _bisa_ditulis(sebelah) else lama


def _pindahkan_bila_diminta(tujuan: Path) -> None:
    """
    Memindahkan isi penyimpanan lama ke lokasi baru, sekali, saat startup.

    Dikerjakan DI SINI dan bukan lewat permintaan HTTP karena basis datanya
    ikut pindah: memindahkan berkas SQLite yang sedang terbuka adalah cara
    yang rapi untuk merusaknya. Pada titik ini belum ada satu pun koneksi yang
    dibuka — `db.py` mengimpor modul ini, bukan sebaliknya.

    Berkas dipindahkan satu per satu dan yang sudah ada di tujuan dilewati,
    jadi pemindahan yang terputus di tengah bisa dilanjutkan dengan menjalankan
    aplikasinya lagi. Yang asal tidak pernah dihapus selain per-berkas yang
    sudah berhasil pindah.
    """
    penanda = _user_data_dir() / "pindah-dari.txt"
    if not penanda.is_file():
        return
    try:
        asal = Path(penanda.read_text(encoding="utf-8").strip())
        if asal.resolve() != tujuan.resolve() and asal.is_dir():
            tujuan.mkdir(parents=True, exist_ok=True)
            for item in asal.rglob("*"):
                if item.is_dir():
                    continue
                rel = item.relative_to(asal)
                akhir = tujuan / rel
                if akhir.exists():
                    continue
                akhir.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(item), str(akhir))
    except (OSError, ValueError):
        # Pemindahan yang gagal tidak boleh menghalangi aplikasi menyala; yang
        # belum pindah tetap ada di tempat lama dan penandanya dibiarkan supaya
        # percobaan berikutnya melanjutkannya.
        return
    try:
        penanda.unlink()
    except OSError:
        pass


STORAGE_DIR = _storage_terpilih()
_pindahkan_bila_diminta(STORAGE_DIR)

# .env dibaca dari penyimpanan pengguna saat terbungkus — folder aplikasi bukan
# tempat yang bisa ditulis, dan isinya hilang saat aplikasi diperbarui.
load_dotenv(STORAGE_DIR / ".env" if FROZEN else BACKEND_DIR / ".env")
def _folder_pilihan(nama: str, bawaan: Path) -> Path:
    """
    Folder yang dipilih pengguna untuk satu jenis berkas, atau bawaannya.

    Dibaca SEKALI saat startup dan disimpan sebagai konstanta, bukan dibaca
    ulang tiap pemakaian. Alasannya praktis: `DOWNLOAD_DIR` dipakai sebagai
    nilai tetap di belasan tempat — termasuk sebagai string yang dibekukan saat
    impor di `ytdlp.py` — dan membuat semuanya dinamis berarti menyentuh
    lusinan baris demi setelan yang berubah beberapa kali seumur hidup
    pemasangan. Menggantinya menuntut aplikasi dijalankan ulang, sama seperti
    memindahkan seluruh penyimpanan.

    Penunjuknya tinggal di folder data sistem, bukan di dalam folder yang
    ditunjuknya — sebuah berkas yang menyebutkan di mana sesuatu berada tidak
    bisa ikut tinggal di dalamnya.
    """
    try:
        penunjuk = _user_data_dir() / f"lokasi-{nama}.txt"
        if penunjuk.is_file():
            pilihan = Path(penunjuk.read_text(encoding="utf-8").strip()).expanduser()
            if str(pilihan).strip() and _bisa_ditulis(pilihan):
                return pilihan.resolve()
    except OSError:
        pass
    return bawaan


# Keduanya bisa ditaruh di mana saja, terpisah dari penyimpanan lainnya.
#
# Ini dua folder yang ISINYA BESAR dan yang paling sering dibuka orang sendiri:
# video sumber yang diunduh sebelum diklip, dan klip jadinya. Menaruhnya di
# tempat yang dipilih pengguna membuat keduanya bisa ditemukan, dipindahkan ke
# cakram lain, dan dibersihkan saat penyimpanan penuh — tanpa menebak-nebak di
# mana aplikasi menyembunyikannya.
DOWNLOAD_DIR = _folder_pilihan("unduhan", STORAGE_DIR / "local_downloads")
CLIPS_DIR = _folder_pilihan("klip", STORAGE_DIR / "edited_clips")
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
    # Salinan ringan yang diputar Studio untuk sumber besar (services/proksi.py).
    "proksi": STORAGE_DIR / "proksi",
    # Video yang diambil dari komputer pengguna. Folder sendiri, bukan
    # local_downloads: berkas yang tidak pernah diunduh tidak pantas muncul di
    # halaman Unduhan (terlapor pengguna: "sangat tidak masuk akal").
    "impor": STORAGE_DIR / "impor",
}
IMPOR_DIR = MEDIA_DIRS["impor"]

for _d in (DOWNLOAD_DIR, CLIPS_DIR, THUMBS_DIR, LOGS_DIR, MODELS_DIR, VOICE_DIR, IMPOR_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# Modul yang menyalin DOWNLOAD_DIR atau CLIPS_DIR ke namanya sendiri saat
# diimpor. Daftarnya pendek dan disengaja: `setel_folder` di bawah harus
# memperbarui setiap salinan, kalau tidak sebagian aplikasi akan menulis ke
# folder lama dan sebagian ke folder baru. Ada uji yang memeriksa daftar ini
# tetap lengkap (tests/test_folder.py), supaya impor baru tidak lolos diam-diam.
_SALINAN_FOLDER = {
    "unduhan": [
        ("app.routers.videos", "DOWNLOAD_DIR", None),
        ("app.services.paths", "DOWNLOAD_DIR", None),
        ("app.services.ytdlp", "DOWNLOAD_DIR", str),
        ("app.services.ytdlp", "_DOWNLOAD_DIR", None),
    ],
    "klip": [
        ("app.services.render", "CLIPS_DIR", None),
        ("app.services.profil", "CLIPS_DIR", None),
    ],
}
_KATEGORI_MEDIA = {"unduhan": "local_downloads", "klip": "edited_clips"}


def setel_folder(jenis: str, tujuan: Path) -> None:
    """
    Mengarahkan folder unduhan atau klip ke tempat baru TANPA menjalankan ulang.

    Ini pengecualian yang disengaja dari aturan di `_folder_pilihan`: folder
    yang dibaca sekali saat startup. Pengecualiannya ada karena memindahkan
    berkas sambil aplikasi berjalan tidak ada gunanya bila aplikasi yang sama
    masih mencarinya di tempat lama. Berkas yang sudah pindah akan terlihat
    hilang sampai dijalankan ulang, dan "sudah dipindahkan tapi hilang" adalah
    bentuk kegagalan yang paling sulit dipercaya.

    Hanya nama yang benar-benar disalin modul lain yang diperbarui; sisanya
    membaca `config.X` setiap kali dan ikut sendiri.
    """
    import importlib
    import sys as _sys

    if jenis not in _SALINAN_FOLDER:
        raise ValueError(f"jenis folder tidak dikenal: {jenis}")
    tujuan = Path(tujuan).expanduser().resolve()
    tujuan.mkdir(parents=True, exist_ok=True)

    globals()["DOWNLOAD_DIR" if jenis == "unduhan" else "CLIPS_DIR"] = tujuan
    MEDIA_DIRS[_KATEGORI_MEDIA[jenis]] = tujuan

    for nama_modul, nama, ubah in _SALINAN_FOLDER[jenis]:
        modul = _sys.modules.get(nama_modul)
        if modul is None:
            try:
                modul = importlib.import_module(nama_modul)
            except ImportError:
                continue
        setattr(modul, nama, ubah(tujuan) if ubah else tujuan)

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
    # Auto-klip punya jalurnya sendiri, dan jalur ini LEBAR. Yang membatasi
    # mesin bukan jumlah pekerjaan yang terbuka melainkan dua sumber daya yang
    # sudah dijaga sendiri-sendiri: `jobs.gerbang_cpu` (Whisper, pelacakan
    # wajah, encode — satu per satu) dan `jobs.gerbang_unduh` (jalur pita).
    #
    # Terukur pada pemasangan sungguhan: dengan lebar 3, "Cari ulang klip"
    # untuk video yang SUDAH terunduh dan SUDAH punya transkrip — pekerjaan
    # beberapa detik — menunggu 6,6 menit di belakang tiga unduhan, sambil
    # menampilkan pemutar yang tampak menggantung. Yang antre seharusnya
    # unduhannya, bukan seluruh pekerjaannya.
    "klip": int(os.getenv("OMNICLIP_LANE_KLIP", "8")),
    # Unggahan punya jalurnya sendiri, dan lebarnya SATU. Bukan karena memori —
    # unggahan hampir tidak memakainya — melainkan karena mengirim selusin klip
    # ke satu kanal dalam satu ledakan adalah persis pola yang membuat YouTube
    # menandai sebuah kanal. Satu per satu, berurutan, selalu.
    "upload": 1,
}

# Unduhan yang boleh berjalan bersamaan, lintas jenis pekerjaan. Dua: tiap
# unduhan sudah memakai 8 sambungan fragmen, jadi pita 100 Mbps tetap terisi,
# sementara permintaan serentak ke YouTube lebih sedikit. Tiga bersamaan
# berjalan tepat sebelum IP ditandai "not a bot" (21 September 2026).
UNDUH_BERSAMAAN = int(os.getenv("OMNICLIP_UNDUH_BERSAMAAN", "2"))

# Jeda minimum antara dua unggahan YouTube yang berhasil. Nol berarti langsung
# menyambung; bawaannya sengaja tidak nol.
UPLOAD_GAP_SECONDS = int(os.getenv("OMNICLIP_UPLOAD_GAP", "90"))
JOB_PROGRESS_MIN_INTERVAL = 0.25  # detik antar tulisan progress ke DB


# --- Transkrip ----------------------------------------------------------------
WHISPER_MODEL_DEFAULT = os.getenv("OMNICLIP_WHISPER_MODEL", "base")
WHISPER_IDLE_UNLOAD_SECONDS = 600
# Urutan bahasa caption yang DICOBA LEBIH DULU. Bukan daftar tertutup: kalau
# tidak satu pun ada, `fetch_youtube_captions` melanjutkan ke bahasa yang
# benar-benar dimiliki videonya. Daftar ini cuma menyatakan "kalau ada
# pilihan, saya mau yang ini".
CAPTION_LANGS = ("id", "id-ID", "en", "en-US")


def get_caption_langs() -> tuple[str, ...]:
    """
    Urutan bahasa pilihan pengguna, dari basis data.

    Kosong = pakai bawaan. Nilainya berupa kode bahasa dipisah koma, mis.
    "ja,en" untuk orang yang mengklip video Jepang dan lebih suka takarirnya
    dalam bahasa aslinya.
    """
    try:
        from .repos import settings as settings_repo
        raw = settings_repo.get("transcript.langs").strip()
    except Exception:
        raw = ""
    if not raw:
        return CAPTION_LANGS
    pilihan = tuple(x.strip() for x in raw.split(",") if x.strip())
    return pilihan or CAPTION_LANGS


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


# --- Aplikasi Google bawaan ---------------------------------------------------
# Identitas aplikasi Google yang IKUT di dalam OmniClip, supaya pemakainya tidak
# perlu membuat project Google Cloud sendiri hanya untuk bisa menekan "Masuk
# dengan Google".
#
# Rahasia klien ikut dibagikan, dan itu memang tidak apa-apa DI SINI: Google
# menerbitkan jenis klien "Desktop app" justru untuk aplikasi yang dipasang di
# komputer orang, dan menyatakan rahasianya BUKAN rahasia. Pengamannya PKCE,
# bukan kerahasiaan (lihat RFC 8252). Untuk TikTok dan Meta aturannya berbeda
# dan rahasianya benar-benar rahasia; itu sebabnya keduanya tidak ditempuh
# lewat jalan ini.
#
# Kosong secara bawaan, dan selama kosong perilakunya persis seperti sebelum
# ini: pemiliknya memasang berkas OAuth-nya sendiri. Diisi lewat variabel
# lingkungan saat membangun rilis, jadi ia tidak pernah masuk riwayat git.
GOOGLE_CLIENT_ID = os.getenv("OMNICLIP_GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("OMNICLIP_GOOGLE_CLIENT_SECRET", "").strip()

# Variabel lingkungan saja tidak cukup untuk aplikasi yang DIBUNGKUS.
#
# `os.getenv` dibaca di komputer yang MENJALANKAN aplikasi, bukan di komputer
# yang membangunnya, dan di sana variabelnya tentu kosong. Jadi alur build
# menuliskan identitasnya ke modul kecil di bawah ini, yang ikut masuk ke dalam
# bundel. Berkasnya tidak ada di riwayat git (lihat .gitignore) dan tidak ada
# saat bekerja dari sumber, jadi selama seseorang membangun sendiri tanpa
# rahasia itu, perilakunya persis seperti sebelumnya.
if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
    try:
        from .identitas_google import CLIENT_ID as _ID, CLIENT_SECRET as _RAHASIA
        GOOGLE_CLIENT_ID = (_ID or "").strip()
        GOOGLE_CLIENT_SECRET = (_RAHASIA or "").strip()
    except Exception:       # noqa: BLE001 — tidak ada identitas bawaan, itu sah
        pass


def google_bawaan() -> Optional[dict]:
    """Berkas OAuth client bentuk dict dari identitas bawaan, atau None."""
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        return None
    return {"installed": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    }}


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


def _pecah_kunci(raw: str) -> list[str]:
    """Beberapa kunci dalam satu kolom: dipisah baris baru, koma, atau spasi."""
    import re as _re
    keluar, terlihat = [], set()
    for bagian in _re.split(r"[\s,;]+", raw or ""):
        k = bagian.strip()
        if k and k not in terlihat:
            terlihat.add(k)
            keluar.append(k)
    return keluar


def get_api_keys() -> list[str]:
    """
    SEMUA kunci Gemini yang boleh dipakai, urut dari yang pertama dicoba.

    Kuota Gemini dihitung per PROJECT Google, bukan per kunci. Itu kalimat dari
    dokumentasi Google sendiri, dan bedanya penting: dua kunci dari project yang
    sama berbagi jatah yang sama persis. Yang menambah jatah adalah kunci dari
    project KEDUA, dan itu pula yang memberi jalan keluar saat satu project
    sedang tidak bisa dipakai.

    Karena itu kolom kuncinya menerima lebih dari satu, dipisah baris baru atau
    koma. Yang di basis data lebih dulu daripada `.env`, dengan alasan yang
    sama seperti dulu: basis data bisa diisi dari HP, dan isian lewat
    antarmuka adalah yang lebih baru dan lebih disengaja.
    """
    dari_db: list[str] = []
    try:
        from .repos import settings as settings_repo
        dari_db = _pecah_kunci(settings_repo.get("ai.api_key"))
    except Exception:  # basis data belum siap saat impor paling awal
        pass
    dari_env = _pecah_kunci(os.environ.get("GEMINI_API_KEY", ""))
    # Keduanya digabung, bukan salah satu saja: kunci di `.env` milik pemilik
    # aplikasi dan kunci di basis data ditambahkan belakangan; membuang yang
    # satu karena yang lain terisi berarti membuang jatah yang sudah ada.
    keluar, terlihat = [], set()
    for k in dari_db + dari_env:
        if k not in terlihat:
            terlihat.add(k)
            keluar.append(k)
    return keluar


def get_api_key() -> str:
    """Kunci pertama yang berlaku. Lihat `get_api_keys` untuk selebihnya."""
    kunci = get_api_keys()
    return kunci[0] if kunci else ""


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
    """
    Berkas cookies dari variabel lingkungan.

    Pilihan cookies yang sebenarnya sekarang tinggal di `services/cookies.py`
    dan disimpan di basis data, supaya bisa diatur dari dalam aplikasi. Fungsi
    ini ditinggalkan agar pemasangan lama yang sudah menyetel variabelnya tidak
    berubah perilaku diam-diam; `cookies.sumber()` tetap menghormatinya.
    """
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
