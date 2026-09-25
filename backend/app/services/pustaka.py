"""
Pembaruan pustaka otomatis — untuk pustaka yang memang bisa diperbarui sendiri.

Alasannya: satu-satunya kegagalan yang selalu datang dari LUAR aplikasi ini
adalah YouTube mengubah caranya. Gejalanya HTTP 403 di tengah unduhan, atau
"Sign in to confirm you're not a bot", dan perbaikannya tidak pernah ada di
kode ini — ia datang dari rilis yt-dlp berikutnya, sering dalam hitungan hari.
Selama pembaruan itu menuntut perintah di terminal, aplikasi yang dipasang dari
exe tidak pernah bisa menerimanya.

Caranya TIDAK memakai pip. Di dalam bundel PyInstaller pip tidak ada, dan
site-packages-nya ditukar seluruhnya setiap kali aplikasi memperbarui diri.
Sebagai gantinya: wheel diunduh dari PyPI, diverifikasi sha256-nya, dibongkar ke
folder penyimpanan pengguna, dan folder itu ditaruh di DEPAN `sys.path`. Wheel
murni-Python tidak butuh kompilasi apa pun, jadi ini bekerja sama saja di
Windows, Linux, dan macOS, dari kode sumber maupun dari exe.

BATASNYA, dan ini disengaja: tidak semua pustaka ikut.

  * Paket dengan kode terkompilasi — numpy, opencv, onnxruntime, ctranslate2
    (lewat faster-whisper), pydantic — TIDAK pernah disentuh. Wheel-nya terikat
    versi Python dan arsitektur CPU, ukurannya puluhan hingga ratusan megabita,
    dan satu wheel yang keliru tidak membuat satu fitur gagal melainkan membuat
    aplikasi tidak bisa dijalankan sama sekali. Memperbaikinya menuntut hal yang
    persis ingin dihindari di sini: terminal.
  * Paket yang antarmukanya kita pakai langsung — FastAPI, uvicorn, pustaka
    Google — juga tidak. Perubahan yang mematahkan di sana mematahkan KODE INI,
    dan itu diperbaiki dengan merilis versi OmniClip baru, bukan dengan
    menukar pustakanya diam-diam di bawah kaki pengguna.

Yang tersisa adalah paket murni-Python yang tugasnya berbicara dengan layanan
luar yang berubah sendiri. Di situlah pembaruan otomatis benar-benar menjawab
sesuatu, dan hanya itu yang didaftarkan di bawah.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

log = logging.getLogger("omniclip.pustaka")

# nama di PyPI -> (nama modul, alasan ikut diperbarui)
OTOMATIS: dict[str, tuple[str, str]] = {
    "yt-dlp": (
        "yt_dlp",
        "YouTube mengubah caranya tanpa pemberitahuan; perbaikannya selalu "
        "datang dari rilis yt-dlp, bukan dari kode OmniClip.",
    ),
    "edge-tts": (
        "edge_tts",
        "Memakai antarmuka tidak resmi Microsoft untuk suara pembaca judul. "
        "Antarmuka itu berubah sewaktu-waktu dan paketnya murni Python.",
    ),
}

JEDA_PERIKSA = 12 * 3600      # jangan menembak PyPI tiap kali aplikasi dibuka
BATAS_UNDUH = 64 * 1024 * 1024
WAKTU_HABIS = 20


def folder_overlay() -> Path:
    from ..config import STORAGE_DIR
    return Path(STORAGE_DIR) / "pustaka"


def _folder_paket(paket: str) -> Path:
    return folder_overlay() / paket.replace("-", "_")


def _penunjuk(paket: str) -> Path:
    return _folder_paket(paket) / "aktif.txt"


def versi_aktif(paket: str) -> str:
    """Versi yang sudah dipasang overlay, atau "" kalau memakai bawaan bundel."""
    try:
        return _penunjuk(paket).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def aktifkan() -> list[str]:
    """
    Menaruh versi hasil pembaruan di depan `sys.path`.

    HARUS dipanggil sebelum modul mana pun yang diperbarui ikut diimpor —
    sekali sebuah modul masuk ke `sys.modules`, mengubah `sys.path` tidak lagi
    berpengaruh. Karena itu pemanggilannya ada di baris-baris pertama
    run.py dan app/main.py, bukan di dalam lifespan.
    """
    dipakai = []
    for paket in OTOMATIS:
        versi = versi_aktif(paket)
        if not versi:
            continue
        d = _folder_paket(paket) / versi
        if not d.is_dir():
            continue
        jalur = str(d)
        if jalur not in sys.path:
            sys.path.insert(0, jalur)
        dipakai.append(f"{paket} {versi}")
    return dipakai


def versi_terpasang(paket: str) -> str:
    """Versi yang benar-benar aktif di proses ini, dibaca dari modulnya."""
    modul = OTOMATIS[paket][0]
    try:
        m = __import__(modul)
        v = getattr(m, "__version__", "")
        if not v:
            v = getattr(getattr(m, "version", None), "__version__", "")
        return str(v or "")
    except Exception:
        return ""


def _angka(versi: str) -> tuple:
    """
    Versi jadi tuple yang bisa dibandingkan.

    Sengaja sederhana: yang dibandingkan hanya versi paket yang sama dari PyPI,
    dan semuanya memakai angka dipisah titik ("2026.8.19", "7.2.3"). Bagian
    yang bukan angka dijadikan 0 supaya pra-rilis tidak pernah menang atas
    rilis biasa.
    """
    return tuple(int(b) if b.isdigit() else 0 for b in re.split(r"[.\-+]", versi))


def _json_pypi(paket: str) -> dict:
    url = f"https://pypi.org/pypi/{paket}/json"
    req = urllib.request.Request(url, headers={"User-Agent": "OmniClip"})
    with urllib.request.urlopen(req, timeout=WAKTU_HABIS) as r:
        return json.loads(r.read().decode("utf-8"))


def _wheel_murni(data: dict, versi: str) -> dict | None:
    """
    Wheel `py3-none-any` untuk sebuah versi.

    Kalau tidak ada, paketnya punya kode terkompilasi dan TIDAK boleh dipasang
    lewat jalur ini — pengecekan ini yang menjaga daftar OTOMATIS tetap jujur
    meski suatu hari sebuah paket di dalamnya berubah sifat.
    """
    for berkas in data.get("releases", {}).get(versi, []):
        nama = berkas.get("filename", "")
        if berkas.get("packagetype") == "bdist_wheel" and nama.endswith("-py3-none-any.whl"):
            return berkas
    return None


def periksa(paket: str) -> dict:
    """Membandingkan versi yang berjalan dengan rilis terbaru di PyPI."""
    sekarang = versi_terpasang(paket)
    try:
        data = _json_pypi(paket)
    except Exception as e:
        return {"paket": paket, "sekarang": sekarang, "terbaru": "",
                "ada_baru": False, "galat": str(e)[:160]}
    terbaru = str(data.get("info", {}).get("version") or "")
    berkas = _wheel_murni(data, terbaru) if terbaru else None
    ada_baru = bool(
        terbaru and sekarang and berkas and _angka(terbaru) > _angka(sekarang))
    return {"paket": paket, "sekarang": sekarang, "terbaru": terbaru,
            "ada_baru": ada_baru, "galat": "",
            "murni_python": bool(berkas), "_berkas": berkas}


def pasang(paket: str, info: dict | None = None) -> dict:
    """Mengunduh, memverifikasi, lalu membongkar wheel versi terbaru."""
    info = info or periksa(paket)
    if info.get("galat"):
        return {"dipasang": False, "alasan": info["galat"], **info}
    if not info.get("ada_baru"):
        return {"dipasang": False, "alasan": "sudah mutakhir", **info}
    berkas = info.get("_berkas")
    if not berkas:
        return {"dipasang": False,
                "alasan": "tidak ada wheel murni-Python; dilewati demi keamanan",
                **info}

    versi = info["terbaru"]
    harapan = (berkas.get("digests") or {}).get("sha256", "")
    if not harapan:
        return {"dipasang": False, "alasan": "PyPI tidak memberi sha256", **info}

    req = urllib.request.Request(berkas["url"], headers={"User-Agent": "OmniClip"})
    with urllib.request.urlopen(req, timeout=60) as r:
        isi = r.read(BATAS_UNDUH + 1)
    if len(isi) > BATAS_UNDUH:
        return {"dipasang": False, "alasan": "wheel terlalu besar", **info}

    nyata = hashlib.sha256(isi).hexdigest()
    if nyata != harapan:
        # Berkas yang tidak cocok tidak pernah menyentuh cakram.
        return {"dipasang": False, "alasan": "sha256 tidak cocok", **info}

    dasar = _folder_paket(paket)
    tujuan = dasar / versi
    sementara = dasar / f".{versi}.sedang"
    shutil.rmtree(sementara, ignore_errors=True)
    sementara.mkdir(parents=True, exist_ok=True)
    try:
        import io
        with zipfile.ZipFile(io.BytesIO(isi)) as z:
            for anggota in z.namelist():
                # Jangan percaya nama di dalam arsip: satu "../" sudah cukup
                # untuk menulis di luar folder tujuan.
                jalur = (sementara / anggota).resolve()
                if not str(jalur).startswith(str(sementara.resolve())):
                    raise ValueError(f"jalur mencurigakan di wheel: {anggota}")
            z.extractall(sementara)
        shutil.rmtree(tujuan, ignore_errors=True)
        os.replace(sementara, tujuan)
        # Penunjuk ditulis PALING AKHIR: sampai baris ini, versi baru belum
        # dipakai sama sekali, jadi pemasangan yang terputus di tengah tidak
        # meninggalkan aplikasi menunjuk ke folder yang setengah jadi.
        _penunjuk(paket).write_text(versi, encoding="utf-8")
    except Exception as e:
        shutil.rmtree(sementara, ignore_errors=True)
        return {"dipasang": False, "alasan": f"gagal membongkar: {e}", **info}

    _bersihkan_lama(paket, versi)
    hasil = {k: v for k, v in info.items() if k != "_berkas"}
    return {"dipasang": True, "alasan": "", "perlu_restart": True, **hasil}


def _bersihkan_lama(paket: str, simpan: str) -> None:
    """Menyisakan satu versi lama sebagai jalan pulang, membuang sisanya."""
    dasar = _folder_paket(paket)
    try:
        versi = sorted((d.name for d in dasar.iterdir()
                        if d.is_dir() and not d.name.startswith(".")), key=_angka)
    except OSError:
        return
    for nama in versi[:-2]:
        if nama != simpan:
            shutil.rmtree(dasar / nama, ignore_errors=True)


def mundur(paket: str) -> bool:
    """
    Kembali ke versi sebelumnya.

    Dipanggil saat modul hasil pembaruan ternyata tidak bisa diimpor. Tanpa ini
    satu rilis rusak di PyPI akan membuat aplikasi gagal menyala dan
    satu-satunya perbaikan adalah menghapus folder lewat pengelola berkas.
    """
    dasar = _folder_paket(paket)
    aktif = versi_aktif(paket)
    try:
        versi = sorted((d.name for d in dasar.iterdir()
                        if d.is_dir() and not d.name.startswith(".")), key=_angka)
    except OSError:
        versi = []
    sebelumnya = [v for v in versi if v != aktif]
    if sebelumnya:
        _penunjuk(paket).write_text(sebelumnya[-1], encoding="utf-8")
    else:
        try:
            _penunjuk(paket).unlink()
        except OSError:
            pass
    shutil.rmtree(dasar / aktif, ignore_errors=True)
    log.warning("Pustaka %s dikembalikan dari %s", paket, aktif or "(bawaan)")
    return True


def _boleh_periksa() -> bool:
    from ..repos import settings as settings_repo
    try:
        terakhir = float(settings_repo.get("pustaka.periksa_terakhir", "0") or 0)
    except ValueError:
        terakhir = 0.0
    return time.time() - terakhir > JEDA_PERIKSA


def _catat_periksa() -> None:
    from ..repos import settings as settings_repo
    try:
        settings_repo.set_value("pustaka.periksa_terakhir", str(time.time()))
    except Exception:
        pass


def perbarui_semua(*, paksa: bool = False) -> list[dict]:
    """Memeriksa lalu memasang semua paket yang boleh diperbarui sendiri."""
    if not paksa and not _boleh_periksa():
        return []
    hasil = []
    for paket in OTOMATIS:
        try:
            h = pasang(paket)
        except Exception as e:                       # jangan pernah menjatuhkan startup
            h = {"paket": paket, "dipasang": False, "alasan": str(e)[:160]}
        hasil.append({k: v for k, v in h.items() if not k.startswith("_")})
        if h.get("dipasang"):
            log.info("Pustaka %s diperbarui ke %s, berlaku setelah OmniClip "
                     "dijalankan ulang", paket, h.get("terbaru"))
    _catat_periksa()
    return hasil


def periksa_di_latar() -> None:
    """Menjalankan pembaruan di thread terpisah supaya startup tidak menunggu."""
    def kerja():
        try:
            perbarui_semua()
        except Exception as e:
            log.info("Pemeriksaan pustaka dilewati: %s", str(e)[:160])

    threading.Thread(target=kerja, name="pustaka-update", daemon=True).start()


def periksa_kesehatan() -> None:
    """
    Memastikan setiap paket hasil pembaruan benar-benar bisa diimpor, dan
    mundur kalau tidak.

    Dipanggil setelah `aktifkan()`. Inilah yang membuat pembaruan otomatis aman
    dinyalakan tanpa pengawasan: rilis yang rusak di PyPI berumur satu kali
    jalan, bukan selamanya.
    """
    for paket, (modul, _) in OTOMATIS.items():
        if not versi_aktif(paket):
            continue
        try:
            __import__(modul)
        except Exception as e:
            log.warning("Pustaka %s hasil pembaruan gagal diimpor (%s), "
                        "dikembalikan ke versi sebelumnya", paket, str(e)[:120])
            mundur(paket)
            # Buang jejak impor gagal supaya percobaan berikutnya bersih.
            for nama in [n for n in sys.modules if n == modul or n.startswith(modul + ".")]:
                sys.modules.pop(nama, None)
            for d in [p for p in sys.path if f"/{paket.replace('-', '_')}/" in p.replace("\\", "/")]:
                sys.path.remove(d)
