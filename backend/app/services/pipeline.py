"""Handler job yang menyusun pekerjaan panjang jadi langkah-langkah terpantau."""

import logging
import os

from ..errors import AppError, RenderError
from ..repos import media as media_repo
from .jobs import JobContext
from .paths import find_local_video
from .ytdlp import YtdlpError, download_youtube_media, get_video_info

log = logging.getLogger("omniclip.pipeline")


def run_download(ctx: JobContext) -> dict:
    """
    payload: {video_id: str, resolution: str}

    Menggantikan endpoint /api/download yang dulu memblokir request selama
    berapa pun lamanya unduhan, tanpa progress dan tanpa cara membatalkan.
    """
    video_id = ctx.payload["video_id"]
    resolution = ctx.payload.get("resolution", "720p")

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
        ctx.progress(0.05 + 0.90 * frac, stage="download", message=message)

    ctx.progress(0.05, stage="download", message=f"Mengunduh «{title[:48]}»…")
    result = download_youtube_media(video_id, resolution, on_progress=on_progress)

    if not result.get("success"):
        raise AppError(result.get("error", "Pengunduhan gagal."),
                       code=result.get("code", "DOWNLOAD_FAILED"), status=502)

    ctx.progress(0.97, stage="persist", message="Menyimpan catatan unduhan…")
    download_id = media_repo.record_download(video_id, result)

    actual = result.get("resolution")
    requested = result.get("requested_resolution")
    note = None
    if actual and requested and actual != requested:
        # Jujur: YouTube tidak selalu punya resolusi yang diminta.
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
        speaker_colors=tuple(style_in.get("speaker_colors")
                             or ("#7CFFB2", "#FFB3C7", "#B39DFF")),
    )

    total = sum(float(s["end"]) - float(s["start"]) for s in segments)
    label = "Merender klip" if len(segments) == 1 else f"Merender {len(segments)} potongan gabungan"
    frame_mode = ctx.payload.get("frame_mode") or "smart"

    # Pelacakan wajah berjalan sebelum encode dan memakan beberapa detik. Tanpa
    # pesan sendiri, pengguna melihat bar diam di 2% tanpa tahu sebabnya.
    if frame_mode == "smart":
        ctx.progress(0.02, stage="reframe", message="Melacak wajah pembicara…")
    else:
        ctx.progress(0.02, stage="prepare", message=f"{label}…")

    def on_progress(frac: float) -> None:
        ctx.progress(0.08 + 0.90 * frac, stage="encode",
                     message=f"{label}… {int(frac * 100)}%")

    result = render_clip(
        source_video_path=str(source),
        segments=segments,
        subtitles=subtitles,
        aspect_ratio=ctx.payload.get("aspect_ratio", "9:16"),
        hook_text=ctx.payload.get("hook_text", ""),
        watermark=ctx.payload.get("watermark", ""),
        video_filter=ctx.payload.get("video_filter", "normal"),
        caption_style=style,
        frame_mode=frame_mode,
        video_id=video_id,
        on_progress=on_progress,
        should_cancel=lambda: ctx.cancelled,
    )

    ctx.check_cancelled()
    if not result.get("success"):
        raise RenderError(detail=str(result.get("error", ""))[:2000])

    ctx.progress(1.0, stage="done", message="Klip selesai dirender.")
    return {
        "video_id": video_id,
        "clip_name": result["clip_name"],
        "duration": result["duration"],
        "file_size": result.get("file_size"),
        "segments": segments,
        "frame_mode": result.get("frame_mode"),
        "face_coverage": result.get("face_coverage"),
        "web_url": f"/api/media/edited_clips/{result['clip_name']}",
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


def _stage_progress(ctx: JobContext, stage: str, frac: float, message: str) -> None:
    lo, hi = STAGES[stage]
    ctx.progress(lo + (hi - lo) * max(0.0, min(1.0, frac)), stage=stage, message=message)


def run_auto_clip(ctx: JobContext) -> dict:
    """
    payload: {video_id, quality, whisper_model, max_clips, use_gemini}

    Satu job yang bisa ditonton pengguna dari awal sampai akhir:
    metadata -> unduh -> transkrip -> pemilihan momen -> simpan.
    """
    import tempfile
    from pathlib import Path

    from ..config import GEMINI_MODELS, MAX_TRANSCRIPT_CHARS, get_env_api_key
    from ..repos import analyses as analyses_repo
    from ..repos import transcripts as tx_repo
    from .clipmodel import build_clip_payload
    from .heuristics import generate_candidates, validate_and_snap
    from .media import energy_track, extract_audio_wav, probe, zscore
    from .transcript import get_transcript, words_to_sentences

    video_id = ctx.payload["video_id"]
    quality = ctx.payload.get("quality", "720p")
    whisper_model = ctx.payload.get("whisper_model", "base")
    # 0 = biarkan sistem yang menentukan dari durasi video.
    requested_clips = int(ctx.payload.get("max_clips") or 0)
    use_gemini = bool(ctx.payload.get("use_gemini", True))

    # --- 1. Metadata ---------------------------------------------------------
    _stage_progress(ctx, "resolve", 0.2, "Membaca informasi video…")
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
    source = find_local_video(video_id)
    if source is None:
        _stage_progress(ctx, "download", 0.0, f"Mengunduh «{title[:44]}»…")

        def on_dl(frac: float, message: str) -> None:
            ctx.check_cancelled()
            _stage_progress(ctx, "download", frac, message)

        result = download_youtube_media(video_id, quality, on_progress=on_dl)
        if not result.get("success"):
            raise AppError(result.get("error", "Pengunduhan gagal."),
                           code=result.get("code", "DOWNLOAD_FAILED"), status=502)
        media_repo.record_download(video_id, result)
        source = Path(result["file_path"])
    else:
        _stage_progress(ctx, "download", 1.0, "Video sudah tersedia di penyimpanan lokal.")

    if not duration:
        duration = float(probe(source).get("duration") or 0)
    ctx.check_cancelled()

    # --- 3. Transkrip --------------------------------------------------------
    _stage_progress(ctx, "captions", 0.2, "Mencari transkrip…")

    tmpdir = tempfile.mkdtemp(prefix=f"omni_{ctx.job_id[:8]}_")
    audio_path = os.path.join(tmpdir, "audio.wav")
    transcript = None
    try:
        # Audio hanya diekstrak bila caption tidak ada — ekstraksi memakan waktu.
        def need_audio() -> str:
            if not os.path.exists(audio_path):
                _stage_progress(ctx, "transcribe", 0.02, "Menyiapkan audio…")
                extract_audio_wav(source, audio_path)
            return audio_path

        from .captions import fetch_youtube_captions
        transcript = fetch_youtube_captions(video_id)

        if transcript:
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
        sentences = words_to_sentences(words)
        tx_repo.save(video_id=video_id, source=transcript["source"],
                     model=whisper_model if transcript["source"] == "whisper" else transcript["language"],
                     language=transcript["language"], words=words, sentences=sentences)
        stored = tx_repo.get_best(video_id)

        _stage_progress(ctx, "analyze", 0.15, "Mengukur energi bicara…")
        energy = zscore(energy_track(source, duration=duration or 600))

        # --- Perkiraan penutur ------------------------------------------------
        # Hasilnya menempel di tiap kata sebagai "sp", sehingga setiap baris
        # subtitle nanti bisa diwarnai per orang. Ini PERKIRAAN dari warna suara,
        # bukan pengenalan suara terlatih; `speaker_confident` menyatakan apakah
        # pemisahannya cukup meyakinkan untuk dipercaya.
        speaker_count, speaker_conf, speaker_score = 0, False, None
        if ctx.payload.get("diarize", True) and sentences:
            try:
                _stage_progress(ctx, "analyze", 0.3, "Memperkirakan jumlah narasumber…")
                from .diarize import analyze_speakers
                wav = need_audio()
                dia = analyze_speakers(
                    wav, [(x["s"], x["e"]) for x in sentences],
                    speakers=ctx.payload.get("speakers") or None,
                )
                speaker_count = dia.speaker_count
                speaker_conf = dia.confident
                speaker_score = dia.separation
                if dia.speaker_count > 1:
                    for sent, label in zip(sentences, dia.labels):
                        a, b = sent["wi"]
                        for w in words[a:b]:
                            w["sp"] = int(max(0, label))
            except Exception as e:
                # Perkiraan penutur tidak pernah boleh menjatuhkan pipeline.
                log.warning("Perkiraan penutur gagal: %s", str(e)[:200])

        _stage_progress(ctx, "analyze", 0.5, "Mencari momen paling menarik…")
        from .heuristics import LENGTH_PRESETS
        preset = LENGTH_PRESETS.get(ctx.payload.get("clip_length") or "medium",
                                    LENGTH_PRESETS["medium"])
        # Kandidat dibuat lebih banyak daripada jatah akhirnya. Kelebihan itu
        # dipakai dua kali: sebagai bahan pilihan yang lebih luas untuk Gemini,
        # dan sebagai cadangan bila model mengembalikan lebih sedikit dari yang
        # diminta.
        candidates = validate_and_snap(
            generate_candidates(sentences, words, energy, duration=duration,
                                target=preset["target"], ideal=preset["ideal"],
                                max_out=max_clips + 8),
            sentences, duration, max_duration=preset["max"],
        )
        heuristic_pool = list(candidates)
        engine = "heuristic"
        model_used = None
        ctx.check_cancelled()

        # --- 5. Penajaman oleh Gemini (opsional) -----------------------------
        api_key = ctx.payload.get("api_key") or get_env_api_key()
        if use_gemini and api_key and candidates:
            _stage_progress(ctx, "gemini", 0.2, "Menyusun ulang peringkat dengan Gemini…")
            try:
                from .gemini import refine_candidates
                candidates, model_used = refine_candidates(
                    sentences=sentences, candidates=candidates, video_title=title,
                    api_key=api_key, models=GEMINI_MODELS, max_clips=max_clips,
                    max_chars=MAX_TRANSCRIPT_CHARS,
                    max_seconds=preset["max"],
                    model_override=ctx.payload.get("gemini_model") or None,
                )
                candidates = validate_and_snap(candidates, sentences, duration,
                                               max_duration=preset["max"])
                engine = "gemini"
            except Exception as e:
                # Kegagalan Gemini TIDAK boleh menjatuhkan pipeline: hasil
                # heuristik tetap valid dan tetap jujur.
                log.warning("Gemini gagal, memakai hasil heuristik: %s", str(e)[:200])
                _stage_progress(ctx, "gemini", 1.0, "Gemini tidak tersedia — memakai mesin lokal.")

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
        clips = [build_clip_payload(c, words=words, sentences=sentences, index=i)
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
            "model_requested": ctx.payload.get("gemini_model") or None,
            "speaker_count": speaker_count,
            "speaker_confident": speaker_conf,
            "speaker_score": speaker_score,
            "clips": clips,
            "local_url": f"/api/media/local_downloads/{source.name}",
        }
        analyses_repo.save(video_id=video_id,
                           transcript_id=stored["id"] if stored else None,
                           engine=engine, model=model_used,
                           params={"max_clips": max_clips,
                                   "max_clips_requested": requested_clips,
                                   "quality": quality},
                           result=payload)

        ctx.progress(1.0, stage="done", message=f"{len(clips)} klip siap ditinjau.")
        return payload

    finally:
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            os.rmdir(tmpdir)
        except OSError:
            pass
