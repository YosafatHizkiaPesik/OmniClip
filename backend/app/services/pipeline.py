"""Handler job yang menyusun pekerjaan panjang jadi langkah-langkah terpantau."""

import logging
import os
from typing import Optional

from ..errors import AppError, JobCancelled, RenderError
from ..repos import media as media_repo
from .jobs import JobContext
from .paths import find_local_video
from .ytdlp import YtdlpError, download_youtube_media, get_video_info

log = logging.getLogger("omniclip.pipeline")


def _singkirkan_audio_lain(video_id: str, audio_lang: Optional[str]):
    """
    Bila berkas lokal video ini memuat audio berbahasa LAIN dari yang diminta,
    berkas itu disingkirkan (diberi akhiran .lama) supaya unduhan baru tidak
    dilewati yt-dlp sebagai "sudah ada". Mengembalikan (lama, asli) untuk
    dipulihkan bila unduhannya gagal, atau None.
    """
    from .ytdlp import audio_cocok, bahasa_audio
    if not audio_lang:
        return None
    src = find_local_video(video_id)
    if src is None or audio_cocok(bahasa_audio(src), audio_lang):
        return None
    lama = src.with_name(src.name + ".lama")
    try:
        os.replace(src, lama)
    except OSError:
        return None
    log.info("Audio %s diminta; berkas lama (%s) disingkirkan", audio_lang, bahasa_audio(lama))
    return lama, src


def _selesaikan_singkiran(singkiran, berhasil: bool) -> None:
    if not singkiran:
        return
    lama, asli = singkiran
    try:
        if berhasil:
            lama.unlink(missing_ok=True)
        elif not asli.exists():
            os.replace(lama, asli)
    except OSError:
        pass


def run_download(ctx: JobContext) -> dict:
    """
    payload: {video_id: str, resolution: str}

    Menggantikan endpoint /api/download yang dulu memblokir request selama
    berapa pun lamanya unduhan, tanpa progress dan tanpa cara membatalkan.
    """
    video_id = ctx.payload["video_id"]
    # Sama seperti auto-clip: yang terbaik, kecuali pemintanya menyebut lain.
    resolution = ctx.payload.get("resolution") or "Terbaik"
    # Jalur audio pilihan; kosong = suara asli video.
    audio_lang = ctx.payload.get("audio_lang") or None

    ctx.progress(0.02, stage="metadata", message="Mengambil informasi video…")
    try:
        info = get_video_info(video_id)
    except YtdlpError as e:
        raise AppError(e.message, code=e.code, status=502, detail=e.original) from e

    media_repo.upsert_video(info)
    title = info.get("title") or video_id
    ctx.check_cancelled()

    def on_progress(frac: float, message: str) -> None:
        # Dipanggil dari dalam yt-dlp; ini juga titik di mana pembatalan
        # menghentikan unduhan yang sedang berjalan.
        ctx.check_cancelled()
        ctx.progress(0.05 + 0.90 * frac, stage="download", message=message,
                     paksa=not message.startswith("Mengunduh"))

    ctx.progress(0.05, stage="download", message=f"Mengunduh «{title[:48]}»…")
    singkiran = _singkirkan_audio_lain(video_id, audio_lang)
    with ctx.giliran_unduh(lambda: ctx.progress(
            0.05, stage="download",
            message="Menunggu giliran mengunduh — unduhan lain sedang berjalan…",
            paksa=True)):
        try:
            result = download_youtube_media(video_id, resolution, on_progress=on_progress,
                                            audio_lang=audio_lang)
        except BaseException:
            _selesaikan_singkiran(singkiran, False)
            raise
    _selesaikan_singkiran(singkiran, bool(result.get("success")))

    if not result.get("success"):
        raise AppError(result.get("error", "Pengunduhan gagal."),
                       code=result.get("code", "DOWNLOAD_FAILED"), status=502)

    ctx.progress(0.97, stage="persist", message="Menyimpan catatan unduhan…")
    download_id = media_repo.record_download(video_id, result)

    actual = result.get("resolution")
    requested = result.get("requested_resolution")
    note = None
    if actual and requested and actual != requested and requested.lower() != "terbaik":
        # Jujur: YouTube tidak selalu punya resolusi yang diminta. "Terbaik"
        # bukan resolusi — 1080p untuknya adalah jawaban, bukan kekurangan.
        note = f"Resolusi {requested} tidak tersedia; yang diunduh {actual}."

    ctx.progress(1.0, stage="done", message=note or f"Selesai ({actual}).")
    return {
        "download_id": download_id,
        "video_id": video_id,
        "file_name": result["file_name"],
        "resolution": actual,
        "requested_resolution": requested,
        "width": result.get("width"),
        "height": result.get("height"),
        "duration": result.get("duration"),
        "file_size": result.get("file_size"),
        "note": note,
        "web_url": f"/api/media/local_downloads/{result['file_name']}",
    }


def _sane_font_size(value, default: int = 96) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if n >= 40 else default


def run_render(ctx: JobContext) -> dict:
    """
    payload: {video_id, segments:[{start,end}], subtitles, aspect_ratio,
              hook_text, watermark, video_filter, caption_style, frame_mode}

    Render dipisah jadi job sendiri supaya pengguna bisa meninjau klip pertama
    sementara klip berikutnya masih di-encode.
    """
    from .clipmodel import rebuild_subtitles_for_segments
    from .render import render_clip
    from .subtitles import FONT_FAMILIES, CaptionStyle

    video_id = ctx.payload["video_id"]
    source = find_local_video(video_id)
    if source is None:
        raise AppError(
            "Video sumber belum diunduh. Unduh videonya dulu, lalu render klip.",
            code="SOURCE_NOT_DOWNLOADED", status=409,
        )

    segments = ctx.payload.get("segments") or []
    if not segments:
        segments = [{"start": ctx.payload.get("start_seconds", 0),
                     "end": ctx.payload.get("end_seconds", 0)}]

    subtitles = ctx.payload.get("subtitles") or []

    style_in = ctx.payload.get("caption_style") or {}
    style = CaptionStyle(
        # font_size lama berasal dari era SRT force_style (nilai khas 24) dan
        # terlalu kecil untuk kanvas 1080x1920. Nilai di bawah 40 diabaikan.
        size=int(style_in.get("size") or _sane_font_size(ctx.payload.get("font_size"))),
        highlight=style_in.get("highlight", "#FFE500"),
        primary=style_in.get("primary", "#FFFFFF"),
        position=style_in.get("position", ctx.payload.get("position", "bottom")),
        uppercase=bool(style_in.get("uppercase", True)),
        animation=style_in.get("animation", "karaoke_pop"),
        # Hanya font yang benar-benar ikut dibundel yang diteruskan. Nama lain
        # akan membuat libass jatuh diam-diam ke DejaVu Sans, dan hasilnya
        # terlihat seperti berkas subtitle, bukan seperti klip.
        font=(style_in.get("font") if style_in.get("font") in FONT_FAMILIES
              else "Montserrat"),
        margin_v=max(24, min(1400, int(style_in.get("margin_v") or 300))),
        outline_px=max(0, min(16, int(style_in.get("outline_px") or 7))),
        pos_x=max(0.0, min(100.0, float(style_in.get("pos_x", 50.0)))),
        box_w=max(20.0, min(100.0, float(style_in.get("box_w", 84.0)))),
        speaker_colors=tuple(style_in.get("speaker_colors")
                             or ("#FFFFFF", "#7CFFB2", "#FFB3C7", "#B39DFF")),
        # Bawaannya tetap menyala, jadi gaya lama tidak berubah artinya.
        per_speaker_colors=bool(style_in.get("per_speaker_colors", True)),
        # Tanda air. Font kosong berarti ikut font subtitle — itu yang
        # diharapkan saat pengguna belum menyentuh setelan ini sama sekali.
        wm_font=(style_in.get("wm_font") if style_in.get("wm_font") in FONT_FAMILIES
                 else ""),
        wm_size=max(8, min(400, int(style_in.get("wm_size") or 34))),
        wm_color=style_in.get("wm_color") or "#FFFFFF",
        wm_opacity=max(0.0, min(1.0, float(style_in.get("wm_opacity", 0.62)))),
        wm_x=max(0.0, min(100.0, float(style_in.get("wm_x", 92.0)))),
        wm_y=max(0.0, min(100.0, float(style_in.get("wm_y", 95.0)))),
        wm_outline=max(0, min(16, int(style_in.get("wm_outline", 2)))),
    )

    total = sum(float(s["end"]) - float(s["start"]) for s in segments)
    label = "Merender klip" if len(segments) == 1 else f"Merender {len(segments)} potongan gabungan"
    frame_mode = ctx.payload.get("frame_mode") or "smart"
    if frame_mode == "otomatis":
        # Klip yang dirender tanpa pernah dibuka di Studio: bingkainya
        # dipilih dari isinya, sama seperti saat klip itu dibuka.
        from .sutradara_ai import jenis_klip_tersimpan
        ctx.progress(0.01, stage="prepare", message="Membaca isi klip (game, wajah, atau tanpa wajah)…")
        try:
            frame_mode = jenis_klip_tersimpan(video_id, source, segments)["mode"]
        except Exception as e:
            log.warning("Jenis klip gagal dibaca, pakai ikut wajah: %s", e)
            frame_mode = "smart"

    # Pelacakan wajah berjalan sebelum encode dan memakan beberapa detik. Tanpa
    # pesan sendiri, pengguna melihat bar diam di 2% tanpa tahu sebabnya.
    if frame_mode == "smart":
        ctx.progress(0.02, stage="reframe", message="Melacak wajah pembicara…")
    elif frame_mode == "gaming":
        ctx.progress(0.02, stage="reframe", message="Mencari kamera wajah pemain…")
    elif frame_mode == "layout":
        frames = (ctx.payload.get("frame_layout") or {}).get("frames") or []
        ctx.progress(0.02, stage="prepare",
                     message=f"Menyusun {len(frames)} bingkai…")
    else:
        ctx.progress(0.02, stage="prepare", message=f"{label}…")

    def on_progress(frac: float) -> None:
        ctx.progress(0.08 + 0.90 * frac, stage="encode",
                     message=f"{label}… {int(frac * 100)}%")

    # Judul dipakai untuk menamai berkas hasilnya. Diambil dari basis data, bukan
    # dari klien: nama berkas ikut terbaca orang saat klipnya diunggah.
    video_row = media_repo.get_video(video_id) or {}

    result = render_clip(
        source_video_path=str(source),
        title=ctx.payload.get("title") or video_row.get("title") or video_id,
        hashtags=ctx.payload.get("hashtags") or [],
        clip_index=ctx.payload.get("clip_index"),
        segments=segments,
        subtitles=subtitles,
        aspect_ratio=ctx.payload.get("aspect_ratio", "9:16"),
        hook_text=ctx.payload.get("hook_text", ""),
        watermark=ctx.payload.get("watermark", ""),
        video_filter=ctx.payload.get("video_filter", "normal"),
        caption_style=style,
        frame_mode=frame_mode,
        frame_layout=ctx.payload.get("frame_layout"),
        frame_keys=ctx.payload.get("frame_keys"),
        media_layers=ctx.payload.get("media_layers"),
        subtitle_kedua=ctx.payload.get("subtitle_kedua"),
        lock_person=ctx.payload.get("lock_person"),
        person_keys=ctx.payload.get("person_keys"),
        title_card=ctx.payload.get("title_card"),
        video_id=video_id,
        on_progress=on_progress,
        should_cancel=lambda: ctx.cancelled,
    )

    ctx.check_cancelled()
    if not result.get("success"):
        raise RenderError(detail=str(result.get("error", ""))[:2000])

    # Unggah otomatis sesuai setelan profil (atau pilihan Studio untuk render
    # ini). Dijalankan di sini, bukan di browser: pemiliknya boleh sudah
    # menutup halaman saat render selesai.
    unggahan = []
    try:
        from .unggah import setelah_render
        unggahan = setelah_render(
            clip_name=result["clip_name"],
            judul=(ctx.payload.get("title") or "").strip() or result["clip_name"].rsplit(".", 1)[0],
            hashtag=ctx.payload.get("hashtags") or [],
            minta=ctx.payload.get("unggah"))
    except Exception as e:
        log.warning("Unggah otomatis tidak bisa diantrekan: %s", e)
        unggahan = [{"target": "-", "galat": str(e)[:200]}]

    pesan = "Klip selesai dirender."
    antre = [u["target"] for u in unggahan if u.get("job_id")]
    if antre:
        pesan += " Diantrekan untuk diunggah ke " + " dan ".join(
            "YouTube" if t == "youtube" else "Google Drive" for t in antre) + "."
    ctx.progress(1.0, stage="done", message=pesan)
    return {
        "unggahan": unggahan,
        "video_id": video_id,
        "clip_name": result["clip_name"],
        "duration": result["duration"],
        "file_size": result.get("file_size"),
        "segments": segments,
        "frame_mode": result.get("frame_mode"),
        "face_coverage": result.get("face_coverage"),
        "web_url": f"/api/media/{result.get('kategori') or 'edited_clips'}/{result['clip_name']}",
    }


# --- Pipeline auto-clip -------------------------------------------------------
# Bobot tiap tahap terhadap progres keseluruhan. Angkanya tetap, tetapi tahap
# transcribe melaporkan kemajuan aslinya, jadi ETA-nya nyata. Ketika video sudah
# punya caption, tahap whisper dilewati dan bar melompat dari 0.55 ke 0.80 —
# itu jujur, dan sekaligus memberi tahu pengguna video mana yang cepat.
STAGES = {
    "resolve":    (0.00, 0.05),
    "download":   (0.05, 0.45),
    "captions":   (0.45, 0.55),
    "transcribe": (0.55, 0.80),
    "analyze":    (0.80, 0.92),
    "gemini":     (0.92, 0.98),
    "persist":    (0.98, 1.00),
}


def _stage_progress(ctx: JobContext, stage: str, frac: float, message: str,
                    paksa: bool = False) -> None:
    lo, hi = STAGES[stage]
    nilai = lo + (hi - lo) * max(0.0, min(1.0, frac))
    # Bar kemajuan tidak pernah mundur. Langkah bantu yang dipakai lebih dari
    # satu tahap — menyiapkan audio dipakai transkripsi DAN perkiraan
    # narasumber — pernah melaporkan dirinya sebagai tahap yang sudah lewat,
    # dan bar melompat dari 82% ke 56%. Bagi yang menunggu, itu terbaca
    # sebagai "prosesnya mengulang dari awal".
    nilai = max(nilai, getattr(ctx, "_puncak", 0.0))
    ctx._puncak = nilai
    ctx.progress(nilai, stage=stage, message=message, paksa=paksa)


# Berapa klip pertama yang bingkainya disusun AI secara otomatis. Bukan semua:
# tiap klip berarti satu panggilan model, dan kuota harian yang sama dipakai
# untuk MEMILIH klip video berikutnya — pekerjaan yang lebih penting daripada
# bingkai klip yang mungkin tidak jadi dirender.
MAKS_BINGKAI_OTOMATIS = 6
NAMA_BINGKAI_OTOMATIS = "ai.bingkai_otomatis"


def bingkai_otomatis() -> bool:
    """Apakah bingkai disusun AI sendiri sesudah auto-klip. Bawaannya mati."""
    from ..repos import settings as settings_repo
    try:
        return (settings_repo.get(NAMA_BINGKAI_OTOMATIS) or "").strip() == "1"
    except Exception:
        return False


def _jadwalkan_bingkai(video_id: str, clips: list[dict], aspect_ratio: str | None) -> int:
    """
    Mengantrekan sutradara bingkai untuk klip yang baru jadi.

    Prioritasnya sengaja paling rendah: pemilik yang menekan "Clip" pada video
    berikutnya harus didahulukan, karena ia sedang menunggu di depan layar
    sementara pekerjaan ini tidak ditunggu siapa pun. Hasilnya dituliskan
    langsung ke klipnya (`terapkan`), jadi saat Studio dibuka bingkainya sudah
    ada — bukan menunggu tombol ditekan satu per satu.
    """
    if not clips or not bingkai_otomatis():
        return 0
    from .jobs import queue

    n = 0
    for c in clips[:MAKS_BINGKAI_OTOMATIS]:
        segmen = [{"start": round(float(s["start"]), 3), "end": round(float(s["end"]), 3)}
                  for s in (c.get("segments") or []) if float(s["end"]) - float(s["start"]) > 0.2]
        if not segmen or not c.get("clip_id"):
            continue
        try:
            queue.enqueue(
                "sutradara",
                {"video_id": video_id, "segments": segmen,
                 "subtitles": c.get("subtitles") or [],
                 "aspect_ratio": aspect_ratio or "9:16", "mesin": "ai",
                 "clip_id": c["clip_id"], "terapkan": True},
                video_id=video_id, priority=900,
                dedupe_key=f"sutradara-oto:{video_id}:{c['clip_id']}")
            n += 1
        except Exception as e:      # satu klip gagal diantre bukan alasan berhenti
            log.warning("Bingkai otomatis tidak bisa diantrekan: %s", str(e)[:200])
    if n:
        log.info("Bingkai AI diantrekan untuk %d klip video %s", n, video_id)
    return n


def run_auto_clip(ctx: JobContext) -> dict:
    """
    payload: {video_id, quality, whisper_model, max_clips, use_gemini}

    Satu job yang bisa ditonton pengguna dari awal sampai akhir:
    metadata -> unduh -> transkrip -> pemilihan momen -> simpan.
    """
    import tempfile
    from pathlib import Path

    from ..config import (
        MAX_TRANSCRIPT_CHARS, get_api_key, get_model_override,
    )
    from ..repos import analyses as analyses_repo
    from ..repos import transcripts as tx_repo
    from .clipmodel import build_clip_payload
    from .heuristics import generate_candidates, validate_and_snap
    from .media import energy_track, probe, zscore
    from .transcript import get_transcript, words_to_sentences

    video_id = ctx.payload["video_id"]
    # Auto-clip SELALU mengambil yang terbaik kecuali diminta lain.
    #
    # Bukan pilihan gaya. Keluarannya 1080x1920, dan jendela 9:16 yang dipotong
    # dari sumber 16:9 hanya selebar 9/16 tingginya — dari 720p itu berarti
    # 405x720 yang lalu diregangkan hampir tiga kali lipat. Detail yang tidak
    # pernah terekam tidak bisa dikembalikan filter apa pun, jadi resolusi
    # sumber adalah plafon kualitas seluruh klip, dan satu-satunya tempat
    # memutuskannya adalah di sini.
    quality = ctx.payload.get("quality") or "Terbaik"
    whisper_model = ctx.payload.get("whisper_model", "base")
    # 0 = biarkan sistem yang menentukan dari durasi video.
    requested_clips = int(ctx.payload.get("max_clips") or 0)
    use_gemini = bool(ctx.payload.get("use_gemini", True))
    # Cari ulang klip dari Studio: video, transkrip, dan label penutur yang
    # sudah ada dipakai lagi; hanya pemilihan momen yang diulang. Analisis
    # sebelumnya dicatat supaya pengguna bisa kembali kepadanya.
    ulang = bool(ctx.payload.get("ulang"))
    sebelumnya = analyses_repo.latest_for_video(video_id) if ulang else None

    # --- 1. Metadata ---------------------------------------------------------
    _stage_progress(ctx, "resolve", 0.2, "Membaca informasi video…")
    from .paths import adalah_impor
    impor = adalah_impor(video_id)
    if impor:
        # Video dari komputer pengguna: YouTube tidak mengenalnya sama sekali.
        # Dulu metadata tetap diminta ke YouTube — "This video is unavailable"
        # — dan impor tidak pernah bisa sampai ke klip.
        berkas = find_local_video(video_id)
        if berkas is None:
            raise AppError("Berkas video impor ini sudah tidak ada di penyimpanan. "
                           "Ambil lagi videonya dari komputer.", code="IMPORT_MISSING", status=404)
        baris = media_repo.get_video(video_id) or {}
        info = {"id": video_id, "title": baris.get("title") or video_id,
                "duration": float(probe(berkas).get("duration") or baris.get("duration") or 0),
                "language": None, "has_captions": False}
    else:
        try:
            info = get_video_info(video_id)
        except YtdlpError as e:
            raise AppError(e.message, code=e.code, status=502, detail=e.original) from e
        media_repo.upsert_video(info)
    title = info.get("title") or video_id
    duration = float(info.get("duration") or 0)
    from .heuristics import auto_clip_count
    max_clips = requested_clips or auto_clip_count(duration)
    ctx.check_cancelled()

    # --- 2. Pastikan video ada di lokal --------------------------------------
    audio_lang = ctx.payload.get("audio_lang") or None
    singkiran = _singkirkan_audio_lain(video_id, audio_lang)
    source = find_local_video(video_id)
    if source is None:
        _stage_progress(ctx, "download", 0.0, f"Mengunduh «{title[:44]}»…")

        def on_dl(frac: float, message: str) -> None:
            ctx.check_cancelled()
            _stage_progress(ctx, "download", frac, message,
                            paksa=not message.startswith("Mengunduh"))

        # Jalur pita dibagi beberapa unduhan saja; yang menunggu di sini tidak
        # menahan pekerjaan lain yang tidak perlu mengunduh apa pun.
        with ctx.giliran_unduh(lambda: _stage_progress(
                ctx, "download", 0.0,
                "Menunggu giliran mengunduh — unduhan lain sedang berjalan…",
                paksa=True)):
            try:
                result = download_youtube_media(video_id, quality, on_progress=on_dl,
                                                audio_lang=audio_lang)
            except BaseException:
                _selesaikan_singkiran(singkiran, False)
                raise
        _selesaikan_singkiran(singkiran, bool(result.get("success")))
        if not result.get("success"):
            raise AppError(result.get("error", "Pengunduhan gagal."),
                           code=result.get("code", "DOWNLOAD_FAILED"), status=502)
        media_repo.record_download(video_id, result)
        source = Path(result["file_path"])
    else:
        _stage_progress(ctx, "download", 1.0,
                        "Video dari komputer siap dibaca." if impor
                        else "Video sudah tersedia di penyimpanan lokal.")

    # Unduhan berjalan bersamaan dengan video lain; mulai dari sini pekerjaan
    # berat (salinan analisis, Whisper, pelacakan wajah) bergiliran satu per
    # satu dengan render, seperti sebelumnya.
    ctx.giliran_cpu(lambda: _stage_progress(
        ctx, "download", 1.0,
        ("Video dari komputer siap" if impor else "Video sudah terunduh")
        + " — menunggu giliran analisis (video lain sedang diproses)…",
        paksa=True))

    # Salinan analisis dimulai SEKARANG, di latar, sementara transkrip dan
    # pemilihan klip berjalan. Begitu pengguna membuka Studio, pelacakan wajah
    # dan gerakan sudah membaca salinan 1280 px, bukan sumber 4K-nya.
    from .proksi import siapkan as _siapkan_proksi
    _siapkan_proksi(source)

    if not duration:
        duration = float(probe(source).get("duration") or 0)
    ctx.check_cancelled()

    # --- 3. Transkrip --------------------------------------------------------
    _stage_progress(ctx, "captions", 0.2, "Mencari transkrip…")

    # Audio disimpan per sumber (services/suara.py), bukan di folder sementara:
    # mengekstraknya berarti membaca seluruh berkas video, dan "Deteksi ulang"
    # nanti membutuhkan audio yang sama.
    from . import suara
    audio_path = ""
    transcript = None
    try:
        # Audio hanya diekstrak bila benar-benar dibutuhkan — ekstraksi mahal.
        def need_audio(tahap: str = "transcribe", bagian: float = 0.02) -> str:
            nonlocal audio_path
            if not audio_path:
                if not suara.ada(source):
                    _stage_progress(ctx, tahap, bagian, "Menyiapkan audio…")
                audio_path = suara.siapkan(source) or ""
                if not audio_path:
                    raise AppError("Audio video ini tidak bisa dibaca.",
                                   code="AUDIO_FAILED", status=500)
            return audio_path

        from .captions import fetch_youtube_captions
        from ..config import get_caption_langs
        tersimpan = tx_repo.get_best(video_id) if ulang else None
        # Transkrip caption tersimpan dalam bahasa yang BUKAN bahasa video
        # adalah sisa aturan lama yang meminta bahasa Indonesia lebih dulu —
        # terukur pada video MrBeast: caption Indonesia tulisan manusia untuk
        # video berbahasa Inggris. Diambil ulang, bukan dipakai lagi. Transkrip
        # Whisper tidak disentuh: ia memang menyalin suara yang ada di berkas.
        bahasa_video = (info.get("language") or "").split("-")[0].lower()
        if (tersimpan and bahasa_video
                and str(tersimpan.get("source", "")).startswith("youtube")
                and (tersimpan.get("language") or "").split("-")[0].lower() != bahasa_video):
            log.info("Transkrip tersimpan berbahasa %s, video berbahasa %s — diambil ulang",
                     tersimpan.get("language"), bahasa_video)
            tersimpan = None
        if tersimpan and tersimpan.get("words") and tersimpan.get("sentences"):
            transcript = {"words": tersimpan["words"], "source": tersimpan["source"],
                          "language": tersimpan.get("language")}
        else:
            tersimpan = None
            # Bahasa video ikut dikirim: tanpa itu caption diminta dalam
            # bahasa pilihan lebih dulu, dan YouTube menerjemahkannya sendiri.
            # Video impor tidak punya subtitle YouTube: langsung ke Whisper.
            transcript = None if impor else fetch_youtube_captions(
                video_id, get_caption_langs(), asli=info.get("language"))

        if tersimpan:
            _stage_progress(ctx, "captions", 1.0,
                            f"Memakai transkrip tersimpan ({len(transcript['words'])} kata).")
        elif transcript:
            _stage_progress(ctx, "captions", 1.0,
                            f"Transkrip ditemukan ({len(transcript['words'])} kata).")
        else:
            _stage_progress(ctx, "transcribe", 0.0,
                            "Video tidak punya subtitle — menyalin ucapan dengan Whisper…")
            from .whisper import transcribe_audio
            wav = need_audio()
            words, language = transcribe_audio(
                wav, model_size=whisper_model,
                on_progress=lambda f: _stage_progress(
                    ctx, "transcribe", f,
                    f"Menyalin ucapan… {int(f * duration // 60)}:{int(f * duration % 60):02d}"
                    f" dari {int(duration // 60)}:{int(duration % 60):02d}"),
                should_cancel=lambda: ctx.cancelled,
            )
            if words:
                transcript = {"words": words, "language": language, "source": "whisper"}

        ctx.check_cancelled()

        # --- 4. Pemilihan momen ---------------------------------------------
        if not transcript or not transcript["words"]:
            # Jujur: tanpa transkrip, tidak ada subtitle dan tidak ada analisis
            # isi pembicaraan. Sistem lama MENGARANG kalimat di titik ini.
            _stage_progress(ctx, "persist", 0.5, "Video ini tidak punya transkrip.")
            payload = {
                "video_id": video_id, "title": title, "duration": duration,
                "has_transcript": False, "engine": "none", "clips": [],
                "message": "Video ini tidak punya transkrip dan ucapannya tidak bisa "
                           "disalin, jadi klip otomatis tidak bisa disusun. "
                           "Anda masih bisa memotong manual di Studio.",
            }
            analyses_repo.save(video_id=video_id, transcript_id=None, engine="heuristic",
                               model=None, params={"reason": "no_transcript"}, result=payload)
            ctx.progress(1.0, stage="done", message="Selesai tanpa transkrip.")
            return payload

        # Penanda non-ucapan dibuang SEBELUM kalimat disusun, bukan hanya saat
        # subtitle dibentuk. Kalau tidak, "[Tertawa]" tetap ikut masuk ke teks
        # kalimat — dan dari sana menular ke judul otomatis klip, ke kutipan
        # yang dikirim ke Gemini, dan ke ringkasan transkrip yang tersimpan.
        from .clipmodel import strip_non_speech
        words = strip_non_speech(transcript["words"])
        if tersimpan:
            # Kalimat tersimpan, bukan disusun ulang: label penutur dan sidik
            # suara yang tersimpan dikunci pada kalimat-kalimat INI.
            sentences = tersimpan["sentences"]
            stored = tersimpan
        else:
            sentences = words_to_sentences(words)
            tx_repo.save(video_id=video_id, source=transcript["source"],
                         model=whisper_model if transcript["source"] == "whisper" else transcript["language"],
                         language=transcript["language"], words=words, sentences=sentences)
            stored = tx_repo.get_best(video_id)

        _stage_progress(ctx, "analyze", 0.15, "Mengukur energi bicara…")
        # Dari audio tersimpan bila ada: jauh lebih kecil daripada videonya.
        energy = zscore(energy_track(suara.tersimpan(source) or source,
                                     duration=duration or 600))

        # --- Perkiraan penutur ------------------------------------------------
        # Hasilnya menempel di tiap kata sebagai "sp", sehingga setiap baris
        # subtitle nanti bisa diwarnai per orang. Ini PERKIRAAN dari warna suara,
        # bukan pengenalan suara terlatih; `speaker_confident` menyatakan apakah
        # pemisahannya cukup meyakinkan untuk dipercaya.
        speaker_count, speaker_conf, speaker_score = 0, False, None
        speaker_requested = ctx.payload.get("speakers") or None
        lama = (sebelumnya or {}).get("result") or {}
        label_lama = lama.get("label_kalimat")
        if ulang and not speaker_requested:
            speaker_requested = lama.get("speaker_requested")
        if ulang and label_lama and len(label_lama) == len(sentences):
            # Label hasil deteksi (atau deteksi ulang) pengguna DIPAKAI LAGI.
            # Mengulang pemisahan suara bisa memberi nomor yang berbeda, dan
            # warna tiap orang yang sudah diatur pengguna akan tertukar.
            _stage_progress(ctx, "analyze", 0.3, "Memakai penanda narasumber sebelumnya…")
            for sent, label in zip(sentences, label_lama):
                a, b = sent["wi"]
                for w in words[a:b]:
                    w.pop("sp", None)
                    if label:
                        w["sp"] = int(label)
            speaker_count = int(lama.get("speaker_count") or 0)
            speaker_conf = lama.get("speaker_confident", False)
            speaker_score = lama.get("speaker_score")
        elif ctx.payload.get("diarize", True) and sentences:
            try:
                _stage_progress(ctx, "analyze", 0.3, "Memperkirakan jumlah narasumber…")
                from .diarize import analyze_speakers, label_from_evidence
                from .sutradara import perkiraan_pemain
                jumlah = speaker_requested
                if jumlah is None:
                    # Gameplay berfacecam: jumlah orang dari GAMBAR, bukan suara.
                    # Lihat catatan di sutradara.perkiraan_pemain.
                    jumlah = perkiraan_pemain(source, duration or 0)
                # Satu orang tidak perlu dipisahkan — dan tidak perlu audio.
                dia = analyze_speakers(
                    need_audio("analyze", 0.3) if jumlah != 1 else "",
                    [(x["s"], x["e"]) for x in sentences],
                    speakers=jumlah,
                )
                speaker_count = dia.speaker_count
                speaker_conf = dia.confident
                speaker_score = dia.separation
                label_akhir = list(dia.labels)
                if jumlah is None and dia.speaker_count > 1:
                    # Tanpa satu wajah pun di video (gameplay tanpa facecam,
                    # kartun), "penutur" kecil hampir pasti efek suara atau
                    # suara tokoh game. Lihat sutradara.tanpa_wajah.
                    from .sutradara import lebur_penutur_kecil, tanpa_wajah
                    if tanpa_wajah(source, duration or 0):
                        label_akhir, baru = lebur_penutur_kecil(label_akhir)
                        if baru < speaker_count:
                            log.info("Video tanpa wajah: %d penutur dilebur jadi %d",
                                     speaker_count, baru)
                            speaker_count = baru
                if speaker_count > 1:
                    for sent, label in zip(sentences, label_akhir):
                        a, b = sent["wi"]
                        for w in words[a:b]:
                            w["sp"] = int(max(0, label))
            except Exception as e:
                # Perkiraan penutur tidak pernah boleh menjatuhkan pipeline.
                log.warning("Perkiraan penutur gagal: %s", str(e)[:200])

        _stage_progress(ctx, "analyze", 0.5, "Mencari momen paling menarik…")
        from .heuristics import DURASI_MAKS
        # Tidak ada lagi preset panjang. Panjang tiap klip ditentukan isinya —
        # lihat catatan panjang di heuristics.py.
        #
        # Kandidat dibuat lebih banyak daripada jatah akhirnya. Kelebihan itu
        # dipakai dua kali: sebagai bahan pilihan yang lebih luas untuk Gemini,
        # dan sebagai cadangan bila model mengembalikan lebih sedikit dari yang
        # diminta.
        candidates = validate_and_snap(
            generate_candidates(sentences, words, energy, duration=duration,
                                max_out=max_clips + 8),
            sentences, duration, max_duration=DURASI_MAKS,
        )
        heuristic_pool = list(candidates)
        engine = "heuristic"
        model_used = None
        ctx.check_cancelled()

        # --- 5. Penajaman oleh Gemini (opsional) -----------------------------
        api_key = ctx.payload.get("api_key") or get_api_key()
        gemini_gagal = None
        if use_gemini and api_key and candidates:
            _stage_progress(ctx, "gemini", 0.2, "Menyusun ulang peringkat dengan Gemini…")
            try:
                from .gemini import refine_candidates
                from .peringkat_model import rantai
                # Tanpa pilihan pengguna, yang dicoba pertama adalah model
                # TERKUAT yang benar-benar bisa dipakai kunci ini — bukan
                # daftar tetap yang ditulis tangan dan cepat tertinggal.
                urutan_model = rantai(api_key, ctx.payload.get("gemini_model")
                                      or get_model_override() or None)
                candidates, model_used = refine_candidates(
                    sentences=sentences, candidates=candidates, video_title=title,
                    api_key=api_key,
                    models=urutan_model,
                    max_clips=max_clips,
                    max_chars=MAX_TRANSCRIPT_CHARS,
                    max_seconds=DURASI_MAKS,
                    kabar=lambda pesan: _stage_progress(ctx, "gemini", 0.3, pesan),
                    batal=ctx.check_cancelled,
                )
                # Pemeriksaan kedua, khusus batas. Gagal di sini tidak
                # membatalkan apa pun: batas dari pemilihan tetap dipakai.
                try:
                    from .gemini import rapikan_batas
                    _stage_progress(ctx, "gemini", 0.75,
                                    "Memeriksa awal dan akhir tiap klip…")
                    diubah = rapikan_batas(
                        sentences=sentences, candidates=candidates, api_key=api_key,
                        models=[model_used] + [m for m in urutan_model if m != model_used],
                        max_seconds=DURASI_MAKS,
                        kabar=lambda pesan: _stage_progress(ctx, "gemini", 0.75, pesan),
                        batal=ctx.check_cancelled,
                    )
                    log.info("Pemeriksaan batas: %d dari %d klip dirapikan",
                             diubah, len(candidates))
                except JobCancelled:
                    raise
                except Exception as e:
                    log.warning("Pemeriksaan batas dilewati: %s", str(e)[:200])
                candidates = validate_and_snap(candidates, sentences, duration,
                                               max_duration=DURASI_MAKS)
                engine = "gemini"
            except JobCancelled:
                raise
            except Exception as e:
                # Kegagalan Gemini TIDAK boleh menjatuhkan pipeline: hasil
                # heuristik tetap valid dan tetap jujur.
                log.warning("Gemini gagal, memakai hasil heuristik: %s", str(e)[:200])
                gemini_gagal = ("Gemini sedang sibuk atau tidak menjawab"
                                if any(x in str(e) for x in ("503", "UNAVAILABLE", "timeout",
                                                             "timed out", "batas waktu"))
                                else "Gemini gagal")
                _stage_progress(ctx, "gemini", 1.0, f"{gemini_gagal} — memakai mesin lokal.")

        # Gemini sering mengembalikan lebih sedikit dari yang diminta — pada
        # video ini 11 dari 19. Sisa jatahnya diisi dari kandidat heuristik
        # terbaik yang belum terpakai, bukan dibiarkan kosong: pada podcast
        # sepanjang satu jam, bahan yang layak masih jauh lebih banyak daripada
        # yang sempat dipilih model. Klip tambahan tetap membawa
        # source "heuristic", jadi asalnya tetap terlihat di UI.
        if len(candidates) < max_clips:
            from .heuristics import _iou
            spare = sorted(heuristic_pool, key=lambda c: c.score, reverse=True)
            for cand in spare:
                if len(candidates) >= max_clips:
                    break
                if all(_iou(cand, k) <= 0.15 for k in candidates):
                    candidates.append(cand)

        # Jatah akhir ditegakkan di satu tempat: tanpa ini, jalur tanpa Gemini
        # akan mengembalikan seluruh kolam kandidat yang sengaja dibuat berlebih.
        #
        # Sekalian tumpang tindih dirapatkan. NMS di dalam generate_candidates
        # membolehkan IoU sampai 0.30 supaya kolamnya beragam; dengan jatah
        # sebelas klip itu jarang terlihat, tapi dengan sembilan belas dua klip
        # bisa berbagi tiga belas detik yang sama dan pengguna melihat dua kartu
        # berisi potongan yang nyaris identik.
        from .heuristics import _iou as _overlap
        final: list = []
        for cand in sorted(candidates, key=lambda c: c.score, reverse=True):
            if len(final) >= max_clips:
                break
            if all(_overlap(cand, k) <= 0.15 for k in final):
                final.append(cand)
        candidates = sorted(final, key=lambda c: c.start)

        # --- 6. Simpan --------------------------------------------------------
        _stage_progress(ctx, "persist", 0.4, "Menyusun hasil…")

        # Gelombang suara untuk linimasa Studio, dihitung SEKARANG dari WAV
        # pendek yang sudah diekstrak — bukan nanti dari berkas videonya.
        # Tanpa ini, membuka Studio untuk video 108 menit di cakram eksternal
        # berarti membaca berkas 3 GB penuh dulu sebelum linimasanya tampil.
        if os.path.exists(audio_path):
            try:
                from ..repos import projects as projects_repo
                from .media import waveform_peaks
                if not projects_repo.get_waveform(video_id, 1200):
                    puncak = waveform_peaks(audio_path, bins=1200, duration=duration)
                    if puncak:
                        projects_repo.save_waveform(video_id, 1200, puncak, duration)
            except Exception as e:                  # tidak boleh menggagalkan pipeline
                log.warning("Gelombang suara tidak disiapkan: %s", str(e)[:160])
        channel = (ctx.payload.get("channel")
                   or (media_repo.get_video(video_id) or {}).get("channel") or "")
        clips = [build_clip_payload(c, words=words, sentences=sentences, index=i,
                                    video_title=title, channel=channel)
                 for i, c in enumerate(candidates, 1)]

        payload = {
            "video_id": video_id,
            "title": title,
            "duration": duration,
            "has_transcript": True,
            "transcript_source": transcript["source"],
            "transcript_words": len(words),
            "engine": engine,
            "model": model_used,
            # Model yang DIMINTA pengguna. Bila berbeda dari `model`, artinya
            # pilihannya gagal (biasanya 429 kuota habis pada model pro) dan
            # sistem memakai cadangan — itu harus terlihat, bukan disembunyikan.
            "model_requested": (ctx.payload.get("gemini_model")
                                or get_model_override() or None),
            "speaker_count": speaker_count,
            "speaker_confident": speaker_conf,
            "speaker_score": speaker_score,
            "speaker_requested": speaker_requested,
            # Gemini diminta tapi gagal: klipnya dari mesin lokal, dan itu
            # harus terbaca, bukan hanya terlihat dari label mesin.
            "gemini_gagal": gemini_gagal,
            # Penutur per kalimat — dibawa oleh "Cari ulang klip" supaya warna
            # tiap orang tidak berubah hanya karena rekomendasinya diganti.
            "label_kalimat": [
                int(words[s_["wi"][0]].get("sp", 0)) if s_["wi"][0] < len(words) else 0
                for s_ in sentences],
            "clips": clips,
            "local_url": f"/api/media/local_downloads/{source.name}",
        }
        if sebelumnya:
            payload["sebelumnya"] = {
                "id": sebelumnya["id"],
                "engine": lama.get("engine"),
                "model": lama.get("model"),
                "clip_count": len(lama.get("clips") or []),
            }
        # Video berbahasa asing (anime Jepang, video Inggris): subtitle aslinya
        # tetap, dan terjemahannya dipasang sebagai subtitle kedua di bawahnya.
        # Kegagalan menerjemahkan tidak boleh menggagalkan klipnya.
        diterjemah = 0
        try:
            from .terjemah import bahasa_otomatis, kedua_untuk_klip
            if bahasa_otomatis() and clips:
                _stage_progress(ctx, "analyze", 0.98, "Menerjemahkan subtitle…", paksa=True)
                from ..config import get_api_key, get_model_override
                from .peringkat_model import rantai
                kunci = get_api_key() or ""
                diterjemah = kedua_untuk_klip(
                    clips, (transcript or {}).get("language") or info.get("language"),
                    api_key=kunci,
                    models=rantai(kunci, get_model_override() or None) if kunci else [],
                    konteks=title[:200])
        except Exception as e:
            log.warning("Terjemahan otomatis gagal: %s", str(e)[:200])
        analyses_repo.save(video_id=video_id,
                           transcript_id=stored["id"] if stored else None,
                           engine=engine, model=model_used,
                           params={"max_clips": max_clips,
                                   "max_clips_requested": requested_clips,
                                   "quality": quality, "ulang": ulang},
                           result=payload)

        n_bingkai = _jadwalkan_bingkai(video_id, clips, ctx.payload.get("aspect_ratio"))

        ctx.progress(1.0, stage="done", message=(
            f"{len(clips)} klip siap ditinjau"
            + (f" (dengan terjemahan)" if diterjemah else "")
            + (f" — bingkai {n_bingkai} klip sedang disusun AI" if n_bingkai else "")
            + (f" — {gemini_gagal}, jadi dipilih mesin lokal. Coba lagi nanti."
               if gemini_gagal
               else f", dipilih {model_used}." if engine == "gemini" and model_used
               else ".")))
        return payload

    finally:
        # Audionya sengaja TIDAK dihapus — "Deteksi ulang" memakainya lagi.
        # Lihat services/suara.py.
        pass


def run_retitle(ctx: JobContext) -> dict:
    """
    payload: {video_id, only_weak}

    Menulis ulang judul dan tagar untuk klip yang sudah ada, tanpa menyentuh
    batas klip, subtitle, atau apa pun yang lain. Klip yang tidak terpilih
    Gemini pada analisis awal keluar dengan judul heuristik — kalimat dari
    klipnya sendiri, akurat dan sama sekali tidak memancing.
    """
    from ..config import get_api_key, get_model_override
    from ..repos import analyses as analyses_repo
    from .gemini import rewrite_titles
    from .peringkat_model import rantai

    video_id = ctx.payload["video_id"]
    only_weak = bool(ctx.payload.get("only_weak", True))

    key = ctx.payload.get("api_key") or get_api_key() or ""
    if not key:
        raise RuntimeError("Kunci Gemini belum diisi di Pengaturan.")

    cached = analyses_repo.latest_for_video(video_id)
    if not cached:
        raise RuntimeError("Video ini belum punya analisis.")
    result = cached["result"]
    clips = result.get("clips") or []

    target = [
        {**c, "index": i}
        for i, c in enumerate(clips)
        if not only_weak or c.get("source") != "gemini" or not (c.get("title") or "").strip()
    ]
    if not target:
        ctx.progress(1.0, stage="done", message="Semua judul sudah ditulis Gemini.")
        return {"changed": 0}

    ctx.progress(0.2, stage="gemini",
                 message=f"Menulis ulang {len(target)} judul…")
    fresh, model = rewrite_titles(
        clips=target, video_title=result.get("title") or "",
        api_key=key,
        models=rantai(key, ctx.payload.get("gemini_model") or get_model_override() or None),
    )

    for idx, row in fresh.items():
        if 0 <= idx < len(clips):
            clips[idx]["title"] = row["title"]
            if row.get("hashtags"):
                clips[idx]["hashtags"] = row["hashtags"]
            clips[idx]["title_source"] = "gemini"

    result["clips"] = clips
    analyses_repo.replace_result(cached["id"], result)
    ctx.progress(1.0, stage="done",
                 message=f"{len(fresh)} judul ditulis ulang oleh {model}.")
    return {"changed": len(fresh), "model": model}


def run_tts_voice(ctx: JobContext) -> dict:
    """
    Mengunduh suara pembaca judul.

    Berkasnya 63 MB dan hanya perlu sekali. Dijadikan job supaya kemajuannya
    terlihat dan supaya ia tidak pernah berjalan diam-diam di tengah render —
    unduhan yang muncul tanpa diminta di tengah pekerjaan lain adalah cara
    tercepat membuat orang tidak percaya pada alat.
    """
    from . import tts

    ctx.progress(0.05, stage="unduh", message="Mengambil suara pembaca judul…")
    if tts.available():
        ctx.progress(1.0, stage="done", message="Suara pembaca sudah ada.")
        return {"available": True, "already": True}

    ok = tts.download_voice(on_progress=lambda name: ctx.progress(
        0.7, stage="unduh", message=f"{name} selesai diunduh."))
    if not ok:
        raise RuntimeError("Gagal mengunduh suara pembaca judul.")
    ctx.progress(1.0, stage="done", message="Suara pembaca siap dipakai.")
    return {"available": tts.available()}


# Berapa klip yang dipindai wajahnya untuk mengumpulkan jangkar.
#
# Bukan semuanya: memindai sembilan belas klip berarti menunggu belasan menit
# untuk pekerjaan yang selama ini selesai dalam dua. Delapan sudah memberi
# 85 sampai 134 potongan bertambatan pada rekaman uji — cukup banyak untuk
# membentuk model suara dan masih menyisakan separuhnya untuk mengujinya.
MAX_ANCHOR_CLIPS = 8


def _bukti_wajah(source, result: dict, sentences: list, ctx) -> Optional[dict]:
    """
    Mengumpulkan bukti "siapa yang terlihat bicara" dari beberapa klip.

    Bukti dikembalikan per KALIMAT dalam linimasa video, bukan per klip, supaya
    bisa langsung dipakai melabeli seluruh rekaman — termasuk bagian yang tidak
    pernah masuk klip mana pun.
    """
    from collections import Counter

    from .reframe import SAMPLE_FPS, plan_reframe, speaking_evidence

    klip = [c for c in (result.get("clips") or [])
            if len({l.get("speaker", 0) for l in (c.get("subtitles") or [])}) > 1]
    if not klip:
        klip = list(result.get("clips") or [])
    klip = klip[:MAX_ANCHOR_CLIPS]
    if not klip:
        return None

    # Kalimat diurut waktu sekali, lalu dicari dengan bisect — mencocokkan tiap
    # sampel ke kalimatnya secara linear akan berarti jutaan perbandingan.
    import bisect
    awal = [float(s["s"]) for s in sentences]

    suara: dict[int, Counter] = {}
    n_orang = 0
    for i, c in enumerate(klip):
        ctx.check_cancelled()
        ctx.progress(0.20 + 0.22 * i / max(1, len(klip)), stage="faces",
                     message=f"Memindai wajah klip {i + 1} dari {len(klip)}…")
        try:
            rencana = plan_reframe(str(source), c["segments"], aspect_ratio="9:16",
                                   track_only=True)
        except Exception as e:                       # noqa: BLE001
            log.info("Pemindaian wajah klip %s gagal: %s", c.get("index"), e)
            continue
        if rencana is None or not rencana.people:
            continue
        n = len(rencana.people[0])
        n_orang = max(n_orang, len(rencana.people))
        ev = speaking_evidence(rencana.people, rencana.people_motion,
                               rencana.people_seen, n)
        # Sampel klip -> detik sumber. Klip bisa tersusun dari beberapa potongan.
        batas, jalan = [], 0.0
        for seg in c["segments"]:
            batas.append((jalan, jalan + float(seg["end"]) - float(seg["start"]),
                          float(seg["start"])))
            jalan = batas[-1][1]
        for t, e in enumerate(ev):
            if e is None:
                continue
            tk = t / SAMPLE_FPS
            for lo, hi, mulai in batas:
                if lo <= tk < hi:
                    detik = mulai + (tk - lo)
                    j = bisect.bisect_right(awal, detik) - 1
                    if 0 <= j < len(sentences) and detik <= float(sentences[j]["e"]) + 0.3:
                        suara.setdefault(j, Counter())[int(e[0])] += float(e[1])
                    break

    if len(suara) < 8 or n_orang < 2:
        log.info("Bukti wajah terlalu sedikit (%d kalimat) — penambatan dilewati",
                 len(suara))
        return None

    span = [None] * len(sentences)
    for j, c in suara.items():
        menang = max(c, key=c.get)
        span[j] = (menang, c[menang] / max(1e-9, sum(c.values())))
    log.info("Bukti wajah terkumpul untuk %d dari %d kalimat, %d orang",
             len(suara), len(sentences), n_orang)
    return {"span": span, "orang": n_orang}


def run_diarize(ctx: JobContext) -> dict:
    """
    payload: {video_id, speakers}

    Menandai ulang penutur pada analisis yang SUDAH ada, tanpa mengunduh atau
    mentranskrip ulang apa pun.

    Ini jalan keluar untuk saat tebakan otomatis meleset. Pemisahan suara
    otomatis harus menebak dua hal sekaligus — berapa orangnya, dan siapa
    bicara kapan — dan yang pertama adalah bagian paling rapuhnya. Ketika
    pengguna sudah tahu jawabannya (ia menonton videonya), memberitahukan
    jumlahnya menghapus separuh masalah dan biasanya memperbaiki sisanya.
    """
    from ..repos import analyses as analyses_repo
    from ..repos import transcripts as tx_repo
    from .clipmodel import rebuild_subtitles_for_segments, strip_non_speech
    from .diarize import analyze_speakers, label_from_evidence
    from . import suara

    video_id = ctx.payload["video_id"]
    speakers = ctx.payload.get("speakers")
    speakers = int(speakers) if speakers else None

    cached = analyses_repo.latest_for_video(video_id)
    if not cached:
        raise AppError("Belum ada analisis untuk video ini.",
                       code="NO_ANALYSIS", status=404)
    stored = tx_repo.get_best(video_id)
    if not stored or not stored.get("words"):
        raise AppError("Video ini belum punya transkrip.",
                       code="NO_TRANSCRIPT", status=409)

    source = find_local_video(video_id)
    if source is None:
        raise AppError("Video sumber belum diunduh.",
                       code="SOURCE_NOT_DOWNLOADED", status=409)

    words = strip_non_speech(stored["words"])
    sentences = stored["sentences"]

    # Audio diambil hanya saat benar-benar dibutuhkan, dan dari simpanan bila
    # ada. Dulu ia diekstrak ulang di awal setiap deteksi ulang — 64 detik untuk
    # video 3,9 GB — termasuk ketika pengguna memilih SATU orang, yang tidak
    # memerlukan audio sama sekali.
    audio_path = ""

    def perlu_audio() -> str:
        nonlocal audio_path
        if not audio_path:
            if not suara.ada(source):
                ctx.progress(0.1, stage="audio",
                             message="Membaca audio video (sekali saja, lalu disimpan)…")
            audio_path = suara.siapkan(source) or ""
            if not audio_path:
                raise AppError("Audio video ini tidak bisa dibaca.",
                               code="AUDIO_FAILED", status=500)
            ctx.check_cancelled()
        return audio_path

    label = (f"Memisahkan {speakers} narasumber…" if speakers
             else "Memperkirakan jumlah narasumber…")

    def dengar(dari: float, sampai: float):
        # Hitungan suara pertama kali bisa satu setengah menit untuk video
        # dua jam; bilah yang diam selama itu terbaca sebagai macet.
        def lapor(bagian: float) -> None:
            ctx.progress(dari + (sampai - dari) * bagian, stage="diarize",
                         message=f"Mendengarkan suara tiap orang… {int(bagian * 100)}%")
            ctx.check_cancelled()
        return lapor

    spans = [(s["s"], s["e"]) for s in sentences]

    # --- Jalur pertama: tambatkan suara ke wajah -------------------------
    #
    # Dicoba lebih dulu karena ia menjawab dua pertanyaan sekaligus. Label
    # yang dihasilkannya ADALAH nomor orang, jadi warna subtitle dan nomor
    # wajah berhenti menjadi dua penomoran berbeda yang kebetulan sama-sama
    # angka. Ia menolak dirinya sendiri bila modelnya gagal uji silang, dan
    # saat itu terjadi jalur lama di bawah yang berjalan.
    dia = None
    if speakers is None:
        # Gameplay berfacecam: jumlah orangnya dibaca dari gambar lebih dulu.
        from .sutradara import perkiraan_pemain
        ctx.progress(0.15, stage="faces", message="Memeriksa apakah ini rekaman gameplay…")
        speakers = perkiraan_pemain(source, float(cached["result"].get("duration") or 0))
        if speakers:
            label = (f"Rekaman gameplay — {speakers} orang di facecam"
                     if speakers > 1 else "Rekaman gameplay — satu pemain")
    if speakers is None:
        ctx.progress(0.20, stage="faces",
                     message="Mencari siapa yang terlihat bicara…")
        bukti = _bukti_wajah(source, cached["result"], sentences, ctx)
        if bukti:
            ctx.progress(0.45, stage="diarize",
                         message="Menambatkan suara ke wajah…")
            dia = label_from_evidence(perlu_audio(), spans, bukti["span"],
                                      bukti["orang"], kemajuan=dengar(0.45, 0.8))

    if dia is None:
        ctx.progress(0.55, stage="diarize", message=label)
        dia = analyze_speakers(perlu_audio() if speakers != 1 else "",
                               spans, speakers=speakers,
                               kemajuan=dengar(0.55, 0.84))

    label_akhir, jumlah_akhir = list(dia.labels), dia.speaker_count
    if speakers is None and jumlah_akhir > 1:
        # Sama seperti analisis pertama: di video tanpa satu wajah pun,
        # "penutur" kecil adalah efek suara atau suara tokoh game.
        from .sutradara import lebur_penutur_kecil, tanpa_wajah
        ctx.progress(0.84, stage="apply", message="Memeriksa apakah ada wajah di video…")
        if tanpa_wajah(source, float(cached["result"].get("duration") or 0)):
            label_akhir, jumlah_akhir = lebur_penutur_kecil(label_akhir)

    ctx.progress(0.85, stage="apply", message="Menerapkan penanda ke subtitle…")
    # Label menempel pada KATA, bukan pada baris subtitle: batas baris bisa
    # berubah setiap kali pengguna menggeser rentang klip, sedangkan katanya
    # tidak. Dari kata, warna baris dihitung ulang kapan pun dibutuhkan.
    for word in words:
        word.pop("sp", None)
    if jumlah_akhir > 1:
        for sentence, speaker in zip(sentences, label_akhir):
            a, b = sentence["wi"]
            for word in words[a:b]:
                word["sp"] = int(max(0, speaker))

    result = dict(cached["result"])
    result["clips"] = [
        {**clip,
         "subtitles": rebuild_subtitles_for_segments(clip["segments"], words)[0]}
        for clip in (result.get("clips") or [])
    ]
    result["speaker_count"] = jumlah_akhir
    result["label_kalimat"] = ([int(max(0, x)) for x in label_akhir]
                               if jumlah_akhir > 1 else [0] * len(sentences))
    result["speaker_confident"] = dia.confident
    result["speaker_score"] = dia.separation
    result["speaker_requested"] = speakers

    analyses_repo.save(
        video_id=video_id, transcript_id=stored["id"],
        engine=result.get("engine", "heuristic"), model=result.get("model"),
        params={"rediarized": True, "speakers": speakers},
        result=result,
    )
    pesan = f"{jumlah_akhir} narasumber ditandai."
    if jumlah_akhir < dia.speaker_count:
        pesan += (f" Video ini tanpa wajah: {dia.speaker_count - jumlah_akhir} suara kecil "
                  "(efek suara, tokoh game) dilebur ke penutur utama.")
    if speakers and 1 < dia.speaker_count < speakers:
        # Jumlahnya tidak diam-diam berbeda dari yang diminta: katakan sebabnya.
        pesan = (f"Diminta {speakers} orang, tapi {speakers - dia.speaker_count} "
                 f"kelompok ternyata suara orang yang sama — {dia.speaker_count} "
                 "narasumber ditandai.")
    ctx.progress(1.0, stage="done", message=pesan)
    return {"speaker_count": dia.speaker_count,
            "speaker_confident": dia.confident,
            "speaker_score": dia.separation,
            "clips": result["clips"]}


# --- Unggah ke Google ---------------------------------------------------------

def run_upload(ctx: JobContext) -> dict:
    """
    payload: {clip_name, target, title, description, tags, privacy, folder_id,
              upload_id}

    Berjalan di lane `upload` yang lebarnya satu, jadi klip naik satu per satu
    berapa pun yang diantrekan sekaligus. Untuk YouTube ada jeda tambahan antar
    unggahan yang berhasil: mengirim selusin video ke satu kanal beruntun adalah
    persis pola yang membuat sebuah kanal ditandai.
    """
    import time as _time

    from ..config import UPLOAD_GAP_SECONDS
    from ..repos import uploads as uploads_repo
    from .google_upload import explain_error, upload_to_drive, upload_to_youtube
    from .paths import safe_media_path

    clip_name = ctx.payload["clip_name"]
    target = ctx.payload.get("target", "drive")
    upload_id = ctx.payload.get("upload_id")

    # Nama berkas datang dari klien, jadi ia tidak boleh dipakai menyusun path
    # begitu saja. safe_media_path menolak apa pun yang keluar dari CLIPS_DIR
    # dan melempar sendiri bila berkasnya tidak ada.
    from . import profil as _profil
    path = safe_media_path(_profil.kategori_klip(_profil.kini()), clip_name)
    size_mb = path.stat().st_size / (1024 * 1024)

    if target == "youtube" and UPLOAD_GAP_SECONDS > 0:
        from . import profil as _profil_u
        elapsed = _time.time() - uploads_repo.last_finished_at("youtube", _profil_u.kini())
        wait = UPLOAD_GAP_SECONDS - elapsed
        while wait > 0:
            ctx.check_cancelled()
            ctx.progress(0.01, stage="spacing",
                         message=f"Memberi jeda antar unggahan… {int(wait)} dtk lagi")
            _time.sleep(min(2.0, wait))
            wait -= 2.0

    label = "YouTube" if target == "youtube" else "Google Drive"
    ctx.progress(0.02, stage="upload",
                 message=f"Mengirim {clip_name} ke {label}… ({size_mb:.1f} MB)")

    def on_progress(frac: float) -> None:
        ctx.progress(0.02 + 0.96 * frac, stage="upload",
                     message=f"Mengirim ke {label}… {int(frac * 100)}%")

    try:
        if target == "youtube":
            result = upload_to_youtube(
                path,
                title=ctx.payload.get("title") or path.stem,
                description=ctx.payload.get("description", ""),
                tags=ctx.payload.get("tags") or [],
                privacy=ctx.payload.get("privacy", "private"),
                on_progress=on_progress,
                should_cancel=lambda: ctx.cancelled,
            )
        else:
            result = upload_to_drive(
                path,
                title=ctx.payload.get("title") or path.name,
                folder_id=ctx.payload.get("folder_id", ""),
                on_progress=on_progress,
                should_cancel=lambda: ctx.cancelled,
            )
    except AppError:
        raise
    except Exception as e:
        message = explain_error(e)
        if upload_id:
            uploads_repo.fail(upload_id, message)
        log.exception("Unggahan ke %s gagal", target)
        raise AppError(message, code="UPLOAD_FAILED", status=502) from e

    if upload_id:
        uploads_repo.finish(upload_id, remote_id=result["remote_id"],
                            remote_url=result["remote_url"])

    ctx.progress(1.0, stage="done", message=f"Terunggah ke {label}.")
    return {
        "clip_name": clip_name,
        "target": target,
        "remote_id": result["remote_id"],
        "remote_url": result["remote_url"],
    }
