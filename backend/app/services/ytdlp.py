import re
import os
import json
import subprocess
import threading
import time
import yt_dlp
from urllib.parse import quote_plus

from ..config import DOWNLOAD_DIR as _DOWNLOAD_DIR, STORAGE_DIR as _STORAGE_DIR
from . import cookies as cookies_svc
from . import yt_klien

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
            "Kalau masih gagal, atur cookies di Pengaturan.",
            raw,
        )
    if "sign in to confirm" in low or "not a bot" in low or "captcha" in low:
        return YtdlpError(
            "YTDLP_BOT_CHECK",
            "YouTube menolak semua cara masuk yang OmniClip punya untuk video "
            "ini. Sepuluh player client sudah dicoba bergantian. Biasanya ini "
            "hilang sendiri; kalau terus muncul untuk banyak video, yt-dlp perlu "
            "diperbarui — itu perbaikan yang selalu datang dari sisi yt-dlp.",
            raw,
        )
    if "429" in raw or "too many requests" in low or "rate" in low and "limit" in low:
        return YtdlpError(
            "YTDLP_RATE_LIMIT",
            "YouTube sedang membatasi permintaan. Tunggu beberapa menit lalu coba lagi.",
            raw,
        )
    if "fragment" in low:
        # Sejak potongan yang gagal tidak lagi dilewati diam-diam, unduhan
        # yang kehilangan potongan berhenti di sini alih-alih menghasilkan
        # video berlubang.
        return YtdlpError(
            "YTDLP_FRAGMENT",
            "Sebagian video gagal terunduh meski sudah dicoba berulang kali — "
            "biasanya koneksi sempat terputus. Coba unduh lagi: unduhan "
            "melanjutkan dari bagian terakhir, bukan mulai dari awal.",
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
    # Cookies opsional, dipilih dari Pengaturan. Lihat services/cookies.py:
    # cookies BUKAN obat verifikasi bot dan sering justru memperburuknya.
    try:
        cookies_svc.terapkan(opts)
    except Exception:
        # Pengaturan yang tidak terbaca tidak boleh mematikan pencarian.
        pass
    return opts


# ---------------------------------------------------------------------------
# Gerbang laju permintaan ke YouTube
#
# Verifikasi bot yang dilaporkan bukan soal identitas, melainkan volume: video
# yang PERSIS SAMA gagal dengan "Sign in to confirm you're not a bot" lalu
# berhasil beberapa menit kemudian tanpa satu pun perubahan. Sumber ledakannya
# terukur: membuka satu halaman hasil pencarian memicu /upload-dates, dan
# fungsi itu menembak YouTube untuk SETIAP kartu — dua puluh permintaan penuh
# dalam kolam delapan thread, dalam hitungan detik, dari satu alamat IP.
#
# Jeda minimum antar permintaan jauh lebih murah daripada blokir yang
# menghentikan seluruh aplikasi selama beberapa menit.
# ---------------------------------------------------------------------------
JEDA_MINIMUM = 0.45          # detik antar permintaan metadata
_kunci_giliran = threading.Lock()
_giliran_terakhir = 0.0


def _tunggu_giliran(jeda: float = JEDA_MINIMUM) -> None:
    """Menahan pemanggil sampai jeda minimum sejak permintaan terakhir lewat."""
    global _giliran_terakhir
    with _kunci_giliran:
        sisa = _giliran_terakhir + jeda - time.monotonic()
        if sisa > 0:
            time.sleep(sisa)
        _giliran_terakhir = time.monotonic()


def _punya_format_video(info: dict) -> bool:
    return any(f.get("vcodec", "none") != "none" and f.get("height")
               for f in (info.get("formats") or []))


def _ekstrak(url: str, opts: dict, **kw):
    """
    extract_info yang berpindah kumpulan player client sampai ada yang
    benar-benar memberi format, lalu mengingat kumpulan mana yang berhasil.

    Kegagalan yang ditangani ada dua bentuk, dan yang kedua justru yang paling
    menipu:

      1. Melempar galat — "Sign in to confirm you're not a bot", atau
         "The page needs to be reloaded".
      2. BERHASIL, tapi mengembalikan judul dan deskripsi lengkap tanpa satu
         pun format video. Tidak ada exception, tidak ada yang tampak salah;
         yang muncul di layar adalah video yang seolah tidak punya resolusi.

    Karena itu keberhasilan diukur dari isi hasilnya, bukan dari ketiadaan
    galat. Lihat yt_klien.py untuk angka pengukurannya.
    """
    galat = None
    for i, (nama, klien) in enumerate(yt_klien.urutan_coba()):
        if i:
            time.sleep(yt_klien.JEDA_ANTAR_STRATEGI)
        try:
            with yt_dlp.YoutubeDL(yt_klien.pasang(opts, klien)) as ydl:
                info = ydl.extract_info(url, download=False, **kw)
        except Exception as e:
            galat = galat or e
            continue
        if _punya_format_video(info):
            yt_klien.catat_berhasil(nama)
            return info

    # Seluruh kumpulan bisa gagal justru KARENA cookies: sesi yang login
    # menuntut token yang tidak bisa dibuat yt-dlp, dan balasannya adalah
    # metadata tanpa format. Satu putaran lagi tanpa cookies, supaya pilihan
    # yang salah di Pengaturan tidak mematikan aplikasi.
    if cookies_svc.aktif():
        polos = cookies_svc.lupakan_cookies(opts)
        for nama, klien in yt_klien.urutan_coba():
            try:
                with yt_dlp.YoutubeDL(yt_klien.pasang(polos, klien)) as ydl:
                    info = ydl.extract_info(url, download=False, **kw)
            except Exception as e:
                galat = galat or e
                continue
            if _punya_format_video(info):
                yt_klien.catat_berhasil(nama)
                # Cookies-nya yang bersalah, bukan YouTube. Dilewati sementara
                # supaya permintaan berikutnya tidak membayar putaran gagal ini
                # lagi — 22 detik melawan 2,7 detik, terukur.
                cookies_svc.lewati_sementara()
                return info

    if galat is not None:
        raise galat
    raise YtdlpError(
        "YTDLP_NO_FORMAT",
        "YouTube tidak memberikan satu pun format video untuk video ini. "
        "Video mungkin masih diproses, khusus member, atau siaran langsung "
        "yang belum selesai.",
        "Semua kumpulan player client dicoba, semuanya mengembalikan nol format.",
    )


def _unduh(url: str, opts: dict):
    """
    Unduhan yang berpindah kumpulan client dengan cara yang sama.

    Dipisah dari `_ekstrak` karena keberhasilannya tidak bisa dinilai dari isi
    hasil: begitu byte pertama turun, pemilihan client sudah selesai. Yang bisa
    dilakukan adalah berpindah ketika client-nya menolak SEBELUM unduhan mulai.
    """
    galat = None
    for i, (nama, klien) in enumerate(yt_klien.urutan_coba()):
        if i:
            time.sleep(yt_klien.JEDA_ANTAR_STRATEGI)
        try:
            ydl = yt_dlp.YoutubeDL(yt_klien.pasang(opts, klien))
            with ydl:
                info = ydl.extract_info(url, download=True)
            yt_klien.catat_berhasil(nama)
            return info, ydl
        except Exception as e:
            galat = galat or e
            pesan = str(e).lower()
            # Kegagalan yang jelas bukan soal client tidak perlu diulang: video
            # privat tetap privat di client mana pun, dan cakram penuh tetap
            # penuh. Mengulangnya hanya menunda pesan galat yang benar.
            if any(t in pesan for t in ("private", "members-only", "members only",
                                        "removed", "does not exist", "no space",
                                        "copyright", "geo-restrict")):
                raise
            continue
    raise galat


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
    channels: list[tuple[str, str]] = []
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
                # Kanal (UC…) dan playlist (PL…) ikut terbawa hasil pencarian
                # YouTube. Keduanya bukan video: kartunya tampil tanpa gambar,
                # tanpa durasi, dan mengkliknya tidak menuju ke mana-mana.
                # Id kanal dicatat karena justru itulah jalan ke video terbaru.
                if _looks_like_channel(video_id):
                    channels.append((video_id, entry.get('title') or ''))
                    continue
                if video_id.startswith('PL') or not entry.get('duration'):
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

    # "Terbaru" dijawab oleh KANALNYA, bukan oleh pengurutan pencarian.
    #
    # Parameter urutan milik YouTube (sp=CAI…) ternyata tetap mencampur
    # relevansi: mencari "raditya dika" lalu mengurutkan terbaru mengembalikan
    # video seminggu lalu di posisi pertama, sementara kanalnya sendiri sudah
    # mengunggah dua video sesudah itu — yang paling baru bahkan tidak ada di
    # hasil pencarian sama sekali. Tab video sebuah kanal selalu urut dari yang
    # terbaru, dan mengambilnya cuma butuh setengah detik.
    if sort == "terbaru" and channels and not is_url:
        fresh = _channel_latest(channels[0][0], limit)
        if fresh:
            seen = {v["id"] for v in fresh}
            results = fresh + [v for v in results if v["id"] not in seen]

    # "Terpopuler" diurutkan ulang di sini.
    #
    # Bukan karena parameter urutan YouTube diabaikan — justru sebaliknya, ia
    # tetap dipakai karena ia yang menentukan KUMPULAN videonya. Tapi YouTube
    # menyelipkan beberapa hasil relevansi di pucuk daftar sebelum urutan
    # tayangannya dimulai. Terukur pada "windah basudara": 1,6 juta - 1,9 juta -
    # 1,2 juta, baru kemudian 17 juta - 8,6 juta - 7,6 juta dan seterusnya
    # menurun rapi. Tiga kartu pertama itulah yang terlihat sebagai "acak".
    #
    # Tidak seperti tanggal unggah, jumlah tayangan IKUT di hasil pencarian
    # datar, jadi mengurutkannya di sini tidak butuh satu pun permintaan
    # tambahan dan tidak bisa salah.
    if sort == "terpopuler":
        results.sort(key=lambda v: v.get("views") or 0, reverse=True)

    return results[:limit]


def _looks_like_channel(ident: str) -> bool:
    return ident.startswith("UC") and len(ident) == 24


def _channel_latest(channel_id: str, limit: int = 20) -> list:
    """
    Video terbaru sebuah kanal, urut dari yang paling baru.

    Dipakai untuk menjawab "terbaru" karena inilah satu-satunya sumber yang
    benar-benar urut waktu. Pencarian YouTube tidak pernah menjanjikan itu.
    """
    opts = _base_opts()
    opts.update({'extract_flat': 'in_playlist', 'skip_download': True,
                 'playlistend': max(1, min(50, limit))})
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        # Kanal yang tidak bisa dibaca bukan alasan mengosongkan hasil pencarian.
        return []

    out = []
    for e in (info.get('entries') or []):
        vid = (e or {}).get('id')
        if not vid or not e.get('duration'):
            continue
        out.append({
            "id": vid,
            "title": e.get('title') or 'Untitled',
            "url": f"https://www.youtube.com/watch?v={vid}",
            "duration": e.get('duration') or 0,
            # `info["title"]` adalah judul TAB ("Raditya Dika - Videos"),
            # bukan nama kanalnya. Dipakai hanya sebagai upaya terakhir, dan
            # akhiran tabnya dibuang.
            "channel": (e.get('uploader') or e.get('channel')
                        or (info.get('uploader') or info.get('channel'))
                        or re.sub(r'\s*-\s*Videos$', '', info.get('title') or '')),
            "views": e.get('view_count') or 0,
            "thumbnail": (e.get('thumbnail')
                          or (e.get('thumbnails', [{}])[-1].get('url') if e.get('thumbnails') else None)
                          or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"),
            "description": e.get('description') or '',
        })
    return out

# Nama yang berarti "ambil setinggi mungkin". Diterima dalam beberapa ejaan
# karena datang dari dua tempat: pilihan pengguna di halaman tonton, dan nilai
# bawaan pipeline auto-clip.
def is_best(resolution: str) -> bool:
    """Apakah nama resolusi ini berarti "setinggi mungkin"."""
    return (resolution or "").strip().lower().startswith(("terbaik", "best"))


BEST_RESOLUTION = {"Terbaik", "terbaik", "best", "Best"}

# Plafon resolusi untuk "Terbaik".
#
# Bukan pembatasan sembarang: keluaran akhir 1080x1920, dan jendela potong dari
# sumber 2160p sudah 1215 piksel — lebih lebar dari yang dibutuhkan, jadi ia
# DIKECILKAN, bukan diregangkan. Di atas ini tidak ada satu piksel pun tambahan
# pada hasil, hanya berkas yang membengkak.
#
# Yang dibayar untuk sampai ke sini nyata dan sudah diukur di mesin ini: di atas
# 1080p YouTube hanya menyediakan VP9/AV1, dan men-decode 10 detik 2160p VP9
# memakan 34,7 detik melawan 10,1 detik untuk 1080p H.264 — 3,5x lebih lambat.
# Pemindaian wajah dan render sama-sama harus men-decode sumbernya, jadi ongkos
# itu muncul dua kali. Angka ini ditulis di sini supaya menurunkannya jadi
# keputusan yang bisa diambil dengan sadar, bukan tebakan: 1440p memberi jendela
# 810 piksel — masih jauh lebih baik daripada 608 piksel milik 1080p — dengan
# decode yang jauh lebih murah.
MAX_BEST_HEIGHT = 2160


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
    # "Terbaik" ditaruh PALING DEPAN, dan hanya bila memang ada yang lebih
    # tinggi dari pilihan pertama — pada video yang cuma punya 360p, menawarkan
    # "Terbaik" di samping "360p" adalah dua nama untuk hal yang sama.
    if max_h > min(int(o.rstrip("p")) for o in options):
        options.insert(0, f"Terbaik ({min(max_h, MAX_BEST_HEIGHT)}p)")
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
    _tunggu_giliran()
    try:
        info = _ekstrak(url, _base_opts())
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
            done = d.get("downloaded_bytes") or 0
            frag_i = d.get("fragment_index")
            frag_n = d.get("fragment_count")

            # Unduhan berfragmen dihitung dari FRAGMEN, bukan dari bita.
            #
            # Pada unduhan DASH bersegmen, `total_bytes` selalu None dan
            # `total_bytes_estimate` adalah terkaan yang BERLIPAT DUA setiap
            # fragmen baru: terukur 712 bita, lalu 3 MB, 1, 2, 4, 9, 17, 35,
            # 71, 141, 283, 567 MB pada satu video yang sama. Membagi bita
            # terunduh dengan angka yang tumbuh secepat pembilangnya membuat
            # pecahannya tidak pernah beranjak dari nol — itulah bar yang
            # "macet", dan pada panggilan pertama pembagi itu masih di bawah
            # satu megabita sehingga pesannya terbaca "0/0 MB".
            #
            # `fragment_index`/`fragment_count` justru terisi dan tepat sejak
            # panggilan pertama (0/2269), jadi itu yang dipakai.
            if frag_n:
                frac = min(1.0, (frag_i or 0) / frag_n)
                ukuran = f"{done / 1048576:.0f} MB · bagian {frag_i or 0}/{frag_n}"
            else:
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                frac = (done / total) if total else 0.0
                ukuran = (f"{done / 1048576:.0f}/{total / 1048576:.0f} MB" if total
                          else f"{done / 1048576:.0f} MB")

            base, span = (0.0, 0.85) if state["stream"] == 0 else (0.85, 0.15)
            overall = base + span * min(1.0, frac)
            if overall - state["last"] >= 0.005:
                state["last"] = overall
                speed = d.get("speed") or 0
                on_progress(overall,
                            f"Mengunduh {ukuran} ({speed / 1048576:.1f} MB/s)" if speed
                            else f"Mengunduh {ukuran}")
        elif status == "finished":
            state["stream"] += 1
            state["last"] = -1.0
            on_progress(0.85 if state["stream"] == 1 else 0.98,
                        "Aliran video selesai — mengunduh audio…" if state["stream"] == 1
                        else "Menggabungkan video dan audio…")

    return hook


# Nama langkah sesudah unduhan, untuk kabar yang bisa dibaca pengguna.
_LANGKAH_PP = {
    "Merger": "Menggabungkan video dan audio",
    "MoveFiles": "Memindahkan berkas ke folder unduhan",
    "FFmpegExtractAudio": "Mengubah audio ke MP3",
}


def _make_pp_hook(on_progress):
    """
    Kabar selama langkah sesudah unduhan.

    Menggabungkan video 3 GB dengan audionya di hard disk eksternal bisa makan
    beberapa menit, dan yt-dlp tidak melaporkan apa pun selama itu. Tanpa kabar
    yang terus berjalan, layar tertahan di "Mengunduh … 100%" dan terbaca macet.
    Jadi selama langkahnya berjalan, lama berjalannya dilaporkan tiap dua detik.
    """
    state = {"henti": None}

    def detak(nama: str, henti: threading.Event) -> None:
        mulai = time.monotonic()
        try:
            while not henti.wait(2.0):
                lama = int(time.monotonic() - mulai)
                try:
                    on_progress(0.99, f"{nama}… ({lama // 60}:{lama % 60:02d})")
                except Exception:
                    return          # dibatalkan — yt-dlp akan berhenti sendiri
        finally:
            try:
                from ..db import close_conn
                close_conn()
            except Exception:
                pass

    def hook(d):
        status = d.get("status")
        if status == "started":
            nama = _LANGKAH_PP.get(d.get("postprocessor") or "", "Merapikan berkas video")
            if state["henti"] is not None:
                state["henti"].set()
            henti = threading.Event()
            state["henti"] = henti
            on_progress(0.99, f"{nama}…")
            threading.Thread(target=detak, args=(nama, henti), daemon=True,
                             name="omniclip-pp-detak").start()
        elif status == "finished" and state["henti"] is not None:
            state["henti"].set()
            state["henti"] = None

    def berhenti():
        if state["henti"] is not None:
            state["henti"].set()

    hook.berhenti = berhenti
    return hook


# Unduhan dipecah menjadi potongan yang diambil lewat beberapa sambungan
# sekaligus. Satu sambungan ke YouTube diperlambat setelah ±30 detik — terukur
# pada internet 100 Mbps: 9,8 MB/s di awal lalu turun ke 2-5 MB/s dan tidak
# kembali. Delapan sambungan paralel bertahan di 8-10,7 MB/s sepanjang unduhan.
#
# `formats=dashy` membuat yt-dlp memperlakukan format HTTPS biasa sebagai
# rangkaian potongan (seperti DASH), sehingga `concurrent_fragment_downloads`
# berlaku padanya. Tanpa itu, opsi paralel hanya berlaku pada format HLS.
SAMBUNGAN_PARALEL = int(os.getenv("OMNICLIP_SAMBUNGAN_UNDUH", "8"))


def _opsi_paralel(opts: dict) -> dict:
    o = dict(opts)
    o["concurrent_fragment_downloads"] = SAMBUNGAN_PARALEL
    ekstra = dict(o.get("extractor_args") or {})
    yt = dict(ekstra.get("youtube") or {})
    yt["formats"] = ["dashy"]
    ekstra["youtube"] = yt
    o["extractor_args"] = ekstra
    return o


def download_youtube_media(url_or_id: str, resolution: str = "720p", on_progress=None):
    """
    Mengunduh media dari YouTube berdasarkan opsi resolusi (360p, 480p, 720p, 1080p, Audio MP3).
    Format output disimpan ke OmniClip_Storage/local_downloads/
    """
    url = url_or_id if url_or_id.startswith("http") else f"https://www.youtube.com/watch?v={url_or_id}"

    # Setup format selector
    format_sort = None
    if resolution == "Audio MP3":
        fmt = "bestaudio[ext=m4a]/bestaudio/best"
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    elif is_best(resolution):
        # "Terbaik": resolusi tertinggi yang ditawarkan YouTube untuk video ini.
        #
        # Ini yang dipakai auto-clip, dan alasannya geometris. Keluaran 9:16
        # adalah 1080x1920, dan jendela yang dipotong dari sumber 16:9 hanya
        # selebar 9/16 tingginya: dari 720p jendelanya 405x720 lalu diregangkan
        # ke 1080x1920 — hampir tiga kali lipat, dan tidak ada filter yang bisa
        # mengembalikan detail yang memang tidak pernah terekam. Dari 1080p
        # jendelanya 608x1080, dari 1440p 810x1440, dari 2160p 1215x2160 yang
        # justru DIKECILKAN ke ukuran akhir. Di situlah batas kegunaannya: lebih
        # tinggi dari 2160p tidak menambah satu piksel pun pada hasil, hanya
        # menambah berkas raksasa dan waktu decode di mesin tanpa GPU.
        res_height = MAX_BEST_HEIGHT
        fmt = (f"bv*[height<=?{res_height}]+ba/b[height<=?{res_height}]/"
               f"bv*+ba/b")
        # Urutan pemilihan, bukan penyaringan: resolusi tertinggi dulu, lalu
        # H.264 di antara yang tingginya sama. H.264 didahulukan karena decode-
        # nya jauh lebih murah di CPU tanpa GPU — tapi hanya sebagai preferensi,
        # sebab di atas 1080p YouTube umumnya hanya menyediakan VP9 atau AV1 dan
        # menolaknya berarti menolak resolusi terbaiknya.
        format_sort = ['res', 'fps', 'vcodec:h264', 'ext:mp4:m4a', 'br']
        postprocessors = []
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
        'fragment_retries': 15,
        # Potongan yang tetap gagal sesudah semua percobaan TIDAK boleh
        # dilewati. Bawaan yt-dlp melewatinya diam-diam lalu tetap merakit
        # berkasnya — hasilnya video yang tampak utuh tapi berlubang: terukur
        # pada satu unduhan 40 menit, dua celah 5,08 detik di aliran videonya
        # sementara audionya lengkap. Di hasil render itu terlihat sebagai
        # gambar yang membeku, dan tidak ada satu pun pesan yang menjelaskan
        # kenapa. Lebih baik unduhannya gagal dan bisa diulang — berkas .part
        # disimpan, jadi pengulangannya melanjutkan, bukan mulai dari nol.
        'skip_unavailable_fragments': False,
        'merge_output_format': 'mp4',
        # Bilah progres teks yt-dlp tetap tercetak saat potongan diunduh
        # paralel meski 'quiet' — kemajuan sudah dilaporkan lewat hook.
        'noprogress': True,
        'restrictfilenames': True, # Hindari karakter spesial di nama file
    })
    if format_sort:
        ydl_opts['format_sort'] = format_sort

    if postprocessors:
        ydl_opts['postprocessors'] = postprocessors
    pp_hook = None
    if on_progress is not None:
        ydl_opts['progress_hooks'] = [_make_progress_hook(on_progress)]
        pp_hook = _make_pp_hook(on_progress)
        ydl_opts['postprocessor_hooks'] = [pp_hook]

    try:
        try:
            info, ydl = _unduh(url, _opsi_paralel(ydl_opts))
        except Exception as e:
            # Unduhan berpotongan adalah percepatan, bukan syarat. Bila gagal
            # karena alasan yang bukan soal videonya (privat, cakram penuh,
            # dibatalkan), ulangi sekali dengan satu sambungan seperti dulu —
            # berkas .part yang ada dilanjutkan, bukan dimulai dari nol.
            pesan = str(e).lower()
            if (type(e).__name__ == "JobCancelled" or
                    any(t in pesan for t in ("private", "members", "removed",
                                             "does not exist", "no space",
                                             "copyright", "geo-restrict"))):
                raise
            print(f"[OmniClip] Unduhan paralel gagal, mengulang dengan satu sambungan: "
                  f"{str(e)[:200]}")
            if on_progress is not None:
                # Sekaligus titik periksa pembatalan: yt-dlp kadang membungkus
                # pembatalan dari dalam hook menjadi DownloadError biasa, dan
                # unduhan yang dibatalkan tidak boleh diulang.
                on_progress(0.0, "Mengulang unduhan dengan satu sambungan…")
            info, ydl = _unduh(url, ydl_opts)
        finally:
            if pp_hook is not None:
                pp_hook.berhenti()

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
# Diturunkan dari 8. Dengan jeda 0,45 detik per permintaan, thread yang lebih
# banyak hanya berebut gerbang yang sama — yang tersisa cuma risikonya.
UPLOAD_DATE_WORKERS = 3

# Tanggal unggah yang sudah pernah diambil.
#
# Tanggal unggah sebuah video tidak pernah berubah, jadi mengambilnya dua kali
# adalah pemborosan murni — dan pemborosan yang terasa, karena tiap pengambilan
# berarti membuka halaman videonya. Dengan ini, mencari kata yang sama dua kali
# atau kembali ke halaman pencarian membuat tanggalnya muncul seketika alih-alih
# menyusul beberapa detik kemudian.
_DATE_CACHE: dict[str, dict] = {}
_DATE_CACHE_MAX = 2000


def fetch_upload_dates(video_ids: list[str]) -> dict:
    """Mengambil tanggal unggah beberapa video sekaligus."""
    from concurrent.futures import ThreadPoolExecutor

    ids = [v for v in dict.fromkeys(video_ids) if v][:50]
    if not ids:
        return {}

    cached = {v: _DATE_CACHE[v] for v in ids if v in _DATE_CACHE}
    ids = [v for v in ids if v not in cached]
    if not ids:
        return cached

    def one(vid: str):
        # Gerbang laju: inilah tempat ledakan permintaan yang memicu verifikasi
        # bot berasal. Dua puluh kartu berarti dua puluh permintaan penuh, dan
        # tanpa jeda semuanya berangkat dalam hitungan detik dari satu IP.
        _tunggu_giliran()
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

    out = dict(cached)
    with ThreadPoolExecutor(max_workers=UPLOAD_DATE_WORKERS) as ex:
        for vid, data in ex.map(one, ids):
            if data and data.get("upload_date"):
                out[vid] = data
                _DATE_CACHE[vid] = data
    if len(_DATE_CACHE) > _DATE_CACHE_MAX:
        for key in list(_DATE_CACHE)[: len(_DATE_CACHE) - _DATE_CACHE_MAX]:
            _DATE_CACHE.pop(key, None)
    return out
