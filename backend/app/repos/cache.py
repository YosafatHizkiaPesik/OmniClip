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
    - `facecam:` (letak kamera pemain sepanjang klip). Sama alasannya, dan
      sampai 27 September 2026 ia satu-satunya dari keempatnya yang masih ikut
      terbuang tiap hari — jadi klip game yang dibuka lagi besoknya memindai
      ulang dari nol. Versinya dijaga terpisah (`FACECAM_VERSI`), jadi hasil
      lama tetap terbuang saat cara memindainya berubah.
    """
    cur = get_conn().execute(
        "DELETE FROM search_cache WHERE created_at < ? AND cache_key NOT LIKE 'jenis:%' "
        "AND cache_key NOT LIKE 'sutradara:%' AND cache_key NOT LIKE 'bingkai:%' "
        "AND cache_key NOT LIKE 'facecam:%' AND cache_key NOT LIKE 'tema:%'",
        (time.time() - maks_umur,),
    )
    return cur.rowcount + pangkas_abadi()


# Entri yang tidak pernah kedaluwarsa: isinya menjelaskan isi sebuah potongan
# video, dan itu tidak berubah. Lihat `bersihkan`.
ABADI = ("jenis:", "sutradara:", "bingkai:", "facecam:", "tema:")

# Plafon isi keempatnya, dalam bita.
#
# Tidak pernah kedaluwarsa BUKAN berarti tidak pernah dibuang. Terukur pada
# penyimpanan pemiliknya 2 Oktober 2026: basis data 25 MB, dan 14,3 MB-nya
# simpanan ini — `bingkai:` sendiri 143 baris untuk 9,0 MB, sekitar 63 KB per
# klip yang pernah dibuka. Tidak ada satu pun aturan yang menghentikannya
# tumbuh, termasuk untuk video yang berkasnya sudah lama dihapus.
#
# 40 MB kira-kira enam ratus klip jejak wajah: jauh di atas berapa pun yang
# dikerjakan orang dalam satu masa, dan tetap memberi basis data batas atas
# yang bisa disebut. Yang dibuang paling lama ditulis, dan membuangnya hanya
# berarti klip lama yang dibuka lagi menghitung ulang — bukan kehilangan.
PLAFON_ABADI = 40 * 1024 * 1024


def pangkas_abadi(plafon: int = PLAFON_ABADI) -> int:
    """
    Membuang entri abadi yang paling lama ditulis sampai isinya muat plafon.

    "Paling lama ditulis", bukan "paling lama tidak dipakai": tabel ini tidak
    mencatat kapan sebuah baris DIBACA, dan menambahkan catatan itu berarti
    tiap pembacaan menulis — mahal, dan merusak arti `created_at` yang dipakai
    TTL di atas.
    """
    conn = get_conn()
    pola = " OR ".join("cache_key LIKE ?" for _ in ABADI)
    arg = [p + "%" for p in ABADI]
    baris = conn.execute(
        f"SELECT cache_key, LENGTH(payload_json) AS n FROM search_cache "
        f"WHERE {pola} ORDER BY created_at DESC", arg,
    ).fetchall()
    jumlah = 0
    buang: list[str] = []
    for r in baris:
        jumlah += int(r["n"] or 0)
        if jumlah > plafon:
            buang.append(r["cache_key"])
    if not buang:
        return 0
    # Dipotong per seribu: SQLite membatasi jumlah parameter satu pernyataan.
    for i in range(0, len(buang), 1000):
        potong = buang[i:i + 1000]
        conn.execute(
            f"DELETE FROM search_cache WHERE cache_key IN ({','.join('?' * len(potong))})",
            potong,
        )
    return len(buang)
