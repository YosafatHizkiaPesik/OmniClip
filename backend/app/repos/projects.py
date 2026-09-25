"""
Akses "project klip" — satu video yang sedang atau sudah diproses jadi klip.

Tidak ada tabel `projects` tersendiri untuk ini: sebuah project sepenuhnya
tersusun dari baris yang sudah ada (`jobs` untuk yang sedang berjalan,
`analyses` untuk hasilnya, `videos` untuk metadatanya). Menyimpannya lagi
sebagai tabel keempat berarti tiga sumber kebenaran yang harus dijaga tetap
sinkron — dan yang paling mungkin melenceng justru statusnya.
"""

import json
import time
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
        """SELECT id, status, progress, stage, message, error, created_at,
                  started_at, eta_seconds, mulai_setelah
           FROM jobs WHERE type = 'auto_clip' AND video_id = ?
           ORDER BY created_at DESC LIMIT 1""",
        (video_id,),
    ).fetchone()
    return dict(row) if row else None


def _ringkasan_analisis(conn, video_id: str) -> Optional[dict]:
    """
    Hanya kolom yang dibutuhkan kartu proyek — TANPA mengurai JSON-nya.

    `_latest_analysis` mengurai seluruh hasil analisis, dan hasil itu memuat
    setiap klip beserta seluruh baris subtitle dan kata-katanya: terukur 50 KB
    sampai 343 KB per proyek, sepuluh megabita untuk lima puluh dua analisis di
    basis data ini. Daftar proyek hanya perlu judul, durasi, mesin, dan BERAPA
    klipnya — jadi versi lama membayar dua megabita penguraian JSON setiap kali
    halaman Partitur dibuka, untuk empat angka.

    SQLite bisa membaca ke dalam JSON-nya sendiri (`json_extract`), jadi
    penguraian itu tidak pernah perlu terjadi di Python.
    """
    row = conn.execute(
        """SELECT id, engine, created_at,
                  json_extract(result_json, '$.title')          AS j_title,
                  json_extract(result_json, '$.duration')       AS j_duration,
                  json_extract(result_json, '$.engine')         AS j_engine,
                  json_extract(result_json, '$.has_transcript') AS j_has_tx,
                  json_extract(result_json, '$.gemini_gagal')    AS j_gagal,
                  json_extract(result_json, '$.sumber_rendah')   AS j_rendah,
                  json_array_length(json_extract(result_json, '$.clips')) AS j_clips
             FROM analyses
            WHERE video_id = ? ORDER BY created_at DESC LIMIT 1""",
        (video_id,),
    ).fetchone()
    if not row:
        return None
    # Bentuknya dibuat sama dengan `_latest_analysis` supaya pemanggilnya tidak
    # perlu tahu bedanya.
    return {
        "id": row["id"], "engine": row["engine"], "created_at": row["created_at"],
        "result": {
            "title": row["j_title"],
            "duration": row["j_duration"],
            "engine": row["j_engine"],
            # SQLite menyimpan boolean sebagai 0/1; kartunya mengharapkan bool.
            "has_transcript": (None if row["j_has_tx"] is None
                               else bool(row["j_has_tx"])),
            # Bukan daftar klipnya, hanya panjangnya: itu saja yang dipakai.
            "clips": [None] * (row["j_clips"] or 0),
            # Kenapa mesinnya lokal. Ikut di sini, bukan hanya di analisis
            # lengkap, karena justru di kartu proyek label "mesin lokal"
            # muncul tanpa sebab yang bisa ditebak siapa pun.
            "gemini_gagal": row["j_gagal"],
            # Sumber di bawah 1080p. Kartu proyek menyebutkannya, supaya klip
            # yang lunak punya sebab yang terbaca, bukan cuma terasa.
            "sumber_rendah": row["j_rendah"],
        },
    }


def list_projects(limit: int = 60, profil_id: Optional[int] = None) -> list[dict]:
    """
    Semua video yang pernah diminta untuk diklip, terbaru dulu.

    Menggabungkan yang sedang berjalan dan yang sudah selesai dalam satu daftar
    supaya halaman Studio bisa menampilkan keduanya sebagai kartu — antrean dan
    hasil di tempat yang sama.

    Dengan `profil_id`, hanya video milik profil itu (tabel profil_video).
    Analisisnya sendiri tetap dipakai bersama antar profil.
    """
    conn = get_conn()
    saring = ("AND video_id IN (SELECT video_id FROM profil_video WHERE profil_id = ?)"
              if profil_id is not None else "")
    args = ((profil_id, profil_id, limit) if profil_id is not None else (limit,))
    rows = conn.execute(
        f"""SELECT video_id, MAX(created_at) AS last_at FROM (
               SELECT video_id, created_at FROM analyses WHERE video_id IS NOT NULL {saring}
               UNION ALL
               SELECT video_id, created_at FROM jobs
                 WHERE type = 'auto_clip' AND video_id IS NOT NULL {saring}
           ) GROUP BY video_id ORDER BY last_at DESC LIMIT ?""",
        args,
    ).fetchall()

    projects = []
    for row in rows:
        vid = row["video_id"]
        analysis = _ringkasan_analisis(conn, vid)
        job = _latest_job(conn, vid)
        video = conn.execute("SELECT * FROM videos WHERE id = ?", (vid,)).fetchone()
        result = (analysis or {}).get("result") or {}


        # Percobaan ulang yang DIJADWALKAN NANTI bukan pekerjaan yang sedang
        # berjalan, dan tidak boleh menutupi hasil yang sudah ada.
        #
        # Terukur 24 September 2026: sebuah video dengan 11 klip siap tinjau
        # berubah menjadi kartu "Menunggu antrean · Menunggu giliran" dengan
        # tahap "Unduh" menyala, hanya karena sistem menjadwalkan pencarian
        # ulang dengan Gemini dua puluh lima menit lagi. Yang melihatnya wajar
        # menyimpulkan videonya harus diunduh dari nol dan klipnya hilang.
        tunda = float(job["mulai_setelah"] or 0) if job else 0.0
        nanti = bool(job and job["status"] == "queued" and tunda > time.time())

        # Urutannya penting. Job yang sedang berjalan menang atas hasil lama:
        # video yang sedang dianalisis ulang harus terlihat sedang berjalan,
        # bukan "siap ditinjau" karena kebetulan punya hasil dari kemarin.
        # Sebaliknya, job yang GAGAL kalah dari hasil tersimpan: analisis lama
        # yang klipnya masih ada tetap bisa dibuka.
        if nanti and result.get("clips"):
            status = "done"
        elif job and job["status"] in ("queued", "running"):
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
            # Video impor tidak punya sampul YouTube: diambil dari berkasnya.
            "thumbnail": ((video["thumbnail_url"] if video else None)
                          or (f"/api/impor/{vid}/sampul"
                              if video and video["channel"] == "Impor lokal" else None)),
            "duration": (video["duration"] if video else None) or result.get("duration"),
            "status": status,
            "clip_count": len(result.get("clips") or []),
            "engine": result.get("engine") or (analysis or {}).get("engine"),
            # Kenapa mesinnya lokal. Tanpa ini label "heuristik" terlihat
            # seperti pilihan, padahal sering ia akibat Gemini yang sedang
            # sibuk, dan yang melihatnya tidak punya cara menduga bahwa
            # "Cari ulang" beberapa menit lagi akan berhasil.
            "mesin_gagal": result.get("gemini_gagal"),
            "sumber_rendah": result.get("sumber_rendah"),
            "has_transcript": result.get("has_transcript"),
            "updated_at": row["last_at"],
            # Kapan pencarian ulang otomatis akan dimulai, bila ada. Kartunya
            # menyebut ini sebagai keterangan kecil, bukan sebagai keadaan
            # video: klipnya sudah ada dan tetap bisa dibuka sekarang.
            "coba_lagi_pada": tunda if nanti else None,
            "job": {
                "id": job["id"], "status": job["status"],
                "progress": job["progress"], "stage": job["stage"],
                "message": job["message"], "error": job["error"],
                "started_at": job["started_at"], "eta_seconds": job["eta_seconds"],
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
