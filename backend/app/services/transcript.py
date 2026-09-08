"""
Orkestrasi transkrip: caption YouTube dulu, faster-whisper sebagai cadangan,
lalu pemecahan menjadi kalimat.

Kalimat adalah unit kerja mesin klip. Semua batas klip dipaksa jatuh di batas
kalimat, sehingga klip tidak pernah dimulai atau berhenti di tengah kata —
artefak paling mencolok dari sistem lama.
"""

import logging
import re
from typing import Optional, TypedDict

from ..config import CAPTION_LANGS, WHISPER_MODEL_DEFAULT
from ..repos import transcripts as tx_repo
from .captions import TranscriptResult, Word, fetch_youtube_captions

log = logging.getLogger("omniclip.transcript")

# Tanda baca akhir kalimat.
TERMINAL_RE = re.compile(r"[.!?…]+[\"'”’)]*$")

# Kata sambung yang menggantung: kalimat yang berakhir di sini terasa terpotong.
DANGLING = {
    "dan", "tapi", "tetapi", "karena", "yang", "atau", "terus", "jadi", "kalau",
    "kalo", "untuk", "dengan", "dari", "ke", "di", "pada", "serta", "namun",
    "sehingga", "supaya", "agar", "bahwa", "adalah", "itu", "ini", "buat",
}


class Sentence(TypedDict):
    s: float
    e: float
    text: str
    wi: tuple[int, int]  # rentang indeks kata [awal, akhir)


def words_to_sentences(
    words: list[Word], *, max_gap: float = 0.65, max_chars: int = 140
) -> list[Sentence]:
    """
    Memecah aliran kata jadi kalimat.

    Pemisah: tanda baca akhir, jeda lebih dari `max_gap`, atau batas panjang.
    Caption ASR YouTube tidak memberi tanda baca sama sekali pada sebagian video,
    jadi aturan jeda yang menanggung sebagian besar kasus.
    """
    if not words:
        return []

    sentences: list[Sentence] = []
    start_idx = 0
    buf: list[str] = []

    def flush(end_idx: int) -> None:
        nonlocal start_idx, buf
        if end_idx <= start_idx:
            return
        text = " ".join(buf).strip()
        if text:
            sentences.append({
                "s": words[start_idx]["s"],
                "e": words[end_idx - 1]["e"],
                "text": text,
                "wi": (start_idx, end_idx),
            })
        start_idx = end_idx
        buf = []

    for i, w in enumerate(words):
        buf.append(w["w"])
        gap_next = (words[i + 1]["s"] - w["e"]) if i + 1 < len(words) else 0.0
        cur_len = sum(len(x) + 1 for x in buf)

        if (TERMINAL_RE.search(w["w"])
                or gap_next > max_gap
                or cur_len >= max_chars
                or i == len(words) - 1):
            flush(i + 1)

    return sentences


def ends_dangling(sentence: Sentence) -> bool:
    """Apakah kalimat berakhir pada kata sambung yang menggantung."""
    last = sentence["text"].split()[-1] if sentence["text"].split() else ""
    return last.lower().strip(".,!?;:\"'") in DANGLING


def get_transcript(
    video_id: str,
    *,
    audio_path: Optional[str] = None,
    whisper_model: str = WHISPER_MODEL_DEFAULT,
    langs=CAPTION_LANGS,
    allow_whisper: bool = True,
    on_progress=None,
    should_cancel=None,
) -> Optional[TranscriptResult]:
    """
    Mengambil transkrip word-level, dengan cache database.

    Urutan: cache -> caption YouTube -> faster-whisper.
    Mengembalikan None bila tidak ada transkrip yang bisa didapat sama sekali —
    pemanggil WAJIB memperlakukan itu sebagai "tidak ada subtitle", bukan
    kesempatan untuk mengarang kalimat.
    """
    cached = tx_repo.get_best(video_id)
    if cached:
        log.info("Transkrip dari cache (%s, %d kata)", cached["source"], len(cached["words"]))
        return {"words": cached["words"], "language": cached["language"], "source": cached["source"]}

    if on_progress:
        on_progress(0.1, "Mencari transkrip di YouTube…")

    result = fetch_youtube_captions(video_id, langs)

    if result is None and allow_whisper and audio_path:
        if on_progress:
            on_progress(0.15, "Video tidak punya subtitle — menyalin ucapan dengan Whisper…")
        from .whisper import transcribe_audio  # impor lambat: model besar

        words, language = transcribe_audio(
            audio_path,
            model_size=whisper_model,
            on_progress=(lambda f: on_progress(0.15 + 0.8 * f, "Menyalin ucapan…")) if on_progress else None,
            should_cancel=should_cancel,
        )
        if words:
            result = {"words": words, "language": language, "source": "whisper"}

    if result is None:
        log.info("Video %s tidak punya transkrip", video_id)
        return None

    sentences = words_to_sentences(result["words"])
    tx_repo.save(
        video_id=video_id,
        source=result["source"],
        model=whisper_model if result["source"] == "whisper" else result["language"],
        language=result["language"],
        words=result["words"],
        sentences=sentences,
    )
    return result
