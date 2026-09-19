"""
Cookies YouTube: diambil langsung dari browser, atau dari berkas cookies.txt.

Sebelumnya satu-satunya jalan adalah menyetel variabel lingkungan
`OMNICLIP_COOKIES_FILE` sebelum aplikasi dijalankan — tidak bisa dilakukan dari
dalam aplikasi yang sudah menyala, apalagi dari exe yang diklik dua kali. Saat
YouTube menuntut verifikasi bot, pesan yang muncul menyuruh melakukan sesuatu
yang tidak tersedia di tempat pesan itu muncul.

yt-dlp bisa membaca basis data cookie browser sendiri (`cookiesfrombrowser`),
jadi tidak ada berkas yang perlu diekspor siapa pun. Itu jalur utama di sini;
unggah cookies.txt disediakan untuk kasus browsernya ada di komputer lain.

PERINGATAN YANG DIUKUR, bukan diduga (16 September 2026, yt-dlp 2026.08.19):
cookies dari browser yang SEDANG LOGIN justru membuat ekstraksi lebih buruk.
Diuji pada tiga video, permintaan polos mengembalikan 37/34/32 format video;
permintaan yang sama dengan cookies Firefox mengembalikan NOL untuk ketiganya.
Sesi yang terautentikasi menuntut proof-of-origin token yang tidak bisa dibuat
yt-dlp sendiri, dan tanpa token itu YouTube membalas dengan metadata tanpa satu
pun format yang bisa diunduh.

Karena itu dua hal di modul ini tidak boleh dilepas:
  * `uji()` menjalankan perbandingan yang sama secara nyata dan melaporkan
    angkanya, supaya jawabannya datang dari YouTube hari ini dan bukan dari
    komentar ini.
  * `patut_dicoba_tanpa_cookies()` membuat pemanggil mundur ke permintaan polos
    ketika cookies menghasilkan nol format.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Optional

from ..repos import settings as settings_repo

# Nama yang dikenal yt-dlp. `safari` sengaja tidak ditawarkan di Linux/Windows.
BROWSER_CHROMIUM = ("chrome", "chromium", "brave", "edge", "opera", "vivaldi")
BROWSER_SEMUA = ("firefox",) + BROWSER_CHROMIUM + ("safari",)

KUNCI_MODE = "cookies.mode"        # "mati" | "browser" | "berkas"
KUNCI_BROWSER = "cookies.browser"
KUNCI_PROFIL = "cookies.profil"
KUNCI_BERKAS = "cookies.berkas"


def _dir_browser(nama: str) -> Optional[str]:
    """
    Folder profil sebuah browser di komputer ini, atau None kalau tidak ada.

    Memakai penunjuk jalur milik yt-dlp sendiri alih-alih menyalin daftar jalur
    per sistem operasi: daftar itu berubah (snap, flatpak, Chrome di Windows),
    dan salinan yang membeku akan mengatakan "tidak terpasang" untuk browser
    yang sebenarnya ada.
    """
    try:
        if nama == "firefox":
            from yt_dlp.cookies import _firefox_browser_dirs
            for d in _firefox_browser_dirs():
                if os.path.isdir(d):
                    return d
            return None
        if nama == "safari":
            d = os.path.expanduser("~/Library/Cookies")
            return d if os.path.isdir(d) else None
        from yt_dlp.cookies import _get_chromium_based_browser_settings
        d = _get_chromium_based_browser_settings(nama).get("browser_dir")
        return d if d and os.path.isdir(d) else None
    except Exception:
        return None


def daftar_browser() -> list[dict]:
    """Browser yang benar-benar punya profil di komputer ini."""
    import sys
    keluar = []
    for nama in BROWSER_SEMUA:
        if nama == "safari" and sys.platform != "darwin":
            continue
        d = _dir_browser(nama)
        if d:
            keluar.append({"nama": nama, "folder": d})
    return keluar


def sumber() -> dict:
    """Pilihan cookies yang sedang berlaku."""
    mode = settings_repo.get(KUNCI_MODE, "mati") or "mati"
    berkas = settings_repo.get(KUNCI_BERKAS, "")
    # Variabel lingkungan tetap dihormati dan menang, supaya pemasangan lama
    # yang sudah menyetelnya tidak berubah perilaku diam-diam.
    env = os.environ.get("OMNICLIP_COOKIES_FILE", "").strip()
    if env and os.path.exists(env):
        return {"mode": "berkas", "browser": "", "profil": "", "berkas": env,
                "dari_env": True}
    if mode == "berkas" and not (berkas and os.path.exists(berkas)):
        mode = "mati"
    return {
        "mode": mode,
        "browser": settings_repo.get(KUNCI_BROWSER, ""),
        "profil": settings_repo.get(KUNCI_PROFIL, ""),
        "berkas": berkas,
        "dari_env": False,
    }


def simpan(mode: str, *, browser: str = "", profil: str = "", berkas: str = "") -> dict:
    if mode not in ("mati", "browser", "berkas"):
        raise ValueError("Mode cookies harus 'mati', 'browser', atau 'berkas'.")
    if mode == "browser" and browser not in BROWSER_SEMUA:
        raise ValueError(f"Browser '{browser}' tidak dikenal yt-dlp.")
    if mode == "berkas" and not (berkas and os.path.exists(berkas)):
        raise ValueError("Berkas cookies tidak ditemukan.")
    # Pilihan baru dari pengguna membatalkan pelewatan otomatis: keputusannya
    # yang menang, dan hasilnya dinilai ulang dari nol.
    _batalkan_pelewatan()
    settings_repo.set_value(KUNCI_MODE, mode)
    settings_repo.set_value(KUNCI_BROWSER, browser)
    settings_repo.set_value(KUNCI_PROFIL, profil)
    if berkas:
        settings_repo.set_value(KUNCI_BERKAS, berkas)
    return sumber()


# ---------------------------------------------------------------------------
# Pelewatan otomatis
#
# Kalau permintaan dengan cookies gagal dan permintaan yang sama tanpa cookies
# berhasil, cookies-nya sedang merugikan. Tanpa catatan ini, SETIAP permintaan
# berikutnya mengulang seluruh putaran yang gagal itu lebih dulu — terukur 22
# detik untuk membuka satu halaman video, padahal jawabannya tersedia dalam 2,7
# detik. Pengguna tidak perlu tahu apa pun tentang ini; sistem yang memutuskan.
#
# Berlaku sementara, bukan permanen: aturan YouTube berubah, dan cookies yang
# hari ini merugikan bisa besok justru satu-satunya jalan masuk.
# ---------------------------------------------------------------------------
LAMA_DILEWATI = 6 * 3600
_kunci_lewat = threading.Lock()
_dilewati_sampai = 0.0


def lewati_sementara() -> None:
    """Menandai cookies sedang merugikan, jadi jangan dipakai dulu."""
    global _dilewati_sampai
    with _kunci_lewat:
        _dilewati_sampai = time.time() + LAMA_DILEWATI


def sedang_dilewati() -> bool:
    with _kunci_lewat:
        return time.time() < _dilewati_sampai


def _batalkan_pelewatan() -> None:
    """Dipanggil saat pengguna mengubah pilihannya sendiri."""
    global _dilewati_sampai
    with _kunci_lewat:
        _dilewati_sampai = 0.0


def terapkan(opts: dict) -> dict:
    """Menambahkan cookies ke opsi yt-dlp. Mengembalikan opts yang sama."""
    if sedang_dilewati():
        return opts
    s = sumber()
    if s["mode"] == "browser" and s["browser"]:
        # Bentuk tuple milik yt-dlp: (nama, profil, keyring, container).
        opts["cookiesfrombrowser"] = (s["browser"], s["profil"] or None, None, None)
    elif s["mode"] == "berkas" and s["berkas"]:
        opts["cookiefile"] = s["berkas"]
    return opts


def aktif() -> bool:
    """Apakah cookies benar-benar ikut dikirim pada permintaan berikutnya."""
    return sumber()["mode"] != "mati" and not sedang_dilewati()


def lupakan_cookies(opts: dict) -> dict:
    """Salinan opts tanpa cookies apa pun — dipakai untuk percobaan ulang polos."""
    bersih = dict(opts)
    bersih.pop("cookiesfrombrowser", None)
    bersih.pop("cookiefile", None)
    return bersih


# Video yang dipakai menguji. Dipilih karena sudah ada belasan tahun, publik,
# tanpa pembatasan umur maupun wilayah — jadi kegagalannya pasti soal cookies.
VIDEO_UJI = "dQw4w9WgXcQ"


def _hitung_format(opts: dict) -> tuple[int, str]:
    """(jumlah format video, pesan galat) untuk satu set opsi yt-dlp."""
    import yt_dlp
    o = {"quiet": True, "no_warnings": True, "skip_download": True,
         "socket_timeout": 30, "ignore_no_formats_error": True, **opts}
    try:
        with yt_dlp.YoutubeDL(o) as ydl:
            info = ydl.extract_info(VIDEO_UJI, download=False, process=False)
    except Exception as e:
        return 0, str(e)[:200]
    n = sum(1 for f in (info.get("formats") or [])
            if f.get("vcodec", "none") != "none" and f.get("height"))
    return n, ""


def uji() -> dict:
    """
    Menjalankan perbandingan sungguhan: dengan cookies versus tanpa cookies.

    Jawabannya harus datang dari YouTube saat tombolnya ditekan. Aturan tentang
    proof-of-origin token berubah tanpa pemberitahuan, jadi apa pun yang ditulis
    sebagai kesimpulan tetap di kode ini akan salah suatu hari nanti.
    """
    s = sumber()
    polos, galat_polos = _hitung_format({})
    if s["mode"] == "mati":
        return {"mode": "mati", "polos": polos, "galat_polos": galat_polos,
                "dengan": None, "galat": "", "terbaca": 0, "saran": (
                    "Tanpa cookies YouTube memberi "
                    f"{polos} format video untuk video uji."
                    if polos else
                    "Tanpa cookies YouTube tidak memberi satu pun format. "
                    "Coba pilih browser di atas, lalu uji lagi.")}

    terbaca, galat_baca = 0, ""
    try:
        from yt_dlp.cookies import load_cookies
        if s["mode"] == "browser":
            jar = load_cookies(None, (s["browser"], s["profil"] or None, None, None), None)
        else:
            jar = load_cookies(s["berkas"], None, None)
        terbaca = len(jar)
    except Exception as e:
        galat_baca = str(e)[:200]

    dengan, galat_dengan = (0, galat_baca) if galat_baca else _hitung_format(terapkan({}))

    if galat_baca:
        saran = f"Cookies tidak bisa dibaca: {galat_baca}"
    elif dengan == 0 and polos > 0:
        saran = (f"Cookies terbaca ({terbaca} butir), tapi dengan cookies ini YouTube "
                 f"tidak memberi satu pun format video — sementara tanpa cookies ia "
                 f"memberi {polos}. Jangan dipakai sekarang: sesi yang login menuntut "
                 "token yang tidak bisa dibuat yt-dlp. Matikan cookies.")
    elif dengan == 0 and polos == 0:
        saran = ("Keduanya gagal. Ini bukan soal cookies — YouTube sedang membatasi "
                 "komputer ini. Tunggu beberapa menit.")
    elif dengan >= polos:
        saran = (f"Cookies bekerja: {dengan} format dengan cookies, {polos} tanpa. "
                 "Aman dipakai.")
    else:
        saran = (f"Cookies memberi {dengan} format, tanpa cookies {polos}. "
                 "Lebih baik dimatikan.")

    return {"mode": s["mode"], "polos": polos, "galat_polos": galat_polos,
            "dengan": dengan, "galat": galat_baca, "terbaca": terbaca,
            "dilewati": sedang_dilewati(), "saran": saran}


def simpan_berkas_unggahan(isi: bytes, folder: Path) -> str:
    """Menyimpan cookies.txt yang diunggah, memvalidasi bentuknya lebih dulu."""
    teks = isi.decode("utf-8", errors="replace")
    baris = [b for b in teks.splitlines() if b.strip() and not b.startswith("#")]
    # Format Netscape: tujuh kolom dipisah tab. Satu baris sah sudah cukup untuk
    # membedakan berkas yang benar dari berkas yang salah pilih.
    if not any(len(b.split("\t")) == 7 for b in baris):
        raise ValueError(
            "Ini bukan berkas cookies Netscape. Ekspor ulang dengan ekstensi "
            "seperti 'Get cookies.txt LOCALLY' saat membuka youtube.com.")
    folder.mkdir(parents=True, exist_ok=True)
    tujuan = folder / "youtube_cookies.txt"
    tujuan.write_text(teks, encoding="utf-8")
    try:
        os.chmod(tujuan, 0o600)   # berisi sesi login; jangan terbaca user lain
    except OSError:
        pass
    return str(tujuan)
