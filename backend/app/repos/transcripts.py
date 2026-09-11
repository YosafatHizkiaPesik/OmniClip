"""Akses tabel `transcripts`."""

import json
from typing import Optional

from ..db import get_conn, now, tx

# Urutan kualitas: caption tulisan manusia > ASR YouTube > Whisper lokal.
SOURCE_RANK = {"youtube_manual": 3, "whisper": 2, "youtube_asr": 1}


def save(*, video_id: str, source: str, model: str | None, language: str | None,
         words: list[dict], sentences: list[dict]) -> int:
    duration = words[-1]["e"] if words else 0.0
    with tx() as conn:
        conn.execute(
            """INSERT INTO transcripts (video_id, source, model, language, has_words,
                                        words_json, segments_json, duration, created_at)
               VALUES (?,?,?,?,1,?,?,?,?)
               ON CONFLICT(video_id, source, model) DO UPDATE SET
                 words_json=excluded.words_json, segments_json=excluded.segments_json,
                 language=excluded.language, duration=excluded.duration,
                 created_at=excluded.created_at""",
            (video_id, source, model, language,
             json.dumps(words, ensure_ascii=False),
             json.dumps(sentences, ensure_ascii=False),
             duration, now()),
        )
        row = conn.execute(
            "SELECT id FROM transcripts WHERE video_id=? AND source=? AND model IS ?",
            (video_id, source, model),
        ).fetchone()
    return row["id"] if row else 0


def _hydrate(row) -> dict:
    d = dict(row)
    kata = json.loads(d.pop("words_json") or "[]")
    # Takarir resmi kanal berwaktu PER-CUE, bukan per-kata: satu entri memuat
    # kalimat utuh. Dipecah di sini, di pintu keluar penyimpanan, supaya
    # transkrip yang sudah terlanjur tersimpan dalam bentuk itu ikut terbetulkan
    # tanpa harus diunduh ulang — dan supaya setiap pemakainya melihat bentuk
    # yang sama. Pemecahnya aman dijalankan berulang: entri yang memang sudah
    # satu kata dilewati apa adanya.
    from ..services.captions import split_phrases
    d["words"] = split_phrases(kata)
    d["sentences"] = json.loads(d.pop("segments_json") or "[]")
    return d


def get_best(video_id: str) -> Optional[dict]:
    """Mengembalikan transkrip terbaik yang tersimpan untuk sebuah video."""
    rows = get_conn().execute(
        "SELECT * FROM transcripts WHERE video_id = ?", (video_id,)
    ).fetchall()
    if not rows:
        return None
    best = max(rows, key=lambda r: SOURCE_RANK.get(r["source"], 0))
    return _hydrate(best)


def get_for_video(video_id: str) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM transcripts WHERE video_id = ? ORDER BY created_at DESC", (video_id,)
    ).fetchall()
    return [_hydrate(r) for r in rows]


def delete_for_video(video_id: str) -> None:
    get_conn().execute("DELETE FROM transcripts WHERE video_id = ?", (video_id,))
