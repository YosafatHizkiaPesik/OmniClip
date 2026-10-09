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
from .fonts import dir_font
from .subtitles import CaptionStyle, sensor_aktif, HookSpec, build_ass, gaya_dari_dict
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


# Laju bingkai hasil render.
#
# Sampai 5 Oktober 2026 angkanya dipatok 30, dan alasannya masuk akal: sumber
# 60 fps membawa dua kali bingkai yang dibutuhkan melewati setiap crop, scale,
# dan blur, lalu separuhnya dibuang begitu sampai ke pengode. Pada mesin 15 watt
# itu bukan penghematan kecil.
#
# Yang tidak ikut dihitung: apa yang hilang. Untuk klip GAMEPLAY, separuh laju
# bingkai adalah kehilangan mutu yang paling kelihatan di layar — jauh lebih
# terasa daripada bitrate. Dilaporkan pemiliknya sesudah mengunggah beberapa
# video: "kualitasnya jelek meskipun sudah ada tulisan SD dan HD". Terukur pada
# klip jadinya: 1080x1920, 13,7 Mbps — resolusi dan bitrate justru baik — tapi
# 30 fps dari sumber 60 fps.
#
# Jadi sekarang laju sumber yang diikuti, dan 30 tetap bisa dipilih di
# Pengaturan untuk render yang harus cepat.
#
# Ongkosnya ternyata jauh lebih kecil daripada dugaan. Terukur 5 Oktober 2026 di
# mesin pemiliknya (i5-8250U, VAAPI), klip 6 detik dari sumber 60 fps:
#
#   60 fps  11,4 detik
#   30 fps  10,3 detik
#
# Sebelas persen, bukan dua kali lipat. Yang menanggung beban berat adalah
# pengode GPU, dan ia tidak peduli berapa bingkai yang masuk; yang berlipat
# hanya kerja filter, dan filter di mode blur ringan. Susunan gaming dengan
# linimasa bingkai lebih berat daripada ini, jadi angkanya akan berbeda — tapi
# dugaan "dua kali lipat" yang dipakai sebagai alasan mematok 30 selama ini
# tidak pernah diukur.
LAJU_MAKS = 60          # di atas ini tidak ada platform pendek yang peduli
LAJU_MIN = 24           # sumber yang lebih lambat dari ini dinaikkan ke sini


def laju_render(src_fps: Optional[float] = None) -> int:
    """
    Laju bingkai keluaran: ikut sumber (bawaan) atau dipatok 30.

    Sumber yang lajunya tidak terbaca memakai 30, bukan menebak: menebak
    terlalu tinggi berarti ffmpeg menggandakan bingkai dan berkasnya membesar
    tanpa satu pun gambar baru.
    """
    try:
        from ..repos import settings as settings_repo
        pilihan = (settings_repo.get("render.fps") or "").strip().lower()
    except Exception:                                    # noqa: BLE001
        pilihan = ""
    if pilihan == "30":
        return 30
    try:
        n = int(round(float(src_fps)))
    except (TypeError, ValueError):
        return 30
    if n <= 0:
        return 30
    return max(LAJU_MIN, min(LAJU_MAKS, n))


def _build_segment_graph(segments: list[dict],
                         fps: int = 30) -> tuple[list[str], str, str]:
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

        # `fps` LANGSUNG sesudah pemotongan, untuk semua mode: celah di sumber
        # yang berlubang (unduhan yang kehilangan potongan) diisi bingkai
        # terakhir, jadi gambar dan suara tetap sinkron. Angkanya dari
        # `laju_render` — ikut sumber kecuali Pengaturan memintanya 30.
        parts.append(
            f"[{i}:v]trim=start={pre:.3f}:duration={dur:.3f},setpts=PTS-STARTPTS,"
            f"fps={fps}[v{i}]"
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
# Tinggi bidang WAJAH sebagai persen kanvas. Sisanya untuk permainannya.
#
# Turun dari 40 ke 32 pada 25 September 2026 atas permintaan pemiliknya:
# "adjust lagi agar tampilan game lebih besar daripada reaksi". Pada 40 kedua
# bidang nyaris sama besar, dan yang sebenarnya jadi isi klip justru
# permainannya; wajah pemain di situ adalah reaksi, bukan subjek.
#
# 32 memberi permainan 68% kanvas. Batas bawahnya tetap dijaga oleh
# `tinggi_wajah_otomatis`: kalau kotak reaksi tidak muat di panel sependek itu,
# ia naik sendiri sampai muat.
GAMING_WAJAH_TINGGI = 32.0


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
#
# Batas atas turun dari 50 ke 40 pada 25 September 2026, atas permintaan
# pemiliknya: "wajahnya terlalu besar, buat saja 30-40% untuk wajah". Pada 50
# permainan tinggal separuh kanvas, padahal yang jadi isi klip justru
# permainannya.
#
# Diukur pada 49 bentuk panel facecam (lebar 12-44%, tinggi 18-90%): hanya 4
# yang nilainya berubah, dan 2 di antaranya — panel yang sangat sempit dan
# sangat tinggi, 12x60 dan 16x90 — kotak reaksinya jadi meluber lebih dari 8%
# ke luar panel, artinya sedikit layar permainan ikut terlihat di sisi wajah.
# Bentuk seperti itu jarang, dan pembatas yang bisa diseret di pratinjau
# membetulkannya dalam satu gerakan.
#
# Rata-rata bidang wajah sendiri hampir tidak bergeser, 31,9% -> 31,3%: batas
# lama memang jarang terpakai. Yang benar-benar menjawab keluhan pemiliknya
# adalah pembatas yang bisa diseret, bukan angka ini.
GAMING_WAJAH_MIN, GAMING_WAJAH_MAKS = 30.0, 40.0
# Porsi kotak reaksi yang boleh berada di luar panel facecam (berisi permainan).
REAKSI_LUAR_MAKS = 0.08
# Geser potongan permainan sejauh ini (persen) demi menghindari seluruh panel
# masih diterima; lebih jauh dari itu hanya WAJAH yang dihindari.
PERMAINAN_GESER_MAKS = 3.0


def _ruang_wajah(muka, panel: Optional[dict] = None) -> Optional[dict]:
    """
    Petak wajah [x1,y1,x2,y2] (persen) -> kotak kepala utuh yang harus terlihat.

    Dengan `panel`, hasilnya DIKURUNG di dalam panel facecam. Ruang kepala yang
    meluap keluar panel berarti potongan bidang wajah ikut memuat gambar
    permainan di sebelahnya, dan itu persis yang tidak boleh terjadi.
    """
    if not muka or len(muka) != 4:
        return None
    x1, y1, x2, y2 = (float(v) for v in muka)
    fw, fh = max(0.1, x2 - x1), max(0.1, y2 - y1)
    a = max(0.0, x1 - KEPALA_SAMPING * fw)
    b = min(100.0, x2 + KEPALA_SAMPING * fw)
    c = max(0.0, y1 - KEPALA_ATAS * fh)
    d = min(100.0, y2 + KEPALA_BAWAH * fh)
    if panel:
        pa, pb = float(panel["x"]), float(panel["x"]) + float(panel["w"])
        pc, pd = float(panel["y"]), float(panel["y"]) + float(panel["h"])
        a, b = max(a, pa), min(b, pb)
        c, d = max(c, pc), min(d, pd)
        if b - a <= 0.01 or d - c <= 0.01:
            return None
    return {"x": a, "y": c, "w": b - a, "h": d - c}


def _petak_wajah(facecam: dict):
    """
    Petak kepala yang dipakai untuk membentuk potongan bidang wajah.

    Yang dipakai `awan_kotak`: petak yang memuat SELURUH posisi wajah selama
    jendela pemindaian, yaitu jelajah gerak orangnya, bukan satu kepala.

    Sempat diganti `wajah_kotak` (satu kepala berukuran tengah) pada
    30 September 2026 untuk menghentikan potongan yang meluap keluar panel.
    Itu memang berhenti, tapi sekalian membuang toleransi terhadap gerakan:
    terukur pada empat klip LaperGang, 1.456 sampel berwajah, wajah yang
    benar-benar termuat di potongannya turun jadi 64,5%. Dengan jelajah
    geraknya, 73,3%.

    Yang menghentikan luapan bukan mengecilkan petaknya melainkan MENGURUNGnya
    di dalam panel — itu dikerjakan `_ruang_wajah(muka, panel)`. Jadi keduanya
    bisa sekaligus: menampung gerakan, dan tidak pernah keluar facecam.

    `wajah_kotak` tetap disimpan dan dipakai sebagai cadangan, plus sebagai
    dasar penanda `awan_besar` yang memecah jendela berisi dua letak.
    """
    return facecam.get("awan_kotak") or facecam.get("wajah_kotak")


def _pilih(lo: float, hi: float, plo: float, phi: float, ingin: float) -> float:
    """Nilai di [lo,hi] (syarat) yang sebisanya juga di [plo,phi], sedekat mungkin ke `ingin`."""
    if lo > hi:
        lo = hi = (lo + hi) / 2
    a, b = max(lo, plo), min(hi, phi)
    if a <= b:
        return min(max(ingin, a), b)
    # Tidak bisa dua-duanya: syarat menang, dan sedekat mungkin ke panel.
    return min(max((plo + phi) / 2, lo), hi)


# Bagian ruang sisa yang ditaruh di ATAS kepala; sisanya di bawah.
ATAS_KEPALA_SISA = 0.25

# Seberapa jauh potongan reaksi boleh MELAMPAUI panel ke samping, dalam pecahan
# lebar panel, demi memakai seluruh TINGGI panel.
#
# Diminta pemiliknya 9 Oktober 2026: "bingkai untuk wajahnya terlalu crop
# wajahnya saja, seharusnya dilebihkan juga untuk crop badannya, jika full
# wajahnya nantinya terlalu besar di hasil preview dan render".
#
# Ia benar, dan sebabnya bentuk. Bidang wajah selebar kanvas berasio 1,41:1
# sementara panel facecam hampir persegi. Potongan terbesar berasio bidang yang
# muat DI DALAM panel karena itu membuang tinggi panelnya: terukur pada klip 1
# video pemiliknya, panel 15,2x27,0% dipotong jadi 15,2x19,2%. Yang terbuang
# 29% tinggi panel, dan di situlah bahu dan dadanya.
#
# Dengan melampaui panel ke samping, tinggi panel terpakai penuh:
#
#   di dalam panel     potongan 15,2x19,2%  zoom 3,70x  wajah 47% lebar kanvas
#   tinggi panel penuh potongan 21,4x27,0%  zoom 2,63x  wajah 33% lebar kanvas
#
# Harganya nyata dan harus disebut: sekitar 14% lebar bidang di kiri dan di
# kanan berisi gambar permainan, bukan facecam.
#
# Angkanya PER SISI, dan 0,22 bukan pilihan selera. Ia persis sebanyak yang
# dibutuhkan supaya tinggi panel terpakai penuh pada bentuk panel yang biasa
# (hampir persegi) dengan bidang wajah 40%. Dicoba 0,35 lebih dulu dan ditolak
# dengan angkanya sendiri: potongannya jadi 25,8% lebar, 42% bidang wajah
# berisi permainan, dan wajahnya tinggal 27% lebar kanvas. Itu bukan lagi
# "dilebihkan sedikit untuk badannya", itu bidang permainan yang kebetulan ada
# wajahnya.
#
# Nol mengembalikan perilaku sebelum hari itu, persis.
LUAR_PANEL_MAKS = 0.22


def _pakai_tinggi_panel(dasar: dict, panel: dict, rasio_px: float,
                       src_aspek: float) -> dict:
    """
    Melebarkan potongan reaksi sampai SELURUH tinggi panel terpakai.

    Lihat LUAR_PANEL_MAKS untuk angka dan harganya. Dipanggil sesudah potongan
    terbesar yang muat di dalam panel sudah dihitung, jadi yang dikerjakan di
    sini hanya menukar tinggi yang terbuang dengan lebar yang melampaui panel.

    Tidak pernah melampaui bingkai sumber, dan tidak pernah mengecilkan apa pun:
    kalau pelebarannya tidak muat, yang dikembalikan potongan semula.
    """
    if LUAR_PANEL_MAKS <= 0:
        return dasar
    ph = float(panel["h"])
    if ph <= float(dasar["h"]) + 0.01:
        return dasar                                 # tingginya memang sudah penuh
    # Lebar yang dibutuhkan supaya potongan setinggi panel tetap berasio bidang.
    w = ph * rasio_px / src_aspek
    tambah = w - float(dasar["w"])
    if tambah <= 0:
        return dasar
    if tambah > LUAR_PANEL_MAKS * float(panel["w"]) * 2:
        # Terlalu jauh: ambil sebanyak yang diizinkan, tingginya ikut menyesuaikan.
        w = float(dasar["w"]) + LUAR_PANEL_MAKS * float(panel["w"]) * 2
    h = w * src_aspek / rasio_px
    if w > 100.0 or h > 100.0:
        return dasar
    # Dipusatkan pada panel, lalu dikurung di dalam bingkai sumber.
    x = float(panel["x"]) + float(panel["w"]) / 2 - w / 2
    y = float(panel["y"]) + ph / 2 - h / 2
    x = min(max(0.0, x), 100.0 - w)
    y = min(max(0.0, y), 100.0 - h)
    return {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2)}


def kotak_reaksi(kotak: dict, muka, rasio_px: float, src_aspek: float) -> dict:
    """
    Potongan bidang reaksi: SEBESAR MUNGKIN di dalam kotak facecam, berasio
    bidangnya, dan diletakkan pada kepalanya.

    Tanpa `muka` (petak wajah tidak diketahui — kotak yang diseret pengguna)
    hasilnya sama: kotak terbesar berasio bidang yang muat di dalam panel,
    hanya letaknya di tengah panel.

    UKURANNYA DITENTUKAN PANEL, BUKAN KEPALA. Ini kebalikan dari aturan
    30 September 2026, dan koreksi atasnya.

    Aturan lama mengambil sebesar KEPALA berikut ruangnya, dengan alasan yang
    waktu itu benar: potongan sebesar panel membawa meja, kursi, dan dinding,
    dan wajahnya hanya mengisi 16-18% luasnya. Tapi obatnya kelewatan. Terukur
    pada klip pemiliknya: panel 386x303 piksel dipotong jadi 240x136 — lebih
    kecil daripada panelnya di KEDUA sisi, padahal 320x303 muat di situ.
    Akibatnya dua-duanya: facecamnya tidak tampil utuh, DAN perbesarannya naik
    dari 3,4x ke 4,5x sehingga lebih buram. Dilaporkan 1 Oktober 2026:
    "bingkai wajahnya terlalu kecil, apakah kamu tidak bisa memetakkan ukuran
    facecam... agar bingkai bisa pas dengan ukuran kotak facecam tersebut".
    Ia benar.

    Yang membuat aturan lama perlu adalah potongan yang MELEBIHI panel, bukan
    potongan yang mengisinya. Mengisi panel setepat-tepatnya memberi ketiganya
    sekaligus: tidak ada permainan yang ikut masuk (potongan ada di dalam
    panel), facecamnya tampil sebanyak yang muat, dan perbesarannya sekecil
    yang bisa dicapai bidang selebar itu.

    Yang dipilih kepala karena itu tinggal LETAKNYA. Panel yang bentuknya
    berbeda dari bidangnya tetap harus dipangkas pada satu sisi, dan yang
    menentukan di mana memangkasnya adalah di mana kepalanya.
    """
    dasar = _pas_rasio(kotak, rasio_px, src_aspek, dalam=True)
    dasar = _pakai_tinggi_panel(dasar, kotak, rasio_px, src_aspek)
    butuh = _ruang_wajah(muka, kotak)
    if butuh is None:
        return dasar
    w, h = float(dasar["w"]), float(dasar["h"])
    # Batas geser: panelnya sendiri bila potongan masih muat di dalamnya, atau
    # seluruh bingkai bila potongan memang sengaja melampauinya (lihat
    # `_pakai_tinggi_panel`). Tanpa pelonggaran ini, `_pilih` di bawah menerima
    # rentang kosong dan potongannya terlempar ke tengah panel.
    px, py = float(kotak["x"]), float(kotak["y"])
    pw, ph = float(kotak["w"]), float(kotak["h"])
    if w > pw:
        px, pw = max(0.0, px + pw / 2 - w / 2), w
    if h > ph:
        py, ph = max(0.0, py + ph / 2 - h / 2), h
    # Panel syarat KERAS, kepala syarat lunak: apa pun yang di luar panel
    # isinya permainan, dan permainan di bidang wajah adalah keluhan yang
    # berulang — "bingkai wajahnya terlalu besar melebihi facecam bahkan
    # memotong bingkai game" (30 September 2026).
    x = _pilih(px, px + pw - w,
               butuh["x"] + butuh["w"] - w, butuh["x"],
               butuh["x"] + butuh["w"] / 2 - w / 2)
    # Ruang sisa ditaruh sebagian besar DI BAWAH kepala, bukan dibagi rata.
    #
    # Menaruhnya rata berarti separuhnya di atas kepala. Bila tepi atas panel
    # ditaksir terlalu tinggi — dan itu sering, karena facecam menempel di sudut
    # sehingga tepinya berimpit dengan tepi bingkai — ruang di atas itu terisi
    # gambar permainan, dan bidang wajah menampilkan langit-langit Minecraft di
    # atas kepala orangnya. Terlihat pada render klip LaperGang, 30 September
    # 2026. Di bawah kepala yang ada bahu dan dada, yang memang bagian dari
    # bidikan wajah.
    sisa = max(0.0, h - butuh["h"])
    y = _pilih(py, py + ph - h,
               butuh["y"] + butuh["h"] - h, butuh["y"],
               butuh["y"] - sisa * ATAS_KEPALA_SISA)
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
    """
    Tinggi bidang wajah (30-40%) yang membuat potongannya MENUTUP paling banyak
    kotak facecam.

    Dulu yang dicari tinggi terendah yang kotak reaksinya tidak meluber keluar
    panel. Sejak `kotak_reaksi` memotong di DALAM panel tanpa kecuali, ukuran
    itu selalu nol dan pilihannya selalu jatuh ke angka terendah — ukuran yang
    sudah tidak mengukur apa pun.

    Yang diukur sekarang hal yang benar-benar dilihat orang: seberapa banyak
    isi kotak facecam yang sampai ke layar. Bidang selebar kanvas berbentuk
    sangat lebar sementara panel facecam tegak, jadi panel selalu dipangkas
    pada satu sisi; bidang yang lebih tinggi berbentuk kurang lebar, dan
    pangkasannya lebih sedikit. Dilaporkan pemiliknya 1 Oktober 2026:
    "bingkai wajahnya terlalu kecil... agar bingkai bisa pas dengan ukuran
    kotak facecam tersebut".

    Seri dimenangkan tinggi TERENDAH: bidang permainan tidak boleh kehilangan
    satu piksel pun demi perbaikan yang tidak terlihat.
    """
    langkah = [GAMING_WAJAH_MIN + 2.5 * i
               for i in range(int((GAMING_WAJAH_MAKS - GAMING_WAJAH_MIN) / 2.5) + 1)]
    terbaik, nilai_terbaik = GAMING_WAJAH_TINGGI, -1.0
    for wajah in langkah:
        rasio = out_w / max(1.0, out_h * wajah / 100.0)
        tutup = []
        for p in posisi:
            f = p["facecam"]
            luas = max(1e-6, float(f["w"]) * float(f["h"]))
            r = kotak_reaksi(f, _petak_wajah(f), rasio, src_aspek)
            tutup.append((float(r["w"]) * float(r["h"])) / luas)
        nilai = sum(tutup) / max(1, len(tutup))
        # 1% bedanya tidak terlihat; di bawah itu yang menang tinggi terendah.
        if nilai > nilai_terbaik + 0.01:
            terbaik, nilai_terbaik = wajah, nilai
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
            wajah_saja=[_ruang_wajah(_petak_wajah(p["facecam"]), p["facecam"])
                        or p["facecam"] for p in posisi])
    # BIDANG WAJAH SELEBAR KANVAS.
    #
    # Sempat dipersempit mengikuti bentuk kotak facecam, 1 Oktober 2026, atas
    # usul pemiliknya sendiri: "bukannya lebih enak jika bingkai itu pas sesuai
    # dengan kotak facecam". Secara ukuran itu memang jadi persis — tumpang
    # tindih potongan dengan panelnya naik dari 71% ke 97% — tapi yang ia lihat
    # bukan itu: bidangnya jadi kotak kecil di tengah dengan permainan kabur di
    # kiri dan kanannya. "Tampilannya malah berbeda dengan yang saya minta."
    # Diminta kembali seperti semula di hari yang sama.
    #
    # Yang tidak bisa dipunyai dua-duanya, dan itu ukur-mengukur bentuk saja:
    # panel facecam tegak atau hampir persegi, bidang selebar kanvas sangat
    # lebar. Sumber tegak tidak bisa mengisi bidang lebar tanpa dipotong. Jadi
    # yang dipilih di sini mengisi penuh, dan `kotak_reaksi` di bawah yang
    # memotong panel itu ke bentuk bidangnya — dengan KEPALA sebagai acuan, dan
    # tanpa pernah keluar dari panelnya.
    wajah_dst = {"x": 0, "y": 0, "w": 100, "h": round(wajah, 2)}
    rasio_wajah = (out_w * wajah_dst["w"]) / (out_h * wajah_dst["h"])
    # POTONGAN PERMAINAN DIHITUNG PER LETAK, bukan sekali untuk seluruh klip.
    #
    # `main_src` di atas menghindari SEMUA facecam yang pernah muncul di klip
    # ini. Pada klip pendek itu benar dan murah: facecamnya satu tempat saja.
    # Pada klip panjang ia runtuh — pemiliknya memasukkan satu video 12 menit
    # utuh sebagai satu klip, 7 Oktober 2026, dan melaporkan "akurasi bingkai
    # menurun di video klip yang panjang". Sebabnya mekanis: streamer
    # memindahkan kameranya beberapa kali, jadi yang harus dihindari adalah
    # GABUNGAN semua letak itu, dan tidak ada potongan yang bisa menghindari
    # kiri-bawah dan kanan-bawah sekaligus tanpa membuang bagian tengah
    # permainannya.
    #
    # Tiap letak wajah sudah menjadi potongan waktunya sendiri saat dirender
    # (`pecah_reaksi`), jadi potongan permainannya ikut berganti di batas yang
    # sama: yang dihindari hanya facecam yang BENAR-BENAR ada pada saat itu.
    rasio_main = ((out_w * main_dst["w"]) / (out_h * main_dst["h"])
                  if permainan != "utuh" else None)
    reaksi = []
    for p in posisi:
        kotak = {k: round(float(p["facecam"][k]), 2) for k in ("x", "y", "w", "h")}
        muka = _petak_wajah(p["facecam"])
        muka = [round(float(v), 2) for v in muka] if muka else None
        r = {"t": round(float(p["t"]), 2), "kotak": kotak,
             "src": kotak_reaksi(kotak, muka, rasio_wajah, src_aspek)}
        if muka:
            # Disimpan supaya editor menghitung ulang potongan yang sama saat
            # tinggi bidang wajah digeser.
            r["muka"] = muka
        if rasio_main is not None:
            ruang = _ruang_wajah(muka, p["facecam"]) or p["facecam"]
            r["main"] = _permainan_tanpa_wajah([p["facecam"]], rasio_main, src_aspek,
                                               wajah_saja=[ruang])
        reaksi.append(r)
    reaksi = _rapikan_reaksi(reaksi)
    return {
        "background": "blur",
        # Setelan susunan, supaya editor bisa menampilkan dan mengubahnya.
        "gaming": {"wajah": round(wajah, 2), "permainan": permainan},
        "reaksi": reaksi,
        "frames": [
            # Permainan digambar lebih dulu supaya wajah berada di atasnya bila
            # suatu saat keduanya bersinggungan.
            #
            # `id` ikut, dan itu bukan hiasan. Studio memilih kotak yang sedang
            # diseret dengan `frames.find(f => f.id === frameId)`. Tanpa id,
            # DUA kotak sama-sama cocok dengan `undefined`: menyeret kotak
            # Reaksi menulis potongannya ke Permainan juga, dan keduanya
            # langsung bertumpuk jadi satu. Dilaporkan pemiliknya 1 Oktober
            # 2026, dengan dua tangkapan layar sebelum dan sesudah.
            #
            # Dulu susunan ini selalu lewat `susunanDariServer` di peramban,
            # yang memasang id sendiri. Sejak pemanasan menuliskan susunannya
            # langsung ke klip (services/bingkai_awal.py), jalan itu tidak lagi
            # selalu dilalui — jadi idnya harus datang dari sini.
            {"id": "permainan", "label": "Permainan", "src": main_src,
             "dst": main_dst, "fit": "cover"},
            {"id": "reaksi", "label": "Reaksi", "src": reaksi[0]["src"],
             "dst": wajah_dst, "fit": "cover"},
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


# Berapa banyak letak facecam yang boleh dibawa satu klip.
#
# Dulu 64, dipatok di model permintaan tanpa pernah diuji pada klip panjang.
# Terbukti salah 7 Oktober 2026: pemiliknya memasukkan satu video 17 menit utuh
# sebagai SATU klip, facecamnya berpindah 68 kali, dan seluruh render ditolak
# sebelum dimulai — "List should have at most 64 items after validation, not
# 68". Yang ia lihat di Studio cuma dinding JSON.
#
# Batasnya bukan selera melainkan ongkos: tiap letak jadi satu potongan `trim`
# di filtergraph. Pada klip 17 menit, 68 potongan masih wajar; 512 memberi
# ruang untuk video satu jam tanpa pernah menolak pekerjaan orang.
REAKSI_MAKS = 512

# Letak yang berlaku lebih pendek dari ini digabung ke tetangganya.
#
# Setengah detik bingkai di tempat lain lalu kembali tidak terbaca sebagai
# "kamera pindah"; yang terlihat cuma kedipan. Menggabungkannya juga yang
# menjaga jumlah potongan tetap masuk akal pada klip panjang.
REAKSI_JARAK_MIN = 0.8


def _rapikan_reaksi(reaksi: list, maks: int = REAKSI_MAKS) -> list:
    """
    Letak facecam yang terlalu rapat digabung, lalu jumlahnya dibatasi.

    Yang dibuang saat masih terlalu banyak adalah yang paling SEBENTAR
    berlakunya: letak yang cuma sedetik lebih mudah dikorbankan daripada letak
    yang memayungi dua menit klip.
    """
    urut = sorted((r for r in reaksi or [] if isinstance(r, dict)),
                  key=lambda r: float(r.get("t") or 0))
    if len(urut) <= 1:
        return urut
    rapat = [urut[0]]
    for r in urut[1:]:
        if float(r.get("t") or 0) - float(rapat[-1].get("t") or 0) < REAKSI_JARAK_MIN:
            continue
        rapat.append(r)
    if len(rapat) <= maks:
        return rapat
    # Lama berlakunya tiap letak, untuk memilih yang dibuang.
    def lama(i: int) -> float:
        t = float(rapat[i].get("t") or 0)
        return (float(rapat[i + 1].get("t") or 0) - t) if i + 1 < len(rapat) else float("inf")
    urutan_buang = sorted(range(1, len(rapat)), key=lama)[:len(rapat) - maks]
    buang = set(urutan_buang)
    return [r for i, r in enumerate(rapat) if i not in buang]


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
            # Potongan permainan ikut berganti bersama letak wajahnya, kalau
            # pemindaian menyertakannya. Klip yang disimpan sebelum
            # 7 Oktober 2026 tidak punya medan ini dan tetap memakai potongan
            # tetap seperti dulu.
            if r.get("main"):
                frames[0]["src"] = dict(r["main"])
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
                  plan_gerak=None, frame_zoom: float = 1.0,
                  frame_geser_y: float = 0.0) -> str:
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
        from .reframe import build_reframe_filter, petak_zoom
        zw, zh, zy = petak_zoom(plan_gerak, frame_zoom, frame_geser_y)
        rantai = build_reframe_filter(
            plan_gerak, workdir / f"gerak_kunci{i}.cmd", out_w, out_h, name=f"fg{i}",
            crop_w=zw, crop_h=zh, crop_y=zy)
        return f"{masuk}{rantai},setsar=1{keluar}"

    if mode == "smart" and plan is not None and plan.usable:
        from .reframe import build_reframe_filter, petak_zoom
        orang = k.get("person")
        zw, zh, zy = petak_zoom(plan, frame_zoom, frame_geser_y)
        rantai = build_reframe_filter(
            plan, workdir / f"reframe_kunci{i}.cmd", out_w, out_h,
            name=f"fk{i}", person=int(orang) if orang is not None else None,
            crop_w=zw, crop_h=zh, crop_y=zy)
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
                           plan_gerak=None, frame_zoom: float = 1.0,
                           frame_geser_y: float = 0.0,
                           fps: int = 30) -> tuple[str, list]:
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
    bagian = [f"{in_label}fps={fps},split={n}" + "".join(f"[fsrc{i}]" for i in range(n))]
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
            plan_gerak=plan_gerak, frame_zoom=frame_zoom,
            frame_geser_y=frame_geser_y))
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


def _petak_dari_rect(rect: dict, out_w: int, out_h: int) -> tuple[int, int, int, int]:
    """
    Petak bebas yang digambar pengguna, dalam PERSEN kanvas.

    Persen, bukan piksel: klip yang sama dirender 1080x1920 dan 1080x1350, dan
    petak berpiksel akan pindah tempat di antara keduanya. Persen berarti angka
    yang sama berarti hal yang sama di setiap rasio, sama seperti `pos_x` dan
    `box_w` pada subtitle.

    Dijepit ke dalam kanvas, lalu dibulatkan genap: h264 menolak lebar atau
    tinggi ganjil, dan yang gagal bukan filternya melainkan seluruh rendernya.
    """
    x = max(0.0, min(100.0, float(rect.get("x", 0.0))))
    y = max(0.0, min(100.0, float(rect.get("y", 0.0))))
    w = max(2.0, min(100.0 - x, float(rect.get("w", 100.0))))
    h = max(2.0, min(100.0 - y, float(rect.get("h", 100.0))))
    pw = max(2, _even(out_w * w / 100.0))
    ph = max(2, _even(out_h * h / 100.0))
    px = int(round(out_w * x / 100.0))
    py = int(round(out_h * y / 100.0))
    # Digeser masuk bila pembulatan genap membuatnya melewati tepi kanvas.
    px = max(0, min(px, out_w - pw))
    py = max(0, min(py, out_h - ph))
    return px, py, pw, ph


def petak_sisipan(l: dict, out_w: int, out_h: int) -> tuple[int, int, int, int]:
    """
    Petak sebuah sisipan: rect bebas kalau ada, kalau tidak preset lamanya.

    Preset tidak dibuang saat rect ditambahkan, dan itu disengaja: klip yang
    sudah tersimpan sejak sebelum hari ini memakainya, dan klip yang sudah jadi
    tidak boleh berubah tampilannya sendiri hanya karena aplikasinya diperbarui.
    """
    rect = l.get("rect")
    if isinstance(rect, dict):
        return _petak_dari_rect(rect, out_w, out_h)
    return _petak_sisipan(str(l.get("posisi") or "penuh"), out_w, out_h)


# Tinggi huruf sisipan teks, dalam persen tinggi kanvas.
TEKS_UKURAN_BAWAAN = 4.5
TEKS_WARNA_BAWAAN = "#FFFFFF"
TEKS_KELUARGA_BAWAAN = "Archivo Black"


def _siapkan_teks(l: dict, durasi: float) -> Optional[dict]:
    """Satu lapisan teks yang sudah bersih, atau None bila tidak ada isinya."""
    teks = str(l.get("teks") or "").strip()
    if not teks:
        return None
    try:
        t = max(0.0, float(l.get("t") or 0.0))
    except (TypeError, ValueError):
        return None
    if t >= durasi:
        return None
    try:
        dur = float(l["dur"]) if l.get("dur") not in (None, "") else durasi - t
    except (TypeError, ValueError):
        dur = durasi - t
    dur = min(max(0.05, dur), durasi - t)
    if dur <= 0.05:
        return None
    try:
        opasitas = max(0.0, min(1.0, float(l.get("opasitas", 1.0))))
        masuk = max(0.0, min(dur / 2, float(l.get("fade_masuk") or 0.0)))
        keluar_f = max(0.0, min(dur / 2, float(l.get("fade_keluar") or 0.0)))
        ukuran = max(1.0, min(40.0, float(l.get("ukuran") or TEKS_UKURAN_BAWAAN)))
    except (TypeError, ValueError):
        opasitas, masuk, keluar_f, ukuran = 1.0, 0.0, 0.0, TEKS_UKURAN_BAWAAN
    rect = l.get("rect")
    return {
        "jenis": "teks", "path": None, "punya_suara": False,
        "teks": teks[:200],
        "t": t, "dur": dur, "mulai": 0.0, "volume": 0.0,
        "posisi": str(l.get("posisi") or "bawah"),
        "rect": rect if isinstance(rect, dict) else None,
        "isi": "muat",
        "opasitas": opasitas, "fade_masuk": masuk, "fade_keluar": keluar_f,
        "ukuran": ukuran,
        "keluarga": str(l.get("keluarga") or TEKS_KELUARGA_BAWAAN),
        "warna": str(l.get("warna") or TEKS_WARNA_BAWAAN),
        "garis": str(l.get("garis") or "#000000"),
        "tebal_garis": max(0.0, min(12.0, float(l.get("tebal_garis") or 3.0))),
        "latar": str(l.get("latar") or ""),      # kosong = tanpa kotak di belakangnya
        "ulang": False,
    }


def siapkan_sisipan(lapisan: Optional[list], durasi: float) -> list[dict]:
    """Membersihkan daftar sisipan dan mencari berkasnya. Yang tak dikenal dibuang."""
    from . import aset as aset_svc

    keluar: list[dict] = []
    for l in lapisan or []:
        if not isinstance(l, dict):
            continue
        # Sisipan TEKS tidak punya berkas.
        #
        # Diminta pemiliknya 30 September 2026, dengan alasan yang jelas: ada
        # kampanye yang mensyaratkan tulisan tertentu muncul di klip, misalnya
        # "@motionklip" berikut logonya. Itu bukan judul klip — judul punya
        # tema, animasi, dan tempatnya sendiri di awal — melainkan tempelan
        # yang berdiri sendiri, bisa ditaruh di mana saja, selama apa saja, dan
        # bisa diatur ketembusannya seperti tempelan lain.
        if str(l.get("jenis") or "") == "teks" or (l.get("teks") and not l.get("aset")):
            satu = _siapkan_teks(l, durasi)
            if satu:
                keluar.append(satu)
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
        ulang = bool(l.get("ulang", False))
        # Panjangnya dibatasi isi berkasnya, KECUALI kalau diulang: musik satu
        # menit yang dipasang untuk klip dua menit memang dimaksudkan berputar
        # dua kali, bukan dipotong jadi satu menit.
        if info["jenis"] != "gambar" and panjang_aset > 0 and not ulang:
            dur = min(dur, max(0.05, panjang_aset - mulai))
        dur = min(dur, durasi - t)
        if dur <= 0.05:
            continue
        # Rect bebas: dipakai bila ada, kalau tidak preset lamanya (`posisi`).
        rect = l.get("rect")
        rect = rect if isinstance(rect, dict) else None
        # Isi petak: "penuh" memotong sisi yang kelebihan, "muat" memuat utuh
        # dengan ruang kosong di sisanya. Bawaannya mengikuti kebiasaan lama,
        # yaitu video memenuhi petaknya dan gambar dimuat utuh, supaya klip
        # yang sudah tersimpan tidak berubah tampilannya sendiri.
        isi = str(l.get("isi") or ("muat" if info["jenis"] == "gambar" else "penuh"))
        if isi not in ("penuh", "muat"):
            isi = "penuh"
        try:
            opasitas = max(0.0, min(1.0, float(l.get("opasitas", 1.0))))
            masuk = max(0.0, min(dur / 2, float(l.get("fade_masuk") or 0.0)))
            keluar_f = max(0.0, min(dur / 2, float(l.get("fade_keluar") or 0.0)))
        except (TypeError, ValueError):
            opasitas, masuk, keluar_f = 1.0, 0.0, 0.0
        keluar.append({
            "path": path, "jenis": info["jenis"], "punya_suara": info.get("punya_suara"),
            "t": t, "dur": dur, "mulai": mulai, "volume": vol,
            "posisi": str(l.get("posisi") or "penuh"),
            "rect": rect,
            "isi": isi,
            "opasitas": opasitas,
            "fade_masuk": masuk,
            "fade_keluar": keluar_f,
            # Berkas yang lebih pendek daripada petaknya diulang sampai penuh.
            # Berguna untuk musik latar dan cuplikan pendek yang dijadikan
            # gelang; tanpa ini sisanya senyap atau membeku.
            "ulang": ulang,
            "redam": bool(l.get("redam", False)),
        })
    return keluar


# --- Redam musik latar --------------------------------------------------------
# Seberapa dalam musik turun saat orang bicara, dan seberapa cepat ia turun dan
# naik lagi. -11 dB adalah jarak yang dipakai pembuat klip: cukup untuk kalimat
# terdengar utuh, tidak sampai membuat musiknya seperti hilang lalu muncul.
# Turunnya lebih cepat daripada naiknya, supaya kata pertama tidak tertimpa dan
# musik tidak melompat kembali di tengah napas.
REDAM_DALAM = 0.28          # 0,28 linear = -11 dB
REDAM_TURUN = 0.18          # detik
REDAM_NAIK = 0.45           # detik
REDAM_RAPAT = 0.35          # jeda sependek ini dianggap masih satu kalimat
REDAM_RENTANG_MAKS = 24     # batas panjang rumusnya


def rentang_bicara(subtitles: Optional[list[dict]],
                   rapat: float = REDAM_RAPAT) -> list[tuple[float, float]]:
    """
    Kapan saja ada orang bicara di klip ini, dari waktu tiap kata.

    Celah antar suku kata bukan kesunyian. Tanpa dirapatkan, musik akan naik
    dan turun puluhan kali dalam satu kalimat, dan itu terdengar jauh lebih
    buruk daripada musik yang tidak mengalah sama sekali.
    """
    kata: list[tuple[float, float]] = []
    for baris in (subtitles or []):
        for w in (baris.get("words") or []):
            a, b = float(w.get("s", 0.0)), float(w.get("e", 0.0))
            if b > a:
                kata.append((a, b))
        if not (baris.get("words") or []):
            a, b = float(baris.get("start", 0.0)), float(baris.get("end", 0.0))
            if b > a:
                kata.append((a, b))
    if not kata:
        return []
    kata.sort()
    gabung: list[list[float]] = [list(kata[0])]
    for a, b in kata[1:]:
        if a - gabung[-1][1] <= rapat:
            gabung[-1][1] = max(gabung[-1][1], b)
        else:
            gabung.append([a, b])
    # Rumus lavfi yang terlalu panjang dievaluasi tiap bingkai audio. Rentang
    # yang jeda-nya paling pendek digabung lebih dulu sampai jumlahnya masuk.
    while len(gabung) > REDAM_RENTANG_MAKS:
        i = min(range(len(gabung) - 1),
                key=lambda j: gabung[j + 1][0] - gabung[j][1])
        gabung[i][1] = gabung[i + 1][1]
        del gabung[i + 1]
    return [(a, b) for a, b in gabung]


def rumus_redam(bicara: list[tuple[float, float]]) -> Optional[str]:
    """
    Rumus volume yang mengecilkan musik tepat saat orang bicara.

    Dulu ini dikerjakan `sidechaincompress`, yang menebak dari kerasnya audio
    utama. Diukur pada satu klip podcast: musiknya turun 2 dB dan turun SAMA
    RATA, baik saat orang bicara maupun saat jeda — jadi fiturnya menurunkan
    musik tanpa pernah benar-benar mengalah pada kalimat. Sebabnya audio
    podcast sudah diratakan `loudnorm` sebelum sampai ke situ, jadi jeda dan
    kata sama kerasnya dan tidak ada yang bisa dideteksi.

    Waktu tiap kata sudah kita punya dari transkrip. Memakai itu berarti
    redamannya tidak menebak sama sekali: ia turun di kata yang memang ada.
    """
    if not bicara:
        return None
    a_, r_ = REDAM_TURUN, REDAM_NAIK
    # Dua kalimat yang jaraknya lebih pendek daripada waktu naik + turun tidak
    # sempat mengembalikan musik ke penuh: yang terdengar bukan musik yang
    # kembali, melainkan musik yang memompa. Digabung dulu, jadi di antara
    # keduanya musik tetap di bawah.
    rapat: list[list[float]] = []
    for a, b in sorted(bicara):
        if rapat and a - rapat[-1][1] < r_ + a_:
            rapat[-1][1] = max(rapat[-1][1], b)
        else:
            rapat.append([a, b])
    bagian = [
        f"clip((t-{max(0.0, a - a_):.3f})/{a_:.3f},0,1)"
        f"*clip(({b + r_:.3f}-t)/{r_:.3f},0,1)"
        for a, b in rapat
    ]
    puncak = bagian[0]
    for x in bagian[1:]:
        puncak = f"max({puncak},{x})"
    return f"1-{1.0 - REDAM_DALAM:.3f}*({puncak})"


def _lolos_teks(t: str) -> str:
    """Teks yang aman untuk `drawtext`: tanda yang punya arti bagi ffmpeg dikawal."""
    keluar = []
    for ch in t:
        if ch in "\\":
            keluar.append("\\\\")
        elif ch in ":'%":
            keluar.append("\\" + ch)
        elif ch == "\n":
            keluar.append("\\n")
        else:
            keluar.append(ch)
    return "".join(keluar)


def _warna_ff(warna: str, bawaan: str = "white") -> str:
    w = (warna or "").strip()
    if not w:
        return bawaan
    if w.startswith("#") and len(w) in (4, 7):
        return "0x" + (w[1:] if len(w) == 7 else "".join(c * 2 for c in w[1:]))
    return w


def _graf_teks(bagian: list[str], l: dict, video: str, i: int,
               out_w: int, out_h: int) -> str:
    """Satu `drawtext` untuk sebuah sisipan teks. Mengembalikan label barunya."""
    from .fonts import _berkas_keluarga

    t0, dur = float(l["t"]), float(l["dur"])
    t1 = t0 + dur
    tinggi = max(8, int(round(out_h * float(l.get("ukuran") or TEKS_UKURAN_BAWAAN) / 100.0)))
    x, y, w, h = petak_sisipan(l, out_w, out_h)
    # Di tengah petaknya, tapi TIDAK PERNAH keluar kanvas.
    #
    # Tulisan bisa lebih lebar daripada petaknya — "@namakanal" pada preset
    # sudut sudah cukup — dan tanpa kurungan ini ujungnya terpotong di tepi
    # layar. Terlihat pada render uji 30 September 2026. Komanya dikawal karena
    # di dalam nilai opsi `drawtext` koma memisahkan filter.
    tengah_x = f"{x}+({w}-text_w)/2"
    tengah_y = f"{y}+({h}-text_h)/2"
    px = f"max(0\\,min({out_w}-text_w\\,{tengah_x}))"
    py = f"max(0\\,min({out_h}-text_h\\,{tengah_y}))"

    # Alfa yang berubah menurut waktu: ketembusan, lembut masuk, lembut keluar,
    # ketiganya dalam satu ungkapan. Waktunya waktu KLIP, karena `drawtext`
    # menggambar di atas video yang jamnya sudah jam klip.
    op = float(l.get("opasitas", 1.0))
    fi = float(l.get("fade_masuk") or 0.0)
    fo = float(l.get("fade_keluar") or 0.0)
    alfa = f"{op:.3f}"
    if fi > 0:
        alfa = f"if(lt(t,{t0 + fi:.3f}),(t-{t0:.3f})/{fi:.3f}*{op:.3f},{alfa})"
    if fo > 0:
        alfa = f"if(gt(t,{t1 - fo:.3f}),({t1:.3f}-t)/{fo:.3f}*{op:.3f},{alfa})"

    opsi = [
        f"text='{_lolos_teks(str(l.get('teks') or ''))}'",
        f"fontsize={tinggi}",
        f"fontcolor={_warna_ff(l.get('warna'), 'white')}",
        f"x={px}", f"y={py}",
        f"alpha='{alfa}'",
        f"enable='between(t,{t0:.3f},{t1:.3f})'",
    ]
    berkas = _berkas_keluarga(str(l.get("keluarga") or ""))
    if berkas and Path(berkas).is_file():
        opsi.append(f"fontfile='{ffpath(Path(berkas))}'")
    tebal = float(l.get("tebal_garis") or 0.0)
    if tebal > 0:
        opsi.append(f"borderw={int(round(tebal))}")
        opsi.append(f"bordercolor={_warna_ff(l.get('garis'), 'black')}")
    latar = str(l.get("latar") or "").strip()
    if latar:
        opsi.append("box=1")
        opsi.append(f"boxcolor={_warna_ff(latar, 'black')}@0.55")
        opsi.append(f"boxborderw={max(4, tinggi // 5)}")
    keluar = f"[svt{i}]"
    bagian.append(f"{video}drawtext={':'.join(opsi)}{keluar}")
    return keluar


def build_sisipan_graph(lapisan: list[dict], vin: str, ain: str, *,
                        input_awal: int, out_w: int, out_h: int,
                        bicara: Optional[list[tuple[float, float]]] = None
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
        if l["jenis"] == "teks":
            # Teks digambar LANGSUNG di atas video, tanpa masukan tambahan.
            #
            # Membuatnya jadi gambar lebih dulu berarti satu proses dan satu
            # berkas sementara per tempelan, untuk hasil yang sama. `drawtext`
            # sudah bisa semuanya: font yang dibundel, garis luar, kotak latar,
            # dan alfa yang berubah menurut waktu — yang terakhir itulah yang
            # membuat lembut masuk, lembut keluar, dan ketembusan bisa
            # dinyatakan dalam satu ungkapan.
            video = _graf_teks(bagian, l, video, i, out_w, out_h)
            continue
        if l["jenis"] == "gambar":
            inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(l["path"])]
        else:
            # `-stream_loop -1` memutar berkasnya berulang, dan `-t` di
            # bawahnya yang menghentikannya. Urutannya penting: keduanya opsi
            # MASUKAN, jadi keduanya harus berdiri sebelum `-i`.
            if l.get("ulang"):
                inputs += ["-stream_loop", "-1"]
            inputs += ["-ss", f"{l['mulai']:.3f}", "-t", f"{dur:.3f}", "-i", str(l["path"])]

        if l["jenis"] in ("video", "gambar"):
            x, y, w, h = petak_sisipan(l, out_w, out_h)
            # `setpts ... +t0/TB` menggeser cuplikannya ke waktunya di klip;
            # tanpa itu overlay menempelkannya di detik nol, lalu `enable`
            # menyembunyikannya — cuplikan yang "tidak muncul" padahal ada.
            geser = f"setpts=PTS-STARTPTS+{t0:.3f}/TB"
            # Lembut masuk dan keluar, plus ketembusan. Ketiganya bekerja pada
            # SALURAN ALFA, bukan dengan menggelapkan gambarnya: sisipan yang
            # memudar harus memperlihatkan video di bawahnya, bukan berubah
            # jadi persegi hitam. Waktunya relatif terhadap awal sisipan
            # sendiri, jadi ditulis sebelum `setpts` menggesernya.
            efek = []
            if l.get("fade_masuk", 0) > 0:
                efek.append(f"fade=t=in:st=0:d={l['fade_masuk']:.3f}:alpha=1")
            if l.get("fade_keluar", 0) > 0:
                efek.append(f"fade=t=out:st={max(0.0, dur - l['fade_keluar']):.3f}:"
                            f"d={l['fade_keluar']:.3f}:alpha=1")
            if l.get("opasitas", 1.0) < 1.0:
                efek.append(f"colorchannelmixer=aa={l['opasitas']:.3f}")
            rantai = ("," + ",".join(efek)) if efek else ""

            if l.get("isi") == "muat":
                # DIMUAT utuh, bukan dipotong memenuhi petaknya: logo persegi di
                # petak 16:9 kehilangan atas-bawahnya kalau dipotong. Gambarnya
                # ditaruh di tengah petak, dan transparansi PNG ikut terbawa.
                bagian.append(
                    f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                    f"setsar=1,format=yuva420p{rantai},{geser}[sv{i}]")
                px = f"{x}+({w}-overlay_w)/2"
                py = f"{y}+({h}-overlay_h)/2"
            else:
                bagian.append(
                    f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                    f"crop={w}:{h},setsar=1,format=yuva420p{rantai},{geser}[sv{i}]")
                px, py = str(x), str(y)
            keluar = f"[svo{i}]"
            bagian.append(
                f"{video}[sv{i}]overlay=x={px}:y={py}:eof_action=pass:"
                f"enable='between(t,{t0:.3f},{t0 + dur:.3f})'{keluar}")
            video = keluar

        if l["volume"] > 0 and (l["jenis"] == "audio" or l.get("punya_suara")):
            ms = int(round(t0 * 1000))
            afade = ""
            if l.get("fade_masuk", 0) > 0:
                afade += f",afade=t=in:st=0:d={l['fade_masuk']:.3f}"
            if l.get("fade_keluar", 0) > 0:
                afade += (f",afade=t=out:st={max(0.0, dur - l['fade_keluar']):.3f}"
                          f":d={l['fade_keluar']:.3f}")
            bagian.append(
                f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
                f"asetpts=PTS-STARTPTS,volume={l['volume']:.3f}{afade},"
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
            rumus = rumus_redam(bicara or [])
            if rumus:
                # Dituntun transkrip: musik turun di kata yang memang ada.
                for j, lab in enumerate(diredam):
                    bagian.append(f"{lab}volume=volume='{rumus}':eval=frame[sd{j}]")
                    biasa.append(f"[sd{j}]")
            else:
                # Tanpa transkrip — klip permainan tanpa kata, misalnya — hanya
                # kerasnya audio utama yang bisa jadi petunjuk. Lebih lemah, dan
                # dipakai justru karena tidak ada yang lebih baik.
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


# --- Perapian suara -----------------------------------------------------------
# Tiga tingkat, dan yang kedua adalah bawaannya.
#
# "seimbang" hanya meratakan kekerasan ke -16 LUFS: aman untuk apa pun,
# termasuk musik dan suara permainan. "bersih" menambah tiga filter yang
# ditujukan pada SUARA ORANG — desis dihilangkan, gemuruh di bawah 80 Hz
# dipotong, dan jarak antara bisikan dan teriakan dirapatkan. Ketiganya membuat
# rekaman HP terdengar jauh lebih rapi, dan ketiganya juga merusak musik. Itu
# sebabnya ia pilihan, bukan bawaan.
SUARA_RANTAI = {
    "mati": "anull",
    "seimbang": "loudnorm=I=-16:TP=-1.5:LRA=11",
    "bersih": ("highpass=f=80,afftdn=nf=-25,"
               "acompressor=threshold=-18dB:ratio=3:attack=12:release=220,"
               "loudnorm=I=-16:TP=-1.5:LRA=9"),
}


def _rantai_suara() -> str:
    """Rantai filter suara menurut setelan. Salah nama = kembali ke bawaan."""
    try:
        from ..repos import settings as settings_repo
        pilihan = (settings_repo.get("render.suara") or "").strip()
    except Exception:
        pilihan = ""
    return SUARA_RANTAI.get(pilihan) or SUARA_RANTAI["seimbang"]


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


def _baris_judul_video(judul: Optional[dict], durasi_klip: float,
                       out_w: int, out_h: int) -> list[str]:
    """Baris ASS judul di dalam video, atau kosong bila tidak dinyalakan."""
    if not judul or not judul.get("aktif") or not (judul.get("teks") or "").strip():
        return []
    from .tema_judul import ass_judul
    mulai = max(0.0, float(judul.get("mulai") or 0.0))
    durasi = judul.get("durasi")
    akhir = durasi_klip if not durasi else min(durasi_klip, mulai + float(durasi))
    if akhir <= mulai:
        return []
    return ass_judul(str(judul.get("tema") or "kartu-putih"), str(judul["teks"]),
                     mulai=mulai, akhir=akhir,
                     pos_x=float(judul.get("pos_x", 50.0)), pos_y=float(judul.get("pos_y", 14.0)),
                     box_w=float(judul.get("box_w", 84.0)), ukuran=float(judul.get("ukuran", 72.0)),
                     out_w=out_w, out_h=out_h,
                     # Di atas subtitle, di bawah tanda air.
                     lapis=20)


def render_clip(
    *,
    source_video_path: str,
    segments: list[dict],
    subtitles: Optional[list[dict]] = None,
    aspect_ratio: str = "9:16",
    hook_text: str = "",
    judul_video: Optional[dict] = None,
    watermark: str = "",
    video_filter: str = "normal",
    caption_style: Optional[CaptionStyle] = None,
    frame_mode: str = "smart",
    # "smooth" = kamera mengikuti dengan mulus; "cut" = diam di dalam satu
    # bidikan lalu berpindah seketika. Keduanya sah — yang mulus terasa
    # sinematik, yang memotong terasa seperti hasil editor.
    frame_motion: str = "smooth",
    # Perbesaran dan geseran tegak bingkai wajah. zoom 1.0 dan geser 0 berarti
    # persis seperti sebelum setelan ini ada. Lihat `reframe.petak_zoom`.
    frame_zoom: float = 1.0,
    frame_geser_y: float = 0.0,
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
    # `buat=True`: di sinilah berkasnya benar-benar ditulis, jadi di sinilah
    # foldernya pantas lahir. Lihat `profil.folder_klip`.
    folder_keluar = _profil.folder_klip(_profil.kini(), buat=True)
    out_name = build_clip_filename(
        title=title or vid,
        index=clip_index,
        start=float(first["start"]),
        existing=folder_keluar,
    )
    out_path = folder_keluar / out_name

    workdir = Path(tempfile.mkdtemp(prefix="omniclip_render_"))
    try:
        # Laju bingkai keluaran, ditentukan SEKALI di sini lalu dipakai semua
        # tahap: pemotongan, linimasa bingkai, dan pengode. Tiga tempat yang
        # dulu masing-masing menulis 30 sendiri.
        from .media import probe as _probe_laju
        try:
            _fps_sumber = float((_probe_laju(src) or {}).get("fps") or 0) or None
        except Exception:                                # noqa: BLE001
            _fps_sumber = None
        fps_keluar = laju_render(_fps_sumber)
        log.info("Laju bingkai render: %s fps (sumber %s)", fps_keluar,
                 f"{_fps_sumber:.0f}" if _fps_sumber else "tidak terbaca")

        inputs, seg_graph, labels = _build_segment_graph(segments, fps_keluar)
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
                plan_gerak=kunci_plan_gerak,
                frame_zoom=frame_zoom, frame_geser_y=frame_geser_y,
                fps=fps_keluar)
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
                log.info("Facecam tidak ditemukan, mode gaming jatuh ke smart")
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
                    log.info("Wajah tidak terlacak, bingkai pengikut memakai "
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
                from .reframe import petak_zoom
                zw, zh, zy = petak_zoom(plan, frame_zoom, frame_geser_y)
                chain.append(build_reframe_filter(
                    plan, workdir / "reframe.cmd", out_w, out_h,
                    crop_w=zw, crop_h=zh, crop_y=zy))
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

        # Subtitle yang SUDAH terbakar di gambar sumber, mis. anime fansub.
        #
        # Kalau ada, subtitle OmniClip dinaikkan sampai di atasnya. Dulu
        # keduanya bertumpuk dan dua-duanya tidak terbaca, dan satu-satunya
        # jalan keluar adalah pemiliknya menyadarinya sendiri lalu menaikkan
        # subtitle dengan tangan, satu klip demi satu klip.
        try:
            from .teks_tertanam import batas_atas
            awal = float((segments or [{}])[0].get("start") or 0.0)
            atas = batas_atas(source_video_path, awal, min(45.0, total_duration or 30.0))
        except Exception as e:                # deteksi bukan alasan render gagal
            log.warning("Teks tertanam dilewati: %s", str(e)[:160])
            atas = None
        if atas is not None and style_for_render.position != "top":
            # `margin_v` dihitung dari BAWAH kanvas, dan potongan 9:16 dari
            # sumber 16:9 mempertahankan tingginya, jadi persennya berpindah
            # apa adanya. Ditambah sedikit jarak supaya keduanya tidak bersisian.
            perlu = int(round((100.0 - atas) / 100.0 * 1920)) + 40
            if perlu > style_for_render.margin_v:
                log.info("Subtitle dinaikkan ke %d (ada teks tertanam mulai %.0f%%)",
                         perlu, atas)
                style_for_render = replace(style_for_render, margin_v=perlu)

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
        judul_baris = _baris_judul_video(judul_video, total_duration, out_w, out_h)
        if ada_teks or kedua_lines or hook_text.strip() or watermark.strip() or judul_baris:
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
                    tambahan=judul_baris,
                    # Sakelar sensor kata kasar, milik seluruh aplikasi.
                    # Dibaca DI SINI, bukan dititipkan lewat gaya subtitle:
                    # gaya itu tersimpan per klip, dan sakelar yang diubah hari
                    # ini tidak boleh dikalahkan oleh gaya yang disimpan bulan
                    # lalu.
                    sensor=sensor_aktif(),
                ),
                encoding="utf-8",
            )
            ass_arg = ffpath(ass_path)
            fonts = ffpath(dir_font()) if FONTS_DIR.is_dir() else None
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
                out_w=out_w, out_h=out_h, bicara=rentang_bicara(subtitles))
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
            graph += f";{alabel}{_rantai_suara()}[aout]"
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
            fonts_dir = ffpath(dir_font()) if FONTS_DIR.is_dir() else None
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
                    # Keyframe tiap dua detik, apa pun lajunya.
                    "-r", str(fps_keluar), "-g", str(fps_keluar * 2),
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
            # Identitas video sumbernya, ditulis di sini juga dan bukan hanya
            # diturunkan dari tabel `videos` saat diperlukan. Klip jadi bisa
            # hidup lebih lama daripada baris sumbernya, dan kredit di deskripsi
            # unggahan tidak boleh ikut hilang bersama baris itu (JOB-2 F0-1).
            "sumber": _sumber_klip(vid),
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


def _sumber_klip(video_id) -> dict:
    """Identitas video sumber untuk sidecar; kosong bila tidak terbaca."""
    try:
        from ..repos.media import sumber_video
        return sumber_video(str(video_id or ""))
    except Exception:                                # noqa: BLE001
        return {}


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
