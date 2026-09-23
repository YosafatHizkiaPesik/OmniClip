"""
Mesin render ffmpeg.

Perbaikan dibanding versi lama:
  - klip bisa terdiri dari beberapa segmen yang disambung (menit 10 + menit 50);
  - hook_text benar-benar digambar ke video, bukan hanya disimpan ke JSON;
  - rasio 16:9 punya cabang sendiri (dulu diam-diam tidak melakukan apa pun);
  - nama file memuat ID video sehingga tidak saling menimpa;
  - dual-seek yang akurat ke frame, bukan menempel ke keyframe;
  - ada timeout, progres nyata, dan pembatalan;
  - stderr ffmpeg masuk log, bukan dikirim ke browser.
"""

import json
import logging
import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Optional

from dataclasses import replace

from ..config import CLIPS_DIR, FONTS_DIR, LOGS_DIR
from .proses import popen
from .paths import extract_id_from_filename
from .reframe import build_reframe_filter, plan_reframe
from .paths import ffpath
from .subtitles import CaptionStyle, HookSpec, build_ass, gaya_dari_dict
from . import titlecard as tc

log = logging.getLogger("omniclip.render")

# Preroll untuk dual-seek: `-ss` besar sebelum `-i` (cepat, menempel keyframe),
# lalu `-ss` kecil sesudah `-i` (akurat ke frame).
PREROLL = 5.0


def kabur(w: int, h: int) -> str:
    """
    Latar kabur selebar kanvas, dikerjakan pada gambar seperempat ukuran.

    Semula filter kaburnya bekerja langsung pada kanvas penuh 1080x1920
    (boxblur 28, enam lintasan). Itu filter termahal di seluruh render:
    terukur 0,2x waktu nyata — 18,8 detik untuk empat detik video — sebelum
    satu piksel pun dikodekan. Tiap susunan gaming di linimasa bingkai
    membayarnya sekali lagi, jadi klip gaming -> reaksi -> gaming tidak selesai
    dalam lima menit dan tampak seperti macet.

    Latar kabur memang tidak punya detail untuk dipertahankan. Dikecilkan
    empat kali, dikaburkan, lalu dibesarkan lagi, hasilnya tidak bisa dibedakan
    dari yang lama di samping-sampingan, dan waktunya 3,6 detik.
    """
    return (f"scale={max(2, w // 4)}:{max(2, h // 4)},boxblur=9:3,"
            f"scale={w}:{h}")


ASPECT_FILTERS = {
    "9:16": (
        "split[bgsrc][fgsrc];"
        "[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920," + kabur(1080, 1920) + "[bg];"
        "[fgsrc]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"
    ),
    "1:1": "crop=w='min(iw,ih)':h='min(iw,ih)',scale=1080:1080,setsar=1",
    "4:5": "crop=w='min(iw,ih*4/5)':h='min(ih,iw*5/4)',scale=1080:1350,setsar=1",
    # Cabang ini sebelumnya tidak ada sama sekali, sehingga memilih 16:9
    # menghasilkan video tanpa perubahan resolusi apa pun.
    "16:9": ("scale=1920:1080:force_original_aspect_ratio=decrease,"
             "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1"),
}

# Crop tengah statis. Dipakai bila pengguna memilih "tengah", atau sebagai
# jalur paling murah untuk sumber yang memang sudah terkomposisi di tengah.
CENTER_FILTERS = {
    "9:16": "crop=w='min(iw,ih*9/16)':h=ih,scale=1080:1920,setsar=1",
    "1:1": "crop=w='min(iw,ih)':h='min(iw,ih)',scale=1080:1080,setsar=1",
    "4:5": "crop=w='min(iw,ih*4/5)':h=ih,scale=1080:1350,setsar=1",
    "16:9": ("scale=1920:1080:force_original_aspect_ratio=decrease,"
             "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1"),
}

VIDEO_FILTERS = {
    "normal": None,
    "vibrant": "eq=contrast=1.15:saturation=1.35:brightness=0.02",
    "cinematic": "curves=preset=medium_contrast,eq=saturation=0.92",
    "bw": "hue=s=0,eq=contrast=1.1",
    "vintage": "curves=preset=vintage,eq=saturation=0.8",
}

PLAY_RES = {"9:16": (1080, 1920), "1:1": (1080, 1080),
            "4:5": (1080, 1350), "16:9": (1920, 1080)}


def _run_ffmpeg(cmd: list[str], *, duration: float,
                on_progress: Optional[Callable[[float], None]] = None,
                should_cancel: Optional[Callable[[], bool]] = None,
                timeout: Optional[float] = None) -> tuple[int, str]:
    """Menjalankan ffmpeg sambil membaca `-progress pipe:1`."""
    if timeout is None:
        timeout = max(240.0, duration * 20)

    proc = popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                 text=True, bufsize=1)
    deadline = time.time() + timeout
    cancelled = timed_out = False

    try:
        for line in proc.stdout:
            if should_cancel is not None and should_cancel():
                cancelled = True
                break
            if time.time() > deadline:
                timed_out = True
                break
            if on_progress is not None and line.startswith("out_time_us="):
                try:
                    done = int(line.split("=", 1)[1].strip()) / 1_000_000.0
                except ValueError:
                    continue
                if duration > 0:
                    on_progress(max(0.0, min(1.0, done / duration)))
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        stderr_text = proc.stderr.read() or ""
        proc.stdout.close()
        proc.stderr.close()

    if cancelled:
        return -1, "Dibatalkan oleh pengguna."
    if timed_out:
        return -1, f"Timeout setelah {timeout:.0f} detik.\n{stderr_text}"
    return (proc.returncode if proc.returncode is not None else -1), stderr_text


def _build_segment_graph(segments: list[dict]) -> tuple[list[str], str, str]:
    """
    Menyusun input dan filtergraph untuk memotong lalu menyambung segmen.

    Setiap segmen menjadi INPUT tersendiri dengan `-ss` miliknya, sehingga
    ffmpeg bisa melompat cepat ke menit 50 tanpa mendekode dari awal. Tanpa ini,
    satu klip gabungan dari video 68 menit akan mendekode puluhan menit sia-sia.
    """
    inputs: list[str] = []
    parts: list[str] = []
    concat_labels: list[str] = []

    for i, seg in enumerate(segments):
        start = max(0.0, float(seg["start"]))
        end = max(start + 0.2, float(seg["end"]))
        dur = end - start
        pre = min(start, PREROLL)

        # SEMUA opsi seek harus berada SEBELUM `-i` miliknya. Opsi yang ditulis
        # setelah `-i` akan diperlakukan ffmpeg sebagai opsi input berikutnya —
        # atau, untuk input terakhir, sebagai opsi OUTPUT, yang diam-diam
        # memotong hasil akhir.
        #
        # Ketelitian frame didapat dari `trim=start=pre` di dalam filtergraph:
        # `-ss` melompat cepat ke keyframe terdekat, lalu trim memotong presisi.
        inputs += ["-ss", f"{start - pre:.3f}", "-t", f"{pre + dur:.3f}", "-i", "SRC"]

        # `fps=30` LANGSUNG sesudah pemotongan, untuk semua mode:
        #   - sumber 60 fps (rekaman game) membawa dua kali bingkai yang
        #     dibutuhkan hasil 30 fps melewati setiap crop, scale, dan blur di
        #     belakangnya — pada susunan gaming dan linimasa bingkai, itu
        #     beberapa filter berat per bingkai yang separuhnya dibuang begitu
        #     sampai ke pengode;
        #   - celah di sumber yang berlubang (unduhan yang kehilangan potongan)
        #     diisi bingkai terakhir, jadi gambar dan suara tetap sinkron.
        parts.append(
            f"[{i}:v]trim=start={pre:.3f}:duration={dur:.3f},setpts=PTS-STARTPTS,"
            f"fps=30[v{i}]"
        )
        parts.append(
            f"[{i}:a]atrim=start={pre:.3f}:duration={dur:.3f},asetpts=PTS-STARTPTS[a{i}]"
        )
        concat_labels += [f"[v{i}]", f"[a{i}]"]

    if len(segments) == 1:
        return inputs, ";".join(parts), "[v0]|[a0]"

    parts.append(f"{''.join(concat_labels)}concat=n={len(segments)}:v=1:a=1[vcat][acat]")
    return inputs, ";".join(parts), "[vcat]|[acat]"


def _even(v: float, lo: int = 2) -> int:
    """Pembulatan ke genap. yuv420p mencuplik krominansi 2x2, jadi lebar atau
    tinggi ganjil membuat ffmpeg menolak atau menghasilkan baris rusak."""
    return max(lo, int(round(v / 2.0)) * 2)


def _pct_rect(rect: dict, w: int, h: int) -> tuple[int, int, int, int]:
    """Persegi persen -> piksel, dijepit di dalam bidangnya."""
    rw = _even(max(1.0, min(100.0, float(rect.get("w", 100)))) / 100.0 * w)
    rh = _even(max(1.0, min(100.0, float(rect.get("h", 100)))) / 100.0 * h)
    rw = min(rw, _even(w))
    rh = min(rh, _even(h))
    rx = _even(max(0.0, min(100.0, float(rect.get("x", 0)))) / 100.0 * w, lo=0)
    ry = _even(max(0.0, min(100.0, float(rect.get("y", 0)))) / 100.0 * h, lo=0)
    return min(rx, max(0, w - rw)), min(ry, max(0, h - rh)), rw, rh


def build_layout_graph(layout: dict, in_label: str, out_label: str, *,
                       src_w: int, src_h: int, out_w: int, out_h: int,
                       plan=None, workdir=None, awalan: str = "") -> str:
    """
    Menyusun beberapa potongan video sumber menjadi satu kanvas.

    Inilah yang membuat klip main game dan klip reaksi streamer mungkin: satu
    video sumber, beberapa jendela ke dalamnya, masing-masing diletakkan sendiri
    di kanvas hasil. Karena semua bingkai berasal dari input yang sama, tidak ada
    dekode kedua — `split` membagi aliran yang sudah terdekode.

    Celah antar bingkai diisi versi kabur dari sumbernya (atau hitam), bukan
    dibiarkan kosong: ffmpeg akan mengisi piksel yang tidak tertimpa dengan
    apa pun yang kebetulan ada di buffer latar.
    """
    frames = [f for f in (layout.get("frames") or []) if isinstance(f, dict)]
    if not frames:
        return ""

    # `awalan` membuat setiap label di graf ini unik. Tanpanya, dua susunan
    # dalam satu linimasa bingkai — gaming, reaksi, gaming lagi — memakai
    # `[lsrc0]`, `[lbg]`, `[lo0]` yang SAMA dua kali. ffmpeg tidak menolaknya;
    # ia menyambung grafnya silang dan macet. Terukur: klip 15 detik tidak
    # selesai dalam 300 detik, dan pada klip yang lebih panjang gambarnya
    # membeku selama potongan reaksinya.
    L = lambda nama: f"[{awalan}{nama}]"

    parts: list[str] = []
    n = len(frames)
    # Satu cabang per bingkai, plus satu untuk latar.
    parts.append(f"{in_label}split={n + 1}" + "".join(f"{L(f'lsrc{i}')}" for i in range(n + 1)))

    bg = L('lbg')
    if layout.get("background") == "black":
        # Sumber latar tetap dipakai supaya panjang dan laju frame-nya persis
        # sama dengan bingkainya; `drawbox` mengecatnya hitam penuh.
        parts.append(
            f"{L(f'lsrc{n}')}scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},drawbox=x=0:y=0:w={out_w}:h={out_h}:color=black:t=fill,"
            f"setsar=1{L('lbg')}"
        )
    else:
        parts.append(
            f"{L(f'lsrc{n}')}scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},{kabur(out_w, out_h)},setsar=1{L('lbg')}"
        )

    for i, f in enumerate(frames):
        sx, sy, sw, sh = _pct_rect(f.get("src") or {}, src_w, src_h)
        dx, dy, dw, dh = _pct_rect(f.get("dst") or {}, out_w, out_h)
        if f.get("fit") == "contain":
            place = (f"scale={dw}:{dh}:force_original_aspect_ratio=decrease,"
                     f"pad={dw}:{dh}:(ow-iw)/2:(oh-ih)/2:color=black")
        else:
            place = (f"scale={dw}:{dh}:force_original_aspect_ratio=increase,"
                     f"crop={dw}:{dh}")

        # Bingkai yang mengikuti orang: lebar dan tinggi jendelanya tetap
        # datang dari kotak yang digambar pengguna, tapi posisi mendatarnya
        # digerakkan jejak wajah. Tiap bingkai memakai instance crop bernama
        # sendiri — dengan satu nama bersama, perintah untuk bingkai pertama
        # akan ikut menggeser bingkai kedua.
        if f.get("follow") and plan is not None and workdir is not None:
            from .reframe import build_reframe_filter
            # Orang yang dibuntuti dipilih dari LETAK KOTAKNYA: pengguna
            # menaruh bingkai di atas seseorang, dan bingkai itu mengikuti orang
            # tersebut. Bukan tebakan siapa yang sedang bicara — tebakan itu
            # sudah saya coba dan hasilnya lebih buruk daripada tidak menebak.
            src_rect = f.get("src") or {}
            centre_pct = float(src_rect.get("x", 0)) + float(src_rect.get("w", 100)) / 2
            crop = build_reframe_filter(
                plan, workdir / f"reframe_{awalan}{i}.cmd", out_w, out_h,
                name=f"{awalan}lf{i}", crop_w=sw, crop_h=sh, crop_y=sy,
                person=(int(f["person"]) if f.get("person") is not None
                        else plan.person_near(centre_pct)), scale=False)
            parts.append(f"{L(f'lsrc{i}')}{crop},{place},setsar=1{L(f'lf{i}')}")
        else:
            parts.append(f"{L(f'lsrc{i}')}crop={sw}:{sh}:{sx}:{sy},{place},setsar=1{L(f'lf{i}')}")

    # Ditumpuk berurutan: bingkai terakhir di daftar tergambar paling atas,
    # sama seperti urutan yang ditampilkan panelnya.
    prev = bg
    for i in range(n):
        nxt = f"{L(f'lo{i}')}" if i < n - 1 else out_label
        sx, sy, sw, sh = _pct_rect(frames[i].get("dst") or {}, out_w, out_h)
        parts.append(f"{prev}{L(f'lf{i}')}overlay={sx}:{sy}:shortest=0{nxt}")
        prev = nxt

    return ";".join(parts)


SLUG_MAX = 52


def slugify(text: str) -> str:
    """
    Judul video -> potongan nama berkas yang aman dan masih bisa dibaca.

    Hanya huruf, angka, dan tanda hubung yang lolos. Aksen dibuang lewat
    normalisasi Unicode supaya "Café" jadi "Cafe" dan bukan "Caf".
    """
    import re
    import unicodedata

    cleaned = unicodedata.normalize("NFKD", text)
    cleaned = cleaned.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", cleaned).strip("-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned[:SLUG_MAX].strip("-") or "klip"


# --- Susunan klip gameplay -----------------------------------------------------
#
# Video orang bermain game tidak bisa dipotong seperti podcast. Memaksa
# face-tracking ke sana menghasilkan crop yang meloncat mengejar wajah kecil di
# pojok; menjatuhkannya ke bilah kabur justru membuang wajahnya sama sekali dan
# menyisakan gambar permainan yang diperkecil di tengah. Keduanya membuang satu
# dari dua hal yang membuat klip gameplay layak ditonton.
#
# Yang disusun di sini dua bidang: reaksi pemain di atas, permainannya di bawah.
#
# Permainan dipasang "contain" dan bukan "cover" — itu keputusan yang sengaja.
# "Cover" akan memenuhi bidangnya tanpa bilah, tapi untuk bingkai 16:9 yang
# dijadikan 9:16 itu berarti membuang sebagian besar lebarnya, dan di permainan
# justru di pinggir layar itulah peta, darah, dan musuh berada. Yang diminta
# adalah "gameplay yang jelas", dan jelas berarti UTUH.

# Tinggi bidang wajah dalam persen kanvas. Sisanya milik permainan — TIDAK ada
# sisa yang dibiarkan kosong.
#
# Versi pertama menyisakan 28% di bawah sebagai latar kabur supaya subtitle
# punya tempat duduk. Hasilnya terlihat di layar dan salah: bidang permainannya
# jadi kecil dengan lubang kosong besar di bawahnya, dan yang dilaporkan
# pemiliknya adalah "tidak full klipnya". Subtitle memang lebih baik duduk di
# atas gambar daripada di atas kekosongan.
GAMING_WAJAH_TINGGI = 40.0


def rasio_bidang_wajah(out_w: int, out_h: int) -> float:
    """Lebar/tinggi bidang wajah di kanvas hasil."""
    return out_w / max(1.0, out_h * GAMING_WAJAH_TINGGI / 100.0)


def _pas_rasio(r: dict, rasio_px: float, src_aspek: float, dalam: bool = False) -> dict:
    """
    Kotak sumber yang rasionya (dalam PIKSEL) sama dengan bidang tujuannya,
    berpusat di tengah kotak `r`, sebesar mungkin tanpa keluar dari bingkai.

    Kotak yang rasionya berbeda dari bidangnya dipotong lagi oleh "cover" saat
    dirender — dan yang terlihat di meja bingkai jadi lebih luas daripada yang
    benar-benar masuk ke klip. Menyamakan rasionya membuat kotak itu jujur.
    """
    cx = float(r["x"]) + float(r["w"]) / 2
    cy = float(r["y"]) + float(r["h"]) / 2
    # rasio persen = rasio piksel / rasio sumber
    k = rasio_px / max(1e-6, src_aspek)
    h = float(r["h"])
    w = h * k
    if dalam:
        # Di DALAM kotaknya: panel facecam yang lebih tegak dari bidang wajah
        # dipangkas atas-bawahnya, bukan dilebarkan ke samping — yang di
        # sampingnya adalah layar permainan, dan itu yang tampil sebagai
        # sepotong gelap di sebelah wajah.
        w = min(float(r["w"]), h * k)
        h = w / k
    if w > 100.0:
        w = 100.0
        h = w / k
    if h > 100.0:
        h = 100.0
        w = h * k
    x = min(max(0.0, cx - w / 2), 100.0 - w)
    y = min(max(0.0, cy - h / 2), 100.0 - h)
    return {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2)}


# Ruang di sekitar petak wajah (pecahan tinggi/lebar petak) yang harus ikut
# masuk bidang reaksi. Petaknya dari YuNet: alis sampai dagu. Tanpa ruang ini
# rambut dan dahi terpotong — terlapor, dan terukur pada klip Devour: 3% dari
# tinggi bingkai di atas alis, sementara kepalanya butuh ±6%.
KEPALA_ATAS = 0.35
KEPALA_BAWAH = 0.22
KEPALA_SAMPING = 0.25
# Batas tinggi bidang wajah otomatis, persen kanvas.
GAMING_WAJAH_MIN, GAMING_WAJAH_MAKS = 40.0, 50.0
# Porsi kotak reaksi yang boleh berada di luar panel facecam (berisi permainan).
REAKSI_LUAR_MAKS = 0.08
# Geser potongan permainan sejauh ini (persen) demi menghindari seluruh panel
# masih diterima; lebih jauh dari itu hanya WAJAH yang dihindari.
PERMAINAN_GESER_MAKS = 3.0


def _ruang_wajah(muka) -> Optional[dict]:
    """Petak wajah [x1,y1,x2,y2] (persen) -> kotak kepala utuh yang harus terlihat."""
    if not muka or len(muka) != 4:
        return None
    x1, y1, x2, y2 = (float(v) for v in muka)
    fw, fh = max(0.1, x2 - x1), max(0.1, y2 - y1)
    a = max(0.0, x1 - KEPALA_SAMPING * fw)
    b = min(100.0, x2 + KEPALA_SAMPING * fw)
    c = max(0.0, y1 - KEPALA_ATAS * fh)
    d = min(100.0, y2 + KEPALA_BAWAH * fh)
    return {"x": a, "y": c, "w": b - a, "h": d - c}


def _pilih(lo: float, hi: float, plo: float, phi: float, ingin: float) -> float:
    """Nilai di [lo,hi] (syarat) yang sebisanya juga di [plo,phi], sedekat mungkin ke `ingin`."""
    if lo > hi:
        lo = hi = (lo + hi) / 2
    a, b = max(lo, plo), min(hi, phi)
    if a <= b:
        return min(max(ingin, a), b)
    # Tidak bisa dua-duanya: syarat menang, dan sedekat mungkin ke panel.
    return min(max((plo + phi) / 2, lo), hi)


def kotak_reaksi(kotak: dict, muka, rasio_px: float, src_aspek: float) -> dict:
    """
    Potongan bidang reaksi: rasionya sama dengan bidangnya, memuat SELURUH
    kepala, dan sebisanya tetap di dalam panel facecam.

    Tanpa `muka` (petak wajah tidak diketahui — kotak yang diseret pengguna)
    sama dengan `_pas_rasio(..., dalam=True)` seperti dulu.
    """
    dasar = _pas_rasio(kotak, rasio_px, src_aspek, dalam=True)
    butuh = _ruang_wajah(muka)
    if butuh is None:
        return dasar
    k = rasio_px / max(1e-6, src_aspek)
    h = max(float(dasar["h"]), butuh["h"], butuh["w"] / k)
    w = h * k
    if w > 100.0:
        w, h = 100.0, 100.0 / k
    if h > 100.0:
        h, w = 100.0, 100.0 * k
    px, py = float(kotak["x"]), float(kotak["y"])
    pw, ph = float(kotak["w"]), float(kotak["h"])
    x = _pilih(butuh["x"] + butuh["w"] - w, butuh["x"], px, px + pw - w,
               butuh["x"] + butuh["w"] / 2 - w / 2)
    y = _pilih(butuh["y"] + butuh["h"] - h, butuh["y"], py, py + ph - h,
               butuh["y"] + butuh["h"] / 2 - h / 2)
    x = min(max(0.0, x), 100.0 - w)
    y = min(max(0.0, y), 100.0 - h)
    return {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2)}


def _porsi_luar(r: dict, panel: dict) -> float:
    """Porsi luas `r` yang berada di luar `panel`."""
    ix = max(0.0, min(r["x"] + r["w"], panel["x"] + panel["w"]) - max(r["x"], panel["x"]))
    iy = max(0.0, min(r["y"] + r["h"], panel["y"] + panel["h"]) - max(r["y"], panel["y"]))
    luas = max(1e-6, r["w"] * r["h"])
    return 1.0 - (ix * iy) / luas


def tinggi_wajah_otomatis(posisi: list, src_aspek: float, out_w: int, out_h: int) -> float:
    """Tinggi bidang wajah terendah (40-50%) yang kotak reaksinya tetap di panel."""
    terbaik, nilai_terbaik = GAMING_WAJAH_TINGGI, None
    langkah = [GAMING_WAJAH_MIN + 2.5 * i
               for i in range(int((GAMING_WAJAH_MAKS - GAMING_WAJAH_MIN) / 2.5) + 1)]
    for wajah in langkah:
        rasio = out_w / max(1.0, out_h * wajah / 100.0)
        luar = max(_porsi_luar(kotak_reaksi(p["facecam"], p["facecam"].get("awan_kotak"),
                                            rasio, src_aspek), p["facecam"])
                   for p in posisi)
        if luar <= REAKSI_LUAR_MAKS:
            return wajah
        if nilai_terbaik is None or luar < nilai_terbaik - 1e-6:
            terbaik, nilai_terbaik = wajah, luar
    return terbaik


def susun_layout_gaming(facecam, *, src_w: int = 1920, src_h: int = 1080,
                        out_w: int = 1080, out_h: int = 1920,
                        wajah: Optional[float] = None,
                        permainan: str = "isi") -> dict:
    """
    Kotak facecam -> susunan dua bidang yang dimengerti build_layout_graph.

    `facecam` boleh satu kotak, atau daftar `deteksi_facecam_waktu`
    ([{"t", "facecam"}]) bila wajahnya berpindah di tengah klip. Letak-letak
    itu disimpan di `reaksi`, dan `pecah_reaksi` memecahnya jadi potongan
    waktu saat merender.

    `permainan`:
      - "utuh"  seluruh layar permainan, selebar kanvas, tepat di bawah wajah;
                sisanya latar kabur tempat subtitle.
      - "isi"   bidang permainan memenuhi sisa kanvas; sisi kiri-kanan
                terpotong.
    Keduanya hanya titik berangkat: bidang permainan selalu dihitung dari
    BENTUK kotak sumbernya (`_bidang_permainan`), jadi kotak yang diubah
    pengguna tampil utuh tanpa dipotong lagi.
    """
    posisi = facecam if isinstance(facecam, list) else [{"t": 0.0, "facecam": facecam}]
    src_aspek = src_w / max(1, src_h)
    out_aspek = out_w / max(1, out_h)
    if wajah is None:
        # Tinggi bidang wajah mengikuti BENTUK panelnya: panel tegak butuh
        # bidang yang lebih tinggi supaya kepalanya muat tanpa ikut menyedot
        # permainan di sebelahnya.
        wajah = tinggi_wajah_otomatis(posisi, src_aspek, out_w, out_h)
    wajah = max(15.0, min(75.0, float(wajah)))
    if permainan == "utuh":
        main_src = {"x": 0, "y": 0, "w": 100, "h": 100}
        main_dst = _bidang_permainan(main_src, wajah, src_aspek, out_aspek)
    else:
        # Memenuhi seluruh sisa kanvas — tanpa bilah kosong — dengan potongan
        # permainan yang TIDAK memuat facecam, supaya wajah tidak tampil dua
        # kali (sekali besar di atas, sekali kecil di dalam permainan).
        main_dst = {"x": 0, "y": round(wajah, 2), "w": 100, "h": round(100 - wajah, 2)}
        main_src = _permainan_tanpa_wajah(
            [p["facecam"] for p in posisi],
            (out_w * main_dst["w"]) / (out_h * main_dst["h"]), src_aspek,
            wajah_saja=[_ruang_wajah(p["facecam"].get("awan_kotak")) or p["facecam"]
                        for p in posisi])
    wajah_dst = {"x": 0, "y": 0, "w": 100, "h": round(wajah, 2)}
    rasio_wajah = (out_w * wajah_dst["w"]) / (out_h * wajah_dst["h"])
    reaksi = []
    for p in posisi:
        kotak = {k: round(float(p["facecam"][k]), 2) for k in ("x", "y", "w", "h")}
        muka = p["facecam"].get("awan_kotak")
        muka = [round(float(v), 2) for v in muka] if muka else None
        r = {"t": round(float(p["t"]), 2), "kotak": kotak,
             "src": kotak_reaksi(kotak, muka, rasio_wajah, src_aspek)}
        if muka:
            # Disimpan supaya editor menghitung ulang potongan yang sama saat
            # tinggi bidang wajah digeser.
            r["muka"] = muka
        reaksi.append(r)
    return {
        "background": "blur",
        # Setelan susunan, supaya editor bisa menampilkan dan mengubahnya.
        "gaming": {"wajah": round(wajah, 2), "permainan": permainan},
        "reaksi": reaksi,
        "frames": [
            # Permainan digambar lebih dulu supaya wajah berada di atasnya bila
            # suatu saat keduanya bersinggungan.
            {"label": "Permainan", "src": main_src, "dst": main_dst, "fit": "cover"},
            {"label": "Reaksi", "src": reaksi[0]["src"], "dst": wajah_dst, "fit": "cover"},
        ],
    }


def _permainan_tanpa_wajah(facecams: list, rasio_px: float, src_aspek: float,
                          wajah_saja: Optional[list] = None) -> dict:
    """
    Potongan permainan setinggi bingkai berasio `rasio_px`, sedekat mungkin ke
    tengah, yang tidak bersinggungan dengan facecam mana pun di klip ini.
    Bila tidak ada tempat seperti itu, potongan tengah.

    Menghindari SELURUH panel bisa mendorong permainan jauh dari tengah —
    terukur 4,6% pada The Empty Eye, padahal wajahnya di x >= 81% dan tidak
    akan pernah masuk potongan tengah. Jadi bila menghindari panel menuntut
    geser lebih dari PERMAINAN_GESER_MAKS, yang dihindari hanya kepala di
    dalamnya (`wajah_saja`): sepotong tepi panel di pojok bawah jauh lebih
    ringan daripada permainan yang tidak di tengah.
    """
    if wajah_saja:
        hasil = _permainan_tanpa_wajah(facecams, rasio_px, src_aspek)
        k = rasio_px / max(1e-6, src_aspek)
        w = min(100.0, 100.0 * k)
        if abs(hasil["x"] - (50.0 - w / 2)) > PERMAINAN_GESER_MAKS:
            return _permainan_tanpa_wajah(wajah_saja, rasio_px, src_aspek)
        return hasil
    k = rasio_px / max(1e-6, src_aspek)
    h = 100.0
    w = min(100.0, h * k)
    if w >= 100.0:
        return {"x": 0, "y": round(max(0.0, (100 - 100 / k) / 2), 2),
                "w": 100, "h": round(min(100.0, 100 / k), 2)}
    tengah = 50.0 - w / 2
    calon = [tengah]
    for f in facecams:
        calon += [float(f["x"]) - w, float(f["x"]) + float(f["w"])]

    def bebas(x):
        return all(x + w <= float(f["x"]) + 0.5 or x >= float(f["x"]) + float(f["w"]) - 0.5
                   for f in facecams)

    sah = [x for x in calon if -1e-6 <= x <= 100 - w + 1e-6 and bebas(x)]
    x = min(sah, key=lambda v: abs(v - tengah)) if sah else tengah
    return {"x": round(min(max(0.0, x), 100 - w), 2), "y": 0, "w": round(w, 2), "h": 100}


def _bidang_permainan(src: dict, wajah: float, src_aspek: float, out_aspek: float) -> dict:
    """Bidang permainan selebar kanvas, setinggi bentuk kotak sumbernya."""
    rasio_px = (float(src["w"]) / max(1e-6, float(src["h"]))) * src_aspek
    sisa = 100.0 - wajah
    h = 100.0 * out_aspek / rasio_px
    if h > sisa:
        h = sisa
        w = h * rasio_px / out_aspek
        return {"x": round((100 - w) / 2, 2), "y": round(wajah, 2),
                "w": round(w, 2), "h": round(h, 2)}
    return {"x": 0, "y": round(wajah, 2), "w": 100, "h": round(h, 2)}


def pecah_reaksi(keys: list, durasi: float, bawaan: Optional[dict]) -> list:
    """
    Kunci "gaming" yang wajahnya berpindah -> beberapa kunci "layout", satu per
    letak wajah. Kunci lain tidak disentuh.
    """
    urut = sorted((k for k in keys or [] if isinstance(k, dict)),
                  key=lambda k: float(k.get("t") or 0))
    keluar: list = []
    for i, k in enumerate(urut):
        t0 = float(k.get("t") or 0)
        t1 = float(urut[i + 1].get("t") or 0) if i + 1 < len(urut) else durasi
        tata = k.get("layout") or (bawaan if (k.get("mode") or "") == "gaming" else None)
        reaksi = (tata or {}).get("reaksi") or []
        if (k.get("mode") or "") != "gaming" or not tata or not tata.get("frames"):
            keluar.append(k)
            continue
        if len(reaksi) <= 1 or len(tata["frames"]) < 2:
            keluar.append({**k, "layout": tata})
            continue
        for j, r in enumerate(reaksi):
            a = max(t0, float(r.get("t") or 0))
            b = min(t1, float(reaksi[j + 1].get("t") or 0) if j + 1 < len(reaksi) else t1)
            if b - a <= 0.05:
                continue
            frames = [dict(f) for f in tata["frames"]]
            frames[1]["src"] = dict(r["src"])
            keluar.append({**k, "t": round(a, 3), "mode": "layout",
                           "layout": {**tata, "frames": frames}})
    return keluar


# --- Bingkai yang berubah sepanjang klip ---------------------------------------
#
# Satu klip, beberapa cara membingkai, masing-masing berlaku di potongan waktu
# sendiri. Ini menjawab dua hal yang sebelumnya tidak bisa dilakukan sama
# sekali, dan keduanya datang dari kebutuhan yang sama:
#
#   Podcast bertiga — narasumber bicara, kamera mengikutinya; lalu ia melempar
#   lelucon dan yang penting justru REAKSI dua orang lain. "Ikuti wajah" secara
#   definisi hanya memberi satu wajah, jadi momen terbaiknya hilang.
#
#   Gameplay horor — adegan menegangkan butuh wajah DAN permainan berdampingan;
#   begitu jumpscare-nya datang, yang ingin dilihat orang cuma wajahnya, penuh
#   satu layar.
#
# Cara kerjanya: tiap kunci menghasilkan gambar 1080x1920 UTUH lewat cabangnya
# sendiri, lalu semuanya ditumpuk dengan `enable=between(t,…)` sehingga persis
# satu yang terlihat pada satu waktu.
#
# Kenapa bukan satu crop yang ukurannya digerakkan sendcmd — yang jauh lebih
# murah: mengubah LEBAR crop di tengah aliran mengubah ukuran bingkai yang
# masuk ke `scale`, dan itu memaksa ffmpeg menyusun ulang filter graph-nya di
# tengah jalan. Menggerakkan posisi saja aman (itulah yang dipakai "ikuti
# wajah"), mengganti ukuran tidak. Ongkos cara ini adalah tiap cabang tetap
# dihitung walau sedang tidak terlihat — untuk dua sampai empat kunci, itu
# harga yang jelas dan bisa diprediksi, bukan kegagalan yang muncul sesekali.

# Pergantian dibulatkan ke batas ini supaya `between()` tidak pernah punya
# celah maupun tumpang tindih yang terlihat.
KUNCI_EPS = 0.001


def _urut_kunci(keys: list, durasi: float) -> list[dict]:
    """Membersihkan daftar kunci jadi potongan waktu yang berurutan dan utuh."""
    bersih = []
    for k in keys or []:
        if not isinstance(k, dict):
            continue
        try:
            t = max(0.0, float(k.get("t") or 0.0))
        except (TypeError, ValueError):
            continue
        if t >= durasi:
            continue
        bersih.append({**k, "t": t})
    if not bersih:
        return []
    bersih.sort(key=lambda k: k["t"])
    # Kunci pertama selalu dimulai dari nol: potongan tanpa pembingkaian akan
    # tampil sebagai latar kabur kosong, yang tidak pernah diinginkan siapa pun.
    bersih[0]["t"] = 0.0
    for i, k in enumerate(bersih):
        k["akhir"] = bersih[i + 1]["t"] if i + 1 < len(bersih) else durasi
    return [k for k in bersih if k["akhir"] - k["t"] > KUNCI_EPS]


def _cabang_kunci(k: dict, i: int, masuk: str, keluar: str, *,
                  src_w: int, src_h: int, out_w: int, out_h: int,
                  aspect_ratio: str, plan, workdir, layout_gaming,
                  plan_gerak=None) -> str:
    """Satu kunci -> potongan graf yang menghasilkan kanvas penuh."""
    mode = (k.get("mode") or "smart").lower()

    if mode == "box" and k.get("rect"):
        x, y, w, h = _pct_rect(k["rect"], src_w, src_h)
        # `increase` lalu crop: kotak yang digambar pengguna jarang persis
        # serasi dengan kanvasnya, dan meregangkan gambar jauh lebih buruk
        # daripada memangkas beberapa piksel di sisinya.
        return (f"{masuk}crop={w}:{h}:{x}:{y},"
                f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
                f"crop={out_w}:{out_h},setsar=1{keluar}")

    if mode in ("gaming", "layout"):
        tata = k.get("layout") or (layout_gaming if mode == "gaming" else None)
        if tata and tata.get("frames"):
            return build_layout_graph(tata, masuk, keluar, src_w=src_w, src_h=src_h,
                                      out_w=out_w, out_h=out_h,
                                      plan=plan, workdir=workdir, awalan=f"k{i}_")
        mode = "smart"

    if mode == "motion" and plan_gerak is not None and plan_gerak.usable:
        from .reframe import build_reframe_filter
        rantai = build_reframe_filter(
            plan_gerak, workdir / f"gerak_kunci{i}.cmd", out_w, out_h, name=f"fg{i}")
        return f"{masuk}{rantai},setsar=1{keluar}"

    if mode == "smart" and plan is not None and plan.usable:
        from .reframe import build_reframe_filter
        orang = k.get("person")
        rantai = build_reframe_filter(
            plan, workdir / f"reframe_kunci{i}.cmd", out_w, out_h,
            name=f"fk{i}", person=int(orang) if orang is not None else None)
        return f"{masuk}{rantai},setsar=1{keluar}"

    # Usulan sutradara tidak pernah jatuh ke bilah kabur — pemiliknya
    # memutuskan layar harus selalu penuh. Rencana wajah/gerakan yang tidak
    # terpakai di kunci sutradara jadi potong tengah, yang tetap memenuhi layar.
    if mode == "center" or (k.get("asal") in ("ai", "otomatis")
                            and mode in ("smart", "motion")):
        f = CENTER_FILTERS.get(aspect_ratio) or CENTER_FILTERS["9:16"]
        return f"{masuk}{f}{keluar}"

    # Sisanya, termasuk "smart"/"motion" yang rencananya tidak terpakai:
    # bilah kabur.
    f = ASPECT_FILTERS.get(aspect_ratio) or ASPECT_FILTERS["9:16"]
    return f"{masuk}{f}{keluar}"


def build_frame_keys_graph(keys: list, in_label: str, out_label: str, *,
                           src_w: int, src_h: int, out_w: int, out_h: int,
                           durasi: float, aspect_ratio: str = "9:16",
                           plan=None, workdir=None,
                           layout_gaming: Optional[dict] = None,
                           plan_gerak=None) -> tuple[str, list]:
    """
    Graf untuk daftar kunci pembingkaian. Mengembalikan (graf, kunci_terpakai).

    Graf kosong berarti tidak ada yang bisa disusun — pemanggil lalu kembali ke
    jalur satu-mode seperti biasa.
    """
    dipakai = _urut_kunci(keys, durasi)
    if len(dipakai) < 2:
        # Satu kunci bukan linimasa, melainkan satu mode biasa. Ditolak di sini
        # supaya tidak ada klip yang membayar ongkos cabang berganda percuma.
        return "", dipakai

    # Potongan-potongan DISAMBUNG, bukan ditumpuk.
    #
    # Versi sebelumnya menjalankan semua cara membingkai sekaligus lalu
    # menumpuknya dengan `overlay` + `enable=between(...)` di atas latar kabur.
    # Secara teori benar; dalam praktik `overlay` harus MENYINKRONKAN semua
    # cabang, termasuk cabang yang baru punya bingkai di detik ke-21, dan pada
    # klip 40 detik dengan kunci gaming -> reaksi -> gaming hasilnya kehilangan
    # 3,8 detik bingkai tepat di potongan reaksinya: gambar membeku, video lebih
    # pendek daripada audionya. Klip 10 detik dengan kunci yang sama lolos, jadi
    # kesalahannya tidak terlihat di uji pendek.
    #
    # Di sini tiap potongan diproses di jendela waktunya sendiri lalu
    # disambung dengan `concat`, yang membaca potongan satu per satu dan tidak
    # menyinkronkan apa pun. Latar kabur yang tidak pernah terlihat juga tidak
    # perlu dihitung lagi.
    n = len(dipakai)
    # `fps` di depan: laju bingkai tetap, dan CELAH di sumber diisi bingkai
    # terakhir sebelum celahnya. Tanpa ini, sumber yang berlubang — unduhan
    # yang kehilangan potongan — membuat potongan yang tersambung lebih pendek
    # daripada jendelanya, dan video berakhir jauh sebelum audionya.
    bagian = [f"{in_label}fps=30,split={n}" + "".join(f"[fsrc{i}]" for i in range(n))]
    for i, k in enumerate(dipakai):
        t0, t1 = k["t"], k["akhir"]
        # `trim` TANPA mengatur ulang cap waktu: berkas perintah `sendcmd`
        # (ikut wajah, ikut gerakan) memakai waktu KLIP, jadi cabangnya harus
        # melihat waktu aslinya. Cap waktu baru dinolkan SESUDAH cabangnya,
        # karena `concat` menyambung potongan yang masing-masing mulai dari nol.
        bagian.append(f"[fsrc{i}]trim=start={t0:.3f}:end={t1:.3f}[fwin{i}]")
        bagian.append(_cabang_kunci(
            k, i, f"[fwin{i}]", f"[fk{i}]", src_w=src_w, src_h=src_h,
            out_w=out_w, out_h=out_h, aspect_ratio=aspect_ratio,
            plan=plan, workdir=workdir, layout_gaming=layout_gaming,
            plan_gerak=plan_gerak))
        # Semua potongan wajib seragam — ukuran, laju, format piksel — atau
        # `concat` menolaknya.
        bagian.append(f"[fk{i}]scale={out_w}:{out_h},setsar=1,format=yuv420p,"
                      f"setpts=PTS-STARTPTS[fc{i}]")
    bagian.append("".join(f"[fc{i}]" for i in range(n))
                  + f"concat=n={n}:v=1:a=0{out_label}")
    return ";".join(bagian), dipakai


# --- Sisipan: media dari luar video sumber -------------------------------------
#
# Seluruh jalur render tadinya berangkat dari SATU berkas: tiap bidang, tiap
# bingkai, adalah jendela ke dalam video yang sama. Sisipan adalah berkas KEDUA
# dan seterusnya — cuplikan pertandingan di bawah orang yang membahasnya, logo,
# musik latar, efek suara — masing-masing input ffmpeg sendiri yang ditempel
# pada waktunya.
#
# Urutan penempelan dipilih dengan sengaja: gambar sisipan ditumpuk SESUDAH
# pembingkaian dan SEBELUM subtitle. Sebelum pembingkaian, cuplikannya ikut
# terpotong crop 9:16 dan kehilangan dua pertiga lebarnya; sesudah subtitle,
# cuplikan layar penuh menutupi teksnya.

# Petak tujuan per posisi, dalam pecahan kanvas: (x, y, lebar, tinggi).
POSISI_SISIPAN = {
    "penuh": (0.0, 0.0, 1.0, 1.0),
    "atas": (0.0, 0.0, 1.0, 0.5),
    "bawah": (0.0, 0.5, 1.0, 0.5),
    "tengah": (0.0, 0.25, 1.0, 0.5),
    # Gambar-dalam-gambar di pojok kanan atas, 16:9 selebar 46% kanvas.
    "sudut": (0.50, 0.06, 0.46, None),
}


def _petak_sisipan(posisi: str, out_w: int, out_h: int) -> tuple[int, int, int, int]:
    x, y, w, h = POSISI_SISIPAN.get(posisi) or POSISI_SISIPAN["penuh"]
    pw = _even(out_w * w)
    ph = _even(pw * 9 / 16) if h is None else _even(out_h * h)
    return int(round(out_w * x)), int(round(out_h * y)), pw, ph


def siapkan_sisipan(lapisan: Optional[list], durasi: float) -> list[dict]:
    """Membersihkan daftar sisipan dan mencari berkasnya. Yang tak dikenal dibuang."""
    from . import aset as aset_svc

    keluar: list[dict] = []
    for l in lapisan or []:
        if not isinstance(l, dict):
            continue
        path = aset_svc.jalur(str(l.get("aset") or ""))
        info = aset_svc.info(str(l.get("aset") or "")) if path else None
        if path is None or info is None:
            log.warning("Sisipan dilewati: aset %r tidak ditemukan", l.get("aset"))
            continue
        try:
            t = max(0.0, float(l.get("t") or 0.0))
            mulai = max(0.0, float(l.get("mulai_sumber") or 0.0))
            vol = max(0.0, min(2.0, float(l.get("volume", 1.0))))
        except (TypeError, ValueError):
            continue
        if t >= durasi:
            continue
        panjang_aset = float(info.get("durasi") or 0.0)
        dur = l.get("dur")
        dur = float(dur) if dur not in (None, "") else (
            panjang_aset - mulai if panjang_aset > 0 else 4.0)
        if info["jenis"] != "gambar" and panjang_aset > 0:
            dur = min(dur, max(0.05, panjang_aset - mulai))
        dur = min(dur, durasi - t)
        if dur <= 0.05:
            continue
        keluar.append({
            "path": path, "jenis": info["jenis"], "punya_suara": info.get("punya_suara"),
            "t": t, "dur": dur, "mulai": mulai, "volume": vol,
            "posisi": str(l.get("posisi") or "penuh"),
            "redam": bool(l.get("redam", False)),
        })
    return keluar


def build_sisipan_graph(lapisan: list[dict], vin: str, ain: str, *,
                        input_awal: int, out_w: int, out_h: int
                        ) -> tuple[list[str], str, str, str]:
    """
    (input tambahan, graf, label video, label audio).

    Label yang dikembalikan sama dengan masukannya bila tidak ada yang perlu
    dilakukan, jadi pemanggil tidak perlu memeriksa apa pun.
    """
    inputs: list[str] = []
    bagian: list[str] = []
    video = vin
    suara: list[tuple[str, bool]] = []      # (label, diredam)
    idx = input_awal

    for i, l in enumerate(lapisan):
        t0, dur = l["t"], l["dur"]
        if l["jenis"] == "gambar":
            inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(l["path"])]
        else:
            inputs += ["-ss", f"{l['mulai']:.3f}", "-t", f"{dur:.3f}", "-i", str(l["path"])]

        if l["jenis"] in ("video", "gambar"):
            x, y, w, h = _petak_sisipan(l["posisi"], out_w, out_h)
            # `setpts ... +t0/TB` menggeser cuplikannya ke waktunya di klip;
            # tanpa itu overlay menempelkannya di detik nol, lalu `enable`
            # menyembunyikannya — cuplikan yang "tidak muncul" padahal ada.
            geser = f"setpts=PTS-STARTPTS+{t0:.3f}/TB"
            if l["jenis"] == "gambar":
                # Gambar DIMUAT utuh, bukan dipotong memenuhi petaknya: logo
                # persegi di petak 16:9 kehilangan atas-bawahnya kalau dipotong.
                # Transparansi PNG ikut dibawa (yuva420p), dan gambarnya
                # ditaruh di tengah petak.
                bagian.append(
                    f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                    f"setsar=1,format=yuva420p,{geser}[sv{i}]")
                px = f"{x}+({w}-overlay_w)/2"
                py = f"{y}+({h}-overlay_h)/2"
            else:
                bagian.append(
                    f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                    f"crop={w}:{h},setsar=1,format=yuv420p,{geser}[sv{i}]")
                px, py = str(x), str(y)
            keluar = f"[svo{i}]"
            bagian.append(
                f"{video}[sv{i}]overlay=x={px}:y={py}:eof_action=pass:"
                f"enable='between(t,{t0:.3f},{t0 + dur:.3f})'{keluar}")
            video = keluar

        if l["volume"] > 0 and (l["jenis"] == "audio" or l.get("punya_suara")):
            ms = int(round(t0 * 1000))
            bagian.append(
                f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
                f"asetpts=PTS-STARTPTS,volume={l['volume']:.3f},"
                f"adelay={ms}|{ms}[sa{i}]")
            suara.append((f"[sa{i}]", l["redam"]))
        idx += 1

    audio = ain
    if suara:
        # Audio utama diseragamkan ke 48 kHz stereo SEBELUM dicampur.
        #
        # `loudnorm` diam-diam mengeluarkan 192 kHz. Dicampur langsung dengan
        # sisipan 48 kHz, `amix` salah menghitung panjangnya dan memotong
        # seluruh audio klip: terukur, klip 10 detik keluar dengan audio 7,1
        # detik. Diseragamkan dulu, panjangnya kembali 10,0.
        bagian.append(f"{ain}aresample=48000,aformat=channel_layouts=stereo[sutama0]")
        utama = "[sutama0]"
        diredam = [lab for lab, r in suara if r]
        biasa = [lab for lab, r in suara if not r]
        if diredam:
            # Musik latar mengecil sendiri saat orang bicara. Tanpa ini pilihan
            # volumenya selalu salah: cukup keras untuk terdengar di jeda
            # berarti menutupi kalimat, cukup pelan untuk kalimat berarti
            # hilang di jeda.
            n = len(diredam)
            bagian.append(f"{utama}asplit={n + 1}[sutama]"
                          + "".join(f"[ssc{j}]" for j in range(n)))
            utama = "[sutama]"
            for j, lab in enumerate(diredam):
                bagian.append(f"{lab}[ssc{j}]sidechaincompress="
                              f"threshold=0.02:ratio=9:attack=15:release=450:makeup=1"
                              f"[sd{j}]")
                biasa.append(f"[sd{j}]")
        semua = [utama] + biasa
        bagian.append(
            "".join(semua) + f"amix=inputs={len(semua)}:duration=first:normalize=0,"
            "alimiter=limit=0.97[scampur]")
        audio = "[scampur]"

    return inputs, ";".join(bagian), video, audio


def build_clip_filename(*, title: str, index: Optional[int], start: float,
                        existing: Path) -> str:
    """
    Nama berkas hasil render yang bisa dikenali tanpa dibuka.

    Nama lama berbentuk "dSq0Z5XpoLc_1459360_56360_a5ee3fb1.mp4": unik, tapi
    tidak memberi tahu apa pun. Setelah mengekspor sepuluh klip, tidak ada cara
    tahu mana yang mana selain memutarnya satu per satu — dan berkas itu yang
    diunggah ke media sosial, tempat nama berkas ikut terbaca orang.

    Bentuk barunya "Pertemuan-Bersejarah-dr-Tirta_klip-03_24m19s.mp4": judul
    videonya, nomor klipnya, dan menit keberapa ia diambil. Tabrakan diselesaikan
    dengan akhiran angka, bukan dengan menempelkan uuid ke setiap nama.
    """
    minutes = int(start // 60)
    seconds = int(start % 60)
    parts = [slugify(title)]
    if index:
        parts.append(f"klip-{int(index):02d}")
    parts.append(f"{minutes:02d}m{seconds:02d}s")
    stem = "_".join(parts)

    candidate = f"{stem}.mp4"
    n = 2
    while (existing / candidate).exists():
        candidate = f"{stem}-{n}.mp4"
        n += 1
    return candidate


def render_clip(
    *,
    source_video_path: str,
    segments: list[dict],
    subtitles: Optional[list[dict]] = None,
    aspect_ratio: str = "9:16",
    hook_text: str = "",
    watermark: str = "",
    video_filter: str = "normal",
    caption_style: Optional[CaptionStyle] = None,
    frame_mode: str = "smart",
    # "smooth" = kamera mengikuti dengan mulus; "cut" = diam di dalam satu
    # bidikan lalu berpindah seketika. Keduanya sah — yang mulus terasa
    # sinematik, yang memotong terasa seperti hasil editor.
    frame_motion: str = "smooth",
    frame_layout: Optional[dict] = None,
    # Linimasa pembingkaian: [{t, mode, rect?, person?, layout?}] dalam waktu
    # KLIP. Bila berisi dua kunci atau lebih, ia menang atas `frame_mode`.
    frame_keys: Optional[list] = None,
    # Sisipan: [{aset, t, dur?, mulai_sumber?, posisi?, volume?, redam?}] dalam
    # waktu KLIP. Lihat build_sisipan_graph.
    media_layers: Optional[list] = None,
    # Subtitle kedua (biasanya terjemahan): {aktif, bahasa, lines, style}.
    subtitle_kedua: Optional[dict] = None,
    lock_person: Optional[int] = None,
    # Tanda linimasa dari pengguna: [{t, person}] dalam waktu KLIP.
    person_keys: Optional[list] = None,
    # Kartu judul di awal klip. Disusun terpisah lalu disambung di sini.
    title_card: Optional[dict] = None,
    loudnorm: bool = True,
    video_id: str = "",
    title: str = "",
    hashtags: Optional[list] = None,
    clip_index: Optional[int] = None,
    on_progress: Optional[Callable[[float], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> dict[str, Any]:
    """
    Memotong, menyambung, dan merender satu klip.

    `segments` adalah daftar {start, end} dalam linimasa video asli.
    `subtitles` memakai linimasa KLIP (mulai dari 0) — hasil dari
    clipmodel.rebuild_subtitles_for_segments().
    """
    src = Path(source_video_path)
    if not src.is_file():
        return {"success": False, "error": "File video sumber tidak ditemukan."}

    segments = [s for s in segments if float(s["end"]) - float(s["start"]) > 0.2]
    if not segments:
        return {"success": False, "error": "Rentang klip tidak valid."}

    total_duration = sum(float(s["end"]) - float(s["start"]) for s in segments)

    vid = video_id or extract_id_from_filename(src.name) or "clip"
    first = segments[0]
    # Folder klip milik profil yang meminta render ini (services/profil.py).
    from . import profil as _profil
    folder_keluar = _profil.folder_klip(_profil.kini())
    out_name = build_clip_filename(
        title=title or vid,
        index=clip_index,
        start=float(first["start"]),
        existing=folder_keluar,
    )
    out_path = folder_keluar / out_name

    workdir = Path(tempfile.mkdtemp(prefix="omniclip_render_"))
    try:
        inputs, seg_graph, labels = _build_segment_graph(segments)
        inputs = [str(src) if x == "SRC" else x for x in inputs]
        vlabel, alabel = labels.split("|")

        # Pembingkaian. Smart reframe mengikuti wajah pembicara; bila wajah
        # jarang terlihat (gameplay, screencast, slide) rencananya ditolak dan
        # kita jatuh ke blur-pad, karena memaksa pelacakan di rekaman layar
        # menghasilkan crop yang meloncat-loncat.
        chain: list[str] = []
        out_w, out_h = PLAY_RES.get(aspect_ratio, (1080, 1920))
        frame_used = frame_mode if frame_mode in ("blur", "center", "original") else "blur"
        face_coverage = None

        if frame_mode == "original":
            # Bingkai sumber dipertahankan apa adanya: tanpa crop, tanpa bilah,
            # tanpa penskalaan. Subtitle tetap dibakar, jadi kanvas ASS harus
            # memakai ukuran video aslinya — bukan 1080x1920 — supaya ukuran dan
            # posisi teks tidak melenceng.
            from .media import probe as _probe
            info = _probe(src)
            out_w = int(info.get("width") or 1920)
            out_h = int(info.get("height") or 1080)

        # Susunan bingkai sendiri. Bukan satu rantai filter melainkan graf
        # bercabang, jadi ia disusun terpisah dan menghasilkan label barunya
        # sendiri yang lalu dipakai rantai sisanya.
        layout_graph = ""
        # Giliran bicara, dari subtitle yang sudah memuat label penutur hasil
        # diarisasi. Waktunya sudah relatif terhadap klip, sama dengan waktu
        # sampel deteksi wajah, jadi keduanya bisa langsung dibandingkan.
        #
        # Disusun SEBELUM percabangan tata letak. Sebelumnya ia dibuat di
        # bawahnya padahal cabang tata letak sudah memakainya, yang berarti
        # setiap bingkai pengikut di susunan buatan pengguna menabrak
        # UnboundLocalError — bukan salah bingkai, melainkan gagal merender.
        speaker_turns = [
            (float(l["start"]), float(l["end"]), int(l["speaker"]))
            for l in (subtitles or [])
            if l.get("speaker") is not None and l.get("end") is not None
        ]

        # Mode gaming: susunannya TIDAK digambar pengguna melainkan diturunkan
        # dari videonya sendiri, lalu dijalankan lewat jalur susunan yang sama.
        # Linimasa pembingkaian diperiksa lebih dulu: ia menggantikan seluruh
        # percabangan mode tunggal di bawahnya.
        kunci_graf = ""
        kunci_dipakai: list = []
        # Satu kunci tetap sebuah keputusan: "seluruh klip ini dibingkai
        # begini". Dulu ia diabaikan dan render kembali ke mode dasar — jadi
        # usulan sutradara "gaming untuk seluruh klip" dirender sebagai ikuti
        # wajah tanpa satu pun tanda. Digandakan di tengah klip, ia melewati
        # jalur linimasa yang sama dengan kunci lainnya.
        # Main game tanpa linimasa = satu kunci "gaming" untuk seluruh klip,
        # supaya wajah yang berpindah di tengah klip bisa dipecah jadi potongan
        # waktu (`pecah_reaksi`) lewat jalur linimasa yang sama.
        if frame_mode == "gaming" and not [k for k in (frame_keys or []) if isinstance(k, dict)]:
            frame_keys = [{"t": 0.0, "mode": "gaming",
                           **({"layout": frame_layout}
                              if frame_layout and frame_layout.get("frames") else {})}]
        satu = [k for k in (frame_keys or []) if isinstance(k, dict)]
        if len(satu) == 1:
            separuh = sum(float(sg["end"]) - float(sg["start"]) for sg in segments) / 2
            frame_keys = [{**satu[0], "t": 0.0}, {**satu[0], "t": round(separuh, 3)}]
        if frame_keys and len([k for k in frame_keys if isinstance(k, dict)]) >= 2:
            from .media import probe as _probe

            info = _probe(src)
            skunci_w = int(info.get("width") or 1920)
            skunci_h = int(info.get("height") or 1080)
            durasi_klip = sum(float(sg["end"]) - float(sg["start"]) for sg in segments)

            # Rencana wajah disusun sekali dan dipakai semua kunci "smart".
            kunci_plan_gerak = None
            if any((k.get("mode") or "") == "motion" for k in frame_keys):
                kunci_plan_gerak = plan_reframe(
                    str(src), segments, aspect_ratio=aspect_ratio,
                    frame_motion=frame_motion, subjek="gerak")

            kunci_plan = None
            # Juga untuk susunan yang bingkainya membuntuti orang (reaksi dari
            # sutradara): tanpa rencana wajah, bingkai itu diam di tempatnya.
            if any((k.get("mode") or "smart") == "smart"
                   or any(f.get("follow") for f in ((k.get("layout") or {}).get("frames") or []))
                   for k in frame_keys):
                kunci_plan = plan_reframe(str(src), segments, aspect_ratio=aspect_ratio,
                                          speaker_turns=speaker_turns,
                                          person_keys=person_keys,
                                          frame_motion=frame_motion)
                if kunci_plan is not None:
                    face_coverage = kunci_plan.face_coverage

            # Begitu pula facecam: dicari sekali, dipakai tiap kunci "gaming".
            tata_gaming = None
            if any((k.get("mode") or "") == "gaming" and not (k.get("layout") or {}).get("frames")
                   for k in frame_keys):
                from .reframe import deteksi_facecam_waktu
                posisi = deteksi_facecam_waktu(src, segments, skunci_w, skunci_h,
                                               rasio_potongan=rasio_bidang_wajah(out_w, out_h))
                if posisi:
                    tata_gaming = susun_layout_gaming(posisi, src_w=skunci_w, src_h=skunci_h,
                                                      out_w=out_w, out_h=out_h)
            frame_keys = pecah_reaksi(frame_keys, durasi_klip, tata_gaming)

            kunci_graf, kunci_dipakai = build_frame_keys_graph(
                frame_keys, vlabel, "[vkeys]",
                src_w=skunci_w, src_h=skunci_h, out_w=out_w, out_h=out_h,
                durasi=durasi_klip, aspect_ratio=aspect_ratio,
                plan=kunci_plan, workdir=workdir, layout_gaming=tata_gaming,
                plan_gerak=kunci_plan_gerak)
            if kunci_graf:
                frame_used = "keys"
                log.info("Linimasa bingkai: %s",
                         " -> ".join(f"{k['t']:.1f}s {k.get('mode','smart')}"
                                     for k in kunci_dipakai))

        dari_gaming = False
        if (not kunci_graf and frame_mode == "gaming" and frame_layout
                and frame_layout.get("frames")):
            # Susunan yang sudah disetel pengguna di Studio (tinggi wajah,
            # permainan utuh/penuh, letak kotak) — dipakai apa adanya.
            frame_mode = "layout"
            dari_gaming = True
        if not kunci_graf and frame_mode == "gaming":
            from .media import probe as _probe
            from .reframe import deteksi_facecam

            info = _probe(src)
            mulai = float(segments[0]["start"]) if segments else 0.0
            panjang = sum(float(sg["end"]) - float(sg["start"]) for sg in segments) or 1.0
            facecam = deteksi_facecam(
                src, mulai, min(panjang, 30.0),
                int(info.get("width") or 1920), int(info.get("height") or 1080),
                rasio_potongan=rasio_bidang_wajah(out_w, out_h))
            if facecam:
                frame_layout = susun_layout_gaming(
                    facecam, src_w=int(info.get("width") or 1920),
                    src_h=int(info.get("height") or 1080), out_w=out_w, out_h=out_h)
                frame_mode = "layout"
                dari_gaming = True
            else:
                # Tidak ada facecam yang diam di satu tempat: ini bukan rekaman
                # gameplay dengan kamera pemain. Jatuh ke pelacakan wajah biasa,
                # yang punya jalur mundurnya sendiri ke bilah kabur.
                log.info("Facecam tidak ditemukan — mode gaming jatuh ke smart")
                frame_mode = "smart"

        if not kunci_graf and frame_mode == "layout" and frame_layout and frame_layout.get("frames"):
            from .media import probe as _probe
            info = _probe(src)
            layout_frames = frame_layout.get("frames") or []

            # Jejak wajah disusun SEKALI dan dipakai bersama semua bingkai yang
            # mengikutinya: mereka mengikuti orang yang sama, jadi menjalankan
            # deteksi dua kali hanya menghabiskan waktu untuk hasil yang sama.
            layout_plan = None
            if any(f.get("follow") for f in layout_frames):
                layout_plan = plan_reframe(str(src), segments,
                                           aspect_ratio=aspect_ratio, track_only=True,
                                           speaker_turns=speaker_turns,
                                           person_keys=person_keys,
                                           frame_motion=frame_motion)
                if layout_plan is not None:
                    face_coverage = layout_plan.face_coverage
                if layout_plan is not None and not layout_plan.centers:
                    layout_plan = None
                if layout_plan is None:
                    log.info("Wajah tidak terlacak — bingkai pengikut memakai "
                             "posisi tetap dari kotaknya")

            layout_graph = build_layout_graph(
                frame_layout, vlabel, "[vlay]",
                src_w=int(info.get("width") or 1920),
                src_h=int(info.get("height") or 1080),
                out_w=out_w, out_h=out_h,
                plan=layout_plan, workdir=workdir,
            )
            if layout_graph:
                # Dilaporkan apa adanya: "gaming" saat susunannya diturunkan
                # sendiri dari videonya, "layout" saat pengguna yang menggambar.
                frame_used = "gaming" if dari_gaming else "layout"

        # "motion" memakai mesin yang sama persis dengan "smart" — yang berbeda
        # hanya APA yang dijejak: pusat massa gerakan, bukan wajah manusia.
        # Itulah yang membuatnya bekerja pada kartun, maskot, dan hewan, yang
        # tidak pernah ditemukan pendeteksi wajah.
        if not kunci_graf and frame_mode in ("smart", "motion"):
            plan = plan_reframe(str(src), segments, aspect_ratio=aspect_ratio,
                                speaker_turns=speaker_turns, lock_person=lock_person,
                                person_keys=person_keys, frame_motion=frame_motion,
                                subjek="gerak" if frame_mode == "motion" else "wajah")
            if plan is not None:
                face_coverage = plan.face_coverage
            if plan is not None and plan.usable:
                chain.append(build_reframe_filter(
                    plan, workdir / "reframe.cmd", out_w, out_h))
                frame_used = frame_mode

        if frame_used not in ("smart", "motion", "original", "layout", "gaming", "keys"):
            table = CENTER_FILTERS if frame_used == "center" else ASPECT_FILTERS
            aspect = table.get(aspect_ratio)
            if aspect:
                chain.append(aspect)

        # Semua yang di atas garis ini MEMBINGKAI; semua yang di bawahnya
        # menghias. Sisipan ditempel tepat di antaranya.
        n_bingkai = len(chain)

        grade = VIDEO_FILTERS.get(video_filter)
        if grade:
            chain.append(grade)

        # Subtitle + hook + watermark, semuanya lewat satu file ASS.
        # Gaya teks dipatok pada kanvas 1080x1920. Pada bingkai orisinal yang
        # tingginya 720 piksel, ukuran dan margin yang sama akan melempar
        # subtitle ke tengah layar dan membuat hurufnya raksasa — jadi keduanya
        # diskalakan mengikuti tinggi kanvas sebenarnya.
        style_for_render = caption_style or CaptionStyle()
        if out_h and out_h != 1920:
            factor = out_h / 1920.0
            style_for_render = replace(
                style_for_render,
                size=max(20, int(round(style_for_render.size * factor))),
                margin_v=max(12, int(round(style_for_render.margin_v * factor))),
                outline_px=max(2, int(round(style_for_render.outline_px * factor))),
                shadow_px=max(1, int(round(style_for_render.shadow_px * factor))),
            )

        # Subtitle kedua: gaya sendiri, diskalakan dengan aturan yang sama.
        kedua_lines, kedua_style = None, None
        if subtitle_kedua and subtitle_kedua.get("aktif", True) and subtitle_kedua.get("lines"):
            kedua_style = gaya_dari_dict(subtitle_kedua.get("style") or {})
            if out_h and out_h != 1920:
                f2 = out_h / 1920.0
                kedua_style = replace(
                    kedua_style,
                    size=max(20, int(round(kedua_style.size * f2))),
                    margin_v=max(12, int(round(kedua_style.margin_v * f2))),
                    outline_px=max(2, int(round(kedua_style.outline_px * f2))),
                    shadow_px=max(1, int(round(kedua_style.shadow_px * f2))),
                )
            kedua_lines = subtitle_kedua["lines"]

        ass_path = None
        # Saklar subtitle ikut dihormati di sini, bukan hanya di dalam
        # build_ass: klip tanpa subtitle, tanpa hook, dan tanpa tanda air tidak
        # perlu melewati filter `ass` sama sekali.
        ada_teks = (style_for_render.aktif and subtitles
                    and any((l.get("text") or "").strip() for l in subtitles))
        if ada_teks or kedua_lines or hook_text.strip() or watermark.strip():
            ass_path = workdir / "captions.ass"
            ass_path.write_text(
                build_ass(
                    lines=subtitles or [],
                    style=style_for_render,
                    hook=HookSpec(text=hook_text) if hook_text.strip() else None,
                    watermark=watermark,
                    play_res=(out_w, out_h),
                    clip_duration=total_duration,
                    kedua_lines=kedua_lines,
                    kedua_style=kedua_style,
                    kedua_ikut_orang=bool(((subtitle_kedua or {}).get("style") or {})
                                          .get("ikut_warna_orang")),
                ),
                encoding="utf-8",
            )
            ass_arg = ffpath(ass_path)
            fonts = ffpath(FONTS_DIR) if FONTS_DIR.is_dir() else None
            chain.append(f"ass=filename='{ass_arg}'" + (f":fontsdir='{fonts}'" if fonts else ""))

        # --- Kartu judul ------------------------------------------------------
        # Disiapkan SEBELUM graf dirangkai karena panjangnya menentukan durasi
        # total, dan durasi total dipakai pelaporan kemajuan.
        card_spec = tc.TitleCardSpec.from_payload(title_card)
        # Font kartu mengikuti font subtitle klip kecuali kartunya menyebut
        # fontnya sendiri. Pratinjau menggambar keduanya dengan font yang sama,
        # jadi render harus begitu juga — kalau tidak, satu-satunya cara
        # mengetahui hasilnya adalah dengan merender.
        if not (title_card or {}).get("font"):
            card_spec.font = (caption_style or CaptionStyle()).font
        card = tc.plan_card(card_spec, workdir, out_w, out_h) if card_spec.enabled else None
        card_notes = list(card.notes) if card else []
        if card and card_spec.mode == "overlay":
            # Judul yang menempel di atas klip berjalan hanyalah satu filter ass
            # lagi di rantai yang sama — tidak ada waktu yang ditambahkan.
            chain.append(tc.overlay_filter(card, str(FONTS_DIR) if FONTS_DIR.is_dir() else None))

        graph = seg_graph
        if kunci_graf:
            graph += ";" + kunci_graf
            vlabel = "[vkeys]"
        elif layout_graph:
            graph += ";" + layout_graph
            vlabel = "[vlay]"
        rantai_bingkai, rantai_hias = chain[:n_bingkai], chain[n_bingkai:]
        if rantai_bingkai:
            graph += f";{vlabel}" + ",".join(rantai_bingkai) + "[vbingkai]"
            vlabel = "[vbingkai]"

        # Sisipan: di atas bingkai, di bawah subtitle.
        sisipan = siapkan_sisipan(media_layers, total_duration)
        sisipan_graf, sisipan_a = "", None
        if sisipan:
            n_input = len([x for x in inputs if x == "-i"])
            s_inputs, sisipan_graf, vlabel, sisipan_a = build_sisipan_graph(
                sisipan, vlabel, "[SISIPAN_A]", input_awal=n_input,
                out_w=out_w, out_h=out_h)
            inputs += s_inputs
            log.info("Sisipan: %s", ", ".join(
                f"{l['jenis']}@{l['t']:.1f}s" for l in sisipan))
            # Graf audio sisipan butuh audio utama yang SUDAH dinormalisasi,
            # yang labelnya baru ada di bawah. `[SISIPAN_A]` adalah penanda
            # tempat yang diganti begitu labelnya diketahui.
            graph += ";" + sisipan_graf

        if rantai_hias:
            graph += f";{vlabel}" + ",".join(rantai_hias) + "[vout]"
            vout = "[vout]"
        else:
            vout = vlabel

        # Normalisasi loudness harus berada DI DALAM filter_complex. ffmpeg
        # menolak `-af` (filter sederhana) untuk stream yang keluar dari
        # filtergraph kompleks: "Simple and complex filtering cannot be used
        # together for the same stream."
        aout = alabel
        if loudnorm:
            graph += f";{alabel}loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
            aout = "[aout]"
        if sisipan_a and sisipan_a != "[SISIPAN_A]":
            # Ucapan dinormalisasi DULU, baru dicampur. Kalau dicampur lebih
            # dulu, loudnorm akan meratakan musik dan ucapan bersama-sama, dan
            # volume yang dipilih pengguna untuk musiknya kehilangan artinya.
            graph = graph.replace("[SISIPAN_A]", aout)
            aout = sisipan_a

        # Kartu yang MENAMBAH waktu disambung paling akhir, sesudah subtitle dan
        # normalisasi: latarnya diambil dari bingkai pertama aliran yang sudah
        # jadi, jadi yang dibekukan adalah gambar yang benar-benar akan dilihat
        # penonton — bukan bingkai mentah 16:9 yang tidak pernah muncul.
        if card is not None and card.adds_time:
            wav_index = None
            if card.wav_path is not None and card.wav_path.is_file():
                wav_index = len([x for x in inputs if x == "-i"])
                inputs += ["-i", str(card.wav_path)]
            fonts_dir = ffpath(FONTS_DIR) if FONTS_DIR.is_dir() else None
            graph += ";" + tc.video_filters(card, vout, "kartu", "utama",
                                            out_w, out_h, fontsdir=fonts_dir)
            graph += ";" + tc.audio_filters(card, wav_index, "kartua")
            graph += (f";[kartu][kartua][utama]{aout}"
                      f"concat=n=2:v=1:a=1[vjadi][ajadi]")
            vout, aout = "[vjadi]", "[ajadi]"
            total_duration += card.seconds

        from . import enkoder

        def perintah(enc: dict) -> list[str]:
            graf, v = graph, vout
            if enc["saring"]:
                graf += f";{vout}{enc['saring']}[venc]"
                v = "[venc]"
            return [enc["ffmpeg"], "-y", "-hide_banner", "-nostdin", "-loglevel", "error",
                    "-progress", "pipe:1", *enc["global"], *inputs,
                    "-filter_complex", graf,
                    "-map", v, "-map", aout,
                    # Encoder GPU bila ada dan terbukti bekerja — lihat
                    # services/enkoder.py. x264 tanpa `-threads`: ia memilih
                    # sendiri, terukur 10% lebih cepat daripada patokan 4.
                    *enc["video"],
                    "-r", "30", "-g", "60",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart",
                    str(out_path)]

        enc = enkoder.pilih()
        cmd = perintah(enc)
        rc, stderr_text = _run_ffmpeg(cmd, duration=total_duration,
                                      on_progress=on_progress, should_cancel=should_cancel)
        batal = bool(should_cancel and should_cancel())
        if rc != 0 and enc["nama"] != "x264" and not batal:
            # GPU yang lolos uji satu detik masih bisa gagal pada klip nyata
            # (memori video habis, driver). Pengguna tidak boleh menanggungnya.
            log.warning("Render dengan %s gagal: %s", enc["nama"], stderr_text[-300:])
            enkoder.tandai_gagal(enc)
            if out_path.exists():
                out_path.unlink()
            cmd = perintah(enkoder.X264)
            rc, stderr_text = _run_ffmpeg(cmd, duration=total_duration,
                                          on_progress=on_progress, should_cancel=should_cancel)

        if rc != 0:
            log_path = LOGS_DIR / f"render_{out_name}.log"
            try:
                log_path.write_text(
                    " ".join(shlex.quote(c) for c in cmd) + "\n\n" + stderr_text,
                    encoding="utf-8",
                )
            except OSError:
                pass
            if out_path.exists():
                out_path.unlink()
            log.error("Render gagal (rc=%s). Log: %s", rc, log_path)
            return {"success": False, "error": "Proses ffmpeg gagal.", "log_path": str(log_path)}

        meta = {
            "file_name": out_name,
            "video_id": vid,
            "title": title,
            # Ikut disimpan supaya formulir unggah bisa mengisinya sendiri
            # nanti, tanpa pengguna mengetik ulang apa yang sudah ia setel.
            "hashtags": hashtags or [],
            "clip_index": clip_index,
            "segments": segments,
            "duration": round(total_duration, 3),
            "aspect_ratio": aspect_ratio,
            "frame_mode": frame_used,
            "face_coverage": face_coverage,
            "frame_layout": frame_layout if frame_used == "layout" else None,
            "hook_text": hook_text,
            "watermark": watermark,
            "video_filter": video_filter,
            "subtitles": subtitles or [],
            "media_layers": media_layers or [],
            "subtitle_kedua": subtitle_kedua,
            "created_at": time.time(),
        }
        (folder_keluar / out_name.replace(".mp4", ".json")).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Takarir terpisah di samping klipnya.
        #
        # Subtitle yang dibakar ke gambar tidak bisa dimatikan penonton, tidak
        # terbaca mesin pencari, dan tidak bisa diterjemahkan YouTube. Berkas
        # .srt ini menjawab ketiganya, ukurannya beberapa kilobita, dan tidak
        # mengubah apa pun pada videonya. Yang gagal ditulis tidak menjatuhkan
        # render — klipnya sendiri sudah jadi.
        try:
            from .subtitles import tulis_srt
            tulis_srt(subtitles or [], folder_keluar / out_name.replace(".mp4", ".srt"))
            kedua = (subtitle_kedua or {}).get("lines") if isinstance(subtitle_kedua, dict) else None
            if kedua:
                tulis_srt(kedua, folder_keluar / out_name.replace(".mp4", ".terjemahan.srt"))
        except Exception as e:
            log.warning("Takarir .srt tidak bisa ditulis: %s", str(e)[:200])

        return {
            "success": True,
            "clip_path": str(out_path),
            "clip_name": out_name,
            "profil_id": _profil.kini(),
            "kategori": _profil.kategori_klip(_profil.kini()),
            "duration": round(total_duration, 3),
            "file_size": out_path.stat().st_size if out_path.exists() else 0,
            "frame_mode": frame_used,
            "face_coverage": face_coverage,
        }
    finally:
        for f in workdir.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            workdir.rmdir()
        except OSError:
            pass


# Daftar klip, ditahan di memori sampai isi foldernya berubah.
#
# Tiap pemanggilan membaca satu `stat` dan satu berkas sidecar JSON per klip.
# Di folder dengan 49 klip di cakram luar itu terukur 0,86 detik — dan halaman
# Klip jadi memanggilnya setiap kali dibuka, termasuk saat kembali dari halaman
# lain. Waktu tempuh cakramnya tidak bisa dikurangi; yang bisa adalah tidak
# menempuhnya lagi untuk jawaban yang belum berubah.
#
# Kuncinya waktu-ubah FOLDER, bukan pewaktu: menulis, menghapus, atau mengganti
# nama berkas di dalamnya mengubah angka itu, jadi klip yang baru selesai
# dirender langsung terlihat tanpa menunggu apa pun kedaluwarsa.
_DAFTAR_KLIP: tuple[float, int, list[dict]] | None = None


def list_local_clips(folder: Optional[Path] = None) -> list[dict]:
    """Klip hasil render beserta metadata sidecar-nya, dari folder satu profil."""
    global _DAFTAR_KLIP

    clips: list[dict] = []
    folder = Path(folder or CLIPS_DIR)
    if not folder.is_dir():
        return clips

    try:
        tanda = (str(folder), folder.stat().st_mtime)
    except OSError:
        tanda = (str(folder), 0.0)
    if _DAFTAR_KLIP is not None and _DAFTAR_KLIP[0] == tanda:
        # Salinan dangkal: pemanggil menambahkan `web_url` ke tiap entri, dan
        # menyerahkan objek simpanan berarti ia ikut tertulis berkali-kali.
        return [dict(c) for c in _DAFTAR_KLIP[2]]

    for path in folder.glob("*.mp4"):
        stat = path.stat()
        entry = {
            "file_name": path.name,
            "file_size": stat.st_size,
            "created_at": stat.st_mtime,
            "metadata": None,
            # Takarir terpisah, bila render menulisnya. Klip lama tidak punya,
            # dan tombolnya tidak boleh muncul untuk berkas yang tidak ada.
            "srt": path.with_suffix(".srt").is_file(),
        }
        sidecar = path.with_suffix(".json")
        if sidecar.is_file():
            try:
                entry["metadata"] = json.loads(sidecar.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        clips.append(entry)

    clips.sort(key=lambda c: c["created_at"], reverse=True)
    _DAFTAR_KLIP = (tanda, len(clips), clips)
    return [dict(c) for c in clips]
