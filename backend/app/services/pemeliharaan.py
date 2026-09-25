"""
Ruang cakram dan cadangan basis data.

Dua pekerjaan yang tidak menarik sama sekali dan keduanya baru terasa penting
pada hari yang buruk.

**Ruang.** Video sumber tidak pernah dibuang sendiri, dan memang tidak boleh:
mengklip ulang video yang sudah dihapus berarti mengunduhnya lagi. Tapi
terukur di komputer pemiliknya, unduhan sudah 42 GB, dan sebagian besar
videonya klipnya sudah jadi. Yang dibutuhkan bukan pembersih otomatis — itu
akan menghapus yang salah — melainkan daftar yang jujur: berkas apa, sebesar
apa, klipnya sudah jadi berapa, dan terakhir dipakai kapan. Yang menghapus
tetap orangnya.

**Cadangan.** Seluruh pekerjaan berbulan-bulan ada di satu berkas SQLite:
analisis, klip, transkrip, setelan, profil. Menyalinnya saat aplikasi berjalan
dengan `cp` bisa menghasilkan berkas yang rusak separuh, karena WAL-nya belum
tergabung. SQLite punya API cadangan yang benar untuk ini, dan itu yang
dipakai.

Memulihkan sengaja TIDAK langsung menimpa. Basis data yang sedang dipakai
tidak bisa ditukar dari dalam dirinya sendiri tanpa mengagetkan setiap
pekerjaan yang sedang berjalan; jadi berkasnya ditaruh di samping, dan
pertukarannya terjadi saat aplikasi berikutnya dimulai — satu-satunya saat
tidak ada yang sedang memegangnya.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Optional

from ..config import DB_PATH, STORAGE_DIR

log = logging.getLogger("omniclip.pemeliharaan")

FOLDER_CADANGAN = STORAGE_DIR / "cadangan"
PENANDA_PULIH = STORAGE_DIR / "pulihkan-dari.txt"
MAKS_CADANGAN = 10          # yang lebih tua dari ini dibuang sendiri


# --- Ruang cakram ---------------------------------------------------------------
def _folder_terpantau() -> dict[str, Path]:
    from .. import config as cfg
    return {
        "unduhan": cfg.DOWNLOAD_DIR,
        "klip": cfg.CLIPS_DIR,
        "proksi": cfg.STORAGE_DIR / "proksi",
        "impor": cfg.STORAGE_DIR / "impor",
        "suara": cfg.STORAGE_DIR / "suara",
        "sampul": cfg.THUMBS_DIR,
        "model": cfg.MODELS_DIR,
        "alat": cfg.STORAGE_DIR / "alat",
        "aset": cfg.STORAGE_DIR / "aset",
    }


def _ukuran(d: Path) -> tuple[int, int]:
    total = jumlah = 0
    try:
        for akar, _dirs, berkas in os.walk(d):
            for n in berkas:
                try:
                    total += (Path(akar) / n).stat().st_size
                    jumlah += 1
                except OSError:
                    pass
    except OSError:
        pass
    return total, jumlah


def rinci() -> dict:
    """Pemakaian ruang per folder, dan video sumber yang layak ditimbang ulang."""
    from ..repos import analyses as analyses_repo
    from .paths import extract_id_from_filename

    folder = []
    for nama, d in _folder_terpantau().items():
        besar, jumlah = _ukuran(d)
        folder.append({"nama": nama, "folder": str(d), "ukuran": besar, "jumlah": jumlah})
    folder.sort(key=lambda f: f["ukuran"], reverse=True)

    # Berapa klip jadi per video: yang menentukan sebuah unduhan "sudah
    # dipakai" atau belum.
    klip_per_video: dict[str, int] = {}
    from .render import list_local_clips
    from . import profil as profil_svc
    from ..repos import profil as profil_repo
    try:
        for p in profil_repo.semua():
            for k in list_local_clips(profil_svc.folder_klip(p["id"])):
                vid = ((k.get("metadata") or {}).get("video_id")
                       or extract_id_from_filename(k["file_name"]) or "")
                if vid:
                    klip_per_video[vid] = klip_per_video.get(vid, 0) + 1
    except Exception as e:
        log.warning("Klip per video tidak terbaca: %s", str(e)[:160])

    from .. import config as cfg
    sumber = []
    try:
        for f in cfg.DOWNLOAD_DIR.iterdir():
            if not f.is_file() or f.suffix.lower() not in (".mp4", ".mkv", ".webm", ".mov"):
                continue
            vid = extract_id_from_filename(f.name) or ""
            st = f.stat()
            sumber.append({
                "berkas": f.name,
                "ukuran": st.st_size,
                "video_id": vid,
                "klip": klip_per_video.get(vid, 0),
                "dipakai": st.st_atime,
                # Kapan berkasnya ditulis, yaitu kapan ia diunduh. Dipakai
                # usulan pembersihan, BUKAN st_atime: memindahkan folder
                # menyetel ulang waktu-akses semua berkas (terukur, semuanya
                # jadi "0 hari" beberapa menit setelah dipindah), sedangkan
                # waktu-tulisnya ikut pindah apa adanya.
                "diunduh": st.st_mtime,
                "dianalisis": bool(vid and analyses_repo.latest_for_video(vid)),
            })
    except OSError:
        pass
    sumber.sort(key=lambda s: s["ukuran"], reverse=True)

    try:
        _, _, sisa = shutil.disk_usage(STORAGE_DIR)
    except OSError:
        sisa = 0
    return {"folder": folder, "sumber": sumber[:60], "sisa_ruang": sisa,
            "total": sum(f["ukuran"] for f in folder),
            "usul": _usul(sumber)}


# Sebuah unduhan layak diusulkan dibuang bila KETIGA syarat ini terpenuhi.
# Ketiganya ada supaya usulnya tidak pernah menyentuh pekerjaan yang belum
# selesai: tanpa syarat "sudah ada klipnya", ia akan menawarkan membuang video
# yang baru diunduh tadi pagi dan belum sempat diklip.
USUL_KLIP_MIN = 1          # sudah menghasilkan klip jadi
USUL_UMUR_HARI = 14        # sudah lama diunduh
USUL_BESAR_MIN = 300 * 1024 * 1024   # cukup besar untuk sepadan


def _usul(sumber: list[dict]) -> dict:
    """
    Video sumber yang layak dibuang, beserta alasannya.

    Bukan penghapus otomatis, dan itu keputusan yang tidak berubah: mengklip
    ulang video yang sudah dihapus berarti mengunduhnya lagi, dan mesin tidak
    tahu mana yang masih akan dipakai pemiliknya. Yang ditambahkan di sini
    hanya PERTANYAANNYA, supaya ruang yang bisa dikembalikan tidak perlu
    ditemukan sendiri di antara enam puluh baris.
    """
    import time as _t

    batas = _t.time() - USUL_UMUR_HARI * 86400
    pilih = [s for s in sumber
             if s["klip"] >= USUL_KLIP_MIN
             and s["ukuran"] >= USUL_BESAR_MIN
             and s.get("diunduh", s["dipakai"]) < batas]
    return {
        "berkas": [s["berkas"] for s in pilih],
        "jumlah": len(pilih),
        "ukuran": sum(s["ukuran"] for s in pilih),
        "syarat": {"klip_min": USUL_KLIP_MIN, "umur_hari": USUL_UMUR_HARI,
                   "besar_min": USUL_BESAR_MIN},
    }


# Folder yang isinya boleh dibuang lewat antarmuka. Yang lain sengaja tidak:
# klip adalah hasil kerja, dan model serta alat akan diunduh ulang.
BOLEH_DIBUANG = ("unduhan", "proksi", "suara", "impor")


def buang(nama_folder: str, berkas: list[str]) -> dict:
    """Menghapus berkas tertentu dari satu folder. Nama diperiksa, bukan dipercaya."""
    from ..errors import AppError
    if nama_folder not in BOLEH_DIBUANG:
        raise AppError(f"Folder '{nama_folder}' tidak boleh dibersihkan dari sini.",
                       code="FOLDER_TERLINDUNG", status=422)
    dasar = _folder_terpantau()[nama_folder].resolve()
    dibuang = terbuang = 0
    for nama in berkas or []:
        p = (dasar / Path(nama).name).resolve()
        # Berkas HARUS berada di dalam foldernya. Nama datang dari peramban,
        # dan "../../omniclip.db" adalah nama berkas yang sah.
        if dasar not in p.parents or not p.is_file():
            continue
        try:
            besar = p.stat().st_size
            p.unlink()
            # Sidecar ikut, supaya tidak meninggalkan .json dan .srt yatim.
            for tambahan in (p.with_suffix(".json"), p.with_suffix(".srt")):
                if tambahan.is_file():
                    tambahan.unlink()
            dibuang += 1
            terbuang += besar
        except OSError as e:
            log.warning("Tidak bisa menghapus %s: %s", p.name, e)
    log.info("Dibersihkan: %d berkas, %.1f MB dari %s", dibuang, terbuang / 1e6, nama_folder)
    return {"dibuang": dibuang, "ukuran": terbuang}


# --- Cadangan -------------------------------------------------------------------
def _nama_cadangan() -> Path:
    return FOLDER_CADANGAN / f"omniclip-{time.strftime('%Y%m%d-%H%M%S')}.db"


def cadangkan() -> dict:
    """
    Menyalin basis data dengan API cadangan SQLite, bukan dengan salin berkas.

    Bedanya bukan teori: dengan WAL menyala, menyalin berkasnya saja
    menghasilkan basis data yang kehilangan transaksi terakhir — dan yang
    kehilangan itu baru ketahuan saat cadangannya dipakai, yaitu pada hari
    ketika ia satu-satunya yang tersisa.
    """
    FOLDER_CADANGAN.mkdir(parents=True, exist_ok=True)
    tujuan = _nama_cadangan()
    asal = sqlite3.connect(str(DB_PATH))
    salin = sqlite3.connect(str(tujuan))
    try:
        with salin:
            asal.backup(salin)
    finally:
        salin.close()
        asal.close()
    _pangkas()
    besar = tujuan.stat().st_size
    log.info("Cadangan dibuat: %s (%.1f MB)", tujuan.name, besar / 1e6)
    return {"berkas": tujuan.name, "ukuran": besar, "folder": str(FOLDER_CADANGAN)}


def _pangkas() -> None:
    try:
        semua = sorted(FOLDER_CADANGAN.glob("omniclip-*.db"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for p in semua[MAKS_CADANGAN:]:
            p.unlink(missing_ok=True)
    except OSError:
        pass


def daftar_cadangan() -> list[dict]:
    if not FOLDER_CADANGAN.is_dir():
        return []
    keluar = []
    for p in sorted(FOLDER_CADANGAN.glob("omniclip-*.db"),
                    key=lambda x: x.stat().st_mtime, reverse=True):
        st = p.stat()
        keluar.append({"berkas": p.name, "ukuran": st.st_size, "waktu": st.st_mtime})
    return keluar


def siapkan_pulih(nama: str) -> dict:
    """
    Menandai cadangan yang akan dipakai saat aplikasi dimulai berikutnya.

    Tidak menimpa sekarang juga, dan itu disengaja: basis data yang sedang
    dipegang puluhan pekerjaan tidak bisa ditukar dari dalam dirinya sendiri
    tanpa membuat separuh di antaranya gagal dengan galat yang tidak
    menjelaskan apa-apa.
    """
    from ..errors import AppError
    p = (FOLDER_CADANGAN / Path(nama).name)
    if not p.is_file():
        raise AppError("Berkas cadangan itu tidak ada.", code="CADANGAN_HILANG", status=404)
    PENANDA_PULIH.write_text(p.name, encoding="utf-8")
    return {"berkas": p.name,
            "pesan": "Cadangan akan dipakai saat OmniClip dijalankan berikutnya. "
                     "Tutup aplikasi, lalu buka lagi."}


def batalkan_pulih() -> None:
    PENANDA_PULIH.unlink(missing_ok=True)


def pulihkan_bila_diminta() -> Optional[str]:
    """
    Dipanggil SEBELUM basis data dibuka, saat aplikasi dimulai.

    Basis data yang sekarang tidak dibuang melainkan disimpan sebagai
    `.sebelum-pulih`: kalau pemiliknya salah memilih cadangan, keadaan
    sebelumnya masih ada dan bisa dikembalikan tangan.
    """
    if not PENANDA_PULIH.is_file():
        return None
    try:
        nama = PENANDA_PULIH.read_text(encoding="utf-8").strip()
        sumber = FOLDER_CADANGAN / Path(nama).name
        if not sumber.is_file():
            log.warning("Cadangan %s tidak ditemukan; pemulihan dilewati", nama)
            return None
        if DB_PATH.is_file():
            shutil.copy2(DB_PATH, DB_PATH.with_suffix(".db.sebelum-pulih"))
        for akhiran in ("-wal", "-shm"):
            Path(str(DB_PATH) + akhiran).unlink(missing_ok=True)
        shutil.copy2(sumber, DB_PATH)
        log.info("Basis data dipulihkan dari %s", nama)
        return nama
    except OSError as e:
        log.error("Pemulihan gagal: %s", e)
        return None
    finally:
        PENANDA_PULIH.unlink(missing_ok=True)
