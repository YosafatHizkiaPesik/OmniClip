"""
Sampah Montase (JOB-4 M6.5), untuk pemindai `services/sampah.py`.

Hanya yang bisa DIBUKTIKAN tidak berguna, sama dengan aturan sampah.py:

  montase_sementara  render yang terputus (montase/render/<proyek>.mp4; render
                     yang selesai dipindah ke folder klip) dan folder kerja
                     pemeriksa animasi (montase/periksa/periksa_*; dihapus sendiri
                     saat pemeriksaan selesai), keduanya diam lebih dari satu jam.
  montase_yatim      turunan yang barisnya sudah tidak ada di basis data: folder
                     bahan (sampul, strip, gelombang, salinan sunting, kata),
                     berkas narasi/rekaman, dan gambar contoh komponen animasi;
                     serta BAHAN YANG BERKAS SUMBERNYA SUDAH HILANG dan tidak dipakai
                     proyek mana pun (klip jadi atau unduhannya sudah dihapus):
                     bahan seperti itu tidak bisa dipakai lagi. Barisnya ikut
                     dibuang sesudah foldernya (`rapikan`).

Yang TIDAK pernah masuk: bahan yang berkasnya masih ada (pustaka "Bahan saya"
memang untuk dipakai nanti), proyek, dan versi proyek.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..repos import montase as repo

DIAM = 3600.0


def _diam(p: Path) -> bool:
    try:
        return time.time() - p.stat().st_mtime > DIAM
    except OSError:
        return False


def _besar(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    total = 0
    for f in p.rglob("*"):
        try:
            total += f.stat().st_size if f.is_file() else 0
        except OSError:
            pass
    return total


def _temuan(p: Path, alasan: str) -> dict:
    return {"jalur": str(p), "nama": p.name, "ukuran": _besar(p), "alasan": alasan}


def sementara(akar: Path) -> list[dict]:
    """`akar` = <penyimpanan>/montase, dari `sampah._folder()`."""
    out = []
    for p in sorted((akar / "render").glob("*.mp4")):
        if _diam(p):
            out.append(_temuan(p, "render Montase yang terputus"))
    for p in sorted((akar / "periksa").glob("periksa_*")):
        if p.is_dir() and _diam(p):
            out.append(_temuan(p, "sisa pemeriksaan animasi"))
    return out


def _sumber_hilang(b: dict) -> bool:
    from ..repos import media as media_repo
    try:
        return not media_repo.abs_from_storage(b["rel_path"]).is_file()
    except Exception:                                # noqa: BLE001
        return False


def yatim(akar: Path) -> list[dict]:
    out = []
    bahan = repo.semua_bahan_ringkas()
    ada = {b["id"] for b in bahan}
    dipakai = repo.bahan_dipakai_semua()
    hilang = {b["id"] for b in bahan if b["id"] not in dipakai and _sumber_hilang(b)}
    d = akar / "bahan"
    if d.is_dir():
        for p in sorted(d.iterdir()):
            if not p.is_dir():
                continue
            if p.name not in ada:
                out.append(_temuan(p, "turunan bahan yang sudah dihapus"))
            elif p.name in hilang:
                out.append(_temuan(p, "bahan yang berkas sumbernya sudah hilang"))
    rujukan = {Path(b["rel_path"]).name for b in bahan if b["asal"] in ("tts", "rekam")}
    for p in sorted((akar / "suara").glob("*")):
        if p.is_file() and p.name not in rujukan and _diam(p):
            out.append(_temuan(p, "suara narasi/rekaman yang bahannya sudah dihapus"))
    komponen = repo.semua_id_komponen()
    for p in sorted((akar / "komponen").glob("*")):
        if p.is_dir() and p.name not in komponen:
            out.append(_temuan(p, "gambar contoh animasi yang sudah dihapus"))
    return out


def rapikan(dibuang: list[str], akar: Path) -> int:
    """Baris bahan yang sumbernya hilang dan foldernya baru saja dibuang."""
    from ..db import tx
    akar = akar / "bahan"
    ids = {Path(j).name for j in dibuang if Path(j).parent == akar}
    if not ids:
        return 0
    dipakai = repo.bahan_dipakai_semua()
    n = 0
    with tx() as c:
        for b in repo.semua_bahan_ringkas():
            if b["id"] in ids and b["id"] not in dipakai and _sumber_hilang(b):
                c.execute("DELETE FROM montase_bahan WHERE id = ?", (b["id"],))
                n += 1
    return n
