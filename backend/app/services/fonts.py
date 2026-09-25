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


# Lebar spasi tiap font, dibaca dari berkasnya sendiri.
#
# Bukan angka yang bisa ditebak: terukur pada font yang dibundel, spasi Bebas
# Neue selebar 0,16 em sementara Archivo Black 0,33 em — beda dua kali lipat.
# Itulah sebabnya "jarak antar katanya sedikit" terasa pada sebagian tema dan
# tidak pada sebagian lain, dan kenapa menambahkan jarak yang SAMA ke semuanya
# hanya memindahkan masalahnya.
_SPASI: dict[str, float] = {}
SPASI_BAWAAN = 0.26


def _berkas_keluarga(keluarga: str) -> Optional[Path]:
    from .subtitles import BUNDLED_FONTS
    for f in BUNDLED_FONTS:
        if f["family"].lower() == (keluarga or "").lower():
            return FONTS_DIR / f["file"]
    for _kode, (berkas, nama, _a, _s) in NOTO.items():
        if nama.lower() == (keluarga or "").lower():
            return dir_font() / berkas
    return None


def _baca_spasi(jalur: Path) -> Optional[float]:
    """Lebar glif spasi dalam em, langsung dari tabel hmtx berkasnya."""
    import struct
    d = jalur.read_bytes()
    n = struct.unpack(">H", d[4:6])[0]
    tabel = {}
    for i in range(n):
        r = d[12 + 16 * i:12 + 16 * i + 16]
        tabel[r[:4]] = struct.unpack(">II", r[8:16])
    if not {b"head", b"hhea", b"hmtx", b"cmap"} <= set(tabel):
        return None
    upem = struct.unpack(">H", d[tabel[b"head"][0] + 18:tabel[b"head"][0] + 20])[0]
    nhm = struct.unpack(">H", d[tabel[b"hhea"][0] + 34:tabel[b"hhea"][0] + 36])[0]

    off = tabel[b"cmap"][0]
    gid = None
    for i in range(struct.unpack(">H", d[off + 2:off + 4])[0]):
        _pid, _eid, sub = struct.unpack(">HHI", d[off + 4 + 8 * i:off + 12 + 8 * i])
        t0 = off + sub
        if struct.unpack(">H", d[t0:t0 + 2])[0] != 4:
            continue
        segx2 = struct.unpack(">H", d[t0 + 6:t0 + 8])[0]
        seg = segx2 // 2
        akhir = [struct.unpack(">H", d[t0 + 14 + 2 * j:t0 + 16 + 2 * j])[0] for j in range(seg)]
        mulai = [struct.unpack(">H", d[t0 + 16 + segx2 + 2 * j:t0 + 18 + segx2 + 2 * j])[0]
                 for j in range(seg)]
        delta = [struct.unpack(">h", d[t0 + 16 + 2 * segx2 + 2 * j:t0 + 18 + 2 * segx2 + 2 * j])[0]
                 for j in range(seg)]
        ro_off = t0 + 16 + 3 * segx2
        ro = [struct.unpack(">H", d[ro_off + 2 * j:ro_off + 2 * j + 2])[0] for j in range(seg)]
        for j in range(seg):
            if mulai[j] <= 0x20 <= akhir[j]:
                if ro[j] == 0:
                    gid = (0x20 + delta[j]) & 0xFFFF
                else:
                    q = ro_off + 2 * j + ro[j] + 2 * (0x20 - mulai[j])
                    gid = struct.unpack(">H", d[q:q + 2])[0]
                break
        if gid:
            break
    if not gid:
        return None
    hm = tabel[b"hmtx"][0]
    i = min(gid, max(0, nhm - 1))
    aw = struct.unpack(">H", d[hm + 4 * i:hm + 4 * i + 2])[0]
    return aw / upem if upem else None


def lebar_spasi(keluarga: str) -> float:
    """Lebar spasi font ini dalam em. Dibaca sekali, lalu diingat."""
    nama = (keluarga or "").strip()
    if nama in _SPASI:
        return _SPASI[nama]
    nilai = SPASI_BAWAAN
    try:
        jalur = _berkas_keluarga(nama)
        if jalur and jalur.is_file():
            nilai = _baca_spasi(jalur) or SPASI_BAWAAN
    except Exception as e:
        log.info("Lebar spasi %s tidak terbaca: %s", nama, str(e)[:120])
    _SPASI[nama] = nilai
    return nilai


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
            log.error("Font %s tidak cocok sidiknya, dibuang", tujuan.name)
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
