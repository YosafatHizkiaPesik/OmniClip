"""
Transkripsi lokal dengan faster-whisper (CPU).

Ini adalah jalur CADANGAN. Sebagian besar video YouTube Indonesia populer sudah
punya caption otomatis dengan timing per-kata, dan jalur itu selesai dalam
hitungan detik. Whisper hanya dipakai bila caption benar-benar tidak ada.

PENTING — kenapa audio diproses per potongan:

faster-whisper memuat SELURUH audio ke memori sebagai float32, lalu menghitung
mel-spectrogram untuk keseluruhannya sekaligus. Pada podcast 75 menit itu
membengkak sampai ~4,4 GB RSS dan memicu OOM killer di mesin 7,6 GB — yang juga
menjatuhkan editor karena backend berjalan di dalam cgroup yang sama.

Dengan memotong audio menjadi bagian ~8 menit, memori puncak turun ke ratusan
MB dan tidak lagi bergantung pada panjang video.
"""

import gc
import logging
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from ..config import WHISPER_IDLE_UNLOAD_SECONDS, WHISPER_MODEL_DEFAULT
from ..errors import AppError, JobCancelled

log = logging.getLogger("omniclip.whisper")

_MODEL = None
_MODEL_SIZE: Optional[str] = None
_LOCK = threading.Lock()
_LAST_USED = 0.0

# Perkiraan RSS model saja, supaya peringatan yang diberikan jujur.
MODEL_RAM_MB = {"tiny": 150, "base": 400, "small": 900, "medium": 2600}

# Panjang tiap potongan dan tumpang tindihnya. 8 menit menjaga puncak memori di
# bawah ~1 GB; tumpang tindih 3 detik mencegah kata terpotong di batas potongan.
CHUNK_SECONDS = 480.0
CHUNK_OVERLAP = 3.0

# Batas aman: di bawah ini transkripsi ditolak dengan pesan jelas, bukan
# dibiarkan berjalan sampai kernel membunuh prosesnya.
MIN_FREE_RAM_MB = 900


def available_ram_mb() -> int:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 0


def current_rss_mb() -> int:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 0


def get_model(size: str = WHISPER_MODEL_DEFAULT):
    """Memuat model (int8, CPU) dan menyimpannya agar tetap hangat antar job."""
    global _MODEL, _MODEL_SIZE, _LAST_USED
    from faster_whisper import WhisperModel

    with _LOCK:
        if _MODEL is None or _MODEL_SIZE != size:
            free = available_ram_mb()
            need = MODEL_RAM_MB.get(size, 900)
            if free and free < need + MIN_FREE_RAM_MB:
                raise AppError(
                    f"RAM tidak cukup untuk menyalin ucapan (tersedia {free} MB, "
                    f"butuh sekitar {need + MIN_FREE_RAM_MB} MB). Tutup aplikasi lain "
                    "lalu coba lagi.",
                    code="LOW_MEMORY", status=507,
                )
            log.info("Memuat model Whisper '%s' (int8, CPU), RAM tersedia %d MB…", size, free)
            t0 = time.time()
            _MODEL = WhisperModel(size, device="cpu", compute_type="int8",
                                  cpu_threads=min(4, os.cpu_count() or 4), num_workers=1)
            _MODEL_SIZE = size
            log.info("Model '%s' siap dalam %.1fs", size, time.time() - t0)
        _LAST_USED = time.time()
        return _MODEL


def unload_if_idle(max_idle: float = WHISPER_IDLE_UNLOAD_SECONDS) -> bool:
    """Melepas model agar RAM kembali ke sistem. Dipanggil janitor di lifespan."""
    global _MODEL, _MODEL_SIZE
    with _LOCK:
        if _MODEL is not None and (time.time() - _LAST_USED) > max_idle:
            log.info("Melepas model Whisper '%s' setelah menganggur", _MODEL_SIZE)
            _MODEL = None
            _MODEL_SIZE = None
            gc.collect()
            return True
    return False


def _audio_duration(path: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=60,
        )
        return float((out.stdout or "0").strip() or 0)
    except (subprocess.SubprocessError, ValueError):
        return 0.0


def _slice_audio(src: str, dest: str, start: float, duration: float) -> bool:
    """Memotong WAV tanpa encode ulang."""
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-loglevel", "error",
         "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", src,
         "-c:a", "pcm_s16le", "-ac", "1", "-ar", "16000", dest],
        capture_output=True, text=True, timeout=600,
    )
    return r.returncode == 0 and Path(dest).is_file()


def _transcribe_file(model, path: str, language: Optional[str],
                     time_offset: float,
                     on_segment: Optional[Callable[[float], None]],
                     should_cancel: Optional[Callable[[], bool]]) -> tuple[list[dict], str]:
    """Menyalin satu file audio dan menggeser semua waktunya dengan `time_offset`."""
    segments, info = model.transcribe(
        path,
        language=language,
        beam_size=1,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        # Keduanya bukan pilihan kosmetik: tanpa ini keheningan panjang memicu
        # repetition loop yang memuntahkan frasa sama selama bermenit-menit.
        condition_on_previous_text=False,
    )

    words: list[dict] = []
    for seg in segments:
        if should_cancel is not None and should_cancel():
            raise JobCancelled()
        for w in (seg.words or []):
            text = (w.word or "").strip()
            if not text:
                continue
            start = float(w.start) + time_offset
            words.append({
                "w": text,
                "s": round(start, 3),
                "e": round(max(float(w.end) + time_offset, start + 0.06), 3),
                "p": round(float(getattr(w, "probability", 0.0) or 0.0), 3),
            })
        if on_segment is not None:
            on_segment(float(seg.end))
    return words, (info.language or language or "id")


def _merge_overlap(existing: list[dict], incoming: list[dict], boundary: float) -> list[dict]:
    """
    Menyambung hasil dua potongan yang saling tumpang tindih.

    Kata dari potongan baru yang jatuh sebelum batas sambungan dibuang bila
    sudah ada padanannya di potongan sebelumnya, sehingga kata di daerah
    tumpang tindih tidak muncul dua kali.
    """
    if not existing:
        return list(incoming)

    tail = [w for w in existing if w["e"] >= boundary - CHUNK_OVERLAP - 0.5]
    tail_keys = {(w["w"].lower(), round(w["s"], 1)) for w in tail}

    merged = list(existing)
    for w in incoming:
        if w["s"] < boundary:
            if (w["w"].lower(), round(w["s"], 1)) in tail_keys:
                continue
            if any(abs(w["s"] - t["s"]) < 0.35 and w["w"].lower() == t["w"].lower() for t in tail):
                continue
        merged.append(w)
    return merged


def transcribe_audio(
    wav_path: str,
    *,
    model_size: str = WHISPER_MODEL_DEFAULT,
    language: Optional[str] = "id",
    on_progress: Optional[Callable[[float], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> tuple[list[dict], str]:
    """
    Menyalin audio jadi daftar kata bertimestamp.

    Audio panjang diproses per potongan agar memori puncak tidak ikut tumbuh
    bersama durasi video.
    """
    duration = _audio_duration(wav_path)
    model = get_model(model_size)
    log.info("Transkripsi %.1f menit, RSS sebelum mulai %d MB", duration / 60, current_rss_mb())

    # Video pendek tidak perlu dipotong.
    if duration <= CHUNK_SECONDS * 1.2 or duration <= 0:
        words, lang = _transcribe_file(
            model, wav_path, language, 0.0,
            (lambda end: on_progress(min(1.0, end / duration))) if (on_progress and duration) else None,
            should_cancel,
        )
        log.info("Selesai: %d kata, RSS puncak %d MB", len(words), current_rss_mb())
        return words, lang

    n_chunks = int(duration // CHUNK_SECONDS) + 1
    log.info("Audio dipotong menjadi %d bagian @ %.0f menit", n_chunks, CHUNK_SECONDS / 60)

    all_words: list[dict] = []
    detected = language or "id"
    tmpdir = tempfile.mkdtemp(prefix="omni_whisper_")

    try:
        position = 0.0
        index = 0
        while position < duration:
            if should_cancel is not None and should_cancel():
                raise JobCancelled()

            start = max(0.0, position - (CHUNK_OVERLAP if index else 0.0))
            length = min(CHUNK_SECONDS + (CHUNK_OVERLAP if index else 0.0), duration - start)
            if length <= 0.5:
                break

            piece = os.path.join(tmpdir, f"chunk_{index}.wav")
            if not _slice_audio(wav_path, piece, start, length):
                raise AppError("Gagal memotong audio untuk transkripsi.",
                               code="AUDIO_SLICE_FAILED", status=500)

            def chunk_progress(end_in_chunk: float, _start=start) -> None:
                if on_progress and duration:
                    on_progress(min(1.0, (_start + end_in_chunk) / duration))

            words, lang = _transcribe_file(model, piece, language, start,
                                           chunk_progress, should_cancel)
            detected = lang or detected
            all_words = _merge_overlap(all_words, words, position)

            os.remove(piece)
            # Lepas array audio potongan ini sebelum memuat potongan berikutnya.
            gc.collect()
            log.info("  bagian %d/%d selesai (%d kata, RSS %d MB)",
                     index + 1, n_chunks, len(all_words), current_rss_mb())

            position += CHUNK_SECONDS
            index += 1

        all_words.sort(key=lambda w: w["s"])
        log.info("Transkripsi selesai: %d kata, RSS akhir %d MB",
                 len(all_words), current_rss_mb())
        return all_words, detected

    finally:
        for f in Path(tmpdir).glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass
        gc.collect()
