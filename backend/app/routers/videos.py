"""Pencarian YouTube, metadata video, dan unduhan."""

import asyncio
import json
import logging
import os
import random
import re
import threading
import uuid
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import FileResponse
from typing import Optional
from pydantic import BaseModel, Field

from ..config import DOWNLOAD_DIR, THUMBS_DIR
from ..db import get_conn
from ..repos import cache as cache_repo
from ..errors import AppError, NotFound
from ..repos import media as media_repo
from ..services.media import poster_frame, probe
from ..services.jobs import queue
from ..services.paths import extract_youtube_id, find_local_video, safe_media_path
from ..services.ytdlp import (
    SEARCH_SORTS,
    YtdlpError,
    fetch_upload_dates,
    get_video_info,
    list_local_downloads,
    search_youtube_videos,
)

log = logging.getLogger("omniclip.videos")
router = APIRouter(prefix="/api", tags=["videos"])


def _as_app_error(exc: YtdlpError) -> AppError:
    status = {
        "YTDLP_RATE_LIMIT": 429,
        "YTDLP_UNAVAILABLE": 404,
        "YTDLP_PRIVATE": 404,
    }.get(exc.code, 502)
    return AppError(exc.message, code=exc.code, status=status, detail=exc.original)


class DownloadRequest(BaseModel):
    url: str = Field(..., description="ID atau URL YouTube")
    # Bawaannya yang terbaik: resolusi sumber adalah plafon kualitas seluruh
    # klip, dan jendela 9:16 yang dipotong darinya jauh lebih sempit daripada
    # bingkai penuhnya.
    resolution: str = "Terbaik"
    # Jalur audio (sulih suara), mis. "en". Kosong = suara asli video.
    audio_lang: Optional[str] = Field(None, max_length=16, pattern=r"^[A-Za-z0-9-]*$")


def _lengkapi_tanggal(hasil: list[dict]) -> list[dict]:
    """
    Menempelkan tanggal unggah yang SUDAH diketahui, tanpa membuka jaringan.

    Tanggalnya datang dari tabel `videos` — diisi setiap kali sebuah video
    pernah dibuka, diunduh, atau tanggalnya pernah diambil. Untuk video yang
    sudah dikenal, kartunya langsung tampil lengkap alih-alih menunggu dua
    belas detik panggilan susulan. Yang belum dikenal tetap diisi belakangan
    oleh /upload-dates seperti sebelumnya.
    """
    ids = [v.get("id") for v in hasil if v.get("id")]
    if not ids:
        return hasil
    tanda = ",".join("?" * len(ids))
    rows = get_conn().execute(
        f"SELECT id, upload_date, view_count FROM videos WHERE id IN ({tanda})", ids
    ).fetchall()
    dikenal = {r["id"]: r for r in rows}
    for v in hasil:
        r = dikenal.get(v.get("id"))
        if r and r["upload_date"] and not v.get("upload_date"):
            v["upload_date"] = r["upload_date"]
    return hasil


# ---------------------------------------------------------------------------
# Melengkapi cache di latar belakang
#
# Muatan pertama sengaja kecil supaya halaman terbuka cepat (20 hasil = 2,1
# detik melawan 4,6 detik untuk 100). Tapi langkah gulir PERTAMA lalu menembak
# YouTube untuk kedua kalinya — dan pencarian YouTube tidak stabil: permintaan
# yang sama semenit kemudian mengembalikan kumpulan video yang berbeda. Daftar
# yang sudah dibaca tetap aman karena sisi halaman hanya MENAMBAH, tapi video
# yang menyusul datang dari kolam yang lain, dan urutannya jadi terasa acak.
#
# Jadi begitu muatan pertama terkirim, sisanya diambil di latar belakang dari
# permintaan yang sama. Saat pengguna sampai ke dasar daftar, jawabannya sudah
# menunggu di cache — satu kolam, satu urutan, tanpa permintaan kedua di jalur
# yang dilihat pengguna.
# ---------------------------------------------------------------------------
_PELENGKAP_JALAN: set[str] = set()
_PELENGKAP_KUNCI = threading.Lock()


def _lengkapi_di_latar(kunci: str, ambil: Callable[[], list], penuh: int,
                       awal: list) -> None:
    """
    `awal` adalah daftar yang SUDAH terkirim ke pengguna, dan ia dipertahankan
    apa adanya di kepala hasil.

    Tanpa itu daftar panjangnya bukan kelanjutan melainkan daftar lain:
    pencarian YouTube tidak stabil, jadi meminta 120 hasil semenit setelah
    meminta 40 mengembalikan kumpulan yang berbeda — termasuk sepuluh teratas
    yang tidak diacak. Kartu yang sedang dibaca orang tidak boleh berganti
    hanya karena ia menggulir ke bawah.
    """
    with _PELENGKAP_KUNCI:
        if kunci in _PELENGKAP_JALAN:
            return
        _PELENGKAP_JALAN.add(kunci)

    def kerja():
        try:
            tambahan = ambil()
            if tambahan:
                sudah = {v.get("id") for v in awal if v.get("id")}
                hasil = list(awal) + [v for v in tambahan
                                      if v.get("id") and v["id"] not in sudah]
                cache_repo.simpan(kunci, {"items": hasil, "diminta": penuh})
                _catat_hasil(hasil)
        except Exception as e:
            # Gagal melengkapi bukan kegagalan: langkah gulir berikutnya akan
            # mengambilnya sendiri seperti sebelumnya.
            log.info("Pelengkapan cache '%s' dilewati: %s", kunci, str(e)[:120])
        finally:
            with _PELENGKAP_KUNCI:
                _PELENGKAP_JALAN.discard(kunci)

    threading.Thread(target=kerja, name="cache-topup", daemon=True).start()


@router.get("/search")
async def search(q: str = Query(..., description="Kata kunci pencarian"),
                 limit: int = 20, sort: str = "relevan",
                 durasi: Optional[str] = None, tanggal: Optional[str] = None):
    if not q.strip():
        return []
    if sort not in SEARCH_SORTS:
        sort = "relevan"
    from ..services.ytdlp import DURASI_KODE, TANGGAL_KODE
    durasi = durasi if durasi in DURASI_KODE else None
    tanggal = tanggal if tanggal in TANGGAL_KODE else None
    if limit <= 20:
        from ..repos import profil as profil_repo
        from ..services import profil
        try:
            await asyncio.to_thread(profil_repo.catat_cari, profil.kini(), q.strip()[:200], 0)
        except Exception:
            pass
    # Plafon 100, bukan 50. Terukur: ytsearch50 butuh 4,2 detik dan ytsearch100
    # butuh 4,8 — ongkosnya ada pada permintaannya, bukan pada jumlah hasilnya,
    # jadi separuh daftar itu sebelumnya dibuang gratis.
    want = min(limit, 100)

    # Cache dulu. Pencarian yang sama terukur 4-5 detik SETIAP kali tanpa ini,
    # dan menekan chip kategori lalu kembali berarti menunggu penuh dua kali.
    #
    # Kuncinya sengaja TIDAK memuat jumlah yang diminta. Versi sebelumnya
    # memuatnya, jadi menggulir satu kueri sampai dasar berarti lima kunci
    # berbeda dan lima permintaan penuh ke YouTube — 20, 40, 60, 80, 100 —
    # untuk daftar yang sebagian besar isinya sama. Ledakan itulah yang
    # memicu verifikasi bot, dan gulir tak hingga membuatnya jadi kebiasaan.
    kunci = f"search:{sort}:{durasi or '-'}:{tanggal or '-'}:{q.strip().lower()}"
    simpanan = await asyncio.to_thread(cache_repo.ambil, kunci)
    # Entri lama disimpan sebagai daftar telanjang. Bentuknya ditangani di sini
    # alih-alih mengosongkan cache saat mulai: menghapusnya berarti pencarian
    # pertama setiap orang setelah pembaruan ini menembak YouTube lagi.
    if isinstance(simpanan, list):
        simpanan = {"items": simpanan, "diminta": len(simpanan)}
    simpanan = simpanan if isinstance(simpanan, dict) else {}
    if simpanan.get("diminta", 0) >= want:
        return await asyncio.to_thread(
            _lengkapi_tanggal, (simpanan.get("items") or [])[:want])

    # Permintaan pertama diambil seukuran yang diminta supaya halaman terbuka
    # cepat (20 hasil = 2,1 detik). Begitu user menggulir sekali, sekalian
    # diambil sampai plafon (100 hasil = 4,6 detik) — langkah-langkah gulir
    # berikutnya lalu dilayani dari cache tanpa menyentuh YouTube lagi.
    ambil = want if want <= 20 else 100
    try:
        hasil = await asyncio.to_thread(search_youtube_videos, q, ambil, sort, durasi, tanggal)
    except YtdlpError as e:
        raise _as_app_error(e) from e

    # Hasil kosong tidak di-cache: ia hampir selalu berarti pembatasan laju
    # atau gangguan sesaat, dan menyimpannya berarti mengunci kegagalan itu
    # selama lima belas menit.
    if hasil:
        await asyncio.to_thread(cache_repo.simpan, kunci,
                                {"items": hasil, "diminta": ambil})
        # Metadata dasarnya ikut disimpan ke tabel `videos`.
        #
        # Bukan demi pencariannya sendiri, melainkan supaya tanggal unggah
        # punya tempat untuk menempel: /upload-dates menulis tanggalnya ke
        # baris video, dan tanpa baris itu dua belas detik kerja per dua puluh
        # video hilang begitu aplikasi ditutup.
        await asyncio.to_thread(_catat_hasil, hasil)
        if ambil < 100:
            _lengkapi_di_latar(
                kunci, lambda: search_youtube_videos(q, 100, sort), 100, hasil)
    return await asyncio.to_thread(_lengkapi_tanggal, hasil[:want])


def _catat_hasil(hasil: list[dict]) -> None:
    """Menyimpan metadata ringan tiap hasil pencarian. Judul yang kosong dilewati."""
    for v in hasil:
        if not v.get("id") or not (v.get("title") or "").strip():
            continue
        try:
            media_repo.upsert_video({
                "id": v["id"], "title": v["title"], "channel": v.get("channel"),
                "duration": v.get("duration"), "thumbnail": v.get("thumbnail"),
                "views": v.get("views"), "description": "",
            })
        except Exception:      # satu baris gagal tidak boleh menjatuhkan pencarian
            continue


@router.get("/upload-dates")
async def upload_dates(ids: str = Query(..., description="ID video, dipisah koma")):
    """
    Tanggal unggah untuk beberapa video sekaligus.

    Terpisah dari pencarian dengan sengaja. Hasil pencarian datar YouTube tidak
    memuat tanggal unggah sama sekali, dan mengambilnya berarti membuka tiap
    videonya — sekitar tiga detik untuk enam video, bersamaan. Menjalankan itu
    sebelum daftar hasilnya muncul akan membuat setiap pencarian terasa macet,
    jadi kartunya tampil dulu dan tanggalnya menyusul.
    """
    wanted = [v.strip() for v in ids.split(",") if v.strip()][:50]
    if not wanted:
        return {}
    hasil = await asyncio.to_thread(fetch_upload_dates, wanted)
    # Disimpan ke basis data, bukan hanya ke cache di memori.
    #
    # Tanpa ini, dua belas detik kerja per dua puluh video hilang setiap kali
    # aplikasi ditutup, dan video yang sama harus dibuka lagi satu per satu
    # besok pagi. Dengan ini, pencarian berikutnya sudah membawa tanggalnya
    # bersama kartunya lewat `_lengkapi_tanggal`.
    await asyncio.to_thread(_simpan_tanggal, hasil)
    return hasil


def _simpan_tanggal(hasil: dict) -> None:
    """Menulis tanggal unggah ke baris video yang sudah ada. Tidak membuat baris baru."""
    conn = get_conn()
    for vid, data in (hasil or {}).items():
        if not data or not data.get("upload_date"):
            continue
        try:
            conn.execute(
                "UPDATE videos SET upload_date = ?, view_count = COALESCE(?, view_count) "
                "WHERE id = ? AND (upload_date IS NULL OR upload_date = '')",
                (data.get("upload_date"), data.get("views"), vid),
            )
        except Exception:      # satu baris gagal tidak boleh menjatuhkan respons
            continue


# Kueri beranda. Satu kueri tetap adalah sebab beranda menampilkan video yang
# sama persis berapa kali pun disegarkan: `ytsearchN:` yt-dlp mengembalikan
# urutan yang deterministik, jadi kueri yang sama = daftar yang sama.
TRENDING_QUERIES = [
    "podcast indonesia terbaru",
    "wawancara mendalam indonesia",
    "obrolan santai podcast indonesia",
    "cerita pengalaman hidup indonesia",
    "diskusi bisnis indonesia",
    "talkshow indonesia terbaru",
    "podcast edukasi indonesia",
    "podcast komedi indonesia",
    "kisah inspiratif indonesia",
    "podcast teknologi indonesia",
]


def _kolam_beranda() -> list[str]:
    """
    Kueri beranda untuk profil aktif: minat yang ditulis pemiliknya, lalu
    pencarian terbarunya. Profil yang belum punya keduanya memakai kolam umum.

    Pemiliknya ingin beranda yang terbuka pertama kali sudah sesuai minat —
    satu profil untuk horor, satu untuk podcast — bukan campuran acak yang
    sama untuk semua orang.
    """
    from ..repos import profil as profil_repo
    from ..services import profil
    pid = profil.kini()
    p = profil_repo.ambil(pid) or {}
    minat = [m.strip() for m in (p.get("minat") or []) if isinstance(m, str) and m.strip()]
    sering = [r["query"] for r in profil_repo.kueri_sering(pid, 6)]
    riwayat = [r["query"] for r in profil_repo.riwayat_cari(pid, 8)]
    # Tiga lapis, dengan bobot yang berbeda dan alasannya masing-masing:
    #
    #   minat   x3  pilihan yang ditulis sendiri, dan tidak berubah tiap hari
    #   sering  x2  kata yang berulang kali diketik; itu yang sebenarnya dicari
    #   riwayat x1  jejak, termasuk yang cuma sekali dan mungkin salah ketik
    #
    # Lapis "sering" yang menjawab keluhannya: beranda yang isinya sesuai apa
    # yang memang dicari, supaya tidak perlu mengetik kata yang sama tiap hari.
    kolam = minat * 3 + sering * 2 + riwayat
    return kolam or TRENDING_QUERIES


@router.get("/riwayat-cari")
async def riwayat_cari():
    from ..repos import profil as profil_repo
    from ..services import profil
    return {"riwayat": await asyncio.to_thread(profil_repo.riwayat_cari, profil.kini(), 12)}


@router.delete("/riwayat-cari")
async def hapus_riwayat_cari(q: Optional[str] = None):
    from ..repos import profil as profil_repo
    from ..services import profil
    await asyncio.to_thread(profil_repo.hapus_riwayat, profil.kini(), q)
    return {"ok": True}


@router.get("/trending")
async def trending(limit: int = 20, refresh: int = 0):
    """
    Rekomendasi beranda.

    Tiap panggilan memakai kueri yang berbeda dari kolam di atas dan mengambil
    lebih banyak hasil daripada yang ditampilkan, lalu mengacak sisanya. Hasilnya
    beranda benar-benar berganti isi saat disegarkan — bukan memutar ulang dua
    puluh judul yang sama.

    Sepuluh hasil teratas ditahan di urutannya karena itulah yang paling relevan
    dengan kuerinya; pengacakan hanya berlaku pada ekor daftar.
    """
    want = min(limit, 100)

    # Kueri dan pengacakannya ditentukan oleh `refresh`, bukan oleh keberuntungan.
    #
    # Sebelumnya keduanya diambil dari `random` global, jadi SETIAP permintaan
    # menghasilkan beranda yang berbeda. Untuk satu halaman itu terasa segar;
    # untuk gulir tak hingga itu merusak: menggulir ke dasar meminta daftar yang
    # lebih panjang, server menjawab dengan kueri yang sama sekali lain, seluruh
    # kartu berganti, dan halaman terlempar kembali ke atas. Video yang sedang
    # dilihat hilang tanpa pernah bisa ditemukan lagi.
    #
    # Dengan `refresh` sebagai benih, daftar untuk satu nilai selalu sama dan
    # hanya bertambah panjang. Tombol Segarkan menaikkan nilainya — di situlah
    # tempat isi beranda memang seharusnya berganti.
    acak = random.Random(refresh)
    kolam = await asyncio.to_thread(_kolam_beranda)
    query = acak.choice(kolam)

    from ..services import profil
    kunci = f"trending:{profil.kini()}:{refresh}:{query}"
    simpanan = await asyncio.to_thread(cache_repo.ambil, kunci)
    simpanan = simpanan if isinstance(simpanan, dict) else {}
    if simpanan.get("diminta", 0) >= want:
        return await asyncio.to_thread(
            _lengkapi_tanggal, (simpanan.get("items") or [])[:want])

    ambil = want if want <= 20 else 100
    try:
        pool = await asyncio.to_thread(search_youtube_videos, query, min(ambil * 2, 120))
    except YtdlpError as e:
        raise _as_app_error(e) from e

    # Sepuluh teratas ditahan di urutannya karena itulah yang paling relevan
    # dengan kuerinya; pengacakan hanya berlaku pada ekor daftar.
    head, tail = pool[:10], pool[10:]
    acak.shuffle(tail)
    hasil = head + tail
    if hasil:
        await asyncio.to_thread(cache_repo.simpan, kunci,
                                {"items": hasil, "diminta": ambil})
        await asyncio.to_thread(_catat_hasil, hasil)
        if ambil < 100:
            def penuh() -> list:
                # Benihnya dipakai ulang PERSIS seperti di atas — termasuk satu
                # panggilan `choice` yang ikut menggerakkan keadaannya — supaya
                # daftar panjangnya benar-benar kelanjutan dari yang pendek dan
                # bukan susunan lain yang kebetulan berisi video yang sama.
                r = random.Random(refresh)
                r.choice(TRENDING_QUERIES)
                kolam = search_youtube_videos(query, 120)
                kepala, ekor = kolam[:10], kolam[10:]
                r.shuffle(ekor)
                return kepala + ekor

            _lengkapi_di_latar(kunci, penuh, 100, hasil)
    return await asyncio.to_thread(_lengkapi_tanggal, hasil[:want])


@router.get("/video-info")
async def video_info(url: str = Query(...)):
    video_id = extract_youtube_id(url)
    if not video_id:
        raise NotFound("ID video YouTube tidak dikenali.")
    try:
        info = get_video_info(video_id)
    except YtdlpError as e:
        raise _as_app_error(e) from e
    media_repo.upsert_video(info)
    local = find_local_video(video_id)
    info["downloaded"] = local is not None
    info["local_url"] = f"/api/media/local_downloads/{local.name}" if local else None
    return info


@router.post("/download", status_code=202)
async def start_download(req: DownloadRequest):
    """
    Mengantrekan unduhan dan langsung mengembalikan job_id.

    Unduhan bisa berjalan beberapa menit; menahannya di dalam request berarti
    tanpa progress, tanpa pembatalan, dan tanpa cara memulihkan setelah reload.
    """
    video_id = extract_youtube_id(req.url)
    if not video_id:
        raise NotFound("ID video YouTube tidak dikenali.")

    job_id, created = queue.enqueue(
        "download",
        {"video_id": video_id, "resolution": req.resolution, "audio_lang": req.audio_lang},
        video_id=video_id,
        dedupe_key=f"download:{video_id}:{req.resolution}:{req.audio_lang or 'asli'}",
    )
    return {"job_id": job_id, "created": created, "video_id": video_id}


@router.get("/downloads")
async def downloads():
    """
    Daftar file di local_downloads/, digabung dengan metadata dari database
    bila ada. File yang diunduh sebelum database ada tetap tampil.
    """
    by_name = {}
    for row in media_repo.list_downloads():
        by_name[row["rel_path"].split("/")[-1]] = row

    files = list_local_downloads()
    for f in files:
        f["web_url"] = f"/api/media/local_downloads/{f['file_name']}"
        # Sampul dibuat saat diminta, bukan sekarang: membuat empat puluh
        # bingkai di dalam satu request akan menahan daftarnya berdetik-detik.
        f["thumb_url"] = (f"/api/downloads/{quote(f['file_name'])}/thumb"
                          if f.get("type") != "audio" else None)
        meta = by_name.get(f["file_name"])
        if meta:
            f.update({
                "download_id": meta["id"],
                "video_id": meta["video_id"],
                "width": meta["width"],
                "height": meta["height"],
                "resolution": f"{meta['height']}p" if meta["height"] else None,
                "duration": meta["duration"],
            })
            # Judul dan kanal asli, supaya kartunya terbaca sebagai video —
            # bukan sebagai nama berkas dengan garis bawah.
            video = media_repo.get_video(meta["video_id"]) if meta["video_id"] else None
            if video:
                f.update({"title": video.get("title"),
                          "channel": video.get("channel")})
    return files


@router.get("/downloads/{filename}/thumb")
async def download_thumb(filename: str):
    """
    Sampul sebuah berkas unduhan, dibuat sekali lalu disimpan.

    Bingkai diambil dari seperempat durasi: awal video sering hitam atau berisi
    bumper kanal, dan sampul hitam tidak memberi tahu apa pun tentang isinya.
    """
    path = safe_media_path("local_downloads", filename)
    cache = THUMBS_DIR / f"{path.stem}.jpg"

    if not cache.is_file():
        info = await asyncio.to_thread(probe, path)
        durasi = float(info.get("duration") or 0)
        if not info.get("width"):
            raise NotFound("Berkas ini tidak punya gambar.")
        titik = durasi * 0.25 if durasi > 4 else 0.0
        ok = await asyncio.to_thread(poster_frame, path, cache, at=titik)
        if not ok:
            raise NotFound("Sampul gagal dibuat.")

    return FileResponse(path=cache, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


@router.delete("/downloads/{filename}")
async def delete_download(filename: str):
    path = safe_media_path("local_downloads", filename)
    rel = f"local_downloads/{path.name}"
    from ..services import suara
    audio = suara.tersimpan(path)
    path.unlink()
    if audio is not None:
        suara.buang(audio)
    media_repo.delete_download_row(rel)
    return {"success": True, "file_name": path.name}


# --- Impor video dari komputer sendiri ---------------------------------------

_EKSTENSI_VIDEO = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".mpg", ".mpeg", ".ts"}


def _id_lokal() -> str:
    """
    ID sebelas karakter untuk video yang tidak berasal dari YouTube.

    Panjangnya bukan kebetulan: seluruh sistem sudah menyaring id lewat
    `YT_ID_RE` yang menuntut tepat sebelas karakter, dan `find_local_video`
    mencari berkas yang namanya MEMUAT id itu. Memberi video impor bentuk id
    yang sama membuatnya mengalir lewat jalur yang sudah ada — analisis,
    editor, render — tanpa satu pun cabang khusus.
    """
    return "L" + uuid.uuid4().hex[:10]


@router.get("/impor/{video_id}/sampul")
async def sampul_impor(video_id: str):
    """Sampul video impor: satu bingkai dari seperempat durasinya, disimpan sekali."""
    from ..services.paths import adalah_impor, find_local_video
    if not adalah_impor(video_id):
        raise NotFound("Bukan video impor.")
    path = find_local_video(video_id)
    if path is None:
        raise NotFound("Berkas impor tidak ditemukan.")
    cache = THUMBS_DIR / f"impor_{video_id}.jpg"
    if not cache.is_file():
        info = await asyncio.to_thread(probe, path)
        durasi = float(info.get("duration") or 0)
        ok = await asyncio.to_thread(poster_frame, path, cache,
                                     at=durasi * 0.25 if durasi > 4 else 0.0)
        if not ok:
            raise NotFound("Sampul gagal dibuat.")
    return FileResponse(path=cache, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


class ImporJalurRequest(BaseModel):
    jalur: str = Field(..., min_length=1, max_length=4096)


@router.post("/impor/jalur", status_code=201)
async def impor_jalur(req: ImporJalurRequest):
    """
    Video di komputer ini, DIBACA DI TEMPATNYA — tidak disalin.

    Unggah lewat peramban selalu menyalin (peramban tidak boleh memberi tahu
    jalur berkas), jadi anime 248 MB tersalin utuh ke penyimpanan dan impor
    kedua menggandakannya lagi. OmniClip berjalan di komputer yang sama dengan
    berkasnya, jadi ia cukup mengingat jalurnya. Berkas aslinya tidak pernah
    diubah, dipindah, atau dihapus oleh OmniClip.
    """
    path = Path(req.jalur).expanduser()
    try:
        path = path.resolve()
    except OSError:
        pass
    if not path.is_file():
        raise NotFound("Berkas tidak ditemukan.")
    if path.suffix.lower() not in _EKSTENSI_VIDEO:
        raise AppError(f"Format {path.suffix or '(tanpa ekstensi)'} tidak didukung.",
                       code="IMPORT_BAD_FORMAT", status=422)
    info = await asyncio.to_thread(probe, path)
    if not info.get("width"):
        raise AppError("Berkas ini tidak punya gambar yang bisa dibaca.",
                       code="IMPORT_NOT_VIDEO", status=422)
    from ..services.paths import KANAL_IMPOR
    # Berkas yang sama diimpor lagi: pakai id yang lama, jangan buat kartu baru.
    from ..db import get_conn
    for r in get_conn().execute("SELECT id, meta_json FROM videos WHERE channel = ?", (KANAL_IMPOR,)):
        try:
            if json.loads(r["meta_json"] or "{}").get("jalur") == str(path):
                return {"video_id": r["id"], "title": path.stem[:60], "file_name": path.name,
                        "duration": info.get("duration"), "sudah_ada": True}
        except Exception:
            continue
    vid = _id_lokal()
    judul = path.stem[:60] or "Video impor"
    media_repo.upsert_video({
        "id": vid, "title": judul, "channel": KANAL_IMPOR,
        "duration": info.get("duration"), "thumbnail": None, "jalur": str(path),
    })
    return {"video_id": vid, "title": judul, "file_name": path.name,
            "file_size": path.stat().st_size, "duration": info.get("duration"),
            "width": info.get("width"), "height": info.get("height")}


@router.get("/impor/{video_id}/berkas")
async def berkas_impor(video_id: str):
    """Memutar video impor yang ada di luar folder OmniClip (mendukung Range)."""
    from ..services.paths import jalur_luar
    path = jalur_luar(video_id)
    if path is None:
        raise NotFound("Berkas impor tidak ditemukan.")
    import mimetypes
    return FileResponse(path=path, media_type=mimetypes.guess_type(path.name)[0] or "video/mp4")


@router.post("/impor/berkas", status_code=201)
async def impor_berkas(berkas: UploadFile = File(...)):
    """
    Menerima satu berkas video dari komputer pengguna.

    Ditulis mengalir per potongan, bukan dibaca utuh ke memori: video satu jam
    berukuran beberapa gigabita, dan mesin ini punya sekitar empat gigabita
    yang bisa dipakai.
    """
    nama_asli = os.path.basename(berkas.filename or "video")
    ext = Path(nama_asli).suffix.lower()
    if ext not in _EKSTENSI_VIDEO:
        raise AppError(f"Format {ext or '(tanpa ekstensi)'} tidak didukung.",
                       code="IMPORT_BAD_FORMAT", status=422)

    vid = _id_lokal()
    judul = Path(nama_asli).stem[:60] or "Video impor"
    aman = re.sub(r"[^\w.\- ]+", "_", judul).strip() or "video"
    # Folder impor sendiri — bukan local_downloads, supaya berkas yang tidak
    # pernah diunduh tidak muncul di halaman Unduhan.
    from ..config import IMPOR_DIR
    from ..services.paths import KANAL_IMPOR
    tujuan = IMPOR_DIR / f"{aman}_{vid}{ext}"
    IMPOR_DIR.mkdir(parents=True, exist_ok=True)

    ukuran = 0
    try:
        with open(tujuan, "wb") as f:
            while potong := await berkas.read(1 << 20):
                f.write(potong)
                ukuran += len(potong)
    except OSError as e:
        tujuan.unlink(missing_ok=True)
        raise AppError(f"Gagal menyimpan berkas: {e}", code="IMPORT_WRITE_FAILED",
                       status=500) from e
    finally:
        await berkas.close()

    if ukuran == 0:
        tujuan.unlink(missing_ok=True)
        raise AppError("Berkasnya kosong.", code="IMPORT_EMPTY", status=422)

    info = await asyncio.to_thread(probe, tujuan)
    if not info.get("width"):
        tujuan.unlink(missing_ok=True)
        raise AppError("Berkas ini tidak punya gambar yang bisa dibaca.",
                       code="IMPORT_NOT_VIDEO", status=422)

    media_repo.upsert_video({
        "id": vid, "title": judul, "channel": KANAL_IMPOR,
        "duration": info.get("duration"), "thumbnail": None,
    })
    return {"video_id": vid, "title": judul, "file_name": tujuan.name,
            "file_size": ukuran, "duration": info.get("duration"),
            "width": info.get("width"), "height": info.get("height")}
