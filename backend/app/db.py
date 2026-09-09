"""
Koneksi SQLite dan migrasi.

Keputusan: `sqlite3` stdlib di balik modul repository, bukan SQLAlchemy/SQLModel.
Skema ini punya satu penulis, tidak butuh identity map atau lazy loading, dan
ORM justru akan menambah masalah siklus Session-per-thread di worker job —
tepat di tempat bug akan bersembunyi.
"""

import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Iterator

from .config import DB_PATH

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """Koneksi per-thread. Keempat PRAGMA di bawah ini load-bearing."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH), timeout=15.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        # synchronous=NORMAL bukan sekadar optimasi di sini: storage berada di
        # exFAT lewat FUSE, dan dengan synchronous=FULL throughput jatuh dari
        # ~2150 menjadi ~19 insert/detik (terukur).
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        _local.conn = conn
    return conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """Transaksi eksplisit. isolation_level=None mematikan transaksi implisit Python."""
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def now() -> float:
    return time.time()


# Indeks dalam list == nomor versi. Tambahkan migrasi baru di akhir, jangan
# pernah mengubah yang sudah ada.
MIGRATIONS: list[str] = [
    # --- 0: skema awal ---
    """
    CREATE TABLE videos (
      id             TEXT PRIMARY KEY,
      title          TEXT NOT NULL,
      channel        TEXT,
      channel_id     TEXT,
      duration       REAL,
      thumbnail_url  TEXT,
      description    TEXT,
      view_count     INTEGER,
      upload_date    TEXT,
      meta_json      TEXT,
      fetched_at     REAL NOT NULL,
      created_at     REAL NOT NULL
    );

    CREATE TABLE downloads (
      id             INTEGER PRIMARY KEY AUTOINCREMENT,
      video_id       TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
      kind           TEXT NOT NULL CHECK (kind IN ('video','audio')),
      requested_res  TEXT,
      width          INTEGER,
      height         INTEGER,
      fps            REAL,
      vcodec         TEXT,
      acodec         TEXT,
      rel_path       TEXT NOT NULL UNIQUE,
      file_size      INTEGER,
      duration       REAL,
      status         TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('ready','missing')),
      created_at     REAL NOT NULL
    );
    CREATE INDEX idx_downloads_video ON downloads(video_id, created_at DESC);

    CREATE TABLE transcripts (
      id             INTEGER PRIMARY KEY AUTOINCREMENT,
      video_id       TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
      source         TEXT NOT NULL CHECK (source IN ('youtube_manual','youtube_asr','whisper')),
      model          TEXT,
      language       TEXT,
      has_words      INTEGER NOT NULL DEFAULT 0,
      words_json     TEXT NOT NULL,
      segments_json  TEXT NOT NULL,
      duration       REAL,
      created_at     REAL NOT NULL,
      UNIQUE(video_id, source, model)
    );

    CREATE TABLE analyses (
      id             INTEGER PRIMARY KEY AUTOINCREMENT,
      video_id       TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
      transcript_id  INTEGER REFERENCES transcripts(id) ON DELETE SET NULL,
      engine         TEXT NOT NULL CHECK (engine IN ('heuristic','gemini')),
      model          TEXT,
      params_json    TEXT,
      result_json    TEXT NOT NULL,
      created_at     REAL NOT NULL
    );
    CREATE INDEX idx_analyses_video ON analyses(video_id, created_at DESC);

    CREATE TABLE projects (
      id             TEXT PRIMARY KEY,
      video_id       TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
      analysis_id    INTEGER REFERENCES analyses(id) ON DELETE SET NULL,
      name           TEXT,
      state_json     TEXT NOT NULL,
      updated_at     REAL NOT NULL,
      created_at     REAL NOT NULL
    );
    CREATE INDEX idx_projects_recent ON projects(updated_at DESC);

    CREATE TABLE clips (
      id                   TEXT PRIMARY KEY,
      project_id           TEXT REFERENCES projects(id) ON DELETE SET NULL,
      video_id             TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
      title                TEXT,
      start_seconds        REAL NOT NULL,
      end_seconds          REAL NOT NULL,
      aspect_ratio         TEXT NOT NULL,
      score                REAL,
      score_breakdown_json TEXT,
      hook_text            TEXT,
      hashtags_json        TEXT,
      subtitles_json       TEXT,
      style_json           TEXT,
      rel_path             TEXT UNIQUE,
      thumb_rel_path       TEXT,
      file_size            INTEGER,
      render_job_id        TEXT,
      status               TEXT NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending','rendering','ready','failed')),
      error                TEXT,
      created_at           REAL NOT NULL
    );
    CREATE INDEX idx_clips_recent ON clips(created_at DESC);
    CREATE INDEX idx_clips_video  ON clips(video_id, created_at DESC);

    CREATE TABLE jobs (
      id             TEXT PRIMARY KEY,
      type           TEXT NOT NULL,
      status         TEXT NOT NULL
                     CHECK (status IN ('queued','running','done','failed','cancelled')),
      lane           TEXT NOT NULL DEFAULT 'cpu',
      priority       INTEGER NOT NULL DEFAULT 100,
      parent_id      TEXT REFERENCES jobs(id) ON DELETE CASCADE,
      video_id       TEXT,
      dedupe_key     TEXT,
      payload_json   TEXT NOT NULL,
      progress       REAL NOT NULL DEFAULT 0,
      stage          TEXT,
      message        TEXT,
      eta_seconds    REAL,
      result_json    TEXT,
      error          TEXT,
      error_code     TEXT,
      attempts       INTEGER NOT NULL DEFAULT 0,
      created_at     REAL NOT NULL,
      started_at     REAL,
      finished_at    REAL
    );
    CREATE INDEX idx_jobs_dispatch ON jobs(status, lane, priority, created_at);
    CREATE INDEX idx_jobs_recent   ON jobs(created_at DESC);
    -- Jaminan di level DB terhadap pekerjaan mahal yang terduplikasi
    -- (mis. analisis Gemini yang terulang saat user pindah tab lalu kembali).
    CREATE UNIQUE INDEX idx_jobs_dedupe ON jobs(dedupe_key)
      WHERE dedupe_key IS NOT NULL AND status IN ('queued','running');

    CREATE TABLE search_history (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      query        TEXT NOT NULL,
      result_count INTEGER,
      created_at   REAL NOT NULL
    );
    CREATE INDEX idx_search_recent ON search_history(created_at DESC);

    CREATE TABLE watch_history (
      video_id        TEXT PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
      last_position   REAL NOT NULL DEFAULT 0,
      duration        REAL,
      watch_count     INTEGER NOT NULL DEFAULT 1,
      last_watched_at REAL NOT NULL
    );
    CREATE INDEX idx_watch_recent ON watch_history(last_watched_at DESC);

    CREATE TABLE search_cache (
      cache_key    TEXT PRIMARY KEY,
      payload_json TEXT NOT NULL,
      created_at   REAL NOT NULL
    );

    CREATE TABLE waveforms (
      video_id   TEXT NOT NULL,
      bins       INTEGER NOT NULL,
      peaks_json TEXT NOT NULL,
      duration   REAL,
      created_at REAL NOT NULL,
      PRIMARY KEY (video_id, bins)
    );

    CREATE TABLE settings (
      key        TEXT PRIMARY KEY,
      value      TEXT NOT NULL,
      updated_at REAL NOT NULL
    );
    """,
    # 1 -> 2: riwayat unggahan.
    #
    # Dicatat di basis data, bukan hanya di daftar job: job dibersihkan, dan
    # yang perlu diingat setelah itu adalah "klip ini SUDAH pernah diunggah ke
    # sana" — satu-satunya hal yang mencegah klip yang sama naik dua kali ke
    # kanal yang sama.
    """
    CREATE TABLE uploads (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      clip_name    TEXT NOT NULL,
      target       TEXT NOT NULL,          -- 'drive' | 'youtube'
      status       TEXT NOT NULL,          -- 'running' | 'done' | 'failed'
      remote_id    TEXT,
      remote_url   TEXT,
      title        TEXT NOT NULL DEFAULT '',
      privacy      TEXT NOT NULL DEFAULT '',
      error        TEXT,
      job_id       TEXT,
      created_at   REAL NOT NULL,
      finished_at  REAL
    );
    CREATE INDEX idx_uploads_clip ON uploads(clip_name);
    CREATE INDEX idx_uploads_created ON uploads(created_at DESC);
    """,
]


def _split_statements(script: str) -> list[str]:
    """
    Memecah skrip DDL jadi pernyataan terpisah.

    `Connection.executescript()` tidak dipakai karena ia melakukan COMMIT
    implisit terlebih dahulu, sehingga migrasi tidak bisa dibungkus transaksi —
    kegagalan di tengah akan meninggalkan skema separuh jadi. `complete_statement`
    sadar akan tanda kutip, jadi lebih aman daripada sekadar split(';').
    """
    statements, buf = [], ""
    for line in script.splitlines():
        if line.strip().startswith("--"):
            continue
        buf += line + "\n"
        if sqlite3.complete_statement(buf):
            if buf.strip():
                statements.append(buf.strip())
            buf = ""
    if buf.strip():
        statements.append(buf.strip())
    return statements


def run_migrations() -> None:
    conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        current = 0
        conn.execute("INSERT INTO schema_version(version) VALUES (0)")
    else:
        current = row["version"]

    for version in range(current, len(MIGRATIONS)):
        # DDL di SQLite bersifat transaksional, jadi migrasi ini all-or-nothing.
        with tx() as c:
            for statement in _split_statements(MIGRATIONS[version]):
                c.execute(statement)
            c.execute("UPDATE schema_version SET version = ?", (version + 1,))
        print(f"[OmniClip] Migrasi database {version} -> {version + 1} diterapkan")


def close_conn() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None
