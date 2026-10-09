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

PENGUKURAN (yt-dlp 2026.08.19). 16 September 2026: cookies dari browser yang
login membuat YouTube mengembalikan NOL format pada tiga video, sementara
permintaan polos memberi 32-37. 21 September 2026 terungkap sebabnya: yt-dlp
berjalan TANPA runtime JavaScript. Dengan Deno terpasang (services/alat_yt.py),
dari IP yang sedang ditandai "not a bot", permintaan polos ditolak dan
permintaan dengan cookies memberi 1080p. Cookies kini jalan keluar yang sah
dari IP yang ditandai — sebaiknya dari akun Google cadangan, karena akun yang
dipakai mengunduh bisa ikut ditandai.

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
# Apakah orangnya PERNAH ditanya soal cookies. Beda dari `mode == "mati"`.
#
# Sampai 9 Oktober 2026 keduanya satu: bawaan "mati" tidak bisa dibedakan dari
# "sudah dipikirkan lalu dimatikan", jadi aplikasi tidak pernah berani bertanya
# dan tidak pernah berani memilih sendiri. Akibatnya terlapor dari seorang
# pengguna Windows yang sudah mengklip sebulan tanpa pernah membuka Pengaturan:
# YouTube menandainya bot, dan sepanjang bulan itu OmniClip memang mengirim
# permintaan tanpa cookies sama sekali.
KUNCI_DITANYA = "cookies.ditanya"
# Browser yang SIAP dipakai, tapi belum dipakai.
#
# Ini jawaban atas satu pengukuran yang tidak bisa diabaikan. 9 Oktober 2026,
# dari IP yang TIDAK sedang ditandai, pada video uji yang sama:
#
#     tanpa cookies   12 format
#     dengan cookies    7 format
#
# Jadi menyalakan cookies untuk semua orang bukan kebaikan, ia menurunkan
# pilihan resolusi orang yang jaringannya sedang sehat. Sebaliknya, dari IP
# yang SUDAH ditandai, permintaan polos ditolak sama sekali dan cookies satu-
# satunya jalan masuk (terukur 21 September 2026, lihat docstring di atas).
#
# Dua kenyataan itu hanya cocok dengan satu perilaku: sumbernya disiapkan di
# awal, dan dikirim saat YouTube mulai menolak. Lihat `nyalakan_siaga`, yang
# dipanggil dari jalur galat bot di services/ytdlp.py.
KUNCI_SIAGA = "cookies.siaga"

# Nama cookie yang membuktikan sesi YouTube yang BENAR-BENAR login.
#
# Diperiksa, bukan diasumsikan. Browser bisa punya ribuan cookie youtube.com
# tanpa satu pun sesi login, dan cookies tanpa sesi tidak menolong apa pun
# melawan verifikasi bot.
COOKIE_LOGIN = ("SID", "SAPISID", "__Secure-1PSID", "__Secure-3PAPISID", "LOGIN_INFO")


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


def periksa_browser(nama: str, profil: str = "") -> dict:
    """
    Apakah browser ini benar-benar bisa memberi sesi YouTube yang login.

    Diuji dengan membaca cookie-nya, bukan dengan menebak dari nama browser.
    Itu penting di Windows: yt-dlp 2026.08.19 belum mengerti "app-bound
    encryption" yang dipakai Chrome dan Edge sejak versi 127, jadi untuk
    browser itu pembacaannya sering gagal sekalipun browsernya terpasang dan
    pemakainya login. Menebak akan menyimpan pilihan yang tidak pernah bekerja.

    Hasil: {"nama", "profil", "terpasang", "login", "jumlah", "galat"}.
    """
    hasil = {"nama": nama, "profil": profil, "terpasang": bool(_dir_browser(nama)),
             "login": False, "jumlah": 0, "galat": ""}
    if not hasil["terpasang"]:
        return hasil

    class _Diam:
        """Pencatat yt-dlp yang tidak menulis apa pun; ini pemeriksaan diam."""

        def debug(self, *a, **k):
            pass

        info = warning = error = debug

        def to_screen(self, *a, **k):
            pass

        trouble = to_screen

    try:
        from yt_dlp.cookies import extract_cookies_from_browser
        jar = extract_cookies_from_browser(nama, profil or None, _Diam())
    except Exception as e:                           # noqa: BLE001
        hasil["galat"] = f"{type(e).__name__}: {e}"[:200]
        return hasil
    punya = {c.name for c in jar if (c.domain or "").endswith("youtube.com")}
    hasil["jumlah"] = len(punya)
    hasil["login"] = bool(set(COOKIE_LOGIN) & punya)
    if not hasil["login"]:
        hasil["galat"] = ("Browser ini tidak sedang login ke YouTube."
                          if punya else "Tidak ada cookie YouTube di browser ini.")
    return hasil


def cari_yang_login() -> list[dict]:
    """
    Semua browser di komputer ini, yang bisa memberi sesi login lebih dulu.

    Dipakai dua kali: untuk memilih sendiri saat pertama kali dijalankan, dan
    untuk menampilkan pilihan yang JUJUR di Pengaturan: termasuk alasannya
    kalau sebuah browser tidak bisa dipakai.
    """
    hasil = [periksa_browser(b["nama"]) for b in daftar_browser()]
    return sorted(hasil, key=lambda h: (not h["login"], -h["jumlah"], h["nama"]))


def sudah_ditanya() -> bool:
    """Apakah pilihan cookies pernah ditentukan, entah oleh orang atau sistem."""
    return bool(settings_repo.get(KUNCI_DITANYA, ""))


def tandai_ditanya() -> None:
    settings_repo.set_value(KUNCI_DITANYA, "1")


def siaga() -> str:
    """Browser yang sudah terbukti login dan siap dipakai saat dibutuhkan."""
    return settings_repo.get(KUNCI_SIAGA, "") or ""


def simpan_siaga(nama: str) -> None:
    settings_repo.set_value(KUNCI_SIAGA, nama or "")


def nyalakan_siaga() -> str:
    """
    Menyalakan cookies yang sudah disiapkan, karena YouTube mulai menolak.

    Mengembalikan nama browsernya bila berhasil, atau "" bila tidak ada yang
    siap atau cookies memang sudah menyala. Dipanggil dari jalur galat bot,
    bukan dari antarmuka: saat itu terjadi, orangnya sedang menunggu hasil dan
    tidak sedang membaca setelan.
    """
    nama = siaga()
    if not nama or aktif():
        return ""
    if not periksa_browser(nama)["login"]:
        # Sesinya habis sejak disiapkan. Jangan menyalakan yang sudah mati:
        # itu hanya menukar satu kegagalan dengan kegagalan lain.
        simpan_siaga("")
        return ""
    simpan("browser", browser=nama)
    return nama


def periksa_awal() -> dict:
    """
    Melihat apakah ada browser yang login, TANPA menyimpan apa pun.

    Ini sengaja tidak memutuskan sendiri. Membaca basis data cookie sebuah
    browser berarti memegang sesi Google seseorang, dan mengirimnya ke YouTube
    berarti permintaan OmniClip berjalan atas nama akun itu. Keduanya tidak
    boleh terjadi karena aplikasi menebak bahwa itu yang diinginkan.

    Ditanyakan pemiliknya 9 Oktober 2026: "apakah diawal menjalankan sistem ada
    pemberitahuan persetujuan untuk menggunakan cookies atau tidak". Jawaban
    yang benar hanya satu, yaitu harus ada, dan versi sebelum ini memang
    menyimpannya diam-diam begitu menemukan browser yang login.

    Jadi yang dikerjakan di sini cuma memeriksa, supaya kartu di Beranda bisa
    bertanya dengan menyebut browser yang memang ada. Yang menyimpan
    `simpan_siaga`, dan hanya dipanggil sesudah orangnya menekan "Izinkan".
    """
    if sudah_ditanya():
        return {"perlu_tanya": False, "alasan": "sudah pernah ditentukan",
                **sumber()}
    if (settings_repo.get(KUNCI_MODE, "") or "") not in ("", "mati"):
        # Pemasangan lama yang sudah menyetelnya sebelum ada penanda ini.
        tandai_ditanya()
        return {"perlu_tanya": False, "alasan": "sudah disetel sebelumnya", **sumber()}

    daftar = cari_yang_login()
    ada = [h for h in daftar if h["login"]]
    # `browser_tersedia`, bukan `browser`: `sumber()` sudah memakai `browser`
    # untuk NAMA browser yang dipilih, dan dua arti pada satu kunci membuat
    # yang satu menimpa yang lain tanpa suara. Tertangkap uji.
    return {"perlu_tanya": True, "browser_tersedia": daftar,
            "alasan": (f"{len(ada)} browser sedang login ke YouTube" if ada
                       else "tidak ada browser yang login"),
            **sumber()}


def periksa_awal_di_latar() -> None:
    """
    Memeriksa di latar saat aplikasi menyala; tidak boleh menahan startup.

    Hasilnya tidak disimpan dan tidak mengubah apa pun. Ia hanya memanaskan
    pemeriksaan supaya kartu di Beranda tidak menunggu lama, dan supaya
    catatan log menyebut keadaannya apa adanya.
    """
    def kerja():
        import logging
        catat = logging.getLogger("omniclip.cookies")
        try:
            h = periksa_awal()
            if h.get("perlu_tanya"):
                catat.info("Cookies belum ditentukan; Beranda akan bertanya (%s).",
                           h.get("alasan"))
        except Exception as e:                       # noqa: BLE001
            catat.info("Pemeriksaan cookies awal gagal: %s", str(e)[:140])

    threading.Thread(target=kerja, name="cookies-periksa", daemon=True).start()


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
    # Pilihan apa pun, termasuk "mati", menutup pertanyaan di Beranda.
    settings_repo.set_value(KUNCI_DITANYA, "1")
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
# Bukan Rick Astley: video itu tetap lolos saat IP sudah ditandai (21 Sep 2026,
# 1 dari 6 video yang masih lolos), jadi uji memakainya selalu berkata "aman".
VIDEO_UJI = "jNQXAC9IVRw"


def _hitung_format(opts: dict) -> tuple[int, str]:
    """(jumlah format video, pesan galat) untuk satu set opsi yt-dlp."""
    import yt_dlp
    o = {"quiet": True, "no_warnings": True, "skip_download": True,
         "socket_timeout": 30, "ignore_no_formats_error": True, **opts}
    try:
        from . import alat_yt
        alat_yt.terapkan(o)     # tanpa runtime JS, sesi login selalu gagal
    except Exception:
        pass
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
                 f"tidak memberi satu pun format video, sementara tanpa cookies ia "
                 f"memberi {polos}. Pastikan akun di browser itu masih login dan bisa "
                 "memutar video, atau matikan cookies.")
    elif dengan == 0 and polos == 0:
        saran = ("Keduanya gagal. Bila cookies terbaca tapi tetap gagal, buka YouTube "
                 "di browser itu dan pastikan akunnya masih login.")
    elif polos == 0 and dengan > 0:
        saran = (f"YouTube sedang menandai jaringan ini: tanpa cookies nol format, "
                 f"dengan cookies {dengan}. Biarkan cookies menyala.")
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
