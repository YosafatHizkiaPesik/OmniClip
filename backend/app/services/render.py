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
from .paths import extract_id_from_filename
from .reframe import build_reframe_filter, plan_reframe
from .subtitles import CaptionStyle, HookSpec, build_ass

log = logging.getLogger("omniclip.render")

# Preroll untuk dual-seek: `-ss` besar sebelum `-i` (cepat, menempel keyframe),
# lalu `-ss` kecil sesudah `-i` (akurat ke frame).
PREROLL = 5.0

ASPECT_FILTERS = {
    "9:16": (
        "split[bgsrc][fgsrc];"
        "[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=28:6[bg];"
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

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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

        parts.append(
            f"[{i}:v]trim=start={pre:.3f}:duration={dur:.3f},setpts=PTS-STARTPTS[v{i}]"
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
                       plan=None, workdir=None) -> str:
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

    parts: list[str] = []
    n = len(frames)
    # Satu cabang per bingkai, plus satu untuk latar.
    parts.append(f"{in_label}split={n + 1}" + "".join(f"[lsrc{i}]" for i in range(n + 1)))

    bg = "[lbg]"
    if layout.get("background") == "black":
        # Sumber latar tetap dipakai supaya panjang dan laju frame-nya persis
        # sama dengan bingkainya; `drawbox` mengecatnya hitam penuh.
        parts.append(
            f"[lsrc{n}]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},drawbox=x=0:y=0:w={out_w}:h={out_h}:color=black:t=fill,"
            f"setsar=1[lbg]"
        )
    else:
        parts.append(
            f"[lsrc{n}]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},boxblur=28:6,setsar=1[lbg]"
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
            crop = build_reframe_filter(
                plan, workdir / f"reframe_{i}.cmd", out_w, out_h,
                name=f"lf{i}", crop_w=sw, crop_h=sh, crop_y=sy, scale=False)
            parts.append(f"[lsrc{i}]{crop},{place},setsar=1[lf{i}]")
        else:
            parts.append(f"[lsrc{i}]crop={sw}:{sh}:{sx}:{sy},{place},setsar=1[lf{i}]")

    # Ditumpuk berurutan: bingkai terakhir di daftar tergambar paling atas,
    # sama seperti urutan yang ditampilkan panelnya.
    prev = bg
    for i in range(n):
        nxt = f"[lo{i}]" if i < n - 1 else out_label
        sx, sy, sw, sh = _pct_rect(frames[i].get("dst") or {}, out_w, out_h)
        parts.append(f"{prev}[lf{i}]overlay={sx}:{sy}:shortest=0{nxt}")
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
    frame_layout: Optional[dict] = None,
    loudnorm: bool = True,
    video_id: str = "",
    title: str = "",
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
    out_name = build_clip_filename(
        title=title or vid,
        index=clip_index,
        start=float(first["start"]),
        existing=CLIPS_DIR,
    )
    out_path = CLIPS_DIR / out_name

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
        if frame_mode == "layout" and frame_layout and frame_layout.get("frames"):
            from .media import probe as _probe
            info = _probe(src)
            layout_frames = frame_layout.get("frames") or []

            # Jejak wajah disusun SEKALI dan dipakai bersama semua bingkai yang
            # mengikutinya: mereka mengikuti orang yang sama, jadi menjalankan
            # deteksi dua kali hanya menghabiskan waktu untuk hasil yang sama.
            layout_plan = None
            if any(f.get("follow") for f in layout_frames):
                layout_plan = plan_reframe(str(src), segments,
                                           aspect_ratio=aspect_ratio, track_only=True)
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
                frame_used = "layout"

        if frame_mode == "smart":
            plan = plan_reframe(str(src), segments, aspect_ratio=aspect_ratio)
            if plan is not None:
                face_coverage = plan.face_coverage
            if plan is not None and plan.usable:
                chain.append(build_reframe_filter(
                    plan, workdir / "reframe.cmd", out_w, out_h))
                frame_used = "smart"

        if frame_used not in ("smart", "original", "layout"):
            table = CENTER_FILTERS if frame_used == "center" else ASPECT_FILTERS
            aspect = table.get(aspect_ratio)
            if aspect:
                chain.append(aspect)

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

        ass_path = None
        if (subtitles and any((l.get("text") or "").strip() for l in subtitles)) \
                or hook_text.strip() or watermark.strip():
            ass_path = workdir / "captions.ass"
            ass_path.write_text(
                build_ass(
                    lines=subtitles or [],
                    style=style_for_render,
                    hook=HookSpec(text=hook_text) if hook_text.strip() else None,
                    watermark=watermark,
                    play_res=(out_w, out_h),
                    clip_duration=total_duration,
                ),
                encoding="utf-8",
            )
            ass_arg = str(ass_path).replace("\\", "/").replace(":", r"\:")
            fonts = str(FONTS_DIR) if FONTS_DIR.is_dir() else None
            chain.append(f"ass=filename='{ass_arg}'" + (f":fontsdir='{fonts}'" if fonts else ""))

        graph = seg_graph
        if layout_graph:
            graph += ";" + layout_graph
            vlabel = "[vlay]"
        if chain:
            graph += f";{vlabel}" + ",".join(chain) + "[vout]"
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

        cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-loglevel", "error",
               "-progress", "pipe:1", *inputs,
               "-filter_complex", graph,
               "-map", vout, "-map", aout]

        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
            "-r", "30", "-g", "60", "-threads", "4",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart",
            str(out_path),
        ]

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
            "created_at": time.time(),
        }
        (CLIPS_DIR / out_name.replace(".mp4", ".json")).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return {
            "success": True,
            "clip_path": str(out_path),
            "clip_name": out_name,
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


def list_local_clips() -> list[dict]:
    """Klip hasil render beserta metadata sidecar-nya."""
    clips: list[dict] = []
    if not CLIPS_DIR.is_dir():
        return clips

    for path in CLIPS_DIR.glob("*.mp4"):
        stat = path.stat()
        entry = {
            "file_name": path.name,
            "file_size": stat.st_size,
            "created_at": stat.st_mtime,
            "metadata": None,
        }
        sidecar = path.with_suffix(".json")
        if sidecar.is_file():
            try:
                entry["metadata"] = json.loads(sidecar.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        clips.append(entry)

    clips.sort(key=lambda c: c["created_at"], reverse=True)
    return clips
