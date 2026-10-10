"""Profil: nama, minat, folder klip, setelan unggah, dan gaya teks tiap akun."""

import json
from typing import Optional

from ..db import get_conn, now, tx


def _baris(r) -> dict:
    d = dict(r)
    for k, bawaan in (("minat_json", []), ("unggah_json", {}),
                      ("gaya_json", {}), ("setelan_json", {})):
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


def buat(nama: str, *, warna: str = "#E0473A", minat: Optional[list] = None,
         sementara: bool = False) -> int:
    """
    Membuat profil. `sementara` menandai profil yang masih menunggu izin Google.

    Profil sementara disapu kembali bila izinnya tidak pernah selesai; lihat
    `sapu_sementara`.
    """
    with tx() as c:
        cur = c.execute("INSERT INTO profil (nama, warna, minat_json, created_at, sementara) "
                        "VALUES (?,?,?,?,?)",
                        (nama, warna, json.dumps(minat or [], ensure_ascii=False), now(),
                         1 if sementara else 0))
        return int(cur.lastrowid)


def sahkan(pid: int) -> None:
    """Profil ini sudah punya akun Google; ia bukan lagi profil yang menunggu."""
    with tx() as c:
        c.execute("UPDATE profil SET sementara = 0 WHERE id = ?", (pid,))


def ubah(pid: int, **kolom) -> None:
    sah = {"nama": "nama", "warna": "warna", "folder_klip": "folder_klip",
           "minat": "minat_json", "unggah": "unggah_json", "foto": "foto",
           "gaya": "gaya_json", "setelan": "setelan_json"}
    pasangan = []
    for k, v in kolom.items():
        if k not in sah or v is None:
            continue
        if k in ("minat", "unggah", "gaya", "setelan"):
            v = json.dumps(v, ensure_ascii=False)
        pasangan.append((sah[k], v))
    if not pasangan:
        return
    with tx() as c:
        c.execute(f"UPDATE profil SET {', '.join(f'{k} = ?' for k, _ in pasangan)} WHERE id = ?",
                  (*[v for _, v in pasangan], pid))


# Kelompok setelan yang boleh disimpan per akun.
#
# Dibatasi dengan sengaja. Tanpa daftar ini, satu salah ketik di sisi peramban
# menulis kelompok baru yang tidak pernah dibaca siapa pun, dan tidak ada yang
# memberi tahu. Menambah kelompok baru harus terlihat di sini.
#
#   gaya  gaya subtitle, kartu judul, dan tanda air. Tanda air itu nama kanal.
#   klip  preferensi pengklipan: berapa klip per video, model transkrip, model AI.
#   komentar  gaya komentar pemilik kanal, untuk draf komentar AI (JOB-2 F1-2).
#   merek  intro, outro, dan outro teks kanal (JOB-2 F2-5, services/merek.py).
KELOMPOK = ("gaya", "klip", "komentar", "merek")


def setelan(pid: int, kelompok: str = "") -> dict:
    """
    Setelan milik akun ini. Tanpa `kelompok`, seluruh kantongnya.

    Isi kolom gaya yang lama dipindahkan di sini, sekali, saat pertama dibaca.
    Lihat migrasi `setelan_json` di app/db.py untuk kenapa pindahnya tidak
    dikerjakan SQL.
    """
    pr = ambil(pid)
    if not pr:
        return {}
    kantong = pr.get("setelan")
    kantong = kantong if isinstance(kantong, dict) else {}
    lama = pr.get("gaya")
    if not kantong and isinstance(lama, dict) and lama:
        kantong = {"gaya": lama}
        ubah(pid, setelan=kantong, gaya={})
    if kelompok:
        isi = kantong.get(kelompok) or {}
        return isi if isinstance(isi, dict) else {}
    return kantong


def simpan_setelan(pid: int, kelompok: str, data: dict) -> dict:
    """
    Menyimpan satu kelompok setelan. Yang MENIMPA hanya kunci yang dikirim.

    Digabung, bukan ditukar: editor mengirim gaya utuh, tapi halaman lain bisa
    menyimpan satu kunci saja, dan penukaran utuh akan menghapus sisanya tanpa
    ada yang memintanya.
    """
    if kelompok not in KELOMPOK or not isinstance(data, dict):
        return setelan(pid, kelompok)
    kantong = dict(setelan(pid))
    kantong[kelompok] = {**(kantong.get(kelompok) or {}), **data}
    ubah(pid, setelan=kantong)
    return kantong[kelompok]


def gaya(pid: int) -> dict:
    """Gaya subtitle dan tanda air milik akun ini."""
    return setelan(pid, "gaya")


def simpan_gaya(pid: int, data: dict) -> dict:
    """Menyimpan gaya akun ini; lihat `simpan_setelan`."""
    return simpan_setelan(pid, "gaya", data)


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
