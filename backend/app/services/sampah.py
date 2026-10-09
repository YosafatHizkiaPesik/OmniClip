"""
Sampah: berkas yang tidak mungkin berguna lagi, dan cara membuangnya.

Diminta pemiliknya 9 Oktober 2026: "bisa membersihkan semua sampah yang ada
dan juga jika bisa buat saja mesin yang mendeteksi sampah dan dapat
membersihkannya seperti sampah file yang gagal terunduh atau corupt".

Bedanya dengan `pemeliharaan.py` penting, dan sengaja dipisah. Di sana yang
didaftar BARANG BERHARGA yang mungkin sudah tidak dibutuhkan: video sumber
59 GB yang klipnya sudah jadi. Benda seperti itu tidak boleh dibuang mesin,
karena mesin tidak tahu mana yang masih akan dipakai, dan mengklip ulang video
yang hilang berarti mengunduhnya lagi.

Di sini yang didaftar hanya yang TIDAK MUNGKIN berguna lagi, dan tiap
kelompoknya harus bisa dibuktikan, bukan ditebak:

  salinan_terbengkalai  `.tmp.mp4` dan temannya dari penyalinan yang terputus.
                        Penyalinan yang hidup menulis ke berkasnya terus; yang
                        tidak tersentuh berjam-jam sudah pasti mati.
  pecahan_unduhan       `.part`, `.ytdl`, `.part-FragN` dari unduhan terputus.
  berkas_kosong         Berkas media nol byte. Tidak ada keadaan di mana itu
                        berguna.
  sidecar_yatim         `.json`, `.srt`, `.ass` di folder klip yang `.mp4`-nya
                        sudah tidak ada.
  turunan_yatim         Sidik suara, sampul, dan salinan pratinjau yang video
                        sumbernya sudah dihapus.
  folder_kosong         Folder akun kosong yang profilnya sudah tidak ada.
  panggung_pembaruan    Sisa bongkaran pembaruan yang berhenti di tengah.

Yang TIDAK pernah masuk daftar ini, apa pun umurnya: video sumber, klip jadi,
transkrip, model, font, dan basis data. Kalau suatu hari sesuatu dari daftar
itu muncul di sini, yang salah modul ini.

Kerusakan isi (`berkas_rusak`) diperiksa TERPISAH dan tidak ikut pemindaian
biasa. Membaca ulang tiap video dengan ffprobe memakan menit-menit CPU, dan
pemiliknya sudah pernah melaporkan laptopnya tidak bisa dipakai gara-gara
pekerjaan latar. Jadi ia hanya berjalan kalau diminta.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("omniclip.sampah")

# Berapa lama sebuah berkas sementara harus diam sebelum disebut terbengkalai.
#
# Bukan nol, dan bukan semenit. Penyalinan pratinjau menulis ke `.tmp.mp4`
# secara berkala, tapi pada video panjang jeda antar tulisan bisa puluhan detik
# saat cakramnya sibuk. Terukur pada mesin pemiliknya: salinan yang sehat
# memperbarui berkasnya setiap beberapa detik. Satu jam memberi margin yang
# sangat lebar tanpa membuat sampah menginap berhari-hari.
DIAM_LAMA = 3600.0

# Ambang yang jauh lebih pendek, dipakai HANYA saat aplikasi baru menyala.
#
# Pada saat itu tidak ada satu pun pekerjaan milik aplikasi ini yang sedang
# menulis, jadi berkas sementara apa pun di folder proksi adalah peninggalan
# proses yang sudah mati. Dua menit, bukan nol, karena sebuah salinan OmniClip
# KEDUA bisa saja sedang berjalan di komputer yang sama dan sedang menulis
# berkasnya; salinan yang hidup menyentuh berkasnya jauh lebih sering dari itu.
DIAM_MULAI = 120.0

# Media yang nol byte tetap diberi tenggang: berkas yang BARU dibuat dan belum
# ditulisi memang nol byte sesaat.
KOSONG_TENGGANG = 300.0

MEDIA = (".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".wav", ".opus", ".npz")


def _folder() -> dict:
    from .. import config as cfg
    return {
        "unduhan": Path(cfg.DOWNLOAD_DIR),
        "klip": Path(cfg.CLIPS_DIR),
        "proksi": Path(cfg.STORAGE_DIR) / "proksi",
        "suara": Path(cfg.STORAGE_DIR) / "suara",
        "sampul": Path(cfg.THUMBS_DIR),
        "impor": Path(cfg.IMPOR_DIR),
    }


def _diam(p: Path, lama: float = DIAM_LAMA) -> bool:
    """Berkas ini tidak tersentuh selama `lama` detik?"""
    try:
        return time.time() - p.stat().st_mtime > lama
    except OSError:
        return False


def _besar(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


def _temuan(p: Path, alasan: str) -> dict:
    return {"jalur": str(p), "nama": p.name, "ukuran": _besar(p), "alasan": alasan}


def _salinan_terbengkalai(folder: dict, diam: float = DIAM_LAMA) -> list[dict]:
    """
    Sisa penyalinan pratinjau yang terputus.

    Satu berkas `.tmp.mp4` bisa 220 MB, dan di mesin pemiliknya memang ada satu
    sebesar itu pada 9 Oktober 2026, peninggalan proses yang dihentikan di
    tengah jalan. Berkas kemajuan dan kuncinya ikut: tanpa `.tmp.mp4`-nya,
    keduanya tidak menerangkan apa pun.
    """
    out = []
    d = folder["proksi"]
    if not d.is_dir():
        return out
    for p in sorted(d.iterdir()):
        if not p.is_file():
            continue
        n = p.name
        if ".tmp." in n or n.endswith(".kunci"):
            # Kunci dan berkas kemajuan menunjuk salinan yang sedang dikerjakan.
            # Yang masih punya `.tmp.mp4` hidup tidak disentuh.
            pokok = d / (n.split(".tmp.")[0] + ".tmp.mp4")
            if pokok.is_file() and not _diam(pokok, diam):
                continue
            if _diam(p, diam):
                out.append(_temuan(p, "penyalinan pratinjau terputus"))
    return out


def _pecahan_unduhan(folder: dict) -> list[dict]:
    """`.part`, `.ytdl`, dan pecahan bernomor dari unduhan yang terputus."""
    out = []
    d = folder["unduhan"]
    if not d.is_dir():
        return out
    for p in sorted(d.iterdir()):
        if not p.is_file():
            continue
        n = p.name
        if n.endswith(".ytdl") or ".part" in n or n.endswith(".temp"):
            if _diam(p):
                out.append(_temuan(p, "unduhan terputus"))
    return out


def _berkas_kosong(folder: dict) -> list[dict]:
    """Media nol byte. Tidak ada keadaan di mana berkas seperti itu berguna."""
    out = []
    for nama, d in folder.items():
        if not d.is_dir():
            continue
        for akar, _sub, berkas in os.walk(d):
            for b in berkas:
                p = Path(akar) / b
                if p.suffix.lower() not in MEDIA:
                    continue
                if _besar(p) == 0 and _diam(p, KOSONG_TENGGANG):
                    out.append(_temuan(p, f"berkas kosong di folder {nama}"))
    return out


def _sidecar_yatim(folder: dict) -> list[dict]:
    """
    Keterangan klip yang videonya sudah tidak ada.

    `.json` berisi metadata render, `.srt` dan `.ass` berisi takarirnya. Tanpa
    `.mp4`-nya, ketiganya tidak bisa dipakai apa pun.
    """
    out = []
    d = folder["klip"]
    if not d.is_dir():
        return out
    for akar, _sub, berkas in os.walk(d):
        for b in berkas:
            p = Path(akar) / b
            if p.suffix.lower() not in (".json", ".srt", ".ass"):
                continue
            if not p.with_suffix(".mp4").is_file():
                out.append(_temuan(p, "keterangan klip tanpa videonya"))
    return out


def _turunan_yatim(folder: dict) -> list[dict]:
    """
    Sidik suara dan salinan pratinjau yang video sumbernya sudah dihapus.

    Keduanya menyimpan jalur sumbernya di berkas `.sumber` di sebelahnya, jadi
    pertanyaannya bisa dijawab tanpa menebak dari nama.
    """
    out = []
    for nama in ("proksi", "suara"):
        d = folder[nama]
        if not d.is_dir():
            continue
        for petunjuk in sorted(d.glob("*.sumber")):
            try:
                sumber = petunjuk.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if not sumber or Path(sumber).is_file():
                continue
            for p in sorted(d.glob(petunjuk.stem + ".*")):
                out.append(_temuan(p, f"turunan dari video yang sudah dihapus"))
    return out


def _folder_kosong(folder: dict) -> list[dict]:
    """
    Folder akun kosong yang profilnya sudah tidak ada.

    Folder milik profil yang MASIH ADA tidak disentuh walau kosong: ia akan
    diisi begitu akun itu merender sesuatu.
    """
    out = []
    d = folder["klip"]
    if not d.is_dir():
        return out
    try:
        from ..repos import profil as repo
        from . import profil as layanan
        dipakai = {str(layanan.folder_klip(p["id"]).resolve()) for p in repo.semua()}
    except Exception as e:                           # noqa: BLE001
        log.info("Daftar profil tidak terbaca: %s", str(e)[:140])
        return out
    for p in sorted(d.iterdir()):
        if not p.is_dir():
            continue
        try:
            if any(p.iterdir()) or str(p.resolve()) in dipakai:
                continue
        except OSError:
            continue
        out.append({"jalur": str(p), "nama": p.name, "ukuran": 0,
                    "alasan": "folder akun kosong yang profilnya sudah tidak ada"})
    return out


def _panggung_pembaruan() -> list[dict]:
    """Sisa bongkaran pembaruan yang berhenti di tengah, 300 MB sekali gagal."""
    out = []
    try:
        from . import updater
        induk = updater.folder_aplikasi()
    except Exception:                                # noqa: BLE001
        return out
    if induk is None:
        return out
    for d in sorted(induk.parent.glob(".omniclip-pembaruan-*")):
        if d.is_dir() and _diam(d, DIAM_LAMA):
            besar = 0
            for akar, _s, berkas in os.walk(d):
                for b in berkas:
                    besar += _besar(Path(akar) / b)
            out.append({"jalur": str(d), "nama": d.name, "ukuran": besar,
                        "alasan": "sisa pemasangan pembaruan yang terputus"})
    return out


KELOMPOK = ("salinan_terbengkalai", "pecahan_unduhan", "berkas_kosong",
            "sidecar_yatim", "turunan_yatim", "folder_kosong",
            "panggung_pembaruan")

LABEL = {
    "salinan_terbengkalai": "Salinan pratinjau yang terputus",
    "pecahan_unduhan": "Pecahan unduhan yang terputus",
    "berkas_kosong": "Berkas media kosong",
    "sidecar_yatim": "Keterangan klip tanpa videonya",
    "turunan_yatim": "Turunan dari video yang sudah dihapus",
    "folder_kosong": "Folder akun kosong",
    "panggung_pembaruan": "Sisa pemasangan pembaruan",
    "berkas_rusak": "Berkas media yang tidak bisa dibaca",
}


def pindai(saat_mulai: bool = False) -> dict:
    """
    Semua sampah yang bisa dibuktikan, tanpa membaca isi berkas apa pun.

    Murah dengan sengaja: hanya nama, ukuran, dan waktu sentuh terakhir. Yang
    menuntut pembacaan isi ada di `periksa_rusak`, dan itu tidak pernah
    berjalan sendiri.

    `saat_mulai` memakai ambang diam yang jauh lebih pendek untuk berkas
    sementara penyalinan; lihat DIAM_MULAI untuk kenapa itu sah.
    """
    folder = _folder()
    hasil: dict[str, list[dict]] = {
        "salinan_terbengkalai": _salinan_terbengkalai(
            folder, DIAM_MULAI if saat_mulai else DIAM_LAMA),
        "pecahan_unduhan": _pecahan_unduhan(folder),
        "berkas_kosong": _berkas_kosong(folder),
        "sidecar_yatim": _sidecar_yatim(folder),
        "turunan_yatim": _turunan_yatim(folder),
        "folder_kosong": _folder_kosong(folder),
        "panggung_pembaruan": _panggung_pembaruan(),
    }
    kelompok = [
        {"nama": k, "label": LABEL[k], "jumlah": len(v),
         "ukuran": sum(x["ukuran"] for x in v), "berkas": v}
        for k, v in hasil.items() if v
    ]
    return {
        "kelompok": kelompok,
        "jumlah": sum(k["jumlah"] for k in kelompok),
        "ukuran": sum(k["ukuran"] for k in kelompok),
    }


def periksa_rusak(batas: int = 400) -> dict:
    """
    Berkas media yang TIDAK BISA DIBACA, diperiksa dengan ffprobe.

    Dipisah dari `pindai` karena harganya berbeda jauh: ini membuka tiap berkas
    dan menunggu jawabannya. Pada 51 video sumber dan 8 klip itu beberapa
    menit, dan pemiliknya sudah pernah melaporkan laptopnya tidak bisa dipakai
    gara-gara pekerjaan latar. Jadi ia hanya berjalan kalau diminta.

    Yang dinilai rusak hanya yang ffprobe TOLAK sama sekali, bukan yang
    peringatannya banyak: video dengan paket cacat di tengah masih bisa dirender
    dan masih berisi pekerjaan orang.
    """
    import json
    import subprocess

    folder = _folder()
    rusak: list[dict] = []
    diperiksa = 0
    for nama, d in folder.items():
        if not d.is_dir():
            continue
        for akar, _sub, berkas in os.walk(d):
            for b in sorted(berkas):
                p = Path(akar) / b
                if p.suffix.lower() not in MEDIA or p.suffix.lower() == ".npz":
                    continue
                if diperiksa >= batas:
                    break
                if _besar(p) == 0:
                    continue                         # sudah ditangani `_berkas_kosong`
                diperiksa += 1
                try:
                    r = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries",
                         "format=duration", "-of", "json", str(p)],
                        capture_output=True, timeout=60)
                except (OSError, subprocess.SubprocessError):
                    continue
                if r.returncode != 0:
                    rusak.append(_temuan(p, f"ffprobe menolak membacanya ({nama})"))
                    continue
                try:
                    durasi = float((json.loads(r.stdout or b"{}")
                                    .get("format") or {}).get("duration") or 0)
                except (ValueError, TypeError):
                    durasi = 0.0
                if durasi <= 0:
                    rusak.append(_temuan(p, f"tanpa durasi yang bisa dibaca ({nama})"))
    return {"kelompok": [{"nama": "berkas_rusak", "label": LABEL["berkas_rusak"],
                          "jumlah": len(rusak),
                          "ukuran": sum(x["ukuran"] for x in rusak),
                          "berkas": rusak}] if rusak else [],
            "diperiksa": diperiksa, "jumlah": len(rusak),
            "ukuran": sum(x["ukuran"] for x in rusak)}


def _di_dalam_penyimpanan(p: Path) -> bool:
    """
    Benar-benar di dalam folder yang kita kelola.

    Dijaga karena fungsi di bawah MENGHAPUS, dan jalur datang dari permintaan
    HTTP. Satu jalur yang lolos berarti berkas orang lain yang hilang.
    """
    from .. import config as cfg

    akar = [Path(cfg.STORAGE_DIR), Path(cfg.DOWNLOAD_DIR), Path(cfg.CLIPS_DIR)]
    try:
        from . import updater
        app = updater.folder_aplikasi()
        if app is not None:
            akar.append(app.parent)
    except Exception:                                # noqa: BLE001
        pass
    try:
        nyata = p.resolve()
    except OSError:
        return False
    for a in akar:
        try:
            nyata.relative_to(a.resolve())
            return True
        except (ValueError, OSError):
            continue
    return False


def bersihkan(jalur: Optional[list] = None, saat_mulai: bool = False) -> dict:
    """
    Membuang sampah. Tanpa `jalur`, seluruh hasil `pindai()`.

    Jalur yang dikirim diperiksa dua kali: harus di dalam folder yang kita
    kelola, DAN harus muncul di hasil pemindaian saat ini. Yang kedua membuat
    permintaan tidak bisa menghapus berkas apa pun yang kebetulan ada di sana,
    hanya yang sudah dinilai sampah oleh aturan di berkas ini.
    """
    temuan = pindai(saat_mulai=saat_mulai)
    boleh = {b["jalur"] for k in temuan["kelompok"] for b in k["berkas"]}
    pilih = [j for j in (jalur or boleh) if j in boleh]

    dibuang = gagal = 0
    lega = 0
    for j in pilih:
        p = Path(j)
        if not _di_dalam_penyimpanan(p):
            log.warning("Jalur di luar penyimpanan ditolak: %s", j)
            gagal += 1
            continue
        besar = _besar(p)
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink(missing_ok=True)
            dibuang += 1
            lega += besar
        except OSError as e:
            log.info("Gagal membuang %s: %s", j, str(e)[:120])
            gagal += 1
    if dibuang:
        log.info("Sampah dibuang: %d berkas, %.1f MB", dibuang, lega / 1e6)
    return {"dibuang": dibuang, "gagal": gagal, "lega": lega}


def bersihkan_di_latar() -> None:
    """
    Sapuan ringan saat aplikasi menyala.

    Hanya kelompok yang tidak mungkin keliru dan tidak menuntut pembacaan isi.
    Sisanya menunggu orangnya menekan tombol, karena melihat dulu apa yang akan
    hilang adalah hak yang pantas diberikan.
    """
    import threading

    def kerja():
        try:
            temuan = pindai(saat_mulai=True)
            aman = {"salinan_terbengkalai", "pecahan_unduhan", "panggung_pembaruan"}
            jalur = [b["jalur"] for k in temuan["kelompok"] if k["nama"] in aman
                     for b in k["berkas"]]
            if jalur:
                bersihkan(jalur, saat_mulai=True)
        except Exception as e:                       # noqa: BLE001
            log.info("Sapuan sampah gagal: %s", str(e)[:140])

    threading.Thread(target=kerja, name="sapu-sampah", daemon=True).start()
