"""
Aset yang bisa disisipkan ke klip: video, gambar, musik, dan efek suara.

Dua sumber:

  - BERKAS PENGGUNA, diimpor lewat Studio — cuplikan pertandingan untuk
    podcast bola, musik latar, logo. Disalin ke `aset/` supaya klip tidak rusak
    saat berkas aslinya dipindahkan.
  - SOUNDBOARD, diunduh pengguna lewat `soundboard.py` dari tautan yang ia
    tempel sendiri. Sama seperti berkas pengguna begitu tersimpan.

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

# Rak pustaka. `jenis` menjawab "berkas apa ini", `kategori` menjawab "dipakai
# untuk apa" — dan kedua pertanyaan itu berbeda justru pada berkas suara: mp3
# sepanjang tiga menit dan mp3 sepanjang setengah detik sama-sama `audio`, tapi
# yang satu musik latar dan yang lain efek. Satu rak berisi keduanya membuat
# musik tenggelam di antara puluhan efek pendek begitu pustakanya bertambah.
KATEGORI = ("musik", "efek", "media")

# Batas tebakan awalnya. Bukan aturan alam, hanya titik yang membagi dua
# kebiasaan: efek klip pendek, musik latar panjang. Salah tebak pun bisa
# dipindahkan sendiri oleh pengguna, jadi batas ini tidak perlu sempurna.
DETIK_MUSIK = 20.0


def kategori_awal(jenis: str, durasi: float) -> str:
    if jenis != "audio":
        return "media"
    return "musik" if float(durasi or 0.0) >= DETIK_MUSIK else "efek"

# TIDAK ADA EFEK BAWAAN.
#
# Dicoba dua kali dan ditolak pemiliknya dua kali. Percobaan pertama
# (25 September 2026) memakai satu baris rumus `lavfi` per efek: "efek suara
# bawaan, hilangkan, jelek-jelek". Percobaan kedua (30 September) menyusunnya
# dengan numpy — transien, badan, ekor, sapuan nada dan tapis yang bergerak —
# dan jawabannya sama: "sama sekali tidak ada suara yang saya suka dan akan
# saya pakai".
#
# Kesimpulannya bukan sintesisnya kurang bagus, melainkan yang dicari memang
# bukan suara sintetis. Yang dipakai pembuat klip Indonesia adalah potongan
# soundboard: tawa, teriakan, kutipan acara. Itu rekaman milik orang lain, dan
# membundelnya ke dalam aplikasi yang DIJUAL berarti memindahkan masalah hak
# ciptanya ke pemilik aplikasi.
#
# Jalan keluarnya ada di `soundboard.py`: pengguna menempel tautan soundboard,
# dan OmniClip mengunduhnya ke pustaka MILIK PENGGUNA SENDIRI. Suaranya tetap
# masuk, dipilih pengguna, dan berlaku untuk suara apa pun yang ia temukan
# nanti — bukan hanya yang kebetulan ikut dibundel.
EFEK: dict = {}


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
           catatan: str = "", kategori: str = "") -> dict:
    info = _probe(path)
    durasi = round(float(info.get("duration") or 0.0), 3)
    data = {
        "id": ("efek:" + path.stem) if bawaan else path.stem,
        "nama": nama,
        "jenis": jenis,
        "bawaan": bawaan,
        "catatan": catatan,
        "kategori": kategori if kategori in KATEGORI else kategori_awal(jenis, durasi),
        "durasi": durasi,
        "lebar": int(info.get("width") or 0),
        "tinggi": int(info.get("height") or 0),
        "punya_suara": bool(info.get("acodec")),
        "berkas": path.name,
    }
    if not bawaan:
        _catatan(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def siapkan_efek() -> list[dict]:
    """Tidak ada efek bawaan lagi. Lihat catatan EFEK di atas."""
    return []


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
                if data.get("kategori") not in KATEGORI:
                    data["kategori"] = kategori_awal(
                        data.get("jenis", ""), data.get("durasi", 0.0))
                milik.append(data)
    return efek + milik


def setel_kategori(aset_id: str, kategori: str) -> Optional[dict]:
    """
    Memindahkan aset ke rak lain.

    Tebakan awal memakai durasi, dan durasi tidak tahu apa-apa soal maksud:
    jingle lima detik itu musik, dan rekaman tawa satu menit itu efek. Karena
    itu raknya bisa dipindahkan, dan pilihan pengguna yang disimpan.
    """
    if kategori not in KATEGORI:
        return None
    pth = jalur(aset_id)
    # Aset bawaan tidak punya berkas catatan yang bisa ditulisi; raknya tetap.
    if pth is None or aset_id.startswith("efek:"):
        return None
    cat = _catatan(pth)
    try:
        data = json.loads(cat.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    data["kategori"] = kategori
    cat.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


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
        label, catatan = EFEK[k][:2]
        return _rekam(p, nama=label, jenis="audio", bawaan=True,
                      catatan=catatan, kategori="efek")
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
