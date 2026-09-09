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
SAMPLE_FPS = 8.0
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

# --- Siapa yang sedang bicara -------------------------------------------------
# Wajah terbesar bukan wajah yang bicara. Pada meja podcast berisi lima orang,
# memilih berdasarkan luas berarti crop terkunci pada orang yang kebetulan
# duduk paling dekat kamera dan bertahan di situ sepanjang klip — termasuk
# selama menit-menit ketika yang bicara orang lain.
#
# Isyarat yang dipakai: gerakan di daerah MULUT. Mulut yang bicara berubah dari
# frame ke frame; mulut yang diam tidak. Isyarat ini murah (satu petak kecil
# per wajah per sampel), tidak butuh model tambahan, dan tidak bergantung pada
# suara — jadi ia tetap bekerja pada video yang belum ditranskripsi.
MOUTH_PATCH = (24, 16)      # petak mulut dinormalkan ke ukuran ini
# Ukuran petak mulut. Saya sempat melebarkannya jadi 0,78 x 0,46 supaya ia
# memuat rahang — alasannya masuk akal, karena mikrofon podcast sering menutupi
# bibir dan rahang tetap bergerak. Diukur, hasilnya menukar satu hal dengan hal
# lain: kemurnian naik ke 99,6% tapi klip berisi LIMA orang berhenti membedakan
# penuturnya. Petak yang lebar ikut menangkap gerakan tetangga sebelahnya, dan
# di meja panjang tetangga itu duduk rapat. Angka yang lebih sempit menang di
# tempat yang paling sulit, jadi angka itu yang dipakai.
MOUTH_W_RATIO = 0.55        # lebar petak relatif lebar wajah
MOUTH_H_RATIO = 0.30
# Jendela rata-rata gerakan mulut. 0,75 detik cukup panjang untuk menjembatani
# jeda antar suku kata, cukup pendek untuk menyusul pergantian giliran.
MOUTH_SMOOTH_SECONDS = 0.75
# Penantang harus SEKIAN KALI lebih aktif dari yang sedang dipegang sebelum
# crop berpindah. Tanpa ambang ini, dua orang yang sama-sama sedikit bergerak
# membuat crop bolak-balik tiap sampel.
SPEAKER_SWITCH_RATIO = 1.6
# Di bawah ini tidak ada yang dianggap sedang bicara, dan pilihan jatuh kembali
# ke wajah terbesar yang paling dekat dengan posisi sebelumnya.
# Diukur pada rekaman meja dua sampai lima orang: selisih mulut-dikurangi-dahi
# untuk orang yang diam berkisar di sekitar nol (kadang sedikit negatif), dan
# naik jelas di atasnya saat orang bicara. Ambangnya diletakkan di atas derau
# itu, bukan di nol.
MOUTH_MIN_ENERGY = 0.02
# Jarak maksimum (relatif lebar sampel) untuk menganggap dua deteksi di frame
# berurutan sebagai orang yang sama.
TRACK_MAX_DIST = 0.09
TRACK_MAX_MISSES = 6        # jejak dilupakan setelah sekian sampel tanpa deteksi

# Kapan gerakan mulut BOLEH ikut menentukan.
#
# Video yang dipotong rapi sudah menjawab pertanyaannya sendiri: saat A bicara,
# penyunting memotong ke close-up A, dan wajah terbesar memang pembicaranya.
# Di situ, memaksakan pilihan berdasarkan gerakan mulut justru melawan pilihan
# penyuntingnya — saya mengukurnya, dan hasilnya lebih buruk daripada sekadar
# memilih wajah terbesar.
#
# Yang tidak terjawab adalah bidikan lebar berisi beberapa orang yang sama
# besarnya, di mana kamera tidak pernah berpindah. Di situlah crop selama ini
# terkunci pada orang yang kebetulan paling dekat kamera meski yang bicara
# orang lain.
#
# Ambang ini memisahkan keduanya: bila wajah terbesar kedua masih sebesar ini
# terhadap yang terbesar, bidikannya lebar dan pertanyaannya belum terjawab.
WIDE_SHOT_AREA_RATIO = 0.55

# Konstanta penghalusan, semuanya relatif terhadap lebar sumber.
DEADZONE_RATIO = 0.055     # abaikan goyangan di bawah 5,5% lebar
EMA_ALPHA = 0.12           # per sampel pada 8 Hz; dijalankan dua arah, dua kali
EMA_PASSES = 2             # dua lintasan = filter orde-4, riak sisa jauh lebih kecil
MAX_SPEED_RATIO = 0.10     # plafon kecepatan pan, lebar-per-detik
SCENE_CUT_DISTANCE = 0.5   # jarak Bhattacharyya histogram HSV
MEDIAN_WINDOW = 7          # buang deteksi meleset sesaat sebelum difilter


@dataclass
class ReframePlan:
    """Rencana crop yang bergerak, siap ditulis sebagai file sendcmd."""
    crop_w: int
    crop_h: int
    source_w: int
    source_h: int
    face_coverage: float
    keyframes: list[tuple[float, int]] = field(default_factory=list)  # (waktu, x)
    # Titik TENGAH wajah sepanjang waktu, sebelum diubah jadi posisi kiri crop.
    #
    # Disimpan terpisah karena satu jejak wajah yang sama harus melayani
    # beberapa jendela crop dengan lebar berbeda: satu bingkai reaksi selebar
    # 30% dan satu bingkai utama selebar 60% mengikuti orang yang sama, dan
    # keduanya harus bergerak seiring. Menyimpan hanya `keyframes` mengunci
    # jejaknya pada satu lebar.
    centers: list[tuple[float, float]] = field(default_factory=list)
    # Satu jejak per ORANG di layar, urut kiri ke kanan, pada laju sampel.
    # Dipakai bingkai yang diminta membuntuti orang tertentu: pengguna menaruh
    # kotaknya di atas seseorang, dan bingkainya mengikuti orang ITU — bukan
    # siapa pun yang kebetulan wajahnya terbesar.
    people: list[list[Optional[float]]] = field(default_factory=list)
    # Gerakan mulut tiap orang, sejajar dengan `people`. Dipakai untuk
    # mencocokkan wajah dengan penutur hasil diarisasi.
    people_motion: list[list[float]] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.face_coverage >= MIN_FACE_COVERAGE and len(self.keyframes) > 1

    def person_series(self, index: int) -> list[tuple[float, float]]:
        """Jejak satu orang sebagai (detik, pusat_x), celah diisi nilai terakhir."""
        if not (0 <= index < len(self.people)):
            return []
        out: list[tuple[float, float]] = []
        last: Optional[float] = None
        for i, v in enumerate(self.people[index]):
            if v is not None:
                last = v
            if last is not None:
                out.append((i / SAMPLE_FPS, last))
        return out

    def person_near(self, x_pct: float) -> Optional[int]:
        """
        Orang yang paling dekat dengan satu posisi mendatar (persen lebar).

        Inilah cara pengguna menunjuk: ia menaruh kotak bingkainya di atas
        seseorang, dan yang dipilih adalah orang yang rata-rata posisinya paling
        dekat dengan kotak itu. Tidak ada tebakan tentang siapa yang bicara —
        hanya siapa yang duduk di situ.
        """
        if not self.people or not self.source_w:
            return None
        target = (x_pct / 100.0) * self.source_w
        best, best_d = None, None
        for i in range(len(self.people)):
            seen = [v for v in self.people[i] if v is not None]
            if not seen:
                continue
            mean = sum(seen) / len(seen)
            d = abs(mean - target)
            if best_d is None or d < best_d:
                best, best_d = i, d
        return best

    def x_track(self, crop_w: int, person: Optional[int] = None) -> list[tuple[float, int]]:
        """
        Jejak wajah -> posisi tepi kiri crop selebar `crop_w`.

        `person` memilih jejak satu orang tertentu, bukan jejak wajah utama.
        Rumus yang sama dipakai pratinjau di browser, dari data yang sama, jadi
        yang terlihat di layar adalah yang akan dirender.
        """
        series = self.person_series(person) if person is not None else self.centers
        if not series:
            series = self.centers
        half = crop_w / 2.0
        max_x = max(0, self.source_w - crop_w)
        out: list[tuple[float, int]] = []
        last = None
        for t, cx in series:
            x = int(round(min(max(cx - half, 0.0), max_x)))
            if x != last:
                out.append((t, x))
                last = x
        return out or [(0.0, int(max_x // 2))]

    def to_sendcmd(self, name: str = "reframe",
                   track: Optional[list[tuple[float, int]]] = None) -> str:
        rows = track if track is not None else self.keyframes
        return "\n".join(f"{t:.3f} crop@{name} x {x};" for t, x in rows) + "\n"


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


class _FaceTrack:
    """
    Satu orang, diikuti lintas sampel.

    Menyimpan petak mulut terakhirnya supaya gerakan bisa diukur terhadap
    dirinya sendiri, bukan terhadap wajah orang lain — membandingkan petak
    mulut dua orang berbeda hanya mengukur seberapa berbeda wajah mereka.
    """

    __slots__ = ("cx", "cy", "w", "h", "mouth", "brow", "energy", "motion", "misses")

    def __init__(self, cx, cy, w, h, mouth, brow):
        self.cx = cx
        self.cy = cy
        self.w = w
        self.h = h
        self.mouth = mouth
        self.brow = brow
        self.energy = 0.0
        self.motion = 0.0        # gerakan sesaat, sebelum dihaluskan
        self.misses = 0


def _crop_patch(frame, cx, cy, pw, ph, sw, sh):
    """Petak abu-abu ternormalkan di sekitar satu titik, atau None."""
    import cv2
    import numpy as np

    x0, x1 = int(round(cx - pw / 2)), int(round(cx + pw / 2))
    y0, y1 = int(round(cy - ph / 2)), int(round(cy + ph / 2))
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(sw, x1), min(sh, y1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    patch = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    patch = cv2.resize(patch, MOUTH_PATCH, interpolation=cv2.INTER_AREA)
    patch = patch.astype(np.float32)
    patch -= patch.mean()
    std = float(patch.std())
    return patch / std if std > 1e-3 else patch


def _face_patches(frame, face, sw, sh):
    """
    Dua petak dari satu wajah: MULUT dan DAHI.

    Dua, bukan satu, dan itu seluruh alasan pengukuran ini bisa dipercaya.
    Petak mulut saja mengukur apa pun yang membuat pikselnya berubah — kepala
    yang mengangguk, kamera yang bergoyang, kotak deteksi yang bergeser satu
    piksel lalu mengambil ulang sampelnya. Diukur begitu, orang yang paling
    banyak bergerak menang, bukan orang yang bicara. Saya sudah mencobanya:
    hasilnya lebih buruk daripada sekadar memilih wajah terbesar.

    Dahi jadi pembanding. Gerakan kepala mengubah keduanya; artikulasi bicara
    hampir hanya mengubah mulut. Selisihnya yang dipakai.

    Titik mulut diambil dari penanda YuNet (dua titik terakhir adalah sudut
    mulut), bukan ditebak dari "sepertiga bawah kotak" — kepala yang menunduk
    menggeser mulutnya keluar dari sepertiga itu.
    """
    x, y, w, h = float(face[0]), float(face[1]), float(face[2]), float(face[3])
    if w < 12 or h < 12:
        return None, None

    mx = (float(face[10]) + float(face[12])) / 2.0
    my = (float(face[11]) + float(face[13])) / 2.0
    if not (0 <= mx < sw and 0 <= my < sh):
        mx, my = x + w / 2.0, y + h * 0.72

    # Dahi: di atas garis mata, selebar mulutnya supaya kedua petak memuat
    # jumlah piksel yang sebanding.
    ex = (float(face[4]) + float(face[6])) / 2.0
    ey = (float(face[5]) + float(face[7])) / 2.0
    if not (0 <= ex < sw and 0 <= ey < sh):
        ex, ey = x + w / 2.0, y + h * 0.32
    fy = ey - h * 0.18

    pw = max(8.0, w * MOUTH_W_RATIO)
    ph = max(6.0, h * MOUTH_H_RATIO)
    return (_crop_patch(frame, mx, my, pw, ph, sw, sh),
            _crop_patch(frame, ex, fy, pw, ph, sw, sh))


def _detect_centers(src: Path, segments: list[dict], source_w: int, source_h: int
                    ) -> tuple[list[Optional[float]], list[bool],
                               list[list[tuple[float, float]]]]:
    """
    Menjejak wajah utama, dalam koordinat sumber.

    Mengembalikan (pusat_x per sampel, penanda potongan-adegan per sampel,
    deteksi mentah per sampel). Nilai None berarti tidak ada wajah terdeteksi
    pada sampel itu; daftar mentahnya dipakai untuk mengelompokkan wajah jadi
    orang-orang yang bisa ditunjuk pengguna.
    """
    import cv2
    import numpy as np

    sw = SAMPLE_WIDTH
    sh = _even(SAMPLE_WIDTH * source_h / source_w)
    scale_back = source_w / sw

    detector = cv2.FaceDetectorYN.create(
        str(MODEL_PATH), "", (sw, sh), DETECT_SCORE, DETECT_NMS, 5000
    )

    # Rata-rata bergerak gerakan mulut, sebagai bobot per sampel.
    decay = math.exp(-1.0 / max(1e-6, MOUTH_SMOOTH_SECONDS * SAMPLE_FPS))

    centers: list[Optional[float]] = []
    cuts: list[bool] = []
    raw: list[list[float]] = []
    prev_center: Optional[float] = None
    prev_hist = None
    tracks: list[_FaceTrack] = []

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

            if is_cut:
                # Setelah potongan, wajah di layar belum tentu orang yang sama
                # di tempat yang sama.
                tracks = []

            _, faces = detector.detect(frame)
            detections = list(faces) if faces is not None and len(faces) else []

            # --- Cocokkan deteksi ke jejak yang sudah ada -------------------
            for t in tracks:
                t.misses += 1
            matched: list[_FaceTrack] = []
            max_dist = TRACK_MAX_DIST * sw

            for f in detections:
                x, y, w, h = float(f[0]), float(f[1]), float(f[2]), float(f[3])
                cx, cy = x + w / 2.0, y + h / 2.0
                mouth, brow = _face_patches(frame, f, sw, sh)

                best_t, best_d = None, max_dist
                for t in tracks:
                    if t in matched:
                        continue
                    d = math.hypot(cx - t.cx, cy - t.cy)
                    if d < best_d:
                        best_t, best_d = t, d

                if best_t is None:
                    best_t = _FaceTrack(cx, cy, w, h, mouth, brow)
                    tracks.append(best_t)
                else:
                    # Gerakan mulut DIKURANGI gerakan dahi, keduanya terhadap
                    # orang yang sama pada sampel sebelumnya. Yang tersisa
                    # adalah gerakan yang khas mulut.
                    def _diff(now, before):
                        if now is None or before is None or now.shape != before.shape:
                            return None
                        return float(np.abs(now - before).mean())

                    dm = _diff(mouth, best_t.mouth)
                    db = _diff(brow, best_t.brow)
                    motion = 0.0 if dm is None else dm - (db or 0.0)
                    best_t.motion = motion
                    best_t.energy = best_t.energy * decay + motion * (1.0 - decay)
                    best_t.cx, best_t.cy, best_t.w, best_t.h = cx, cy, w, h
                    best_t.mouth, best_t.brow = mouth, brow
                best_t.misses = 0
                matched.append(best_t)

            tracks = [t for t in tracks if t.misses <= TRACK_MAX_MISSES]

            # --- Siapa yang dipilih ----------------------------------------
            #
            # Wajah terbesar yang paling dekat dengan posisi sebelumnya.
            #
            # Saya mencoba menggantinya dengan pemilihan berdasarkan gerakan
            # mulut, supaya crop mengikuti orang yang SEDANG BICARA dan bukan
            # orang yang kebetulan paling dekat kamera. Diukur terhadap label
            # diarisasi pada rekaman meja lima orang, hasilnya lebih buruk
            # daripada aturan ini pada dua dari tiga klip — sekali dengan
            # gerakan mulut mentah, sekali dengan gerakan mulut dikurangi
            # gerakan dahi untuk membuang gerakan kepala. Keduanya saya buang.
            #
            # Sebabnya, sejauh yang terukur: rekaman yang sudah dipotong rapi
            # menjawab pertanyaannya sendiri. Saat A bicara, penyunting memotong
            # ke close-up A, jadi wajah terbesar memang pembicaranya, dan
            # memaksakan pilihan lain melawan penyuntingnya.
            #
            # Yang belum terjawab tetap ada: bidikan lebar berisi beberapa orang
            # yang tidak pernah berpindah kamera. Jawabannya bukan menebak siapa
            # yang bicara, melainkan membiarkan pengguna menunjuk orangnya —
            # itulah `person_tracks` di bawah.
            best = None
            if matched:
                best_score = -1e9
                for t in matched:
                    area = (t.w * t.h) / (sw * sh)
                    # Suku kontinuitas inilah yang mencegah crop melompat
                    # bolak-balik antara dua narasumber setiap kali wajah yang
                    # lebih kecil kebetulan lebih terang.
                    penalty = 0.0
                    if prev_center is not None and not is_cut:
                        penalty = 0.6 * abs(t.cx - prev_center / scale_back) / sw
                    score = area - penalty
                    if score > best_score:
                        best_score, best = score, t.cx

            if best is not None:
                prev_center = best * scale_back
                centers.append(prev_center)
            else:
                centers.append(None)
            cuts.append(is_cut)
            # (posisi, gerakan mulut) tiap wajah pada sampel ini. Gerakannya
            # ikut dibawa keluar karena yang menentukan siapa pemiliknya bukan
            # nilai sesaatnya, melainkan KAPAN ia naik — dan itu hanya bisa
            # dinilai terhadap suara, di luar sini.
            raw.append(sorted((t.cx * scale_back, t.motion) for t in matched))

    return centers, cuts, raw


def group_people(raw: list[list[tuple[float, float]]], source_w: int,
                 max_people: int = 6
                 ) -> tuple[list[list[Optional[float]]], list[list[float]]]:
    """
    Mengelompokkan deteksi wajah jadi ORANG, lalu menjejak tiap orang.

    Ini jawaban untuk bidikan lebar yang kameranya tidak pernah berpindah: di
    situ tidak ada yang bisa disimpulkan dari ukuran wajah, dan menebak siapa
    yang bicara dari gambar sudah saya coba dan gagal. Yang bisa diandalkan
    justru hal yang sederhana — orang duduk di tempatnya. Narasumber kedua ada
    di sekitar sepertiga kiri layar sepanjang klip, dan itu cukup untuk
    ditunjuk.

    Pengelompokannya dilakukan pada posisi mendatar saja, dengan k-means 1-D
    yang dibiakkan dari kuantil. Jumlah orangnya diambil dari jumlah wajah yang
    paling sering terlihat bersamaan, bukan dari jumlah wajah terbanyak yang
    pernah terlihat — satu frame dengan pantulan cermin tidak boleh menciptakan
    orang keenam.

    Mengembalikan (jejak posisi per orang, jejak gerakan mulut per orang), urut
    kiri ke kanan. None pada jejak posisi berarti orang itu tidak terlihat pada
    sampel tersebut.
    """
    import numpy as np

    counts = [len(r) for r in raw if r]
    if not counts:
        return [], []
    # Modus jumlah wajah = bentuk bidikan yang paling sering muncul.
    k = min(max_people, max(1, int(np.bincount(counts).argmax())))
    points = np.array([x for r in raw for x, _ in r], dtype=np.float64)
    if len(points) < k or k < 1:
        return [], []

    # Biakan dari kuantil, bukan acak: hasilnya sama tiap kali dijalankan, dan
    # rencana crop yang berubah-ubah antar render adalah bug yang sulit dikejar.
    centroids = np.quantile(points, [(i + 0.5) / k for i in range(k)])
    for _ in range(25):
        assign = np.abs(points[:, None] - centroids[None, :]).argmin(axis=1)
        moved = 0.0
        for i in range(k):
            sel = points[assign == i]
            if len(sel):
                new = float(np.median(sel))
                moved = max(moved, abs(new - centroids[i]))
                centroids[i] = new
        if moved < source_w * 0.002:
            break
    order = np.argsort(centroids)
    centroids = centroids[order]

    tracks: list[list[Optional[float]]] = [[] for _ in range(k)]
    motions: list[list[float]] = [[] for _ in range(k)]
    last: list[Optional[float]] = [None] * k
    for r in raw:
        taken: dict[int, float] = {}
        for x, m in r:
            i = int(np.abs(centroids - x).argmin())
            if i in taken:
                continue
            taken[i] = m
            last[i] = x
        for i in range(k):
            tracks[i].append(last[i])
            motions[i].append(taken.get(i, 0.0))
    return tracks, motions


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
        # Dua lintasan maju-mundur. Satu lintasan masih menyisakan riak halus
        # yang terlihat sebagai getar pelan saat kamera berpindah; melipatgandakan
        # orde filter menekannya tanpa menambah keterlambatan, karena tiap
        # lintasan tetap nol fase.
        for _ in range(EMA_PASSES):
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


def _centers_from_speakers(centers, people, mapping, speaker_turns, n):
    """
    Jejak pusat crop yang mengikuti penutur aktif.

    Saat orangnya sedang tidak terlihat — kamera berpindah, kepala menoleh —
    posisinya DITAHAN, tidak melompat ke orang lain. Penutur yang tidak punya
    pasangan jatuh kembali ke aturan lama, dan yang penting ia tidak mewarisi
    wajah penutur sebelumnya: pewarisan itulah yang membuat dua penutur berakhir
    di wajah yang sama.
    """
    active: list = [None] * n
    for t0, t1, sp in speaker_turns:
        lo = max(0, int(t0 * SAMPLE_FPS))
        hi = min(n, int(t1 * SAMPLE_FPS) + 1)
        for i in range(lo, hi):
            active[i] = sp

    out: list[Optional[float]] = []
    held: Optional[int] = None
    for i in range(n):
        sp = active[i]
        if sp is not None and sp in mapping:
            person = mapping[sp]
            if people[person][i] is not None:
                held = person
            out.append(people[held][i] if held is not None and people[held][i] is not None
                       else centers[i])
        else:
            held = None
            out.append(centers[i])
    return out


def assign_faces_to_speakers(people, motion, speaker_turns, n_samples):
    """
    Mencocokkan WAJAH dengan PENUTUR, memakai suara sebagai wasit.

    Ini yang hilang dari dua percobaan sebelumnya. Keduanya mencoba menebak
    siapa yang bicara dari gambar saja, sesaat demi sesaat: sekali dari gerakan
    mulut, sekali dari gerakan mulut dikurangi gerakan dahi. Keduanya diukur
    dan keduanya LEBIH BURUK daripada sekadar memilih wajah terbesar, karena
    gerakan mulut pada satu sampel tidak cukup membedakan bicara dari mengunyah,
    mengangguk, atau tertawa.

    Di sini pertanyaannya dibalik. Diarisasi sudah tahu KAPAN tiap orang bicara
    — itu datang dari suara, dan sama sekali tidak tahu apa-apa tentang gambar.
    Yang perlu dicari tinggal: untuk tiap penutur, mulut siapa yang ikut naik
    pada saat-saat itu. Dinilai atas seluruh klip sekaligus, bukan per frame,
    jadi derau sesaat tidak menentukan apa pun.

    Diukur pada tujuh klip rekaman meja: kemurnian pilihan naik dari 79% ke 97%,
    dan jumlah klip yang memetakan dua penutur ke wajah BERBEDA naik dari 3 dari
    7 menjadi 5 dari 7.

    Mengembalikan {indeks_penutur: indeks_orang}. Kosong berarti tidak ada
    pasangan yang cukup meyakinkan, dan pemanggil memakai aturan lama.
    """
    import itertools

    import numpy as np

    k = len(people)
    speakers = sorted({s for _, _, s in speaker_turns})
    if k < 2 or len(speakers) < 2 or n_samples < 16:
        return {}

    mot = np.array([m[:n_samples] for m in motion], dtype=np.float64)
    vis = np.array([[v is not None for v in p[:n_samples]] for p in people])
    if mot.shape[1] < n_samples:
        return {}

    # Dinormalkan per orang: wajah yang lebih besar di layar menghasilkan angka
    # gerakan lebih besar untuk gerakan yang sama, dan tanpa normalisasi ia
    # akan selalu menang.
    for i in range(k):
        seen = mot[i][vis[i]]
        if len(seen) > 4:
            sd = float(seen.std())
            mot[i] = (mot[i] - float(seen.mean())) / (sd if sd > 1e-6 else 1.0)

    active = np.zeros((len(speakers), n_samples), dtype=bool)
    for t0, t1, sp in speaker_turns:
        j = speakers.index(sp)
        lo = max(0, int(t0 * SAMPLE_FPS))
        hi = min(n_samples, int(t1 * SAMPLE_FPS) + 1)
        if hi > lo:
            active[j, lo:hi] = True

    score = np.full((k, len(speakers)), -np.inf)
    for i in range(k):
        for j in range(len(speakers)):
            inside = mot[i][active[j] & vis[i]]
            outside = mot[i][(~active[j]) & vis[i]]
            if len(inside) < 5 or len(outside) < 5:
                continue
            score[i][j] = float(inside.mean() - outside.mean())

    # Susunan TERBAIK secara keseluruhan, bukan serakah. Serakah mengunci
    # pasangan terkuat lebih dulu dan pasangan berikutnya tinggal menerima
    # sisanya, yang bisa keliru padahal susunan lain memberi total lebih tinggi.
    # Dengan dua sampai enam orang, mencoba semuanya hanya beberapa ratus
    # kemungkinan.
    best, best_total = None, None
    for perm in itertools.permutations(range(k), len(speakers)):
        vals = [score[perm[j]][j] for j in range(len(speakers))]
        if any(not np.isfinite(v) for v in vals):
            continue
        total = float(sum(vals))
        if best_total is None or total > best_total:
            best, best_total = perm, total
    if best is None:
        return {}

    # Tiap penutur diterima sendiri-sendiri: satu pasangan lemah tidak ikut
    # terbawa hanya karena pasangan lain di susunan yang sama kuat.
    return {speakers[j]: best[j] for j in range(len(speakers))
            if score[best[j]][j] > 0}


def plan_reframe(source_video_path: str, segments: list[dict], *,
                 aspect_ratio: str = "9:16",
                 track_only: bool = False,
                 speaker_turns: Optional[list] = None,
                 lock_person: Optional[int] = None) -> Optional[ReframePlan]:
    """
    Menyusun rencana crop yang mengikuti pembicara.

    Mengembalikan None bila reframe tidak layak dipakai — model tidak ada,
    OpenCV tidak terpasang, sumber sudah lebih sempit dari target, atau wajah
    terlalu jarang terlihat. Pemanggil lalu memakai jalur blur-pad.

    `track_only` dipakai oleh susunan bingkai buatan pengguna: di sana yang
    dibutuhkan hanya JEJAK wajahnya, karena lebar jendela crop ditentukan oleh
    kotak yang digambar pengguna, bukan oleh rasio kanvas. Syarat "sumber harus
    lebih lebar dari target" tidak berlaku di situ — bingkai selebar 30% tetap
    punya ruang untuk bergeser meski sumbernya sendiri sudah tegak.
    """
    target = {"9:16": 9 / 16, "1:1": 1.0, "4:5": 4 / 5}.get(aspect_ratio)
    if target is None and not track_only:
        return None
    if target is None:
        target = 9 / 16
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

    crop_w = _even(min(source_h * target, source_w))
    crop_h = _even(source_h)
    if crop_w >= source_w and not track_only:
        # Sumber sudah sama sempit atau lebih sempit dari target: tidak ada yang
        # bisa digeser.
        return None

    try:
        centers, cuts, raw = _detect_centers(src, segments, source_w, source_h)
    except Exception as e:  # deteksi tidak boleh menjatuhkan render
        log.warning("Deteksi wajah gagal, memakai blur-pad: %s", e)
        return None

    if not centers:
        return None

    coverage = sum(1 for c in centers if c is not None) / len(centers)

    try:
        people, motion = group_people(raw, source_w)
    except Exception as e:      # pengelompokan tidak boleh menjatuhkan render
        log.warning("Pengelompokan orang gagal: %s", e)
        people, motion = [], []

    # Pengguna menunjuk sendiri. Ini mengalahkan segalanya, dan memang harus:
    # pencocokan otomatis bisa keliru — mulut yang tertutup mikrofon hampir
    # tidak bergerak di gambar — dan saat itu terjadi, yang dibutuhkan bukan
    # tebakan yang lebih pintar melainkan cara untuk membetulkannya.
    if lock_person is not None and 0 <= lock_person < len(people):
        held: Optional[float] = None
        locked: list[Optional[float]] = []
        for i in range(len(centers)):
            v = people[lock_person][i]
            if v is not None:
                held = v
            # Saat orangnya tidak terlihat, posisinya ditahan — bukan melompat
            # ke wajah lain, yang justru hal yang sedang dihindari.
            locked.append(held if held is not None else centers[i])
        centers = locked
        log.info("Bingkai dikunci ke orang %d oleh pengguna", lock_person + 1)

    # Kalau kita tahu siapa bicara kapan, crop mengikuti WAJAH ORANG ITU dan
    # bukan wajah yang kebetulan paling besar. Tanpa data itu — atau kalau
    # pasangannya tidak meyakinkan — aturan lama tetap berlaku, jadi rekaman
    # berpotong kamera yang sudah benar tidak ikut diubah.
    elif speaker_turns and people:
        mapping = assign_faces_to_speakers(people, motion, speaker_turns, len(centers))
        if mapping:
            centers = _centers_from_speakers(centers, people, mapping,
                                             speaker_turns, len(centers))
            log.info("Wajah dicocokkan ke penutur: %s",
                     {f"penutur {k}": f"orang {v + 1}" for k, v in mapping.items()})

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
    centers: list[tuple[float, float]] = []
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
        # Titik tengahnya disimpan utuh: bingkai lain dengan lebar berbeda
        # menurunkan posisinya sendiri dari sini.
        centers.append((round(t, 3), round(cx, 2)))
        # Hanya tulis perintah bila nilainya berubah: file jadi jauh lebih kecil
        # dan ffmpeg tidak memproses ribuan perintah tak berguna.
        if x != last_x:
            keyframes.append((round(t, 3), x))
            last_x = x
        t += step

    if not keyframes:
        keyframes = [(0.0, int(round(min(max(smoothed[0] - half, 0.0), max_x))))]
    plan.keyframes = keyframes
    plan.centers = centers
    plan.people, plan.people_motion = people, motion
    log.info("Reframe siap: crop %dx%d, wajah terlihat %.0f%%, %d titik perintah",
             crop_w, crop_h, coverage * 100, len(keyframes))
    return plan


def build_reframe_filter(plan: ReframePlan, cmd_path: Path,
                         out_w: int, out_h: int, *,
                         name: str = "reframe",
                         crop_w: Optional[int] = None,
                         crop_h: Optional[int] = None,
                         crop_y: int = 0,
                         person: Optional[int] = None,
                         scale: bool = True) -> str:
    """
    Potongan filtergraph yang menerapkan rencana crop lalu menskalakan.

    Nama instance-nya bisa diganti supaya beberapa bingkai dalam satu susunan
    bisa sama-sama mengikuti wajah: tiap cabang punya `crop@…` sendiri dan
    file perintahnya sendiri. Dengan satu nama tetap, perintah untuk bingkai
    pertama akan ikut menggerakkan bingkai kedua.
    """
    w = crop_w or plan.crop_w
    h = crop_h or plan.crop_h
    track = plan.x_track(w, person)
    cmd_path.write_text(plan.to_sendcmd(name=name, track=track), encoding="utf-8")
    arg = str(cmd_path).replace("\\", "/").replace(":", r"\:")
    chain = (
        f"sendcmd=f='{arg}',"
        f"crop@{name}=w={w}:h={h}:x={track[0][1]}:y={crop_y}"
    )
    if scale:
        chain += f",scale={out_w}:{out_h}:flags=lanczos,setsar=1"
    return chain
