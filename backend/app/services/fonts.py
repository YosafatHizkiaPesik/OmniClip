"""
Font untuk aksara yang tidak dipakai bahasa Indonesia.

Tiga belas font display yang dibundel semuanya hanya memuat huruf Latin. Pada
video Jepang, Korea, Mandarin, atau Arab, libass tidak menemukan satu pun huruf
yang diminta dan menggambar kotak kosong — subtitle yang terlihat seperti
barisan tofu, dan baru ketahuan sesudah render selesai. Di komputer ini
kebetulan ada font Jepang sistem, jadi cacat itu tidak pernah muncul saat
diuji; di Windows yang baru dipasang, ia muncul pada video pertama.

Noto Sans memuat semuanya, tapi berkasnya 4-8 MB per aksara. Karena itu ia
TIDAK dibundel: ia diunduh sekali saat aksaranya benar-benar dipakai, sama
seperti bobot Whisper dan YAMNet, dari rilis resmi Google dengan versi dan
SHA-256 yang dipatok.

Semuanya berlisensi SIL Open Font License 1.1, yang mengizinkan distribusi
ulang tanpa menular ke kode aplikasi.
"""

import hashlib
import logging
import shutil
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Optional

from ..config import FONTS_DIR, FROZEN, STORAGE_DIR

log = logging.getLogger("omniclip.fonts")

_kunci = threading.Lock()

# aksara -> (berkas, keluarga, alamat, sha256)
NOTO = {
    "jp": ("NotoSansJP-Bold.otf", "Noto Sans JP",
           "https://github.com/notofonts/noto-cjk/raw/Sans2.004/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf",
           "1b0edfb500b73a4fa8a4fcaae1bbbd403994e08e73e3e0da37e70d3853f42c5f"),
    "kr": ("NotoSansKR-Bold.otf", "Noto Sans KR",
           "https://github.com/notofonts/noto-cjk/raw/Sans2.004/Sans/SubsetOTF/KR/NotoSansKR-Bold.otf",
           "5a6ceb287ed2fc6cfc6213144ebea68cbd94b20fc9eb873d8486493bf02d9bda"),
    "sc": ("NotoSansSC-Bold.otf", "Noto Sans SC",
           "https://github.com/notofonts/noto-cjk/raw/Sans2.004/Sans/SubsetOTF/SC/NotoSansSC-Bold.otf",
           "c6cb5a93abaa9edc8ee7463b7ebb7f42d618d40e6ed2f7a5371c97b0b64767c0"),
    "ar": ("NotoSansArabic-Bold.ttf", "Noto Sans Arabic",
           "https://github.com/notofonts/notofonts.github.io/raw/main/fonts/"
           "NotoSansArabic/hinted/ttf/NotoSansArabic-Bold.ttf",
           "4e5462d2e8be880317b9f49b5b2da109ddb6a3563d91cc604b67f3535832a555"),
}

# Rentang huruf yang menentukan aksara sebuah teks. Urutannya penting: Hiragana
# dan Katakana hanya ada di bahasa Jepang, sedangkan Han dipakai Jepang maupun
# Mandarin — jadi kana diperiksa lebih dulu, dan Han tanpa kana berarti
# Mandarin.
_RENTANG = (
    ("jp", ((0x3040, 0x309F), (0x30A0, 0x30FF), (0x31F0, 0x31FF))),
    ("kr", ((0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F))),
    ("sc", ((0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0xF900, 0xFAFF))),
    ("ar", ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))),
)


def aksara(teks: str) -> Optional[str]:
    """Aksara non-Latin yang dipakai teks ini, atau None."""
    ada = set()
    for c in teks or "":
        n = ord(c)
        for nama, rentang in _RENTANG:
            if any(a <= n <= b for a, b in rentang):
                ada.add(nama)
                break
    if not ada:
        return None
    # Kana menang atas Han: teks Jepang hampir selalu memuat keduanya, dan
    # Noto Sans JP memuat kedua-duanya juga.
    for nama, _r in _RENTANG:
        if nama in ada:
            return nama
    return None


def dir_font() -> Path:
    """
    Satu folder berisi SEMUA font yang dipakai libass.

    libass hanya menerima satu `fontsdir`, jadi font bawaan dan font yang
    diunduh harus tinggal bersama. Saat dijalankan dari sumber, folder bundel
    memang bisa ditulis dan dipakai apa adanya. Saat terbungkus, isinya tidak
    bisa ditulis — jadi font bawaan disalin sekali ke penyimpanan pengguna, dan
    font unduhan menyusul ke sana.
    """
    if not FROZEN:
        return FONTS_DIR
    tujuan = STORAGE_DIR / "fonts"
    tujuan.mkdir(parents=True, exist_ok=True)
    try:
        for f in FONTS_DIR.glob("*.ttf"):
            sasaran = tujuan / f.name
            if not sasaran.is_file() or sasaran.stat().st_size != f.stat().st_size:
                shutil.copy2(f, sasaran)
    except OSError as e:
        log.warning("Font bawaan tidak bisa disalin: %s", e)
        return FONTS_DIR
    return tujuan


def _unduh(alamat: str, sha: str, tujuan: Path) -> bool:
    with tempfile.NamedTemporaryFile(delete=False, dir=str(tujuan.parent),
                                     suffix=".unduh") as tmp:
        sementara = Path(tmp.name)
    try:
        with urllib.request.urlopen(alamat, timeout=180) as r, sementara.open("wb") as f:
            cerna = hashlib.sha256()
            while True:
                bagian = r.read(262144)
                if not bagian:
                    break
                cerna.update(bagian)
                f.write(bagian)
        if cerna.hexdigest() != sha:
            log.error("Font %s tidak cocok sidiknya — dibuang", tujuan.name)
            sementara.unlink(missing_ok=True)
            return False
        sementara.replace(tujuan)
        return True
    except Exception as e:
        log.warning("Font %s gagal diunduh: %s", tujuan.name, str(e)[:200])
        sementara.unlink(missing_ok=True)
        return False


def keluarga_untuk(teks: str, *, unduh: bool = True) -> Optional[str]:
    """
    Nama keluarga font yang sanggup menggambar teks ini, atau None bila huruf
    Latin saja (yang font bawaannya sudah bisa).

    Font yang belum ada diunduh di sini, sekali, dan pemanggilan berikutnya
    memakai berkas yang sama. Bila unduhannya gagal — tidak ada internet, atau
    rilisnya berubah — jawabannya None: subtitle tetap dirender dengan font
    bawaan, dan kotak kosong lebih baik daripada render yang tidak jadi sama
    sekali.
    """
    kode = aksara(teks)
    if not kode:
        return None
    berkas, keluarga, alamat, sha = NOTO[kode]
    jalur = dir_font() / berkas
    if jalur.is_file():
        return keluarga
    if not unduh:
        return None
    with _kunci:
        if jalur.is_file():           # diunduh oleh pemanggil lain sementara menunggu
            return keluarga
        log.info("Mengunduh font %s untuk aksara %s…", keluarga, kode)
        if not _unduh(alamat, sha, jalur):
            return None
    return keluarga


def terpasang() -> list[dict]:
    """Font aksara yang sudah ada di komputer ini — untuk halaman kesehatan."""
    d = dir_font()
    return [{"aksara": k, "keluarga": v[1], "ada": (d / v[0]).is_file()}
            for k, v in NOTO.items()]
