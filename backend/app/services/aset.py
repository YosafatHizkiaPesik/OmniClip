"""
Aset yang bisa disisipkan ke klip: video, gambar, musik, dan efek suara.

Dua sumber:

  - BERKAS PENGGUNA, diimpor lewat Studio — cuplikan pertandingan untuk
    podcast bola, musik latar, logo. Disalin ke `aset/` supaya klip tidak rusak
    saat berkas aslinya dipindahkan.
  - EFEK BAWAAN, disintesis oleh ffmpeg saat pertama dibutuhkan. Daftarnya
    KOSONG sekarang (lihat `EFEK`), jadi pustaka hanya berisi berkas pengguna.
    Mesinnya sengaja ditinggal utuh: satu rumus yang ditambahkan ke `EFEK`
    cukup untuk menghidupkannya lagi.

Klien TIDAK PERNAH menyebut jalur berkas. Ia menyebut `id`, dan jalurnya dicari
di sini — sama dengan aturan untuk video sumber.
"""

import hashlib
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..config import STORAGE_DIR

log = logging.getLogger("omniclip.aset")

ASET_DIR = STORAGE_DIR / "aset"
EFEK_DIR = ASET_DIR / "efek"

EKSTENSI = {
    "video": {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"},
    "gambar": {".png", ".jpg", ".jpeg", ".webp", ".gif"},
    "audio": {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac"},
}

# Efek bawaan: nama -> (label, catatan, rumus lavfi, durasi).
#
# Masing-masing didengar dan disetel satu per satu, bukan asal sinus. Yang
# penting untuk klip vertikal adalah transien yang jelas — efek yang lembek
# tenggelam di bawah suara orang dan tidak terdengar sama sekali di speaker HP.
# Kosong sejak 25 September 2026, atas keputusan pemiliknya sesudah
# mendengarkan keenamnya: "efek suara bawaan, hilangkan, jelek-jelek".
#
# Yang ditinggalkan hanya isinya, bukan mesinnya. `siapkan_efek` di bawah masih
# bekerja, jadi menambahkan kembali satu rumus di sini cukup untuk
# menghidupkannya lagi, tanpa berkas yang perlu diunduh atau dilisensikan.
# Efek suara yang bagus dibuat dengan telinga, bukan dengan rumus lavfi, dan
# yang dipasang di sini tidak lolos telinga siapa pun.
EFEK: dict[str, tuple[str, str, str, float]] = {}


def _probe(path: Path) -> dict:
    from .media import probe
    try:
        return probe(path) or {}
    except Exception:
        return {}


def _jenis(path: Path) -> Optional[str]:
    ext = path.suffix.lower()
    for jenis, daftar in EKSTENSI.items():
        if ext in daftar:
            return jenis
    return None


def _catatan(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".json")


def _rekam(path: Path, *, nama: str, jenis: str, bawaan: bool = False,
           catatan: str = "") -> dict:
    info = _probe(path)
    data = {
        "id": ("efek:" + path.stem) if bawaan else path.stem,
        "nama": nama,
        "jenis": jenis,
        "bawaan": bawaan,
        "catatan": catatan,
        "durasi": round(float(info.get("duration") or 0.0), 3),
        "lebar": int(info.get("width") or 0),
        "tinggi": int(info.get("height") or 0),
        "punya_suara": bool(info.get("acodec")),
        "berkas": path.name,
    }
    if not bawaan:
        _catatan(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


_EFEK_SIAP: Optional[list[dict]] = None


def siapkan_efek() -> list[dict]:
    """
    Membangkitkan efek bawaan yang belum ada. Aman dipanggil berulang.

    Hasilnya ditahan di memori begitu keenam berkasnya ada: memeriksanya ulang
    dengan ffprobe setiap kali pustaka dibuka memakan 1,5 detik, untuk jawaban
    yang tidak pernah berubah.
    """
    global _EFEK_SIAP
    if _EFEK_SIAP is not None and all(
            (EFEK_DIR / f"{k}.m4a").is_file() for k in EFEK):
        return [dict(e) for e in _EFEK_SIAP]
    EFEK_DIR.mkdir(parents=True, exist_ok=True)
    hasil = []
    for kunci, (label, catatan, rumus, _durasi) in EFEK.items():
        tujuan = EFEK_DIR / f"{kunci}.m4a"
        if not tujuan.is_file():
            cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-loglevel", "error",
                   "-f", "lavfi", "-i", rumus,
                   "-af", "alimiter=limit=0.95,aformat=channel_layouts=stereo",
                   "-c:a", "aac", "-b:a", "160k", str(tujuan)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                log.warning("Efek %s gagal dibuat: %s", kunci, r.stderr[-300:])
                continue
        hasil.append(_rekam(tujuan, nama=label, jenis="audio", bawaan=True, catatan=catatan))
    if len(hasil) == len(EFEK):
        _EFEK_SIAP = [dict(e) for e in hasil]
    return hasil


def daftar() -> list[dict]:
    """Semua aset: efek bawaan lebih dulu, lalu berkas pengguna terbaru."""
    efek = siapkan_efek()
    milik: list[dict] = []
    if ASET_DIR.is_dir():
        for cat in sorted(ASET_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime,
                          reverse=True):
            try:
                data = json.loads(cat.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (ASET_DIR / data.get("berkas", "")).is_file():
                milik.append(data)
    return efek + milik


def jalur(aset_id: str) -> Optional[Path]:
    """id -> berkas di disk. None bila tidak dikenal. Tidak pernah keluar folder."""
    aset_id = (aset_id or "").strip()
    if aset_id.startswith("efek:"):
        kunci = aset_id[5:]
        if kunci not in EFEK:
            return None
        p = EFEK_DIR / f"{kunci}.m4a"
        if not p.is_file():
            siapkan_efek()
        return p if p.is_file() else None
    if not re.fullmatch(r"[a-f0-9]{16}", aset_id):
        return None
    for p in ASET_DIR.glob(f"{aset_id}.*"):
        if p.suffix != ".json" and p.is_file():
            return p
    return None


def info(aset_id: str) -> Optional[dict]:
    p = jalur(aset_id)
    if p is None:
        return None
    if aset_id.startswith("efek:"):
        k = aset_id[5:]
        label, catatan, _r, _d = EFEK[k]
        return _rekam(p, nama=label, jenis="audio", bawaan=True, catatan=catatan)
    try:
        return json.loads(_catatan(p).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def simpan_unggahan(sumber: Path, nama_asli: str) -> dict:
    """Memindahkan berkas unggahan ke folder aset. Menolak jenis yang tak dikenal."""
    jenis = _jenis(Path(nama_asli))
    if jenis is None:
        raise ValueError("Jenis berkas ini tidak didukung. Pakai video (mp4, mov, "
                         "webm), gambar (png, jpg), atau suara (mp3, wav, m4a).")
    ASET_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1()
    with open(sumber, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    sidik = h.hexdigest()[:16]
    tujuan = ASET_DIR / f"{sidik}{Path(nama_asli).suffix.lower()}"
    if not tujuan.is_file():
        shutil.move(str(sumber), tujuan)
    else:
        sumber.unlink(missing_ok=True)
    nama = Path(nama_asli).stem[:80] or sidik
    data = _rekam(tujuan, nama=nama, jenis=jenis)
    if jenis in ("video", "audio") and data["durasi"] <= 0:
        tujuan.unlink(missing_ok=True)
        _catatan(tujuan).unlink(missing_ok=True)
        raise ValueError("Berkas ini tidak bisa dibaca sebagai video atau suara.")
    return data


def hapus(aset_id: str) -> bool:
    if aset_id.startswith("efek:"):
        return False
    p = jalur(aset_id)
    if p is None:
        return False
    p.unlink(missing_ok=True)
    _catatan(p).unlink(missing_ok=True)
    return True
