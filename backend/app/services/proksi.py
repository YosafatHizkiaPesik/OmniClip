"""
Salinan kecil khusus analisis.

Pelacakan wajah, pelacakan gerakan, dan pencarian facecam semuanya membaca
bingkai lewat `reframe._sample_frames`, dan semuanya lalu MENGECILKAN bingkai
itu ke 560-1280 piksel. Tapi untuk mengecilkannya, ffmpeg harus lebih dulu
mendekode bingkai dalam ukuran aslinya — dan pada unduhan 4K VP9 itulah yang
mahal. Terukur: membaca 20 detik video 3840x2160 VP9 memakan 5,1 detik; dari
salinan 1280 px, 0,5 detik. Klip 60 detik: 31 dtk -> 3,3 dtk.

Versi pertama modul ini MEMBUAT MASALAH yang lebih besar daripada yang
dipecahkannya, dan aturannya di bawah ada karena itu:

  - ia hanya mengunci di dalam SATU proses, jadi setiap backend dan setiap
    skrip yang menyentuh video yang sama memulai salinannya sendiri — terukur
    enam salinan video yang sama sekaligus;
  - tidak ada batas jumlah: tiap video yang dibuka memulai satu lagi;
  - berjalan dengan prioritas penuh dan semua inti.

Hasilnya sepuluh ffmpeg, beban mesin 98 pada delapan inti, dan seluruh
aplikasi lambat. Sekarang: SATU antrean, SATU salinan dalam satu waktu untuk
seluruh mesin (berkas kunci), prioritas terendah, dua inti saja.
"""

import hashlib
import logging
import os
import queue
import threading
from pathlib import Path

from ..config import STORAGE_DIR

log = logging.getLogger("omniclip.proksi")

PROKSI_DIR = STORAGE_DIR / "proksi"
LEBAR = 1280
# Di atas lebar ini, mendekode sumbernya lebih mahal daripada mendekode salinan.
AMBANG_LEBAR = 1280
# Inti yang boleh dipakai. Sisanya untuk apa pun yang sedang ditunggu pengguna.
INTI = 2

_antrean: "queue.Queue[Path]" = queue.Queue()
_diantre: set[str] = set()
# Sumber yang sedang ditunggu Studio: dibuat tanpa prioritas rendah dan
# didahulukan dari antrean.
_diburu: set[str] = set()
_kunci = threading.Lock()
_pekerja: threading.Thread | None = None


# Naik setiap kali bentuk salinannya berubah. v2: ikut membawa suara, supaya
# salinan yang sama bisa diputar di Studio (lihat `untuk_pratinjau`).
VERSI = "v2"


def _nama(src: Path) -> Path:
    st = src.stat()
    sidik = hashlib.sha1(f"{src.resolve()}|{st.st_size}|{int(st.st_mtime)}|{VERSI}"
                         .encode()).hexdigest()[:16]
    return PROKSI_DIR / f"{sidik}.mp4"


def _lebar(src: Path) -> int:
    try:
        from .media import probe
        return int(probe(src).get("width") or 0)
    except Exception:
        return 0


def _pid_hidup(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _ambil_kunci(tujuan: Path) -> bool:
    """Kunci antarproses: berkas .kunci berisi PID pemiliknya."""
    kunci = tujuan.with_suffix(".kunci")
    for _ in range(2):
        try:
            fd = os.open(kunci, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            try:
                pemilik = int(kunci.read_text().strip() or 0)
            except (OSError, ValueError):
                pemilik = 0
            if pemilik and _pid_hidup(pemilik):
                return False
            kunci.unlink(missing_ok=True)      # pemiliknya sudah mati
    return False


def _buat(src: Path, tujuan: Path) -> None:
    from .proses import jalankan

    if tujuan.is_file() or not _ambil_kunci(tujuan):
        return
    sementara = tujuan.with_suffix(".tmp.mp4")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-loglevel", "error",
           "-threads", str(INTI), "-i", str(src),
           "-vf", f"scale={LEBAR}:-2",
           # Suara ikut: salinan ini juga yang diputar Studio. Firefox
           # memutar sumber 4K VP9 pada 0,44x kecepatan — terlihat macet atau
           # hitam (terukur 21 September 2026).
           "-map", "0:v:0", "-map", "0:a:0?", "-c:a", "aac", "-b:a", "128k",
           "-movflags", "+faststart",
           # veryfast/crf 30: 9 MB per menit; deteksi wajah tidak berubah
           # (66,7% / 66,9% / 66,0% pada crf 26/30/33).
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
           "-threads", str(INTI),
           # Keyframe tiap detik: analisis selalu melompat ke tengah video.
           "-g", "30", "-keyint_min", "30",
           str(sementara)]
    try:
        log.info("Membuat salinan analisis: %s", src.name)
        with _kunci:
            buru = str(src) in _diburu
        hasil = jalankan(cmd, rendah=not buru)
        if hasil.returncode == 0 and sementara.is_file():
            sementara.replace(tujuan)
            tujuan.with_suffix(".sumber").write_text(str(src.resolve()), encoding="utf-8")
            log.info("Salinan analisis siap: %s", src.name)
        else:
            log.warning("Salinan analisis gagal untuk %s: %s",
                        src.name, (hasil.stderr or "")[-300:])
    finally:
        sementara.unlink(missing_ok=True)
        tujuan.with_suffix(".kunci").unlink(missing_ok=True)


def _ambil_berikut() -> Path:
    """Antrean berikutnya, dengan yang sedang ditunggu Studio didahulukan."""
    while True:
        src = _antrean.get()
        with _kunci:
            if str(src) in _diburu:
                return src
            buru = [q for q in list(_antrean.queue) if str(q) in _diburu]
        if not buru:
            return src
        # Kembalikan ke belakang; yang diburu keluar lebih dulu di putaran ini.
        _antrean.put(src)


def _kerja() -> None:
    while True:
        src = _ambil_berikut()
        try:
            _buat(src, _nama(src))
        except Exception as e:                       # jangan pernah mematikan pekerja
            log.warning("Salinan analisis gagal: %s", e)
        finally:
            with _kunci:
                _diantre.discard(str(src))
                _diburu.discard(str(src))


def bersihkan_yatim() -> int:
    """Membuang salinan yang sumbernya sudah tidak ada, dan sisa pembuatan yang terputus."""
    dibuang = 0
    if not PROKSI_DIR.is_dir():
        return 0
    for catatan in PROKSI_DIR.glob("*.sumber"):
        try:
            asal = Path(catatan.read_text(encoding="utf-8").strip())
        except OSError:
            continue
        try:
            usang = asal.is_file() and _nama(asal).stem != catatan.stem
        except OSError:
            usang = False
        if not asal.is_file() or usang:
            catatan.with_suffix(".mp4").unlink(missing_ok=True)
            catatan.unlink(missing_ok=True)
            dibuang += 1
    for kunci in PROKSI_DIR.glob("*.kunci"):
        try:
            pemilik = int(kunci.read_text().strip() or 0)
        except (OSError, ValueError):
            pemilik = 0
        if not (pemilik and _pid_hidup(pemilik)):
            kunci.unlink(missing_ok=True)
            kunci.with_suffix(".tmp.mp4").unlink(missing_ok=True)
    return dibuang


def siapkan(src: Path) -> None:
    """Antrekan pembuatan salinan bila perlu. Tidak menunggu, tidak menggandakan."""
    global _pekerja
    try:
        src = Path(src)
        if not src.is_file():
            return
        tujuan = _nama(src)
        if tujuan.is_file() or tujuan.with_suffix(".kunci").exists():
            return
        with _kunci:
            if str(src) in _diantre:
                return
        if _lebar(src) <= AMBANG_LEBAR:
            return
        PROKSI_DIR.mkdir(parents=True, exist_ok=True)
        with _kunci:
            if str(src) in _diantre:
                return
            _diantre.add(str(src))
            if _pekerja is None or not _pekerja.is_alive():
                bersihkan_yatim()
                _pekerja = threading.Thread(target=_kerja, daemon=True, name="proksi")
                _pekerja.start()
        _antrean.put(src)
    except OSError:
        pass


def untuk_analisis(src: Path) -> Path:
    """
    Berkas yang sebaiknya DIBACA untuk analisis: salinannya bila sudah siap,
    sumbernya sendiri bila belum (dan pembuatannya diantrekan).
    """
    src = Path(src)
    try:
        tujuan = _nama(src)
    except OSError:
        return src
    if tujuan.is_file():
        return tujuan
    siapkan(src)
    return src


def untuk_pratinjau(src: Path) -> Path | None:
    """
    Salinan yang diputar Studio bila sudah siap; None bila belum (pembuatannya
    didahulukan). Sumber kecil (<= AMBANG_LEBAR) tidak butuh salinan dan
    tidak pernah mendapatkannya — pemanggil memutar sumbernya saja.
    """
    src = Path(src)
    try:
        tujuan = _nama(src)
    except OSError:
        return None
    if tujuan.is_file():
        return tujuan
    with _kunci:
        _diburu.add(str(src))
    siapkan(src)
    return None


def butuh_salinan(src: Path) -> bool:
    return _lebar(Path(src)) > AMBANG_LEBAR
