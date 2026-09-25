"""
Cache hasil pencarian YouTube.

Tabelnya sudah ada sejak awal dan tidak pernah dipakai satu baris kode pun,
sementara setiap pencarian menembak YouTube lagi: terukur 4–5 detik, dan sama
lambatnya pada pencarian yang PERSIS sama semenit kemudian. Menekan satu chip
kategori lalu kembali berarti menunggu penuh dua kali.

Selain lambat, itu juga persis pola yang memicu pembatasan laju YouTube —
kegagalan yang paling mungkin terjadi pada aplikasi ini.
"""

import json
import time
from typing import Any, Optional

from ..db import get_conn, now

# Lima belas menit. Cukup lama untuk menghapus pengulangan dalam satu sesi
# kerja, cukup pendek supaya "Terbaru" tidak berbohong setengah jam.
TTL_DETIK = 15 * 60


def ambil(kunci: str, *, ttl: float = TTL_DETIK) -> Optional[Any]:
    """Isi cache yang masih segar, atau None."""
    row = get_conn().execute(
        "SELECT payload_json, created_at FROM search_cache WHERE cache_key = ?",
        (kunci,),
    ).fetchone()
    if row is None:
        return None
    if time.time() - row["created_at"] > ttl:
        return None
    try:
        return json.loads(row["payload_json"])
    except json.JSONDecodeError:
        return None


def simpan(kunci: str, nilai: Any) -> None:
    get_conn().execute(
        """INSERT INTO search_cache (cache_key, payload_json, created_at)
           VALUES (?,?,?)
           ON CONFLICT(cache_key) DO UPDATE SET
             payload_json = excluded.payload_json,
             created_at = excluded.created_at""",
        (kunci, json.dumps(nilai, ensure_ascii=False), now()),
    )


def bersihkan(maks_umur: float = 24 * 3600) -> int:
    """Membuang entri basi. Dipanggil saat startup, bukan tiap pencarian.

    Dua jenis entri tidak ikut dibuang, karena keduanya menjelaskan isi sebuah
    potongan video — dan isi potongan video tidak pernah basi:

    - `jenis:` (game / wajah / tanpa wajah), puluhan detik per klip.
    - `sutradara:` (momen dan bingkai hasil AI). Menghitungnya ulang bukan
      hanya lambat, tapi memakan kuota model yang jumlahnya terbatas per hari.
    - `bingkai:` (jejak wajah per klip). Beberapa detik per klip pada video
      yang isinya tidak akan pernah berubah, dan yang menunggunya adalah orang
      yang sedang membuka editor.
    """
    cur = get_conn().execute(
        "DELETE FROM search_cache WHERE created_at < ? AND cache_key NOT LIKE 'jenis:%' "
        "AND cache_key NOT LIKE 'sutradara:%' AND cache_key NOT LIKE 'bingkai:%' "
        "AND cache_key NOT LIKE 'tema:%'",
        (time.time() - maks_umur,),
    )
    return cur.rowcount
