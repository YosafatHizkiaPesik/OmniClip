"""
Pengaturan yang bertahan melewati restart.

Tabel `settings` sudah ada sejak migrasi pertama tapi tidak pernah dipakai:
API key hanya ditulis ke `os.environ` proses, jadi ia hilang setiap backend
dimulai ulang dan satu-satunya tempat yang benar-benar menyimpannya adalah
`backend/.env` — berkas yang harus diedit lewat terminal.

Itu tidak masalah selama aplikasi hanya dibuka dari komputer ini. Begitu ia
bisa dibuka dari HP, mengedit `.env` bukan lagi pilihan yang tersedia.
"""

from ..db import get_conn, now, tx


def get(key: str, default: str = "") -> str:
    row = get_conn().execute(
        "SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_value(key: str, value: str) -> None:
    with tx() as c:
        c.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            (key, value, now()),
        )


def delete(key: str) -> None:
    with tx() as c:
        c.execute("DELETE FROM settings WHERE key = ?", (key,))


def get_all(prefix: str = "") -> dict[str, str]:
    sql = "SELECT key, value FROM settings"
    args: tuple = ()
    if prefix:
        sql += " WHERE key LIKE ?"
        args = (prefix + "%",)
    return {r["key"]: r["value"] for r in get_conn().execute(sql, args)}
