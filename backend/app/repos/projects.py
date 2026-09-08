"""
Akses "project klip" — satu video yang sedang atau sudah diproses jadi klip.

Tidak ada tabel `projects` tersendiri untuk ini: sebuah project sepenuhnya
tersusun dari baris yang sudah ada (`jobs` untuk yang sedang berjalan,
`analyses` untuk hasilnya, `videos` untuk metadatanya). Menyimpannya lagi
sebagai tabel keempat berarti tiga sumber kebenaran yang harus dijaga tetap
sinkron — dan yang paling mungkin melenceng justru statusnya.
"""

import json
from typing import Optional

from ..db import get_conn


def _latest_analysis(conn, video_id: str) -> Optional[dict]:
    row = conn.execute(
        """SELECT id, engine, result_json, created_at FROM analyses
           WHERE video_id = ? ORDER BY created_at DESC LIMIT 1""",
        (video_id,),
    ).fetchone()
    if not row:
        return None
    try:
        result = json.loads(row["result_json"] or "{}")
    except json.JSONDecodeError:
        result = {}
    return {"id": row["id"], "engine": row["engine"],
            "created_at": row["created_at"], "result": result}


def _latest_job(conn, video_id: str) -> Optional[dict]:
    row = conn.execute(
        """SELECT id, status, progress, stage, message, error, created_at
           FROM jobs WHERE type = 'auto_clip' AND video_id = ?
           ORDER BY created_at DESC LIMIT 1""",
        (video_id,),
    ).fetchone()
    return dict(row) if row else None


def list_projects(limit: int = 60) -> list[dict]:
    """
    Semua video yang pernah diminta untuk diklip, terbaru dulu.

    Menggabungkan yang sedang berjalan dan yang sudah selesai dalam satu daftar
    supaya halaman Studio bisa menampilkan keduanya sebagai kartu — antrean dan
    hasil di tempat yang sama.
    """
    conn = get_conn()
    rows = conn.execute(
        """SELECT video_id, MAX(created_at) AS last_at FROM (
               SELECT video_id, created_at FROM analyses WHERE video_id IS NOT NULL
               UNION ALL
               SELECT video_id, created_at FROM jobs
                 WHERE type = 'auto_clip' AND video_id IS NOT NULL
           ) GROUP BY video_id ORDER BY last_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()

    projects = []
    for row in rows:
        vid = row["video_id"]
        analysis = _latest_analysis(conn, vid)
        job = _latest_job(conn, vid)
        video = conn.execute("SELECT * FROM videos WHERE id = ?", (vid,)).fetchone()
        result = (analysis or {}).get("result") or {}

        # Urutannya penting. Job yang sedang berjalan menang atas hasil lama:
        # video yang sedang dianalisis ulang harus terlihat sedang berjalan,
        # bukan "siap ditinjau" karena kebetulan punya hasil dari kemarin.
        # Sebaliknya, job yang GAGAL kalah dari hasil tersimpan — analisis lama
        # yang klipnya masih ada tetap bisa dibuka.
        if job and job["status"] in ("queued", "running"):
            status = job["status"]
        elif result.get("clips"):
            status = "done"
        elif job and job["status"] == "failed":
            status = "failed"
        elif analysis:
            status = "empty"
        else:
            status = "unknown"

        projects.append({
            "video_id": vid,
            "title": (video["title"] if video else None) or result.get("title") or vid,
            "channel": video["channel"] if video else None,
            "thumbnail": video["thumbnail_url"] if video else None,
            "duration": (video["duration"] if video else None) or result.get("duration"),
            "status": status,
            "clip_count": len(result.get("clips") or []),
            "engine": result.get("engine") or (analysis or {}).get("engine"),
            "has_transcript": result.get("has_transcript"),
            "updated_at": row["last_at"],
            "job": {
                "id": job["id"], "status": job["status"],
                "progress": job["progress"], "stage": job["stage"],
                "message": job["message"], "error": job["error"],
            } if job else None,
        })
    return projects


def get_waveform(video_id: str, bins: int) -> Optional[list[int]]:
    row = get_conn().execute(
        "SELECT peaks_json, duration FROM waveforms WHERE video_id = ? AND bins = ?",
        (video_id, bins),
    ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["peaks_json"])
    except json.JSONDecodeError:
        return None


def save_waveform(video_id: str, bins: int, peaks: list[int], duration: float) -> None:
    from ..db import now
    get_conn().execute(
        """INSERT INTO waveforms (video_id, bins, peaks_json, duration, created_at)
           VALUES (?,?,?,?,?)
           ON CONFLICT(video_id, bins) DO UPDATE SET
             peaks_json = excluded.peaks_json,
             duration = excluded.duration, created_at = excluded.created_at""",
        (video_id, bins, json.dumps(peaks), duration, now()),
    )
