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
        c.execute("DELETE FROM montase_proyek_versi WHERE proyek_id = ? AND profil_id = ?",
                  (proyek_id, profil_id))
    return cur.rowcount > 0


# --- riwayat versi (JOB-4 M6.4) -------------------------------------------------

VERSI_SIMPAN = 10
JEDA_VERSI = 120.0          # detik antar potret simpan otomatis


def _jumlah_item(dokumen: dict) -> int:
    return sum(len(l.get("item") or []) for l in dokumen.get("lajur") or [])


def catat_versi(profil_id: int, proyek_id: str, revisi: int, dokumen: dict, *,
                alasan: str = "simpan", paksa: bool = False) -> bool:
    """
    Memotret dokumen. Potret `simpan` dilewati bila potret terakhir belum
    JEDA_VERSI detik; `paksa` (ekspor, sebelum pulihkan) selalu dicatat.
    Hanya VERSI_SIMPAN terbaru per proyek yang dipertahankan.
    """
    t = now()
    with tx() as c:
        if not paksa:
            row = c.execute("SELECT MAX(created_at) AS t FROM montase_proyek_versi "
                            "WHERE proyek_id = ? AND profil_id = ?", (proyek_id, profil_id)).fetchone()
            if row and row["t"] and t - row["t"] < JEDA_VERSI:
                return False
        fps = (dokumen.get("kanvas") or {}).get("fps") or 30
        c.execute("""INSERT INTO montase_proyek_versi (proyek_id, profil_id, revisi, alasan, dokumen_json,
                       durasi_detik, jumlah_item, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (proyek_id, profil_id, revisi, alasan, json.dumps(dokumen, ensure_ascii=False),
                   (dokumen.get("durasi") or 0) / fps, _jumlah_item(dokumen), t))
        c.execute("""DELETE FROM montase_proyek_versi WHERE proyek_id = ? AND profil_id = ? AND id NOT IN (
                       SELECT id FROM montase_proyek_versi WHERE proyek_id = ? AND profil_id = ?
                       ORDER BY created_at DESC, id DESC LIMIT ?)""",
                  (proyek_id, profil_id, proyek_id, profil_id, VERSI_SIMPAN))
    return True


def daftar_versi(profil_id: int, proyek_id: str) -> list[dict]:
    rows = get_conn().execute(
        """SELECT id, revisi, alasan, durasi_detik, jumlah_item, created_at FROM montase_proyek_versi
           WHERE proyek_id = ? AND profil_id = ? ORDER BY created_at DESC, id DESC""",
        (proyek_id, profil_id)).fetchall()
    return [dict(r) for r in rows]


def ambil_versi(profil_id: int, proyek_id: str, versi_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM montase_proyek_versi WHERE id = ? AND proyek_id = ? AND profil_id = ?",
        (versi_id, proyek_id, profil_id)).fetchone()
    if row is None:
        return None
    hasil = dict(row)
    hasil["dokumen"] = json.loads(hasil.pop("dokumen_json"))
    return hasil


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


# --- komponen animasi (Tahap 4) ------------------------------------------------
#
# Satu baris = satu VERSI komponen. Revisi lewat chat menambah versi, tidak
# menimpa (JOB-4 M4.6), jadi pemilik bisa kembali ke versi mana pun dan
# proyek lama yang merujuk `id@versi` tetap tergambar sama.

_KOLOM_KOMPONEN = ("id", "versi", "nama", "asal", "sumber_tsx", "hasil_js", "skema_json",
                   "contoh_props", "durasi_bawaan", "permintaan", "status", "catatan",
                   "disimpan", "created_at")


def _baris_komponen(row, *, dengan_kode: bool = False) -> dict:
    d = {k: row[k] for k in _KOLOM_KOMPONEN}
    d["disimpan"] = bool(d["disimpan"])
    for k in ("contoh_props", "catatan"):
        try:
            d[k] = json.loads(d[k]) if d[k] else None
        except ValueError:
            pass
    if not dengan_kode:
        d.pop("hasil_js", None)
    return d


def catat_komponen(profil_id: int, data: dict[str, Any]) -> dict:
    """Menambah versi baru (id baru bila `data['id']` kosong)."""
    kid = data.get("id") or id_baru("km")
    with tx() as c:
        versi = (c.execute("SELECT MAX(versi) FROM montase_komponen WHERE id = ? AND profil_id = ?",
                           (kid, profil_id)).fetchone()[0] or 0) + 1
        c.execute(
            """INSERT INTO montase_komponen (id, versi, profil_id, nama, asal, sumber_tsx, hasil_js,
                 skema_json, contoh_props, durasi_bawaan, permintaan, status, catatan, disimpan,
                 created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
            (kid, versi, profil_id, (data.get("nama") or "Animasi")[:80], data.get("asal", "ai"),
             data["sumber_tsx"], data.get("hasil_js"), data.get("skema_json"),
             json.dumps(data.get("contoh_props") or {}, ensure_ascii=False),
             data.get("durasi_bawaan"), (data.get("permintaan") or "")[:2000],
             data.get("status", "draf"), json.dumps(data.get("catatan") or {}, ensure_ascii=False),
             now()))
    return ambil_komponen(profil_id, kid, versi)


def ambil_komponen(profil_id: int, komponen_id: str, versi: Optional[int] = None, *,
                   dengan_kode: bool = False) -> Optional[dict]:
    c = get_conn()
    if versi is None:
        row = c.execute("SELECT * FROM montase_komponen WHERE id = ? AND profil_id = ? "
                        "ORDER BY versi DESC LIMIT 1", (komponen_id, profil_id)).fetchone()
    else:
        row = c.execute("SELECT * FROM montase_komponen WHERE id = ? AND versi = ? AND profil_id = ?",
                        (komponen_id, versi, profil_id)).fetchone()
    return _baris_komponen(row, dengan_kode=dengan_kode) if row else None


def versi_komponen(profil_id: int, komponen_id: str) -> list[dict]:
    rows = get_conn().execute("SELECT * FROM montase_komponen WHERE id = ? AND profil_id = ? "
                              "ORDER BY versi", (komponen_id, profil_id)).fetchall()
    return [_baris_komponen(r) for r in rows]


def daftar_komponen(profil_id: int, *, hanya_disimpan: bool = False, cari: str = "") -> list[dict]:
    """Versi terbaru tiap komponen; yang disimpan ke pustaka bertanda `disimpan`."""
    rows = get_conn().execute(
        """SELECT k.* FROM montase_komponen k
           JOIN (SELECT id, MAX(versi) AS v FROM montase_komponen WHERE profil_id = ? GROUP BY id) m
             ON m.id = k.id AND m.v = k.versi
           WHERE k.profil_id = ? ORDER BY k.created_at DESC""", (profil_id, profil_id)).fetchall()
    hasil = []
    for r in rows:
        d = _baris_komponen(r)
        simpan = bool(get_conn().execute(
            "SELECT 1 FROM montase_komponen WHERE id = ? AND profil_id = ? AND disimpan = 1",
            (d["id"], profil_id)).fetchone())
        d["di_pustaka"] = simpan
        if hanya_disimpan and not simpan:
            continue
        if cari and cari.lower() not in f"{d['nama']} {d['permintaan']}".lower():
            continue
        hasil.append(d)
    return hasil


def tandai_simpan(profil_id: int, komponen_id: str, versi: int, nama: str) -> bool:
    with tx() as c:
        cur = c.execute("UPDATE montase_komponen SET disimpan = 1, nama = ? WHERE id = ? AND versi = ? "
                        "AND profil_id = ? AND status = 'lolos'", (nama[:80], komponen_id, versi, profil_id))
    return cur.rowcount > 0


def hapus_dari_pustaka(profil_id: int, komponen_id: str) -> bool:
    with tx() as c:
        cur = c.execute("UPDATE montase_komponen SET disimpan = 0 WHERE id = ? AND profil_id = ?",
                        (komponen_id, profil_id))
    return cur.rowcount > 0


def perbarui_komponen(profil_id: int, komponen_id: str, versi: int, **kolom) -> None:
    izin = {"status", "hasil_js", "catatan", "nama", "skema_json"}
    pasang = {k: v for k, v in kolom.items() if k in izin}
    if "catatan" in pasang:
        pasang["catatan"] = json.dumps(pasang["catatan"] or {}, ensure_ascii=False)
    if not pasang:
        return
    with tx() as c:
        c.execute(f"UPDATE montase_komponen SET {', '.join(f'{k} = ?' for k in pasang)} "
                  "WHERE id = ? AND versi = ? AND profil_id = ?",
                  (*pasang.values(), komponen_id, versi, profil_id))
