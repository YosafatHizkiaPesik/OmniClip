"""Riwayat unggahan."""

import time
from typing import Optional

from ..db import get_conn, tx


def create(*, clip_name: str, target: str, title: str, privacy: str,
           job_id: str) -> int:
    with tx() as c:
        cur = c.execute(
            "INSERT INTO uploads(clip_name, target, status, title, privacy, "
            "job_id, created_at) VALUES (?,?,'running',?,?,?,?)",
            (clip_name, target, title, privacy, job_id, time.time()),
        )
        return int(cur.lastrowid)


def attach_job(upload_id: int, job_id: str) -> None:
    with tx() as c:
        c.execute("UPDATE uploads SET job_id=? WHERE id=?", (job_id, upload_id))


def drop(upload_id: int) -> None:
    with tx() as c:
        c.execute("DELETE FROM uploads WHERE id=?", (upload_id,))


def finish(upload_id: int, *, remote_id: str, remote_url: str) -> None:
    with tx() as c:
        c.execute(
            "UPDATE uploads SET status='done', remote_id=?, remote_url=?, "
            "finished_at=? WHERE id=?",
            (remote_id, remote_url, time.time(), upload_id),
        )


def fail(upload_id: int, error: str) -> None:
    with tx() as c:
        c.execute("UPDATE uploads SET status='failed', error=?, finished_at=? "
                  "WHERE id=?", (error[:1000], time.time(), upload_id))


def list_recent(limit: int = 60, clip_name: Optional[str] = None) -> list[dict]:
    sql = "SELECT * FROM uploads"
    args: list = []
    if clip_name:
        sql += " WHERE clip_name = ?"
        args.append(clip_name)
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in get_conn().execute(sql, args)]


def last_finished_at(target: str) -> float:
    """
    Kapan unggahan terakhir ke tujuan ini selesai.

    Dipakai untuk memberi jeda antar unggahan YouTube. Dibaca dari basis data,
    bukan dari variabel dalam memori, supaya jedanya tetap berlaku setelah
    server dinyalakan ulang.
    """
    row = get_conn().execute(
        "SELECT MAX(finished_at) AS t FROM uploads "
        "WHERE target = ? AND status = 'done'", (target,)).fetchone()
    return float(row["t"] or 0.0)
