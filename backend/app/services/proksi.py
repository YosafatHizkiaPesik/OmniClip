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
from typing import Optional

from ..config import STORAGE_DIR

log = logging.getLogger("omniclip.proksi")

PROKSI_DIR = STORAGE_DIR / "proksi"
# Lebar salinan untuk ANALISIS. Cukup untuk menemukan wajah, dan itu satu-satunya
# yang diminta darinya.
LEBAR = 1280
# Lebar salinan yang ikut DIPUTAR di Studio.
#
# Sumber 4K dan VP9 memang tidak bisa diputar peramban tanpa tersendat, jadi di
# sana salinan tidak bisa dihindari. Tapi menontonnya di 1280 piksel berarti
# yang terlihat di editor selalu lebih buruk daripada yang akan dirender, dan
# pada sumber 4K bedanya paling terasa justru karena sumbernya paling tajam.
# 1600 masih ringan didekode (h264, bukan VP9) dan jauh lebih dekat ke hasilnya.
LEBAR_PUTAR = 1600
# Di atas lebar ini, mendekode sumbernya lebih mahal daripada mendekode salinan.
AMBANG_LEBAR = 1280
# Inti yang boleh dipakai saat salinan dibuat DI LATAR, tanpa ada yang
# menunggunya. Sisanya untuk apa pun yang sedang ditunggu pengguna.
INTI = 2
INTI_DITUNGGU = 4
# Inti saat Studio JUSTRU SEDANG MENUNGGU salinan itu. Di situ ia bukan lagi
# pekerjaan latar: ia adalah yang ditunggu, dan menahannya di dua inti berarti
# menahan pemiliknya.
#
# Terukur pada gameplay 2560x1440 VP9 60 fps, per 30 detik sumber, dengan
# enkoder kartu grafis dan 30 fps:
#
#   2 inti  13,9 detik   -> 49 menit untuk video 1 jam 45 menit
#   4 inti  10,5 detik   -> 37 menit
#   6 inti  10,2 detik   -> 35 menit
#   8 inti  10,3 detik   -> 36 menit
#
# Jenuh di empat, jadi empat. Mengambil seluruh inti tidak membuatnya lebih
# cepat dan hanya membuat sisa aplikasi tersendat.

_antrean: "queue.Queue[Path]" = queue.Queue()
_diantre: set[str] = set()
# Sumber yang sedang ditunggu Studio: dibuat tanpa prioritas rendah dan
# didahulukan dari antrean.
_diburu: set[str] = set()
_kunci = threading.Lock()
_pekerja: threading.Thread | None = None


# Naik setiap kali bentuk salinannya berubah. v2: ikut membawa suara, supaya
# salinan yang sama bisa diputar di Studio (lihat `untuk_pratinjau`).
# v3: crf 26, bukan 30. v4: salinan yang ikut ditonton dibuat 1600 px.
VERSI = "v4"


def _lebar_untuk(src: Path) -> int:
    """Salinan yang ikut ditonton dibuat lebih besar daripada yang hanya dibaca mesin."""
    return LEBAR_PUTAR if butuh_salinan(src) else LEBAR


def _nama(src: Path) -> Path:
    st = src.stat()
    sidik = hashlib.sha1(
        f"{src.resolve()}|{st.st_size}|{int(st.st_mtime)}|{VERSI}|{_lebar_untuk(src)}"
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


# Mutu salinan pratinjau, dalam satuan qp/crf. Lebih longgar daripada mutu
# render, dan memang harus: `enkoder.pilih()` menyetel qp 19 karena yang ia
# layani adalah video yang akan diterbitkan. Salinan ini cuma ditonton di
# editor dan dibaca pelacak wajah. Terukur pada gameplay 1440p: qp 19 memakan
# 13,9 detik per 30 detik sumber dan menghasilkan 17 MB; qp 26 memakan 10,3
# detik dan 6 MB, dengan wajah yang sama jelasnya di layar editor.
QP_PROKSI = "26"


def _mutu_proksi(video: list[str]) -> list[str]:
    """Menukar angka mutu enkoder dengan mutu salinan. Daftar kosong dibiarkan."""
    keluar = list(video)
    for i, arg in enumerate(keluar[:-1]):
        if arg in ("-qp", "-crf", "-cq", "-global_quality"):
            keluar[i + 1] = QP_PROKSI
    return keluar


def _buat(src: Path, tujuan: Path) -> None:
    from .proses import jalankan

    if tujuan.is_file() or not _ambil_kunci(tujuan):
        return
    sementara = tujuan.with_suffix(".tmp.mp4")
    # Kartu grafis dipakai bila ada, dan itu bukan sekadar optimasi di sini.
    #
    # Terukur 25 September 2026 pada gameplay 2560x1440 VP9 60 fps sepanjang
    # 1 jam 45 menit, per 30 detik sumber:
    #
    #   dekode saja (batas bawah)                    5,9 detik
    #   seperti dulu: 1600p 60 fps x264 veryfast    17,5 detik  -> 62 menit
    #   1600p 30 fps x264 veryfast                  14,2 detik
    #   1600p 30 fps x264 ultrafast                 10,4 detik  (berkas 2x besar)
    #   1600p 30 fps vaapi                          10,3 detik  (berkas tetap kecil)
    #
    # Jadi 30 fps plus enkoder kartu grafis: 41% lebih cepat tanpa membesarkan
    # berkasnya. Enam puluh dua menit jadi sekitar tiga puluh tujuh, dan itu
    # yang dilaporkan sebagai "loading terus tidak selesai-selesai".
    #
    # 30 fps aman: salinan ini ditonton di editor dan dibaca analisis pada 8
    # sampel per detik, dan tidak satu pun dari keduanya butuh 60.
    with _kunci:
        buru = str(src) in _diburu
    inti = INTI_DITUNGGU if buru else INTI

    from .enkoder import pilih as _enkoder
    try:
        enk = _enkoder()
    except Exception:                                # noqa: BLE001
        enk = {}
    global_gpu = list(enk.get("global") or [])
    saring_gpu = enk.get("saring") or ""
    video_gpu = _mutu_proksi(list(enk.get("video") or []))

    saring = f"scale={_lebar_untuk(src)}:-2,fps={FPS_PROKSI}"
    if saring_gpu:
        saring += "," + saring_gpu
    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-loglevel", "error",
           *global_gpu,
           "-threads", str(inti), "-i", str(src),
           "-vf", saring,
           # Suara ikut: salinan ini juga yang diputar Studio. Firefox
           # memutar sumber 4K VP9 pada 0,44x kecepatan — terlihat macet atau
           # hitam (terukur 21 September 2026).
           "-map", "0:v:0", "-map", "0:a:0?", "-c:a", "aac", "-b:a", "128k",
           "-movflags", "+faststart",
           # veryfast/crf 26: deteksi wajah tidak berubah sama sekali
           # (66,7% / 66,9% / 66,0% pada crf 26/30/33), tapi yang MENONTONNYA
           # berubah. Pada crf 30 salinan 1280x720 keluar di 322 kbit/detik,
           # dan wajah di Studio terlihat berbintik dan pudar dibanding
           # sumbernya — dilaporkan sebagai "kualitas videonya jelek".
           *(video_gpu or ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26"]),
           "-threads", str(inti),
           # Keyframe tiap detik: analisis selalu melompat ke tengah video.
           "-g", "30", "-keyint_min", "30",
           # Kemajuan ditulis ke berkas, bukan dibaca dari stderr.
           #
           # Yang membacanya adalah permintaan HTTP di utas lain, dan berkas di
           # cakram adalah satu-satunya cara keduanya bertemu tanpa kunci
           # tambahan. Tanpa ini, salinan video dua jam terlihat seperti
           # lingkaran berputar yang tidak pernah berubah selama berjam-jam,
           # dan itulah yang dilaporkan dari Windows 25 September 2026:
           # "sudah berapa jam masih loading, tidak bisa mengedit apa pun".
           "-progress", str(sementara.with_suffix(".kemajuan")),
           str(sementara)]
    try:
        log.info("Membuat salinan analisis: %s (%d inti%s)", src.name, inti,
                 ", ditunggu Studio" if buru else "")
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
        sementara.with_suffix(".kemajuan").unlink(missing_ok=True)
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


def kemajuan(src: Path) -> Optional[float]:
    """
    Sejauh mana salinan pratinjau sudah dibuat, 0..1, atau None bila tidak tahu.

    Dibaca dari berkas `-progress` milik ffmpeg. None berarti dua hal yang
    sengaja tidak dibedakan: belum mulai, atau tidak sedang dibuat sama sekali.
    Pemanggilnya hanya perlu tahu apakah ada angka yang layak ditampilkan.
    """
    try:
        sementara = _nama(Path(src)).with_suffix(".tmp.kemajuan")
    except OSError:
        return None
    if not sementara.is_file():
        return None
    try:
        from .media import probe
        total = float(probe(Path(src)).get("duration") or 0)
        if total <= 0:
            return None
        # Berkasnya ditulis terus-menerus; yang berlaku baris `out_time_ms`
        # TERAKHIR, jadi ekornya saja yang dibaca.
        isi = sementara.read_text(encoding="utf-8", errors="ignore")[-2000:]
        detik = None
        for baris in isi.splitlines():
            if baris.startswith("out_time_ms="):
                nilai = baris.split("=", 1)[1].strip()
                if nilai.isdigit():
                    detik = int(nilai) / 1_000_000
        if detik is None:
            return None
        return max(0.0, min(1.0, detik / total))
    except Exception:                                # noqa: BLE001
        return None


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


# Sampai lebar ini, peramban memutar sumbernya sendiri tanpa tersendat.
# Angkanya lebih besar daripada AMBANG_LEBAR dengan sengaja: dua pertanyaan
# yang berbeda dijawab di sini.
AMBANG_PUTAR = 1920
# Codec yang mahal didekode peramban. Terukur 21 September 2026: Firefox
# memutar sumber 4K VP9 pada 0,44x kecepatan, terlihat macet atau hitam.
# Laju bingkai salinan. Sumber 60 fps disalin jadi 30: yang menontonnya adalah
# editor, dan yang membacanya adalah analisis pada 8 sampel per detik. Tidak
# satu pun dari keduanya butuh 60, sementara mengencode 60 memakan dua kali
# lipat kerja.
FPS_PROKSI = 30

CODEC_BERAT = {"vp9", "av1", "av01", "hevc", "h265"}


def butuh_salinan(src: Path) -> bool:
    """
    Apakah PEMUTARAN di Studio butuh salinan, bukan apakah ANALISIS butuh.

    Dua hal yang dulu dijawab satu angka, dan itu yang membuat kualitas
    gambarnya turun tanpa sebab yang kelihatan: sumber 1080p h264 yang bisa
    diputar peramban mana pun tetap diganti salinan 720p, sehingga yang
    dilihat pemiliknya di editor selalu lebih buruk daripada yang akan
    dirender. Analisis tetap memakai salinannya (lihat `siapkan`), karena di
    sana yang mahal adalah mendekode, bukan menonton.
    """
    from .media import probe

    src = Path(src)
    try:
        info = probe(src)
    except Exception:
        return _lebar(src) > AMBANG_LEBAR
    lebar = int(info.get("width") or 0)
    codec = str(info.get("vcodec") or "").lower()
    if lebar > AMBANG_PUTAR:
        return True
    return codec in CODEC_BERAT and lebar > AMBANG_LEBAR
