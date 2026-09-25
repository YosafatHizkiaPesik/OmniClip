"""Profil: nama, minat, folder klip, dan setelan unggah tiap akun."""

import json
from typing import Optional

from ..db import get_conn, now, tx


def _baris(r) -> dict:
    d = dict(r)
    for k, bawaan in (("minat_json", []), ("unggah_json", {})):
        try:
            d[k[:-5]] = json.loads(d.pop(k) or "null") or bawaan
        except json.JSONDecodeError:
            d[k[:-5]] = bawaan
    return d


def semua() -> list[dict]:
    return [_baris(r) for r in get_conn().execute("SELECT * FROM profil ORDER BY id")]


def ambil(pid: int) -> Optional[dict]:
    r = get_conn().execute("SELECT * FROM profil WHERE id = ?", (pid,)).fetchone()
    return _baris(r) if r else None


def buat(nama: str, *, warna: str = "#E0473A", minat: Optional[list] = None) -> int:
    with tx() as c:
        cur = c.execute("INSERT INTO profil (nama, warna, minat_json, created_at) VALUES (?,?,?,?)",
                        (nama, warna, json.dumps(minat or [], ensure_ascii=False), now()))
        return int(cur.lastrowid)


def ubah(pid: int, **kolom) -> None:
    sah = {"nama": "nama", "warna": "warna", "folder_klip": "folder_klip",
           "minat": "minat_json", "unggah": "unggah_json"}
    pasangan = []
    for k, v in kolom.items():
        if k not in sah or v is None:
            continue
        if k in ("minat", "unggah"):
            v = json.dumps(v, ensure_ascii=False)
        pasangan.append((sah[k], v))
    if not pasangan:
        return
    with tx() as c:
        c.execute(f"UPDATE profil SET {', '.join(f'{k} = ?' for k, _ in pasangan)} WHERE id = ?",
                  (*[v for _, v in pasangan], pid))


def hapus(pid: int) -> None:
    with tx() as c:
        c.execute("DELETE FROM profil_video WHERE profil_id = ?", (pid,))
        c.execute("DELETE FROM search_history WHERE profil_id = ?", (pid,))
        c.execute("DELETE FROM profil WHERE id = ?", (pid,))


def tandai_video(pid: int, video_id: str) -> None:
    with tx() as c:
        c.execute("INSERT OR IGNORE INTO profil_video (profil_id, video_id, created_at) "
                  "VALUES (?,?,?)", (pid, video_id, now()))


def lepas_video(pid: int, video_id: str) -> None:
    with tx() as c:
        c.execute("DELETE FROM profil_video WHERE profil_id = ? AND video_id = ?", (pid, video_id))


def video_milik(pid: int) -> set[str]:
    return {r["video_id"] for r in get_conn().execute(
        "SELECT video_id FROM profil_video WHERE profil_id = ?", (pid,))}


def catat_cari(pid: int, kueri: str, jumlah: int) -> None:
    with tx() as c:
        c.execute("INSERT INTO search_history (query, result_count, created_at, profil_id) "
                  "VALUES (?,?,?,?)", (kueri, jumlah, now(), pid))


def riwayat_cari(pid: int, batas: int = 12) -> list[dict]:
    """Kueri unik terbaru, dengan berapa kali dicari."""
    return [dict(r) for r in get_conn().execute(
        """SELECT query, COUNT(*) AS kali, MAX(created_at) AS terakhir
           FROM search_history WHERE profil_id = ?
           GROUP BY lower(trim(query)) ORDER BY terakhir DESC LIMIT ?""", (pid, batas))]


def kueri_sering(pid: int, batas: int = 6, minimal: int = 2) -> list[dict]:
    """
    Kueri yang PALING SERING dicari, bukan yang paling baru.

    Keduanya menjawab pertanyaan yang berbeda. Yang terbaru menjawab "tadi saya
    mencari apa"; yang tersering menjawab "saya ini sebenarnya mencari apa" —
    dan pertanyaan kedua itulah yang seharusnya mengisi beranda, supaya
    pemiliknya tidak mengetik kata yang sama setiap hari.

    `minimal` menjaga kueri yang cuma sekali diketik tidak ikut naik: sekali
    bisa berarti salah ketik, atau rasa penasaran yang sudah selesai.
    """
    return [dict(r) for r in get_conn().execute(
        """SELECT query, COUNT(*) AS kali, MAX(created_at) AS terakhir
           FROM search_history WHERE profil_id = ?
           GROUP BY lower(trim(query)) HAVING kali >= ?
           ORDER BY kali DESC, terakhir DESC LIMIT ?""", (pid, minimal, batas))]


def hapus_riwayat(pid: int, kueri: Optional[str] = None) -> None:
    with tx() as c:
        if kueri is None:
            c.execute("DELETE FROM search_history WHERE profil_id = ?", (pid,))
        else:
            c.execute("DELETE FROM search_history WHERE profil_id = ? AND lower(trim(query)) = lower(trim(?))",
                      (pid, kueri))
