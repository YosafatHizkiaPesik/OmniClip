"""
Bentuk data klip yang dipakai bersama backend dan frontend.

Keputusan penting: sebuah klip adalah DAFTAR SEGMEN, bukan sepasang
start/end tunggal. Ini memungkinkan pengguna menggabungkan menit 10 dengan
menit 50 menjadi satu klip — sistem akan memotong tiap bagian lalu
menyambungnya. Klip hasil AI hampir selalu punya satu segmen; segmen kedua dan
seterusnya muncul saat pengguna mengedit.
"""

import re
import uuid
from typing import Any, Optional

from .captions import Word
from .heuristics import Candidate, REASON_LABELS
from .transcript import Sentence


def new_clip_id() -> str:
    return uuid.uuid4().hex[:12]


# --- Penanda non-ucapan --------------------------------------------------------
# Caption otomatis YouTube dan Whisper sama-sama menyisipkan penanda suara yang
# BUKAN ucapan: "[Musik]", "[Tertawa]", "[Tepuk tangan]", "(applause)", "♪".
# Penanda itu berguna untuk pembaca tunarungu di pemutar YouTube, tapi pada klip
# vertikal ia muncul sebagai baris subtitle utuh yang tidak ada yang
# mengucapkannya — dan ikut memakan jatah baris di layar.
_BRACKETED = re.compile(r"[\[\(（【][^\]\)）】]*[\]\)）】]")
_OPENERS = "[(（【"
_CLOSERS = "])）】"
# Tanda musik dan penanda ganti pembicara gaya broadcast ('>>').
_STRIP_CHARS = " \t♪♫♬>-–—"


def strip_non_speech(words: list[Word]) -> list[Word]:
    """
    Membuang penanda non-ucapan dari deretan kata.

    Penanda bisa datang sebagai satu token ("[Tertawa]") atau terpecah menjadi
    beberapa token ("[Tepuk", "tangan]"), tergantung sumber transkripnya. Karena
    itu kurung dihitung sebagai keadaan yang berjalan, bukan dicocokkan per
    token: begitu sebuah kurung terbuka, semua kata dibuang sampai ia tertutup.
    """
    out: list[Word] = []
    depth = 0

    for w in words:
        token = (w.get("w") or "").strip()
        if not token:
            continue

        if depth > 0:
            depth += sum(token.count(c) for c in _OPENERS)
            depth -= sum(token.count(c) for c in _CLOSERS)
            depth = max(0, depth)
            continue

        core = _BRACKETED.sub("", token)
        opens = sum(core.count(c) for c in _OPENERS)
        closes = sum(core.count(c) for c in _CLOSERS)
        if opens > closes:
            depth = opens - closes
            continue

        core = core.strip(_STRIP_CHARS)
        if not core:
            continue
        out.append({**w, "w": core})

    return out


def sanitize_caption_lines(lines: list[dict]) -> list[dict]:
    """
    Membersihkan baris subtitle yang SUDAH tersimpan.

    Analisis yang dijalankan sebelum penyaringan ini ada tetap menyimpan
    "[Musik]" di dalam hasilnya. Membersihkannya saat dibaca berarti project
    lama ikut membaik tanpa perlu dianalisis ulang.
    """
    out: list[dict] = []
    for line in lines:
        words = line.get("words") or []
        if words:
            kept = strip_non_speech(words)
            if not kept:
                continue
            out.append({**line, "words": kept,
                        "text": " ".join(w["w"] for w in kept).strip(),
                        "start": kept[0]["s"], "end": kept[-1]["e"]})
            continue
        text = _BRACKETED.sub("", line.get("text") or "").strip(_STRIP_CHARS)
        if text:
            out.append({**line, "text": text})
    return out


def slice_words(words: list[Word], start: float, end: float) -> list[Word]:
    """Kata yang jatuh di dalam sebuah rentang waktu."""
    return [w for w in words if w["e"] > start and w["s"] < end]


def words_to_caption_lines(words: list[Word], *, max_words: int = 5,
                           max_chars: int = 30, max_gap: float = 0.45) -> list[dict]:
    """
    Mengelompokkan kata menjadi baris subtitle pendek ala klip vertikal.

    Baris dipecah pada: batas jumlah kata, batas karakter, jeda bicara, atau
    tanda baca akhir kalimat.
    """
    words = strip_non_speech(words)
    lines: list[dict] = []
    buf: list[Word] = []

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        # Satu baris bisa memuat kata dari dua penutur bila giliran berganti di
        # tengah baris; yang dipakai adalah yang terbanyak, karena satu baris
        # hanya punya satu warna.
        labels = [w["sp"] for w in buf if "sp" in w]
        speaker = max(set(labels), key=labels.count) if labels else 0
        lines.append({
            "start": buf[0]["s"],
            "end": buf[-1]["e"],
            "text": " ".join(w["w"] for w in buf).strip(),
            "speaker": speaker,
            "words": [{"w": w["w"], "s": w["s"], "e": w["e"]} for w in buf],
        })
        buf = []

    for i, w in enumerate(words):
        buf.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        chars = sum(len(x["w"]) + 1 for x in buf)
        if (len(buf) >= max_words
                or chars >= max_chars
                or w["w"].endswith((".", "!", "?", "…"))
                or (nxt and nxt["s"] - w["e"] > max_gap)
                or nxt is None):
            flush()
    flush()
    return lines


def rebase_segments(segments: list[dict]) -> list[dict]:
    """
    Menghitung offset setiap segmen pada linimasa klip hasil gabungan.

    Segmen kedua yang aslinya dari menit 50 akan muncul tepat setelah segmen
    pertama pada klip jadinya, jadi subtitle harus digeser sesuai.
    """
    out: list[dict] = []
    offset = 0.0
    for seg in segments:
        dur = max(0.0, float(seg["end"]) - float(seg["start"]))
        out.append({"start": float(seg["start"]), "end": float(seg["end"]),
                    "offset": round(offset, 3), "duration": round(dur, 3)})
        offset += dur
    return out


def build_clip_payload(
    candidate: Candidate,
    *,
    words: list[Word],
    sentences: list[Sentence],
    index: int,
) -> dict[str, Any]:
    """Mengubah kandidat heuristik menjadi klip yang siap dikirim ke UI."""
    segments = [{"start": round(candidate.start, 3), "end": round(candidate.end, 3)}]

    # `subtitles` memakai linimasa KLIP (mulai dari 0) karena itulah yang dipakai
    # pemutar preview dan file ASS saat render. `words` tetap memakai linimasa
    # video asli supaya editor bisa menghitung ulang subtitle ketika pengguna
    # menggeser batas klip atau menambah segmen dari menit lain.
    clip_subtitles, _ = rebuild_subtitles_for_segments(segments, words)
    clip_words = slice_words(words, candidate.start, candidate.end)

    return {
        "clip_id": new_clip_id(),
        "index": index,
        "segments": segments,
        # Dipertahankan agar kode lama yang membaca satu rentang tetap jalan.
        "start_seconds": segments[0]["start"],
        "end_seconds": segments[-1]["end"],
        "duration": round(candidate.duration, 2),
        # Skor ditampilkan 0-100 tapi berasal dari perhitungan nyata 0-1.
        "score": round(candidate.score * 100, 1),
        "score_breakdown": candidate.breakdown,
        "reasons": [REASON_LABELS.get(k, k) for k in candidate.reason_keys],
        "reason_keys": candidate.reason_keys,
        "hook_text": candidate.hook_text,
        # Field berikut hanya terisi bila Gemini ikut menajamkan hasil. UI
        # membedakan alasan terukur (reasons) dari tulisan model (ai_reason).
        "title": getattr(candidate, "suggested_title", "") or "",
        "hashtags": getattr(candidate, "hashtags", []) or [],
        "ai_reason": getattr(candidate, "gemini_reason", "") or "",
        "transcript_text": candidate.text,
        "subtitles": clip_subtitles,
        "words": [{"w": w["w"], "s": w["s"], "e": w["e"]} for w in clip_words],
        "source": "gemini" if getattr(candidate, "gemini_reason", "") else "heuristic",
    }


def rebuild_subtitles_for_segments(
    segments: list[dict], words: list[Word]
) -> tuple[list[dict], list[Word]]:
    """
    Menyusun ulang subtitle setelah pengguna mengubah batas atau menambah segmen.

    Waktu dikembalikan dalam linimasa KLIP (dimulai dari 0), bukan linimasa
    video asli, karena itulah yang dilihat pemutar dan yang dipakai saat render.
    """
    based = rebase_segments(segments)
    all_lines: list[dict] = []
    all_words: list[Word] = []

    for seg in based:
        seg_words = slice_words(words, seg["start"], seg["end"])
        shift = seg["offset"] - seg["start"]
        shifted: list[Word] = [
            {"w": w["w"],
             "s": round(max(0.0, w["s"] + shift), 3),
             "e": round(max(0.0, w["e"] + shift), 3),
             # Label penutur ikut berpindah bersama katanya, supaya warna per
             # orang tetap benar setelah batas klip digeser atau potongan dari
             # menit lain disambungkan.
             **({"sp": w["sp"]} if "sp" in w else {})}
            for w in seg_words
        ]
        all_words.extend(shifted)
        all_lines.extend(words_to_caption_lines(shifted))

    return all_lines, all_words
