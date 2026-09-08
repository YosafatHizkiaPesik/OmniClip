"""Akses tabel `jobs`."""

import json
import sqlite3
import uuid
from typing import Any, Optional

from ..db import get_conn, now, tx

ACTIVE = ("queued", "running")


def _row_to_dict(row: sqlite3.Row | None) -> Optional[dict]:
    if row is None:
        return None
    d = dict(row)
    d["payload"] = json.loads(d.pop("payload_json") or "{}")
    result_json = d.pop("result_json", None)
    d["result"] = json.loads(result_json) if result_json else None
    return d


def create(
    *,
    type_: str,
    payload: dict,
    lane: str = "cpu",
    priority: int = 100,
    parent_id: str | None = None,
    video_id: str | None = None,
    dedupe_key: str | None = None,
) -> tuple[str, bool]:
    """
    Membuat job. Mengembalikan (job_id, dibuat_baru).

    Bila `dedupe_key` sudah dipakai job yang masih queued/running, job itu yang
    dikembalikan — inilah yang mencegah analisis mahal berjalan dua kali.
    """
    job_id = uuid.uuid4().hex
    ts = now()
    try:
        with tx() as conn:
            conn.execute(
                """INSERT INTO jobs (id, type, status, lane, priority, parent_id,
                                     video_id, dedupe_key, payload_json, created_at)
                   VALUES (?,?,'queued',?,?,?,?,?,?,?)""",
                (job_id, type_, lane, priority, parent_id, video_id, dedupe_key,
                 json.dumps(payload, ensure_ascii=False), ts),
            )
        return job_id, True
    except sqlite3.IntegrityError:
        # Bentrok dengan indeks unik parsial pada dedupe_key.
        row = get_conn().execute(
            f"""SELECT id FROM jobs
                WHERE dedupe_key = ? AND status IN {ACTIVE}
                ORDER BY created_at DESC LIMIT 1""",
            (dedupe_key,),
        ).fetchone()
        if row:
            return row["id"], False
        raise


def get(job_id: str) -> Optional[dict]:
    return _row_to_dict(get_conn().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def children(job_id: str) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM jobs WHERE parent_id = ? ORDER BY created_at", (job_id,)
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def claim_next(lane: str) -> Optional[dict]:
    """Mengambil satu job antre pada lane tertentu dan menandainya running (atomik)."""
    with tx() as conn:
        row = conn.execute(
            """SELECT * FROM jobs WHERE status = 'queued' AND lane = ?
               ORDER BY priority ASC, created_at ASC LIMIT 1""",
            (lane,),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            """UPDATE jobs SET status='running', started_at=?, attempts=attempts+1
               WHERE id = ?""",
            (now(), row["id"]),
        )
    return get(row["id"])


def update_progress(job_id: str, *, progress: float | None = None, stage: str | None = None,
                    message: str | None = None, eta_seconds: float | None = None) -> None:
    sets, args = [], []
    if progress is not None:
        sets.append("progress = ?"); args.append(max(0.0, min(1.0, progress)))
    if stage is not None:
        sets.append("stage = ?"); args.append(stage)
    if message is not None:
        sets.append("message = ?"); args.append(message)
    if eta_seconds is not None:
        sets.append("eta_seconds = ?"); args.append(eta_seconds)
    if not sets:
        return
    args.append(job_id)
    get_conn().execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", args)


def finish(job_id: str, *, status: str, result: Any = None,
           error: str | None = None, error_code: str | None = None) -> None:
    get_conn().execute(
        """UPDATE jobs SET status=?, result_json=?, error=?, error_code=?,
                           finished_at=?, progress = CASE WHEN ?='done' THEN 1.0 ELSE progress END
           WHERE id = ?""",
        (status, json.dumps(result, ensure_ascii=False) if result is not None else None,
         error, error_code, now(), status, job_id),
    )


def request_cancel(job_id: str) -> bool:
    """Job antre dibatalkan langsung; job berjalan ditandai lewat event di JobQueue."""
    with tx() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None or row["status"] not in ACTIVE:
            return False
        if row["status"] == "queued":
            conn.execute(
                "UPDATE jobs SET status='cancelled', finished_at=? WHERE id = ?",
                (now(), job_id),
            )
    return True


def recover_interrupted() -> int:
    """
    Dipanggil saat startup. Job yang masih 'running' berarti proses sebelumnya
    mati di tengah jalan — tandai gagal, jangan biarkan menggantung selamanya.
    Job 'queued' dibiarkan agar dijalankan ulang oleh dispatcher.
    """
    with tx() as conn:
        cur = conn.execute(
            """UPDATE jobs SET status='failed', error='Proses backend berhenti di tengah pekerjaan.',
                               error_code='INTERRUPTED', finished_at=?
               WHERE status='running'""",
            (now(),),
        )
        return cur.rowcount


def recent(limit: int = 50) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def active() -> list[dict]:
    rows = get_conn().execute(
        f"SELECT * FROM jobs WHERE status IN {ACTIVE} ORDER BY created_at"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]
