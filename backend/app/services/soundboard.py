"""
Mengambil suara dari papan suara di internet ke pustaka pengguna.

Diminta pemiliknya 30 September 2026, sesudah menolak dua kali usaha membuat
efek suara sendiri: "saya lebih tertarik memasukkan soundboard seperti pada
link ini", menunjuk halaman pencarian Indonesia di myinstants.com.

**Yang diunduh adalah milik ORANG LAIN, dan itu menentukan bentuk fitur ini.**
Isi papan suara semacam itu potongan acara televisi, siaran streamer, dan lagu
— rekaman berhak cipta yang diunggah orang lain lagi. Membundelnya ke dalam
OmniClip berarti mendistribusikan ulang karya orang di dalam aplikasi yang
dijual, dan masalahnya berpindah ke pemilik aplikasi.

Jadi yang dibangun bukan bundel melainkan PENGIMPOR: pengguna menempel tautan
yang ia pilih sendiri, dan berkasnya masuk ke pustakanya sendiri, di mesinnya
sendiri. Persis seperti ia mengunduhnya lewat peramban lalu menekan Impor —
hanya tanpa langkah manualnya. Yang dipakai pengguna tetap pilihannya, dan
tanggung jawabnya tetap miliknya, sama seperti berkas apa pun yang ia impor.

Cloudflare menolak permintaan biasa dari server (terukur: 403 untuk curl
maupun yt-dlp polos). Keduanya bisa lewat dengan menyamar sebagai peramban —
`curl_cffi` untuk halamannya, `yt-dlp --impersonate chrome` untuk berkasnya.
"""
from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

log = logging.getLogger("omniclip.soundboard")

# Situs yang polanya dikenali. Selain ini, tautan LANGSUNG ke berkas suara
# tetap bisa diimpor — itu jalur yang bekerja di mana saja.
POLA_SUARA = re.compile(r"play\(\s*'([^']+\.(?:mp3|wav|ogg|m4a))'", re.I)
POLA_JUDUL = re.compile(r"""onclick="play\(\s*'([^']+)'[^"]*"\s*title="Play ([^"]*?) sound""", re.I)
EKSTENSI_SUARA = (".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".opus")

BATAS_DETIK = 30
# Papan suara berisi potongan pendek. Berkas yang jauh lebih besar dari ini
# hampir pasti bukan yang dimaksud, dan mengunduhnya memakan kuota pengguna.
BATAS_BITA = 25 * 1024 * 1024
MAKS_HASIL = 120


def _bersih(nama: str) -> str:
    nama = re.sub(r"\s+", " ", (nama or "").strip())
    return nama[:80] or "Suara"


def tautan_suara(url: str) -> bool:
    """Apakah ini tautan LANGSUNG ke sebuah berkas suara?"""
    jalur = urlparse(url).path.lower()
    return jalur.endswith(EKSTENSI_SUARA)


def cari(url: str) -> list[dict]:
    """
    Daftar suara pada sebuah halaman papan suara: [{"nama", "url"}].

    Tautan langsung ke berkas dikembalikan apa adanya, jadi pemanggil tidak
    perlu memeriksa dua kemungkinan.
    """
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Tautannya harus dimulai dengan http:// atau https://")
    if tautan_suara(url):
        nama = Path(urlparse(url).path).stem.replace("-", " ").replace("_", " ")
        return [{"nama": _bersih(nama.title()), "url": url}]

    try:
        from curl_cffi import requests
    except ImportError as e:      # noqa: BLE001
        raise RuntimeError(
            "Paket curl_cffi belum terpasang, jadi halaman papan suara tidak bisa "
            "dibaca. Tautan langsung ke berkas mp3 tetap bisa diimpor.") from e

    r = requests.get(url, impersonate="chrome", timeout=BATAS_DETIK)
    if r.status_code != 200:
        raise RuntimeError(f"Halaman itu menjawab {r.status_code}, bukan halaman yang bisa dibaca.")
    teks = r.text

    hasil: list[dict] = []
    terlihat: set[str] = set()
    # Yang bernama lebih dulu: `title="Play X sound"` memberi nama yang benar,
    # sementara nama dari nama berkas sering terpotong dan berimbuhan angka.
    for jalur, judul in POLA_JUDUL.findall(teks):
        penuh = urljoin(url, jalur)
        if penuh in terlihat:
            continue
        terlihat.add(penuh)
        hasil.append({"nama": _bersih(judul), "url": penuh})
    for jalur in POLA_SUARA.findall(teks):
        penuh = urljoin(url, jalur)
        if penuh in terlihat:
            continue
        terlihat.add(penuh)
        nama = Path(urlparse(penuh).path).stem.replace("-", " ").replace("_", " ")
        hasil.append({"nama": _bersih(nama.title()), "url": penuh})
    return hasil[:MAKS_HASIL]


def _unduh_ke(url: str, tujuan: Path) -> Optional[Path]:
    """Mengunduh satu berkas suara. None bila gagal."""
    import yt_dlp
    from yt_dlp.networking.impersonate import ImpersonateTarget

    opts = {
        "outtmpl": str(tujuan / "suara.%(ext)s"),
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "noprogress": True,
        # Menyamar sebagai peramban. Tanpa ini Cloudflare menjawab 403 untuk
        # BERKASNYA, walau metadatanya sudah terbaca — terukur 30 September
        # 2026: `--extractor-args generic:impersonate` saja tidak cukup.
        "impersonate": ImpersonateTarget("chrome"),
        "max_filesize": BATAS_BITA,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([url])
    except Exception as e:                           # noqa: BLE001
        log.info("Suara %s gagal diunduh: %s", url[:90], str(e)[:200])
        return None
    berkas = sorted(tujuan.glob("suara.*"))
    return berkas[0] if berkas else None


def ambil(url: str, nama: str = "") -> dict:
    """
    Mengunduh satu suara dan menyimpannya ke pustaka aset pengguna.

    Mengembalikan catatan aset yang sama bentuknya dengan berkas yang diimpor
    tangan, jadi sisa aplikasi tidak perlu tahu asalnya dari mana.
    """
    from . import aset as aset_svc

    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Tautannya harus dimulai dengan http:// atau https://")
    with tempfile.TemporaryDirectory() as d:
        berkas = _unduh_ke(url, Path(d))
        if berkas is None:
            raise RuntimeError(
                "Berkasnya tidak bisa diunduh. Situsnya mungkin menolak, atau "
                "tautannya bukan tautan berkas suara.")
        asli = _bersih(nama) or berkas.stem
        return aset_svc.simpan_unggahan(berkas, f"{asli}{berkas.suffix}")


__all__ = ["cari", "ambil", "tautan_suara"]
