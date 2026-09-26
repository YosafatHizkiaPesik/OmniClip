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
        hasil.append(_rekam(tujuan, nama=label, jenis="audio", bawaan=True,
                            catatan=catatan, kategori="efek"))
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
        label, catatan, _r, _d = EFEK[k]
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
