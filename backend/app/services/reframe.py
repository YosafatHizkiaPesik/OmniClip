"""
Smart reframe: mengikuti wajah pembicara saat memotong 16:9 menjadi 9:16.

Tanpa ini, memotong bagian tengah frame podcast dua orang menghasilkan klip
yang memotong kepala pembicara persis saat ia paling bersemangat. Jalur blur-pad
memang aman, tapi menyisakan dua bilah kabur yang memakan setengah layar.

Detektor: YuNet (ONNX 232 KB) lewat cv2.FaceDetectorYN. Haar frontal meleset
saat kepala menoleh ~30 derajat — dan itu justru posisi paling sering di
podcast. MediaPipe ditolak karena 40 MB plus rantai protobuf, terlalu berat
untuk mesin dengan RAM 2,9 GB.

Hasilnya dituangkan ke file `sendcmd` yang menggerakkan instance `crop@reframe`
bernama, bukan ekspresi `if()` bersarang: klip 45 detik pada 10 Hz berarti 450
cabang bersarang di parser rekursif ffmpeg — rapuh dan lambat.
"""

import logging
import math
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..config import MODELS_DIR

log = logging.getLogger("omniclip.reframe")

MODEL_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"

# Laju sampling deteksi. 4 Hz cukup: kepala manusia tidak berpindah posisi
# horizontal secara berarti dalam 250 ms, dan ini menjaga klip 45 detik tetap
# di bawah 2 detik pemrosesan.
SAMPLE_FPS = 4.0
SAMPLE_WIDTH = 480

# Laju perintah yang ditulis ke sendcmd. Lebih rapat dari sampling supaya
# gerakan crop terbaca mulus, bukan meloncat tiap 250 ms.
COMMAND_HZ = 10.0

# Ambang di bawah ini artinya rekaman bukan wajah bicara (gameplay, screencast,
# slide). Memaksa face-tracking di situ menghasilkan crop yang meloncat-loncat;
# blur-pad adalah jawaban yang benar.
MIN_FACE_COVERAGE = 0.20

DETECT_SCORE = 0.6
DETECT_NMS = 0.3

# Konstanta penghalusan, semuanya relatif terhadap lebar sumber.
DEADZONE_RATIO = 0.055     # abaikan goyangan di bawah 5,5% lebar
EMA_ALPHA = 0.15           # pada 4 Hz setara konstanta waktu ~1 detik
MAX_SPEED_RATIO = 0.09     # plafon kecepatan pan, lebar-per-detik
SCENE_CUT_DISTANCE = 0.5   # jarak Bhattacharyya histogram HSV


@dataclass
class ReframePlan:
    """Rencana crop yang bergerak, siap ditulis sebagai file sendcmd."""
    crop_w: int
    crop_h: int
    source_w: int
    source_h: int
    face_coverage: float
    keyframes: list[tuple[float, int]] = field(default_factory=list)  # (waktu, x)

    @property
    def usable(self) -> bool:
        return self.face_coverage >= MIN_FACE_COVERAGE and len(self.keyframes) > 1

    def to_sendcmd(self) -> str:
        return "\n".join(f"{t:.3f} crop@reframe x {x};" for t, x in self.keyframes) + "\n"


def _even(value: float) -> int:
    """x264 menolak dimensi ganjil pada yuv420p."""
    return max(2, int(round(value / 2)) * 2)


def _sample_frames(src: Path, start: float, duration: float,
                   width: int, height: int):
    """
    Membaca frame BGR mentah dari ffmpeg.

    cv2.VideoCapture sengaja dihindari: `set(CAP_PROP_POS_FRAMES)` lambat dan
    tidak andal pada H.264 panjang, sementara di sini kita justru perlu melompat
    ke menit ke-50 dengan cepat.
    """
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
           "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(src),
           "-vf", f"fps={SAMPLE_FPS},scale={width}:{height}",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    frame_bytes = width * height * 3
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if not buf or len(buf) < frame_bytes:
                break
            yield buf
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if proc.stdout:
            proc.stdout.close()


def _detect_centers(src: Path, segments: list[dict],
                    source_w: int, source_h: int) -> tuple[list[Optional[float]], list[bool]]:
    """
    Menjejak pusat wajah utama pada seluruh segmen, dalam koordinat sumber.

    Mengembalikan (pusat_x per sampel, penanda potongan-adegan per sampel).
    Nilai None berarti tidak ada wajah terdeteksi pada sampel itu.
    """
    import cv2
    import numpy as np

    sw = SAMPLE_WIDTH
    sh = _even(SAMPLE_WIDTH * source_h / source_w)
    scale_back = source_w / sw

    detector = cv2.FaceDetectorYN.create(
        str(MODEL_PATH), "", (sw, sh), DETECT_SCORE, DETECT_NMS, 5000
    )

    centers: list[Optional[float]] = []
    cuts: list[bool] = []
    prev_center: Optional[float] = None
    prev_hist = None

    for seg in segments:
        start = float(seg["start"])
        duration = max(0.05, float(seg["end"]) - start)
        # Potongan adegan selalu ditandai di sambungan antar segmen: menit 10
        # dan menit 50 adalah adegan berbeda, crop tidak boleh mem-pan ke sana.
        first_of_segment = True

        for buf in _sample_frames(src, start, duration, sw, sh):
            frame = np.frombuffer(buf, dtype=np.uint8).reshape((sh, sw, 3))

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
            cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
            is_cut = first_of_segment
            if prev_hist is not None and not first_of_segment:
                dist = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
                is_cut = dist > SCENE_CUT_DISTANCE
            prev_hist = hist
            first_of_segment = False

            _, faces = detector.detect(frame)
            best = None
            if faces is not None and len(faces):
                best_score = -1e9
                for f in faces:
                    x, y, w, h = float(f[0]), float(f[1]), float(f[2]), float(f[3])
                    cx = x + w / 2.0
                    area = (w * h) / (sw * sh)
                    # Suku kontinuitas inilah yang mencegah crop melompat bolak-balik
                    # antara dua narasumber setiap kali wajah yang lebih kecil
                    # kebetulan lebih terang.
                    penalty = 0.0
                    if prev_center is not None and not is_cut:
                        penalty = 0.6 * abs(cx - prev_center / scale_back) / sw
                    score = area - penalty
                    if score > best_score:
                        best_score = score
                        best = cx
            if best is not None:
                prev_center = best * scale_back
                centers.append(prev_center)
            else:
                centers.append(None)
            cuts.append(is_cut)

    return centers, cuts


def _smooth(centers: list[Optional[float]], cuts: list[bool], *,
            source_w: int, crop_w: int) -> list[float]:
    """
    Menghaluskan jejak wajah menjadi gerakan kamera yang terbaca terkunci.

    Urutan deadzone-lalu-EMA adalah kuncinya: EMA murni terus merayap ke arah
    target dan terbaca sebagai kamera yang hanyut. Deadzone membuat crop DIAM
    selama pembicara hanya bergoyang sedikit — itulah yang membedakan hasil yang
    terlihat sengaja dari yang terlihat gemetar.
    """
    deadzone = DEADZONE_RATIO * source_w
    max_step = (MAX_SPEED_RATIO * source_w) / SAMPLE_FPS
    half = crop_w / 2.0
    lo, hi = half, source_w - half

    # Titik netral bila wajah belum pernah terlihat.
    current = source_w / 2.0
    last_seen = next((c for c in centers if c is not None), None)
    if last_seen is not None:
        current = min(max(last_seen, lo), hi)

    out: list[float] = []
    for center, is_cut in zip(centers, cuts):
        if center is None:
            out.append(current)   # wajah hilang sesaat: tahan posisi
            continue
        target = min(max(center, lo), hi)
        if is_cut:
            current = target      # snap: jangan mem-pan menyeberangi potongan adegan
        elif abs(target - current) > deadzone:
            step = EMA_ALPHA * (target - current)
            current += max(-max_step, min(max_step, step))
        out.append(current)
    return out


def plan_reframe(source_video_path: str, segments: list[dict], *,
                 aspect_ratio: str = "9:16") -> Optional[ReframePlan]:
    """
    Menyusun rencana crop yang mengikuti pembicara.

    Mengembalikan None bila reframe tidak layak dipakai — model tidak ada,
    OpenCV tidak terpasang, sumber sudah lebih sempit dari target, atau wajah
    terlalu jarang terlihat. Pemanggil lalu memakai jalur blur-pad.
    """
    target = {"9:16": 9 / 16, "1:1": 1.0, "4:5": 4 / 5}.get(aspect_ratio)
    if target is None:
        return None
    if not MODEL_PATH.is_file():
        log.info("Model YuNet tidak ada di %s — reframe dilewati", MODEL_PATH)
        return None

    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        log.info("opencv/numpy tidak terpasang — reframe dilewati")
        return None

    src = Path(source_video_path)
    if not src.is_file():
        return None

    from .media import probe
    info = probe(src)
    source_w, source_h = info.get("width") or 0, info.get("height") or 0
    if not source_w or not source_h:
        return None

    crop_w = _even(source_h * target)
    crop_h = _even(source_h)
    if crop_w >= source_w:
        # Sumber sudah sama sempit atau lebih sempit dari target: tidak ada yang
        # bisa digeser.
        return None

    try:
        centers, cuts = _detect_centers(src, segments, source_w, source_h)
    except Exception as e:  # deteksi tidak boleh menjatuhkan render
        log.warning("Deteksi wajah gagal, memakai blur-pad: %s", e)
        return None

    if not centers:
        return None

    coverage = sum(1 for c in centers if c is not None) / len(centers)
    smoothed = _smooth(centers, cuts, source_w=source_w, crop_w=crop_w)

    plan = ReframePlan(crop_w=crop_w, crop_h=crop_h, source_w=source_w,
                       source_h=source_h, face_coverage=round(coverage, 3))
    if coverage < MIN_FACE_COVERAGE:
        log.info("Wajah hanya terlihat di %.0f%% frame — memakai blur-pad", coverage * 100)
        return plan  # usable == False; pemanggil membaca face_coverage untuk log

    # Interpolasi dari laju sampling ke laju perintah supaya gerakannya mulus.
    half = crop_w / 2.0
    max_x = source_w - crop_w
    step = 1.0 / COMMAND_HZ
    total = len(smoothed) / SAMPLE_FPS
    keyframes: list[tuple[float, int]] = []
    last_x = None
    t = 0.0
    while t <= total:
        pos = t * SAMPLE_FPS
        i = int(math.floor(pos))
        frac = pos - i
        a = smoothed[min(i, len(smoothed) - 1)]
        b = smoothed[min(i + 1, len(smoothed) - 1)]
        cx = a + (b - a) * frac
        x = int(round(min(max(cx - half, 0.0), max_x)))
        # Hanya tulis perintah bila nilainya berubah: file jadi jauh lebih kecil
        # dan ffmpeg tidak memproses ribuan perintah tak berguna.
        if x != last_x:
            keyframes.append((round(t, 3), x))
            last_x = x
        t += step

    if not keyframes:
        keyframes = [(0.0, int(round(min(max(smoothed[0] - half, 0.0), max_x))))]
    plan.keyframes = keyframes
    log.info("Reframe siap: crop %dx%d, wajah terlihat %.0f%%, %d titik perintah",
             crop_w, crop_h, coverage * 100, len(keyframes))
    return plan


def build_reframe_filter(plan: ReframePlan, cmd_path: Path,
                         out_w: int, out_h: int) -> str:
    """Potongan filtergraph yang menerapkan rencana crop lalu menskalakan."""
    cmd_path.write_text(plan.to_sendcmd(), encoding="utf-8")
    arg = str(cmd_path).replace("\\", "/").replace(":", r"\:")
    return (
        f"sendcmd=f='{arg}',"
        f"crop@reframe=w={plan.crop_w}:h={plan.crop_h}:x={plan.keyframes[0][1]}:y=0,"
        f"scale={out_w}:{out_h}:flags=lanczos,setsar=1"
    )
