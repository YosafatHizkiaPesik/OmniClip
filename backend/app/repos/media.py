"""Akses tabel `videos` dan `downloads`."""

import json
from pathlib import Path
from typing import Any, Optional

from ..config import STORAGE_DIR
from ..db import get_conn, now, tx


def rel_to_storage(path: Path | str) -> str:
    return str(Path(path).resolve().relative_to(STORAGE_DIR.resolve()))


def abs_from_storage(rel_path: str) -> Path:
    return STORAGE_DIR / rel_path


# --- videos -------------------------------------------------------------------
def upsert_video(info: dict[str, Any]) -> str:
    """Menyimpan metadata video. `info` memakai bentuk keluaran ytdlp.get_video_info."""
    video_id = info.get("id")
    if not video_id:
        raise ValueError("video butuh id")
    ts = now()
    meta = {k: v for k, v in info.items() if k not in ("description",)}
    with tx() as conn:
        conn.execute(
            """INSERT INTO videos (id, title, channel, channel_id, duration, thumbnail_url,
                                   description, view_count, upload_date, meta_json,
                                   fetched_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 title=excluded.title, channel=excluded.channel, duration=excluded.duration,
                 thumbnail_url=excluded.thumbnail_url, description=excluded.description,
                 view_count=excluded.view_count, upload_date=excluded.upload_date,
                 meta_json=excluded.meta_json, fetched_at=excluded.fetched_at""",
            (video_id, info.get("title") or "Tanpa judul", info.get("channel"),
             info.get("channel_id"), info.get("duration"), info.get("thumbnail"),
             info.get("description", ""), info.get("views"), info.get("upload_date"),
             json.dumps(meta, ensure_ascii=False), ts, ts),
        )
    return video_id


def get_video(video_id: str) -> Optional[dict]:
    row = get_conn().execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    return dict(row) if row else None


# --- downloads ----------------------------------------------------------------
def record_download(video_id: str, result: dict[str, Any], *, kind: str = "video") -> int:
    rel = rel_to_storage(result["file_path"])
    with tx() as conn:
        conn.execute(
            """INSERT INTO downloads (video_id, kind, requested_res, width, height,
                                      vcodec, acodec, rel_path, file_size, duration,
                                      status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,'ready',?)
               ON CONFLICT(rel_path) DO UPDATE SET
                 width=excluded.width, height=excluded.height, vcodec=excluded.vcodec,
                 acodec=excluded.acodec, file_size=excluded.file_size,
                 duration=excluded.duration, status='ready'""",
            (video_id, kind, result.get("requested_resolution"), result.get("width"),
             result.get("height"), result.get("vcodec"), result.get("acodec"), rel,
             result.get("file_size"), result.get("duration"), now()),
        )
        row = conn.execute("SELECT id FROM downloads WHERE rel_path = ?", (rel,)).fetchone()
    return row["id"]


def get_download(download_id: int) -> Optional[dict]:
    row = get_conn().execute("SELECT * FROM downloads WHERE id = ?", (download_id,)).fetchone()
    return dict(row) if row else None


def latest_download_for_video(video_id: str) -> Optional[dict]:
    row = get_conn().execute(
        """SELECT * FROM downloads WHERE video_id = ? AND kind='video' AND status='ready'
           ORDER BY COALESCE(height, 0) DESC, created_at DESC LIMIT 1""",
        (video_id,),
    ).fetchone()
    return dict(row) if row else None


def list_downloads() -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM downloads WHERE status='ready' ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def mark_missing(rel_path: str) -> None:
    get_conn().execute("UPDATE downloads SET status='missing' WHERE rel_path = ?", (rel_path,))


def delete_download_row(rel_path: str) -> None:
    get_conn().execute("DELETE FROM downloads WHERE rel_path = ?", (rel_path,))
