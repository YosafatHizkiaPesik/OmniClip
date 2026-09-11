"""Akses tabel `analyses` — hasil pemilihan klip yang di-cache per video."""

import json
from typing import Optional

from ..db import get_conn, now, tx


def save(*, video_id: str, transcript_id: Optional[int], engine: str,
         model: Optional[str], params: dict, result: dict) -> int:
    with tx() as conn:
        cur = conn.execute(
            """INSERT INTO analyses (video_id, transcript_id, engine, model,
                                     params_json, result_json, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (video_id, transcript_id, engine, model,
             json.dumps(params, ensure_ascii=False),
             json.dumps(result, ensure_ascii=False), now()),
        )
        return cur.lastrowid


def replace_result(analysis_id: int, result: dict) -> None:
    """
    Menimpa hasil analisis yang sudah tersimpan.

    Dipakai penulisan ulang judul: yang berubah hanya judul dan tagar, jadi
    membuat baris analisis baru berarti menduplikat seluruh transkrip klip demi
    beberapa kalimat — dan meninggalkan versi lama yang membingungkan saat
    daftar analisis dibaca.
    """
    with tx() as conn:
        conn.execute("UPDATE analyses SET result_json = ? WHERE id = ?",
                     (json.dumps(result, ensure_ascii=False), analysis_id))


def _hydrate(row) -> dict:
    d = dict(row)
    d["params"] = json.loads(d.pop("params_json") or "{}")
    d["result"] = json.loads(d.pop("result_json") or "{}")
    return d


def latest_for_video(video_id: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM analyses WHERE video_id = ? ORDER BY created_at DESC LIMIT 1",
        (video_id,),
    ).fetchone()
    return _hydrate(row) if row else None


def get(analysis_id: int) -> Optional[dict]:
    row = get_conn().execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    return _hydrate(row) if row else None


def delete_for_video(video_id: str) -> None:
    get_conn().execute("DELETE FROM analyses WHERE video_id = ?", (video_id,))
