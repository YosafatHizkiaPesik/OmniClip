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

# Laju sampling deteksi. 6 Hz memberi sinyal yang cukup rapat untuk difilter
# tanpa membuat perencanaan terasa lama (klip 45 detik ~ 270 frame, ~3 detik).
SAMPLE_FPS = 6.0
SAMPLE_WIDTH = 480

# Laju perintah yang ditulis ke sendcmd. 25 Hz melampaui laju frame video,
# sehingga crop tidak pernah "menunggu" perintah berikutnya. Pada 10 Hz,
# perubahan posisi datang tiap 3 frame dan itu terlihat sebagai getar halus.
COMMAND_HZ = 25.0

# Ambang di bawah ini artinya rekaman bukan wajah bicara (gameplay, screencast,
# slide). Memaksa face-tracking di situ menghasilkan crop yang meloncat-loncat;
# blur-pad adalah jawaban yang benar.
MIN_FACE_COVERAGE = 0.20

DETECT_SCORE = 0.6
DETECT_NMS = 0.3

# Konstanta penghalusan, semuanya relatif terhadap lebar sumber.
DEADZONE_RATIO = 0.055     # abaikan goyangan di bawah 5,5% lebar
EMA_ALPHA = 0.12           # per sampel pada 6 Hz; dijalankan dua arah
MAX_SPEED_RATIO = 0.10     # plafon kecepatan pan, lebar-per-detik
SCENE_CUT_DISTANCE = 0.5   # jarak Bhattacharyya histogram HSV
MEDIAN_WINDOW = 5          # buang deteksi meleset sesaat sebelum difilter


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


def _median(values: list[float], window: int) -> list[float]:
    """Median bergerak — membuang deteksi yang meleset satu-dua frame."""
    if window < 3 or len(values) < window:
        return list(values)
    half = window // 2
    out = []
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        chunk = sorted(values[lo:hi])
        out.append(chunk[len(chunk) // 2])
    return out


def _ema_zero_phase(values: list[float], alpha: float) -> list[float]:
    """
    EMA maju lalu mundur.

    EMA satu arah selalu tertinggal di belakang sinyalnya, dan pada gerakan
    kamera itu terlihat sebagai crop yang "mengejar" kepala pembicara. Menjalankan
    filter yang sama ke arah sebaliknya membatalkan pergeseran fasa itu: hasilnya
    halus TAPI tetap sejajar waktu dengan gerakan aslinya.
    """
    if not values:
        return []
    forward = []
    acc = values[0]
    for v in values:
        acc += alpha * (v - acc)
        forward.append(acc)
    backward = [0.0] * len(forward)
    acc = forward[-1]
    for i in range(len(forward) - 1, -1, -1):
        acc += alpha * (forward[i] - acc)
        backward[i] = acc
    return backward


def _apply_deadzone(values: list[float], deadzone: float) -> list[float]:
    """
    Menahan target selama pembicara hanya bergoyang kecil.

    Dijalankan SEBELUM penghalusan, bukan sesudah: kalau sesudah, hasilnya
    berupa tangga yang justru harus dihaluskan lagi. Di sini deadzone hanya
    membentuk sinyal niat — filter berikutnya yang membuat perpindahannya mulus.
    """
    if not values:
        return []
    out = [values[0]]
    held = values[0]
    for v in values[1:]:
        if abs(v - held) > deadzone:
            held = v
        out.append(held)
    return out


def _smooth(centers: list[Optional[float]], cuts: list[bool], *,
            source_w: int, crop_w: int) -> list[float]:
    """
    Mengubah jejak wajah mentah menjadi gerakan kamera yang enak dilihat.

    Rantainya: tahan-saat-hilang -> median -> deadzone -> EMA dua arah ->
    plafon kecepatan. Tiap potongan adegan difilter SENDIRI-SENDIRI, karena
    menghaluskan melewati potongan adegan berarti kamera akan mem-pan
    menyeberangi pergantian kamera — persis yang membuat hasilnya terlihat
    seperti melayang, bukan berpindah.
    """
    if not centers:
        return []

    half = crop_w / 2.0
    lo, hi = half, source_w - half
    deadzone = DEADZONE_RATIO * source_w
    max_step = (MAX_SPEED_RATIO * source_w) / SAMPLE_FPS

    # Isi sampel tanpa wajah dengan nilai terakhir yang diketahui, lalu mundur
    # untuk sampel awal yang belum pernah melihat wajah.
    filled: list[float] = []
    last = next((c for c in centers if c is not None), source_w / 2.0)
    for c in centers:
        if c is not None:
            last = c
        filled.append(last)

    # Pecah menjadi rentang antar potongan adegan.
    bounds = [i for i, is_cut in enumerate(cuts) if is_cut and i > 0]
    runs: list[tuple[int, int]] = []
    prev = 0
    for b in bounds:
        runs.append((prev, b))
        prev = b
    runs.append((prev, len(filled)))

    out: list[float] = []
    for a, b in runs:
        chunk = filled[a:b]
        if not chunk:
            continue
        chunk = [min(max(v, lo), hi) for v in chunk]
        chunk = _median(chunk, MEDIAN_WINDOW)
        chunk = _apply_deadzone(chunk, deadzone)
        chunk = _ema_zero_phase(chunk, EMA_ALPHA)

        # Plafon kecepatan terakhir, supaya perpindahan besar tetap terbaca
        # sebagai gerakan kamera dan bukan lompatan.
        limited = [chunk[0]]
        for v in chunk[1:]:
            prev_v = limited[-1]
            step = max(-max_step, min(max_step, v - prev_v))
            limited.append(prev_v + step)
        out.extend(min(max(v, lo), hi) for v in limited)

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

    # Naikkan dari laju sampling ke laju perintah memakai spline Catmull-Rom.
    # Interpolasi linear melewati titik kontrol dengan pergantian arah mendadak,
    # dan pada gerakan kamera patahan itu terlihat sebagai sentakan kecil tiap
    # kali sampel baru datang. Catmull-Rom melewati setiap titik dengan tangen
    # yang bersambung, jadi kecepatannya ikut mulus — bukan hanya posisinya.
    half = crop_w / 2.0
    max_x = source_w - crop_w
    step = 1.0 / COMMAND_HZ
    total = (len(smoothed) - 1) / SAMPLE_FPS
    n = len(smoothed)

    def at(idx: int) -> float:
        return smoothed[min(max(idx, 0), n - 1)]

    keyframes: list[tuple[float, int]] = []
    last_x = None
    t = 0.0
    while t <= total + 1e-9:
        pos = t * SAMPLE_FPS
        i = int(math.floor(pos))
        u = pos - i
        p0, p1, p2, p3 = at(i - 1), at(i), at(i + 1), at(i + 2)
        cx = 0.5 * (
            (2 * p1)
            + (-p0 + p2) * u
            + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
            + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u
        )
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
