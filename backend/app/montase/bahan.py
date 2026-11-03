"""
Bahan Montase: berkas video, suara, dan gambar yang dipakai proyek (M1.6).

Bahan tidak disalin. Ia MERUJUK berkas yang sudah ada di OmniClip:

  asal        rujukan            berkasnya
  ---------   ----------------   ------------------------------------------
  unduhan     id video YouTube   unduhan terbaik video itu (tabel downloads)
  klip_jadi   nama berkas .mp4   folder klip profil aktif
  aset        id aset            pustaka aset (services/aset.py)
  impor       id aset            berkas yang diunggah dari Montase, disimpan
                                 ke pustaka aset supaya terlihat juga di
                                 Studio Klip

Peramban hanya pernah menyebut (asal, rujukan) dan id bahan; jalurnya
diselesaikan di sini dan tidak pernah dikirim balik (P-7).

Sesudah dicatat, pekerjaan latar menyiapkan, di `<data>/montase/bahan/<id>/`:
  sampul.jpg      satu bingkai, untuk daftar bahan dan kartu proyek
  strip.jpg       sepuluh bingkai berjajar, untuk item di linimasa
  gelombang.json  puncak suara 20 per detik, untuk item di linimasa
  sunting.mp4     salinan kecil (sisi pendek 540 px, keyframe tiap 15
                  bingkai) supaya pratinjau dan penggeseran ringan. Render
                  akhir SELALU memakai berkas asli.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import shutil
from pathlib import Path
from typing import Optional

from ..config import STORAGE_DIR
from ..repos import media as media_repo
from ..repos import montase as repo
from ..services import aset as aset_svc
from ..services import profil
from ..services.media import probe
from ..services.paths import safe_media_path
from ..services.proses import jalankan

log = logging.getLogger("omniclip.montase.bahan")

ASAL = ("unduhan", "klip_jadi", "aset", "impor")
SUNTING_SISI = 540
GELOMBANG_PER_DETIK = 20
GELOMBANG_MAKS = 6000
_EKSTENSI_GAMBAR = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


class BahanTidakSah(ValueError):
    pass


def folder(bahan_id: str) -> Path:
    return STORAGE_DIR / "montase" / "bahan" / bahan_id


# --- sumber yang bisa dipilih -------------------------------------------------

def _judul_video(video_id: str) -> str:
    v = media_repo.get_video(video_id) or {}
    return v.get("title") or video_id


def sumber_tersedia(asal: str) -> list[dict]:
    """Berkas yang bisa dijadikan bahan, untuk panel Bahan. Tanpa jalur."""
    pid = profil.kini()
    if asal == "unduhan":
        hasil, sudah = [], set()
        for d in media_repo.list_downloads():
            if d.get("kind") != "video" or d["video_id"] in sudah:
                continue
            sudah.add(d["video_id"])
            hasil.append({"asal": "unduhan", "rujukan": d["video_id"],
                          "nama": _judul_video(d["video_id"]), "jenis": "video",
                          "durasi": d.get("duration"), "lebar": d.get("width"),
                          "tinggi": d.get("height")})
        return hasil
    if asal == "klip_jadi":
        dir_klip = profil.folder_klip(pid)
        if not dir_klip.is_dir():
            return []
        hasil = []
        for p in sorted(dir_klip.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
            meta = {}
            try:
                meta = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            hasil.append({"asal": "klip_jadi", "rujukan": p.name,
                          "nama": meta.get("title") or p.stem, "jenis": "video",
                          "durasi": meta.get("duration")})
        return hasil
    if asal == "aset":
        return [{"asal": "aset", "rujukan": a["id"], "nama": a.get("nama") or a["id"],
                 "jenis": a.get("jenis"), "durasi": a.get("durasi"),
                 "lebar": a.get("lebar"), "tinggi": a.get("tinggi")}
                for a in aset_svc.daftar() if a.get("jenis") in ("video", "audio", "gambar")]
    raise BahanTidakSah(f"Asal bahan tidak dikenal: {asal}")


def _jalur_sumber(pid: int, asal: str, rujukan: str) -> Path:
    if asal == "unduhan":
        d = media_repo.latest_download_for_video(rujukan)
        jalur = media_repo.abs_from_storage(d["rel_path"]) if d else None
    elif asal == "klip_jadi":
        try:
            jalur = safe_media_path(f"klip_{pid}", rujukan)
        except Exception:
            jalur = None
    elif asal in ("aset", "impor"):
        jalur = aset_svc.jalur(rujukan)
    else:
        raise BahanTidakSah(f"Asal bahan tidak dikenal: {asal}")
    if jalur is None or not Path(jalur).is_file():
        raise BahanTidakSah("Berkasnya tidak ditemukan.")
    return Path(jalur)


def _jenis(jalur: Path, info: dict) -> str:
    if jalur.suffix.lower() in _EKSTENSI_GAMBAR:
        return "gambar"
    if info.get("width"):
        return "video"
    if info.get("acodec"):
        return "audio"
    raise BahanTidakSah("Berkas ini bukan video, suara, atau gambar yang bisa dibaca.")


def rujuk(asal: str, rujukan: str, *, nama: Optional[str] = None) -> dict:
    """Mencatat bahan (atau mengembalikan yang sudah ada) dan menjadwalkan persiapannya."""
    if asal not in ASAL:
        raise BahanTidakSah(f"Asal bahan tidak dikenal: {asal}")
    pid = profil.kini()
    ada = repo.cari_bahan(pid, asal, rujukan)
    if ada is not None:
        return ada
    jalur = _jalur_sumber(pid, asal, rujukan)
    info = probe(jalur)
    jenis = _jenis(jalur, info)
    if nama is None:
        if asal == "unduhan":
            nama = _judul_video(rujukan)
        elif asal in ("aset", "impor"):
            nama = (aset_svc.info(rujukan) or {}).get("nama") or jalur.stem
        else:
            nama = jalur.stem
    data = {
        "asal": asal, "rujukan": rujukan, "nama": nama[:200],
        "rel_path": media_repo.rel_to_storage(jalur), "jenis": jenis,
        "durasi": info.get("duration") if jenis != "gambar" else None,
        "lebar": info.get("width"), "tinggi": info.get("height"), "fps": info.get("fps"),
        "ada_suara": bool(info.get("acodec")),
    }
    baris = repo.catat_bahan(pid, data)
    _jadwalkan_persiapan(baris["id"], pid)
    return baris


def _jadwalkan_persiapan(bahan_id: str, pid: int) -> None:
    try:
        from ..services.jobs import queue
        queue.enqueue("montase_bahan", {"bahan_id": bahan_id, "profil_id": pid},
                      lane="latar", dedupe_key=f"montase_bahan:{bahan_id}")
    except Exception as e:      # noqa: BLE001 - tanpa antrean (tes), bahan tetap tercatat
        log.info("Persiapan bahan %s tidak dijadwalkan: %s", bahan_id, e)


def jalur_asli(pid: int, bahan_id: str) -> Optional[Path]:
    b = repo.ambil_bahan(pid, bahan_id, dengan_jalur=True)
    if b is None:
        return None
    jalur = media_repo.abs_from_storage(b["rel_path"])
    return jalur if jalur.is_file() else None


def jalur_berkas(pid: int, bahan_id: str, *, sunting: bool) -> Optional[Path]:
    """Berkas untuk dibaca: salinan sunting bila diminta dan sudah jadi, selain itu asli."""
    if sunting:
        salinan = folder(bahan_id) / "sunting.mp4"
        if salinan.is_file() and repo.ambil_bahan(pid, bahan_id) is not None:
            return salinan
    return jalur_asli(pid, bahan_id)


def jenis_media(jalur: Path) -> str:
    jenis, _ = mimetypes.guess_type(str(jalur))
    return jenis or "application/octet-stream"


def dipakai_proyek(pid: int, bahan_id: str) -> list[str]:
    """Nama proyek yang memakai bahan ini (untuk menolak penghapusan)."""
    nama = []
    for p in repo.daftar_proyek(pid):
        dok = (repo.ambil_proyek(pid, p["id"]) or {}).get("dokumen", {})
        if bahan_id in dok.get("bahan", {}):
            nama.append(p["nama"])
    return nama


def hapus(pid: int, bahan_id: str) -> bool:
    b = repo.ambil_bahan(pid, bahan_id, dengan_jalur=True)
    if not repo.hapus_bahan(pid, bahan_id):
        return False
    shutil.rmtree(folder(bahan_id), ignore_errors=True)
    if b is not None:
        from .narasi import hapus_berkas_milik
        hapus_berkas_milik(b)
    return True


# --- persiapan di latar -------------------------------------------------------

def _ffmpeg(args: list[str], *, timeout: float) -> bool:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-loglevel", "error", *args]
    try:
        r = jalankan(cmd, rendah=True, timeout=timeout)
    except Exception as e:      # noqa: BLE001
        log.warning("ffmpeg bahan gagal: %s", e)
        return False
    if r.returncode != 0:
        log.warning("ffmpeg bahan gagal: %s", (r.stderr or "")[-300:])
    return r.returncode == 0


def _gelombang(sumber: Path, durasi: float, tujuan: Path) -> None:
    import subprocess

    import numpy as np

    from ..services.proses import popen
    laju = 8000
    proc = popen(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(sumber),
                  "-vn", "-ac", "1", "-ar", str(laju), "-f", "s16le", "-"],
                 rendah=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        data, _ = proc.communicate(timeout=max(120, durasi * 2))
    finally:
        from ..services.proses import lepas
        lepas(proc)
    sampel = np.frombuffer(data, dtype=np.int16)
    if sampel.size == 0:
        return
    n = int(min(GELOMBANG_MAKS, max(1, round(durasi * GELOMBANG_PER_DETIK))))
    potongan = np.array_split(np.abs(sampel.astype(np.int32)), n)
    puncak = np.array([p.max() if p.size else 0 for p in potongan], dtype=np.float64)
    tertinggi = float(puncak.max()) or 1.0
    tujuan.write_text(json.dumps({
        "per_detik": n / durasi if durasi else GELOMBANG_PER_DETIK,
        "puncak": [round(float(v) / tertinggi, 3) for v in puncak],
    }), encoding="utf-8")


def siapkan(bahan_id: str, pid: int) -> dict:
    """Sampul, strip, gelombang, dan salinan sunting. Yang gagal dilewati, bukan menjatuhkan."""
    b = repo.ambil_bahan(pid, bahan_id)
    sumber = jalur_asli(pid, bahan_id)
    if b is None or sumber is None:
        return {"siap": False}
    d = folder(bahan_id)
    d.mkdir(parents=True, exist_ok=True)
    durasi = float(b.get("durasi") or 0)
    hasil = {}

    if b["jenis"] in ("video", "gambar"):
        detik = min(1.0, durasi / 3) if durasi else 0
        hasil["sampul"] = _ffmpeg(["-ss", f"{detik:.2f}", "-i", str(sumber), "-frames:v", "1",
                                   "-vf", "scale=-2:360", str(d / "sampul.jpg")], timeout=120)
    if b["jenis"] == "video" and durasi > 0:
        hasil["strip"] = _ffmpeg(["-i", str(sumber), "-vf",
                                  f"fps=10/{durasi:.3f},scale=-2:90,tile=10x1",
                                  "-frames:v", "1", str(d / "strip.jpg")],
                                 timeout=max(300, durasi))
        sementara = d / "sunting.tmp.mp4"
        sisi = (f"scale='if(gt(iw,ih),-2,{SUNTING_SISI})':'if(gt(iw,ih),{SUNTING_SISI},-2)'")
        hasil["sunting"] = _ffmpeg(
            ["-i", str(sumber), "-vf", sisi, "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "26", "-g", "15", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
             "-movflags", "+faststart", "-threads", "2", str(sementara)],
            timeout=max(600, durasi * 4))
        if hasil["sunting"]:
            sementara.replace(d / "sunting.mp4")
        else:
            sementara.unlink(missing_ok=True)
    if b["ada_suara"] and durasi > 0:
        try:
            _gelombang(sumber, durasi, d / "gelombang.json")
            hasil["gelombang"] = True
        except Exception as e:  # noqa: BLE001
            log.warning("Gelombang %s gagal: %s", bahan_id, e)
            hasil["gelombang"] = False
    repo.tandai_bahan_siap(bahan_id)
    return {"siap": True, **hasil}


def run_siapkan(ctx):
    """Pekerjaan antrean `montase_bahan` (lajur latar)."""
    p = ctx.payload
    ctx.progress(0.1, stage="bahan", message="Menyiapkan bahan Montase")
    return siapkan(p["bahan_id"], int(p.get("profil_id") or profil.kini()))
