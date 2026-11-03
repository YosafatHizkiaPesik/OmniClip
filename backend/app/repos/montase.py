"""
Akses tabel Montase (JOB-4 bagian 17). Semua kueri dibatasi profil yang
diberikan pemanggil; router mengambilnya dari `profil.kini()`.
"""

from __future__ import annotations

import json
import secrets
from typing import Any, Optional

from ..db import get_conn, now, tx


class RevisiBentrok(Exception):
    """Dokumen sudah disimpan pihak lain sejak dibaca."""

    def __init__(self, revisi_kini: int):
        super().__init__(f"revisi kini {revisi_kini}")
        self.revisi_kini = revisi_kini


def id_baru(awalan: str) -> str:
    return f"{awalan}_{secrets.token_hex(6)}"


# --- proyek -------------------------------------------------------------------

def _baris_proyek(row, *, dengan_dokumen: bool) -> dict:
    hasil = {
        "id": row["id"],
        "nama": row["nama"],
        "revisi": row["revisi"],
        "sampul": row["sampul"],
        "durasi_detik": row["durasi_detik"],
        "updated_at": row["updated_at"],
        "created_at": row["created_at"],
    }
    dokumen = json.loads(row["dokumen_json"])
    hasil["kanvas"] = dokumen.get("kanvas", {})
    if dengan_dokumen:
        hasil["dokumen"] = dokumen
    return hasil


def daftar_proyek(profil_id: int) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM montase_proyek WHERE profil_id = ? ORDER BY updated_at DESC",
        (profil_id,)).fetchall()
    return [_baris_proyek(r, dengan_dokumen=False) for r in rows]


def ambil_proyek(profil_id: int, proyek_id: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM montase_proyek WHERE id = ? AND profil_id = ?",
        (proyek_id, profil_id)).fetchone()
    return _baris_proyek(row, dengan_dokumen=True) if row else None


def buat_proyek(profil_id: int, dokumen: dict, *, durasi_detik: float,
                sampul: Optional[str] = None) -> dict:
    t = now()
    with tx() as c:
        c.execute(
            """INSERT INTO montase_proyek (id, profil_id, nama, dokumen_json, revisi,
                 sampul, durasi_detik, updated_at, created_at)
               VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)""",
            (dokumen["id"], profil_id, dokumen["nama"],
             json.dumps(dokumen, ensure_ascii=False), sampul, durasi_detik, t, t))
    return ambil_proyek(profil_id, dokumen["id"])


def simpan_proyek(profil_id: int, proyek_id: str, dokumen: dict, revisi: int, *,
                  durasi_detik: float, sampul: Optional[str]) -> int:
    """Menyimpan bila `revisi` masih yang terbaru. Mengembalikan revisi baru."""
    with tx() as c:
        row = c.execute(
            "SELECT revisi FROM montase_proyek WHERE id = ? AND profil_id = ?",
            (proyek_id, profil_id)).fetchone()
        if row is None:
            raise KeyError(proyek_id)
        if row["revisi"] != revisi:
            raise RevisiBentrok(row["revisi"])
        baru = revisi + 1
        c.execute(
            """UPDATE montase_proyek SET nama = ?, dokumen_json = ?, revisi = ?,
                 sampul = ?, durasi_detik = ?, updated_at = ?
               WHERE id = ? AND profil_id = ?""",
            (dokumen["nama"], json.dumps(dokumen, ensure_ascii=False), baru, sampul,
             durasi_detik, now(), proyek_id, profil_id))
    return baru


def hapus_proyek(profil_id: int, proyek_id: str) -> bool:
    with tx() as c:
        cur = c.execute("DELETE FROM montase_proyek WHERE id = ? AND profil_id = ?",
                        (proyek_id, profil_id))
    return cur.rowcount > 0


# --- bahan --------------------------------------------------------------------

_KOLOM_BAHAN = ("id", "asal", "rujukan", "nama", "jenis", "durasi", "lebar", "tinggi",
                "fps", "ada_suara", "siap", "created_at")


def _baris_bahan(row) -> dict:
    hasil = {k: row[k] for k in _KOLOM_BAHAN}
    hasil["ada_suara"] = bool(hasil["ada_suara"])
    hasil["siap"] = bool(hasil["siap"])
    return hasil


def daftar_bahan(profil_id: int) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM montase_bahan WHERE profil_id = ? ORDER BY created_at DESC",
        (profil_id,)).fetchall()
    return [_baris_bahan(r) for r in rows]


def ambil_bahan(profil_id: int, bahan_id: str, *, dengan_jalur: bool = False) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM montase_bahan WHERE id = ? AND profil_id = ?",
        (bahan_id, profil_id)).fetchone()
    if row is None:
        return None
    hasil = _baris_bahan(row)
    if dengan_jalur:
        hasil["rel_path"] = row["rel_path"]
    return hasil


def cari_bahan(profil_id: int, asal: str, rujukan: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM montase_bahan WHERE profil_id = ? AND asal = ? AND rujukan = ?",
        (profil_id, asal, rujukan)).fetchone()
    return _baris_bahan(row) if row else None


def catat_bahan(profil_id: int, data: dict[str, Any]) -> dict:
    bahan_id = id_baru("bh")
    with tx() as c:
        c.execute(
            """INSERT INTO montase_bahan (id, profil_id, asal, rujukan, nama, rel_path,
                 jenis, durasi, lebar, tinggi, fps, ada_suara, siap, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
            (bahan_id, profil_id, data["asal"], data["rujukan"], data["nama"],
             data["rel_path"], data["jenis"], data.get("durasi"), data.get("lebar"),
             data.get("tinggi"), data.get("fps"), int(bool(data.get("ada_suara"))), now()))
    return ambil_bahan(profil_id, bahan_id)


def tandai_bahan_siap(bahan_id: str) -> None:
    with tx() as c:
        c.execute("UPDATE montase_bahan SET siap = 1 WHERE id = ?", (bahan_id,))


def hapus_bahan(profil_id: int, bahan_id: str) -> bool:
    with tx() as c:
        cur = c.execute("DELETE FROM montase_bahan WHERE id = ? AND profil_id = ?",
                        (bahan_id, profil_id))
    return cur.rowcount > 0
