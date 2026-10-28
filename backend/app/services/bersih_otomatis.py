"""
Pembersihan penyimpanan otomatis: video mentah dan klip jadi yang sudah lama
tidak disentuh.

Diminta pemiliknya 28 Oktober 2026: "bisakah kamu membuat agar sistem akan
menghapus video klip jadi atau video rawnya jika tidak ada aktivitas editing
selama 30 hari atau projek untuk video tersebut sudah selesai agar lebih
menghemat storage".

Ini membalik keputusan lama di `pemeliharaan.py` ("yang menghapus tetap
orangnya"), dan membaliknya atas permintaan orangnya sendiri. Yang dijaga
supaya keputusan itu tetap aman:

- **Hanya video hasil UNDUHAN.** Video mentah yang dibuang bisa diunduh lagi
  dari Studio (tombol "Unduh ulang video"), dan analisis serta suntingannya
  tidak ikut hilang. Video IMPOR adalah berkas kiriman orangnya sendiri yang
  tidak bisa diambil ulang dari mana pun, jadi tidak pernah disentuh.
- **Aktivitas diukur dari tiga sumber**: analisis/suntingan terakhir (setiap
  Simpan menulis baris analisis baru), pekerjaan terakhir untuk video itu
  (unduh, render, unggah), dan waktu klip terakhirnya dirender.
- **Video yang sedang dikerjakan tidak pernah disentuh**: ada pekerjaan yang
  antre atau berjalan untuknya, atau unggahan yang belum selesai.
- **Semuanya bisa dimatikan** dan angkanya bisa diubah di Pengaturan, dan
  kartunya memperlihatkan daftar yang akan dibuang lebih dulu.
- **Putaran otomatis baru berjalan sesudah DISETUJUI sekali** (`disetujui`):
  dicoba pada data pemiliknya, putaran pertama akan membuang 49 video mentah
  sebesar 50,8 GB sekaligus. Sebanyak itu tidak boleh hilang tanpa orangnya
  melihat daftarnya, jadi persetujuan pertama datang dari tombol "Bersihkan
  sekarang" atau dari menyalakan sakelarnya. Sesudah itu berjalan sendiri.

Aturannya:

  video mentah  dibuang bila tidak ada aktivitas selama `hari` (30), ATAU
                proyeknya selesai: sudah punya klip jadi dan tidak disentuh
                selama `selesai_hari` (7).
  klip jadi     dibuang bila klipnya dan videonya sama-sama tidak disentuh
                selama `hari` (30).
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("omniclip.bersih_otomatis")

HARI_BAWAAN = 30
SELESAI_HARI_BAWAAN = 7
_EKSTENSI = (".mp4", ".mkv", ".webm", ".mov", ".m4v")
# Pertama kali sesudah aplikasi dimulai ditunda, supaya membuka aplikasi lalu
# langsung membuka proyek lama tidak berlomba dengan pembersihnya.
TUNDA_AWAL_DETIK = 10 * 60
JARAK_DETIK = 24 * 3600


def setelan() -> dict:
    from ..repos import settings as settings_repo

    def angka(kunci, bawaan, lo, hi):
        try:
            return max(lo, min(hi, int(settings_repo.get(kunci, str(bawaan)) or bawaan)))
        except (TypeError, ValueError):
            return bawaan

    return {
        "aktif": settings_repo.get("bersih.aktif", "1") != "0",
        "disetujui": settings_repo.get("bersih.disetujui", "0") == "1",
        "sumber": settings_repo.get("bersih.sumber", "1") != "0",
        "klip": settings_repo.get("bersih.klip", "1") != "0",
        "hari": angka("bersih.hari", HARI_BAWAAN, 7, 365),
        "selesai_hari": angka("bersih.selesai_hari", SELESAI_HARI_BAWAAN, 1, 365),
        "terakhir": float(settings_repo.get("bersih.terakhir", "0") or 0),
        "hasil_terakhir": settings_repo.get("bersih.hasil_terakhir", ""),
    }


def atur(**ubah) -> dict:
    from ..repos import settings as settings_repo
    for k in ("aktif", "sumber", "klip"):
        if ubah.get(k) is not None:
            settings_repo.set_value(f"bersih.{k}", "1" if ubah[k] else "0")
    # Menyalakan sakelarnya sendiri adalah persetujuan.
    if ubah.get("aktif"):
        settings_repo.set_value("bersih.disetujui", "1")
    for k in ("hari", "selesai_hari"):
        if ubah.get(k) is not None:
            settings_repo.set_value(f"bersih.{k}", str(int(ubah[k])))
    return setelan()


def _aktivitas() -> tuple[dict[str, float], set[str]]:
    """(waktu aktivitas terakhir per video, video yang sedang dikerjakan)."""
    from ..db import get_conn
    conn = get_conn()
    akhir: dict[str, float] = {}

    def catat(vid, t):
        if vid and t:
            akhir[vid] = max(akhir.get(vid, 0.0), float(t))

    for vid, t in conn.execute(
            "SELECT video_id, MAX(created_at) FROM analyses GROUP BY video_id"):
        catat(vid, t)
    for vid, t in conn.execute(
            "SELECT video_id, MAX(COALESCE(finished_at, started_at, created_at)) "
            "FROM jobs WHERE video_id IS NOT NULL GROUP BY video_id"):
        catat(vid, t)
    sibuk = {r[0] for r in conn.execute(
        "SELECT DISTINCT video_id FROM jobs WHERE video_id IS NOT NULL "
        "AND status IN ('queued', 'running')")}
    return akhir, sibuk


def _unggahan_tertunda() -> set[str]:
    from ..db import get_conn
    try:
        return {r[0] for r in get_conn().execute(
            "SELECT clip_name FROM uploads WHERE status NOT IN ('done', 'failed', 'cancelled')")}
    except Exception:                                # noqa: BLE001
        return set()


def _klip_semua_profil() -> list[dict]:
    """Klip jadi seluruh profil: {path, video_id, ukuran, waktu, profil}."""
    from ..repos import profil as profil_repo
    from . import profil as profil_svc
    from .paths import extract_id_from_filename
    from .render import list_local_clips

    keluar, dilihat = [], set()
    for p in profil_repo.semua():
        folder = profil_svc.folder_klip(p["id"])
        try:
            kunci = folder.resolve()
        except OSError:
            continue
        if kunci in dilihat:
            continue
        dilihat.add(kunci)
        for k in list_local_clips(folder):
            meta = k.get("metadata") or {}
            keluar.append({
                "path": folder / k["file_name"],
                "berkas": k["file_name"],
                "video_id": meta.get("video_id") or extract_id_from_filename(k["file_name"]) or "",
                "ukuran": int(k.get("file_size") or 0),
                "waktu": float(k.get("created_at") or 0),
                "profil": p.get("nama") or str(p["id"]),
            })
    return keluar


def rencana(sekarang: Optional[float] = None, st: Optional[dict] = None) -> dict:
    """Apa yang AKAN dibuang menurut setelan sekarang, tanpa membuang apa pun."""
    from .. import config as cfg
    from .paths import extract_id_from_filename

    st = st or setelan()
    sekarang = sekarang or time.time()
    batas = sekarang - st["hari"] * 86400
    batas_selesai = sekarang - st["selesai_hari"] * 86400
    akhir, sibuk = _aktivitas()
    klip = _klip_semua_profil()

    for k in klip:
        if k["video_id"]:
            akhir[k["video_id"]] = max(akhir.get(k["video_id"], 0.0), k["waktu"])
    punya_klip = {k["video_id"] for k in klip if k["video_id"]}

    sumber: list[dict] = []
    if st["sumber"]:
        try:
            berkas = list(Path(cfg.DOWNLOAD_DIR).iterdir())
        except OSError:
            berkas = []
        for f in berkas:
            if not f.is_file() or f.suffix.lower() not in _EKSTENSI:
                continue
            vid = extract_id_from_filename(f.name) or ""
            if not vid or vid in sibuk:
                continue
            try:
                s = f.stat()
            except OSError:
                continue
            # Waktu tulis berkas = waktu diunduh. Bukan waktu akses: memindah
            # folder menyetel ulang waktu akses semua berkas.
            terakhir = max(akhir.get(vid, 0.0), s.st_mtime)
            if terakhir < batas:
                alasan = "diam"
            elif vid in punya_klip and terakhir < batas_selesai:
                alasan = "selesai"
            else:
                continue
            sumber.append({"berkas": f.name, "video_id": vid, "ukuran": s.st_size,
                           "alasan": alasan,
                           "diam_hari": int((sekarang - terakhir) // 86400)})

    buang_klip: list[dict] = []
    if st["klip"]:
        tertunda = _unggahan_tertunda()
        for k in klip:
            if k["berkas"] in tertunda or (k["video_id"] and k["video_id"] in sibuk):
                continue
            terakhir = max(k["waktu"], akhir.get(k["video_id"], 0.0))
            if terakhir < batas:
                buang_klip.append({"berkas": k["berkas"], "video_id": k["video_id"],
                                   "profil": k["profil"], "ukuran": k["ukuran"],
                                   "path": str(k["path"]),
                                   "diam_hari": int((sekarang - terakhir) // 86400)})

    return {
        "setelan": st,
        "sumber": sumber,
        "klip": buang_klip,
        "jumlah": len(sumber) + len(buang_klip),
        "ukuran": sum(x["ukuran"] for x in sumber) + sum(x["ukuran"] for x in buang_klip),
    }


def _hapus(path: Path, ikut: tuple[str, ...] = ()) -> int:
    try:
        besar = path.stat().st_size
        path.unlink()
    except OSError as e:
        log.info("Tidak bisa membuang %s: %s", path.name, e)
        return 0
    for akhiran in ikut:
        try:
            path.with_suffix(akhiran).unlink(missing_ok=True)
        except OSError:
            pass
    return besar


def jalankan(sekarang: Optional[float] = None, *, paksa: bool = False) -> dict:
    """
    Membuang yang ada di `rencana()`. `paksa` = dari tombol, walau setelan
    utamanya mati (tombol "Bersihkan sekarang" adalah perintah langsung).
    """
    from ..repos import settings as settings_repo
    from .proksi import _nama as nama_proksi

    st = setelan()
    if not paksa and not (st["aktif"] and st["disetujui"]):
        return {"dibuang": 0, "bita": 0, "lewat": True}
    if paksa:
        settings_repo.set_value("bersih.disetujui", "1")
    r = rencana(sekarang, st)
    from .. import config as cfg
    dasar = Path(cfg.DOWNLOAD_DIR).resolve()
    n = bita = 0
    for s in r["sumber"]:
        p = (dasar / Path(s["berkas"]).name)
        if p.resolve().parent != dasar:
            continue
        # Nama proksi dihitung dari stat() sumbernya, jadi sebelum dibuang.
        try:
            pr = nama_proksi(p)
        except OSError:
            pr = None
        b = _hapus(p)
        if b:
            n += 1
            bita += b
            if pr is not None and pr.is_file():
                bita += _hapus(pr)
    for k in r["klip"]:
        b = _hapus(Path(k["path"]), (".json", ".srt", ".ass"))
        if b:
            n += 1
            bita += b
    settings_repo.set_value("bersih.terakhir", str(time.time()))
    settings_repo.set_value("bersih.hasil_terakhir",
                            f"{n} berkas, {bita / 1e9:.2f} GB" if n else "")
    if n:
        log.info("Pembersihan otomatis: %d berkas, %.2f GB dikembalikan", n, bita / 1e9)
    return {"dibuang": n, "bita": bita, "lewat": False}


def jalankan_di_latar() -> None:
    """Sekali sesudah aplikasi berjalan 10 menit, lalu sekali sehari."""
    def _gelung():
        time.sleep(TUNDA_AWAL_DETIK)
        while True:
            try:
                st = setelan()
                if (st["aktif"] and st["disetujui"]
                        and time.time() - st["terakhir"] >= JARAK_DETIK * 0.9):
                    jalankan()
            except Exception as e:                   # noqa: BLE001
                log.warning("Pembersihan otomatis dilewati: %s", str(e)[:200])
            time.sleep(3600)

    threading.Thread(target=_gelung, name="bersih-otomatis", daemon=True).start()
