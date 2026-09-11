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
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..config import MODELS_DIR

log = logging.getLogger("omniclip.reframe")

MODEL_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"

# Pengenal wajah: SFace (ONNX 37 MB) lewat cv2.FaceRecognizerSF.
#
# Ini jawaban untuk pertanyaan yang tidak pernah bisa dijawab posisi mendatar:
# SIAPA wajah ini. Penomoran lama memakai tempat duduk — cukup untuk bidikan
# lebar yang kameranya diam, dan salah begitu kameranya berpindah. Terukur pada
# satu klip podcast lima orang: di detik ke-15 hanya ADA DUA wajah di layar,
# tapi keduanya dinomori 2 dan 4, sementara pin 5 tergambar dari posisi basi 16
# piksel di sebelah pin 4. Dua orang di layar, empat nomor tergambar, dan
# tak satu pun menunjuk orang yang benar.
#
# Sidik wajah tidak peduli kamera berpindah ke mana. Yang dibayar untuk itu:
# 23 ms per wajah, jadi sidik diambil per JEJAK, bukan per wajah per sampel —
# satu jejak sudah berarti satu orang yang sama sepanjang ia terlihat.
SFACE_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"

# Ambang kemiripan kosinus dua wajah dianggap orang yang sama. 0,363 adalah
# angka yang disarankan penulis SFace, dan pada rekaman uji hasilnya memang
# tidak berubah di mana pun antara 0,30 dan 0,42 — kelompoknya terpisah jauh,
# bukan pas-pasan di ambang.
IDENTITY_SIMILARITY = 0.363

# Ambang untuk mencocokkan ke DAFTAR TETAP video, lebih tinggi daripada ambang
# pengelompokan di dalam satu klip — dan angkanya diukur, bukan dipilih.
#
# Pada tiga klip dari satu podcast, sidik rata-rata orang yang SAMA antar klip
# berjarak +0,85 sampai +0,98; orang yang BERBEDA berjarak 0,01 sampai 0,38.
# Jurang di antara keduanya lebar sekali, dan 0,363 jatuh di sisi yang salah:
# sepasang kelompok berbeda yang kebetulan bernilai 0,38 ikut tergabung, dan
# satu orang lenyap dari daftar. 0,60 duduk di tengah jurang itu.
#
# Yang dibandingkan di sini rata-rata seluruh kelompok, bukan satu jejak, jadi
# ia memang berhak dituntut lebih tinggi.
ROSTER_SIMILARITY = 0.60

# Wajah yang lebih kecil dari ini tidak disidik. Diukur: pada ambang 26 piksel
# jumlah kelompok berayun 5-6-7 mengikuti ambang kemiripan — sidik dari wajah
# sekecil itu terlalu berderau untuk dipercaya. Pada 34 hasilnya sama persis di
# seluruh rentang ambang.
EMBED_MIN_FACE = 34
# Jarak antar sidik untuk satu jejak, dalam sampel. Wajah orang yang sama tidak
# berubah dalam setengah detik; yang berubah cuma sudut dan cahayanya, dan itu
# yang dirata-ratakan.
EMBED_EVERY = 5
# Cukup tiga. Diuji pada dua klip dengan batas 6, 3, dan 2 sidik per jejak:
# jumlah orang dan persentase kehadirannya SAMA PERSIS di ketiganya — rata-rata
# sidik memang berhenti membaik setelah beberapa sudut. Tiga dipilih, bukan dua,
# sekadar sebagai jarak aman terhadap satu sudut yang buruk.
#
# Ongkosnya nyata dan sudah diukur: pada klip 120 detik, memindai dengan sidik
# 21 detik melawan 13 detik tanpa. Dibayar sekali per klip lalu disimpan —
# geseran batas berikutnya memakai hasil yang sama dalam 0,2 detik.
EMBED_MAX_PER_TRACK = 3

# Laju sampling deteksi. 6 Hz memberi sinyal yang cukup rapat untuk difilter
# tanpa membuat perencanaan terasa lama (klip 45 detik ~ 270 frame, ~3 detik).
SAMPLE_FPS = 8.0
# Diukur pada bidikan lebar lima orang: pada 480 detektor hanya menemukan empat
# dari lima wajah — yang paling jauh terlalu kecil untuk dikenali. 560 menemukan
# kelimanya, sama seperti 720, dengan biaya sepertiga lebih besar alih-alih dua
# kali lipat.
SAMPLE_WIDTH = 560

# Lebar kerja untuk petak mulut, dipisahkan dari lebar deteksi.
#
# Deteksi wajah tidak butuh resolusi tinggi — YuNet menemukan wajah selebar 34
# piksel dengan baik, dan menjalankannya pada 1280 memakan waktu lima kali
# lipat untuk kotak yang sama. Mengukur GERAK MULUT butuh resolusi: artikulasi
# bicara adalah gerakan kecil, dan pada salinan 560 piksel sebuah mulut tinggal
# ~29x16 piksel. Dua kebutuhan yang berbeda, jadi dua angka yang berbeda.
#
# 1280 dipilih sebagai batas: di atas itu pipa mentahnya mulai mahal (satu
# bingkai 4K adalah 25 MB) tanpa menambah apa pun — wajah dalam bidikan meja
# sudah lebih dari cukup tajam pada 1280.
FULL_WIDTH_CAP = 1280

# Laju perintah yang ditulis ke sendcmd. 25 Hz melampaui laju frame video,
# sehingga crop tidak pernah "menunggu" perintah berikutnya. Pada 10 Hz,
# perubahan posisi datang tiap 3 frame dan itu terlihat sebagai getar halus.
# Disamakan dengan laju bingkai keluaran (-r 30), bukan angka bulat sembarang.
#
# Pada 25 Hz melawan 30 fps, lima bingkai tiap detik tidak menerima posisi baru
# sementara sisanya menerima — pola tersendat 5 Hz yang terlihat sebagai gerakan
# patah-patah meski jejaknya sendiri sudah mulus. Satu perintah per bingkai
# menghapusnya sama sekali.
COMMAND_HZ = 30.0

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
# Deadzone dan alpha disetel bersama, dari pengukuran atas 18 klip di 6 video —
# bukan ditebak.
#
# Goyangan kepala antar sampel bernilai median 3,1px dan p90 13,9px pada sumber
# 1280, jadi 2,5% (32px) masih mengabaikannya dengan margin lebih dari dua kali
# lipat p90. Yang lama, 5,5% dengan alpha 0,12, membiarkan kotaknya tertinggal
# rata-rata 2,45% lebar dari wajahnya dan 5,33% pada persentil 90 — itulah
# "bingkainya tidak pas di tengah muka orangnya".
#
#                        galat rata-rata   galat p90   kekasaran
#   lama  5,5%  a=0,12          2,45%          5,33%      0,0649
#   baru  2,5%  a=0,28          1,48%          3,04%      0,0721
#
# Ketepatannya naik 40%, kekasarannya naik 11%. Pertukaran itu diambil karena
# sumber tersendat yang jauh lebih besar — perintah 25 Hz melawan keluaran 30
# fps — dihapus di COMMAND_HZ, dan itu menutup selisih 11% ini berkali lipat.
DEADZONE_RATIO = 0.025
# Ambang untuk berhenti membuntuti, sebagai pecahan dari ambang mulai. Lebih
# rapat supaya keduanya tidak bergantian tiap sampel saat wajahnya pas di
# perbatasan — histeresis, bukan satu ambang.
DEADZONE_EXIT_RATIO = 0.35
EMA_ALPHA = 0.28           # per sampel pada 8 Hz; dijalankan dua arah, dua kali
EMA_PASSES = 2             # dua lintasan = filter orde-4, riak sisa jauh lebih kecil
MAX_SPEED_RATIO = 0.10     # plafon kecepatan pan, lebar-per-detik
SCENE_CUT_DISTANCE = 0.5   # jarak Bhattacharyya histogram HSV
MEDIAN_WINDOW = 7          # buang deteksi meleset sesaat sebelum difilter
# Sebuah bidikan harus muncul di sekian bagian sampel sebelum jumlah wajahnya
# dianggap menentukan berapa orang yang ada.
ROSTER_MIN_SHARE = 0.05

# Berapa lama seorang subjek baru harus bertahan sebelum bingkai benar-benar
# berpindah kepadanya.
#
# Tanpa penahan ini, sela satu kata ("iya", "hmm") sudah cukup memindahkan
# bingkai dan memindahkannya kembali — dan karena perpindahannya seketika,
# hasilnya berkedip. Diukur pada podcast empat orang, 0,6 detik membuang
# sebagian besar sela sambil tetap menangkap giliran bicara yang sungguhan.
MIN_SUBJECT_HOLD = 0.6

# Berapa kuat bukti gerak-mulut harus, sebelum bingkai berhenti mengikuti
# bidikan aslinya dan mulai mengikuti penutur. Dinyatakan dalam statistik-t.
#
# Dipilih dari uji belah-dua pada 41 klip: pada ambang lama (t efektif 0)
# kesepakatan antar paruh cuma 50%, pada t >= 2 ia naik tapi cakupannya turun
# ke 14%. Dua angka itu bersama-sama mengatakan hal yang sama — sinyal gerak
# mulut memang ada, tapi tipis, dan hanya sebagian kecil giliran yang
# membawanya cukup banyak untuk dipercaya.
MIN_SPEAKER_EVIDENCE = 2.0

# Berapa lama posisi seseorang masih boleh dipakai setelah wajahnya tak lagi
# terdeteksi.
#
# Membedakan dua hal yang tampak sama dari deretan angka: kepala yang menoleh
# sebentar (posisinya masih benar, tahan saja) dan kamera yang sudah berpindah
# ke orang lain (posisinya sudah tidak berarti apa-apa). Tanpa batas ini,
# `_trace_people` menahan posisi terakhir SELAMANYA, sehingga bingkai terus
# menunjuk tempat seseorang dulu duduk — di dalam close-up orang lain, tempat
# itu cuma dinding.
UNSEEN_GRACE = 0.8


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
    # Apakah orang itu BENAR-BENAR terdeteksi pada tiap sampel.
    #
    # `people` sengaja menahan posisi terakhir saat wajahnya hilang — itulah
    # yang membuat crop tidak melompat ke tengah tiap kali kepala menoleh. Tapi
    # menahan berarti jejaknya tidak bisa membedakan "sedang tidak terdeteksi"
    # dari "sudah tidak ada di kamera", dan editor memakainya untuk menaruh
    # penanda orang di atas video: hasilnya penanda "orang 2" berdiri di atas
    # kursi kosong sepanjang klip setelah orangnya keluar dari bidikan.
    # Kehadirannya disimpan terpisah supaya keduanya bisa jujur sekaligus.
    people_seen: list[list[bool]] = field(default_factory=list)
    # Penutur mana milik wajah mana: {indeks_penutur: indeks_orang}.
    #
    # Dihitung di sini karena di sinilah kedua sisinya bertemu — gerakan mulut
    # dari gambar, giliran bicara dari suara. Dibawa keluar karena editor
    # membutuhkannya untuk menaruh baris subtitle pada lajur ORANGNYA: tanpa
    # peta ini, nomor penutur dan nomor wajah adalah dua sistem penomoran yang
    # kebetulan sama-sama memakai angka, dan menaruhnya di baris yang sama
    # hanya akan berbohong dengan rapi.
    speaker_faces: dict[int, int] = field(default_factory=dict)

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

    __slots__ = ("cx", "cy", "w", "h", "mouth", "brow", "energy", "motion",
                 "misses", "tid", "emb", "emb_n", "emb_at")

    def __init__(self, cx, cy, w, h, mouth, brow, tid=0):
        self.cx = cx
        self.cy = cy
        self.w = w
        self.h = h
        self.mouth = mouth
        self.brow = brow
        self.energy = 0.0
        self.motion = 0.0        # gerakan sesaat, sebelum dihaluskan
        self.misses = 0
        # Nomor jejak: satu orang selama ia tidak hilang dari layar. Sidik
        # wajahnya dikumpulkan di sini dan dirata-ratakan, karena satu sudut
        # tunggal bisa saja sudut yang buruk.
        self.tid = tid
        self.emb = None
        self.emb_n = 0
        self.emb_at = -10**9


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


# Ukuran petak mulut yang diluruskan. Lebih besar dari MOUTH_PATCH karena ia
# diambil dari bingkai beresolusi penuh, bukan dari salinan 560 piksel.
ALIGNED_PATCH = (48, 32)


def _aligned_patches(full, face, scale: float):
    """
    Petak MULUT dan DAHI dari bingkai beresolusi penuh, diluruskan garis mata.

    Dua perbaikan atas `_face_patches`, dan keduanya terukur pada kontrol
    positif — rekaman satu orang yang bicara terus, tempat "sedang bicara"
    tidak perlu ditebak:

    1. **Resolusi.** Deteksi berjalan pada salinan selebar 560 piksel, dan di
       situ satu wajah hanya selebar ~53 piksel sehingga mulutnya tinggal
       ~29x16. Bingkai aslinya 1280 dan mulutnya ~66x36 — empat kali lipat
       pikselnya, dan artikulasi bicara adalah gerakan kecil.
    2. **Penyelarasan.** Petak lama mengikuti titik mulut tapi tidak pernah
       diputar atau diskalakan, jadi kepala yang miring atau maju-mundur
       menghasilkan selisih piksel besar yang tidak ada hubungannya dengan
       bicara. Di sini petaknya diputar mengikuti garis mata dan diskalakan
       terhadap jarak antar mata, sehingga yang tersisa tinggal perubahan
       bentuk mulut itu sendiri.

    Terukur: korelasi dengan selubung suara naik dari +0,160 ke +0,255, dan
    selisih gerak antara saat suara keras dan lirih naik dari 0,57 ke 0,73
    simpangan baku.
    """
    import cv2
    import numpy as np

    lm = [(float(face[4 + 2 * i]) * scale, float(face[5 + 2 * i]) * scale)
          for i in range(5)]
    (ex1, ey1), (ex2, ey2) = lm[0], lm[1]
    jarak = float(np.hypot(ex2 - ex1, ey2 - ey1))
    if jarak < 8.0:
        return None, None
    sudut = float(np.degrees(np.arctan2(ey2 - ey1, ex2 - ex1)))

    def petak(cx: float, cy: float):
        bw, bh = jarak * 1.4, jarak * 0.9
        M = cv2.getRotationMatrix2D((cx, cy), sudut, 1.0)
        M[0, 2] += bw / 2.0 - cx
        M[1, 2] += bh / 2.0 - cy
        crop = cv2.warpAffine(full, M, (max(4, int(bw)), max(4, int(bh))),
                              flags=cv2.INTER_AREA)
        if crop.size == 0:
            return None
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, ALIGNED_PATCH, interpolation=cv2.INTER_AREA)
        g = g.astype(np.float32)
        g -= g.mean()
        sd = float(g.std())
        return g / sd if sd > 1e-3 else g

    mx = (lm[3][0] + lm[4][0]) / 2.0
    my = (lm[3][1] + lm[4][1]) / 2.0
    # Dahi: di atas garis mata, sejauh 0,55 jarak mata.
    exm, eym = (ex1 + ex2) / 2.0, (ey1 + ey2) / 2.0
    rad = math.radians(sudut)
    fx = exm + math.sin(rad) * jarak * 0.55
    fy = eym - math.cos(rad) * jarak * 0.55
    return petak(mx, my), petak(fx, fy)


def _detect_centers(src: Path, segments: list[dict], source_w: int, source_h: int
                    ) -> tuple[list[Optional[float]], list[bool],
                               list[list[tuple[float, float, int]]], dict]:
    """
    Menjejak wajah utama, dalam koordinat sumber.

    Mengembalikan (pusat_x per sampel, penanda potongan-adegan per sampel,
    deteksi mentah per sampel, sidik wajah per jejak). Nilai None berarti tidak
    ada wajah terdeteksi pada sampel itu; daftar mentahnya dipakai untuk
    mengelompokkan wajah jadi orang-orang yang bisa ditunjuk pengguna.

    Tiap deteksi membawa NOMOR JEJAKNYA. Nomor itu yang menyambungkan wajah di
    sebuah sampel dengan sidik yang diambil dari jejak yang sama beberapa
    sampel sebelumnya — tanpa itu, sidiknya tidak punya alamat.
    """
    import cv2
    import numpy as np

    sw = SAMPLE_WIDTH
    sh = _even(SAMPLE_WIDTH * source_h / source_w)
    scale_back = source_w / sw

    # Bingkai dipipa pada resolusi kerja yang lebih besar daripada lebar
    # deteksi, lalu dikecilkan di sini. Deteksi tetap berjalan di 560 piksel
    # (biayanya tidak berubah), sementara petak mulut diambil dari salinan yang
    # masih tajam — dan gerak mulut adalah gerakan kecil yang paling dulu hilang
    # saat gambarnya diperkecil.
    fw = min(int(source_w), FULL_WIDTH_CAP)
    fh = _even(fw * source_h / source_w)
    to_detect = (fw != sw or fh != sh)

    detector = cv2.FaceDetectorYN.create(
        str(MODEL_PATH), "", (sw, sh), DETECT_SCORE, DETECT_NMS, 5000
    )

    # Pengenal boleh tidak ada. Modelnya 37 MB dan diunduh terpisah; tanpa itu
    # penomoran jatuh ke aturan tempat duduk yang lama — lebih buruk, tapi tetap
    # jalan. Menjatuhkan seluruh render karena satu berkas tambahan tidak ada
    # bukan pertukaran yang benar.
    recognizer = None
    if SFACE_PATH.is_file():
        try:
            recognizer = cv2.FaceRecognizerSF.create(str(SFACE_PATH), "")
        except Exception as e:
            log.warning("Pengenal wajah tidak bisa dimuat: %s", e)

    embeds: dict[int, "np.ndarray"] = {}
    next_tid = 0
    sample_i = -1

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

        for buf in _sample_frames(src, start, duration, fw, fh):
            sample_i += 1
            full = np.frombuffer(buf, dtype=np.uint8).reshape((fh, fw, 3))
            frame = (cv2.resize(full, (sw, sh), interpolation=cv2.INTER_AREA)
                     if to_detect else full)
            full_scale = fw / sw

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
                mouth, brow = _aligned_patches(full, f, full_scale)
                if mouth is None:
                    mouth, brow = _face_patches(frame, f, sw, sh)

                best_t, best_d = None, max_dist
                for t in tracks:
                    if t in matched:
                        continue
                    d = math.hypot(cx - t.cx, cy - t.cy)
                    if d < best_d:
                        best_t, best_d = t, d

                if best_t is None:
                    next_tid += 1
                    best_t = _FaceTrack(cx, cy, w, h, mouth, brow, next_tid)
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

                # --- Sidik wajah -------------------------------------------
                #
                # Dibayar sekali per beberapa sampel per jejak, bukan tiap
                # wajah tiap sampel: 23 ms dikalikan tiap wajah tiap sampel
                # akan melipatduakan waktu pindai untuk jawaban yang sudah
                # diketahui — wajah di jejak yang sama adalah orang yang sama.
                #
                # Wajah kecil dilewati dengan sengaja. Justru di bidikan lebar
                # wajahnya kecil, dan di situ posisi mendatar memang bisa
                # dipercaya karena semua orang duduk di tempatnya. Yang butuh
                # sidik adalah bidikan dekat — dan di situ wajahnya besar. Dua
                # cara ini saling menutup persis di tempat yang satunya lemah.
                if (recognizer is not None
                        and min(w, h) >= EMBED_MIN_FACE
                        and best_t.emb_n < EMBED_MAX_PER_TRACK
                        and sample_i - best_t.emb_at >= EMBED_EVERY):
                    try:
                        v = recognizer.feature(
                            recognizer.alignCrop(frame, f)).flatten().astype(np.float64)
                        n = float(np.linalg.norm(v))
                        if n > 1e-9:
                            v /= n
                            best_t.emb = v if best_t.emb is None else best_t.emb + v
                            best_t.emb_n += 1
                            best_t.emb_at = sample_i
                            embeds[best_t.tid] = (
                                best_t.emb / float(np.linalg.norm(best_t.emb)))
                    except cv2.error:
                        # Kotak wajah yang menyentuh tepi bingkai tidak bisa
                        # diluruskan. Bukan kesalahan — cuma tidak ada sidik
                        # dari sampel itu.
                        pass

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
            raw.append(sorted((t.cx * scale_back, t.motion, t.tid) for t in matched))

    return centers, cuts, raw, embeds


def _cluster_identities(embeds: dict, weight: dict) -> list[list[int]]:
    """
    Menyatukan jejak-jejak yang wajahnya orang yang sama.

    Penggabungan berpasangan dengan hubungan RATA-RATA, bukan tetangga
    terdekat. Tetangga terdekat membuat satu pasang sidik yang kebetulan mirip
    cukup untuk menyatukan dua kelompok besar — dan dua orang yang kebetulan
    berkacamata sama akan tersatukan lewat satu sudut yang buruk. Rata-rata
    menuntut seluruh anggota kedua kelompok saling mirip.

    Diurut dari pasangan paling mirip supaya hasilnya tidak bergantung urutan
    jejak datang: rencana bingkai yang berubah antar render adalah bug yang
    sangat sulit dikejar.
    """
    import numpy as np

    tids = sorted(embeds, key=lambda t: (-weight.get(t, 0), t))
    if len(tids) < 2:
        return [[t] for t in tids]

    M = np.stack([embeds[t] for t in tids])
    S = M @ M.T

    groups = {i: [i] for i in range(len(tids))}
    parent = list(range(len(tids)))

    def akar(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    pasangan = sorted(((float(S[i, j]), i, j)
                       for i in range(len(tids))
                       for j in range(i + 1, len(tids))), reverse=True)
    for sim, i, j in pasangan:
        if sim < IDENTITY_SIMILARITY:
            break
        a, b = akar(i), akar(j)
        if a == b:
            continue
        ga, gb = groups[a], groups[b]
        rata = float(np.mean([S[x, y] for x in ga for y in gb]))
        if rata >= IDENTITY_SIMILARITY:
            parent[b] = a
            groups[a] = ga + gb
            groups.pop(b, None)

    return [[tids[i] for i in mem] for mem in groups.values()]


# Daftar wajah TETAP per video, hidup selintas klip.
#
# Tanpa ini, tiap klip mengelompokkan wajahnya sendiri dari nol dan menomori
# hasilnya dari kiri ke kanan — jadi orang yang sama bisa jadi "orang 2" di satu
# klip dan "orang 4" di klip berikutnya, semata karena siapa yang kebetulan ikut
# tertangkap kamera di rentang itu. Tanda arah bingkai disimpan sebagai NOMOR,
# jadi penomoran yang berpindah bukan cuma membingungkan: ia membuat tanda yang
# sudah dipasang menunjuk orang yang berbeda.
#
# Yang disimpan sidik rata-rata tiap orang beserta berapa kali ia dilihat. Klip
# berikutnya mencocokkan kelompoknya ke daftar ini lebih dulu; yang tidak cocok
# dengan siapa pun ditambahkan di belakang. Nomor sekali diberikan tidak pernah
# berpindah — orang baru selalu dapat nomor baru.
# Kuncinya memuat waktu ubah berkasnya, jadi mengunduh ulang video pada resolusi
# yang lebih baik otomatis memulai daftar yang baru — tidak perlu tombol
# "lupakan wajah" yang tidak pernah jelas kapan harus ditekan.
_ROSTER: "OrderedDict[tuple, dict]" = OrderedDict()
_ROSTER_MAX = 4


def _roster_for(key: tuple) -> dict:
    r = _ROSTER.get(key)
    if r is None:
        r = {"emb": [], "n": [], "x": []}
        _ROSTER[key] = r
        while len(_ROSTER) > _ROSTER_MAX:
            _ROSTER.popitem(last=False)
    else:
        _ROSTER.move_to_end(key)
    return r


def _match_roster(roster: dict, vec, x: float, max_people: int) -> int:
    """
    Nomor orang untuk satu sidik wajah: yang sudah dikenal, atau nomor baru.

    Pencocokannya memakai ambang yang sama dengan pengelompokan di dalam satu
    klip. Kalau daftarnya sudah penuh, yang paling mirip tetap dipakai meski di
    bawah ambang — menolak berarti membuang orangnya sama sekali, dan itu lebih
    buruk daripada nomor yang kurang yakin.
    """
    import numpy as np

    if roster["emb"]:
        M = np.stack(roster["emb"])
        sim = M @ vec
        i = int(np.argmax(sim))
        if float(sim[i]) >= ROSTER_SIMILARITY or len(roster["emb"]) >= max_people:
            n = roster["n"][i]
            # Rata-rata berjalan: sidik orang yang sama dari banyak klip lebih
            # tahan terhadap satu sudut yang buruk daripada sidik pertama saja.
            baru = (M[i] * n + vec) / (n + 1)
            roster["emb"][i] = baru / max(float(np.linalg.norm(baru)), 1e-9)
            roster["n"][i] = n + 1
            roster["x"][i] = (roster["x"][i] * n + x) / (n + 1)
            return i

    roster["emb"].append(vec)
    roster["n"].append(1)
    roster["x"].append(x)
    return len(roster["emb"]) - 1


def _identities_from_faces(raw: list, embeds: dict, max_people: int,
                           roster: Optional[dict] = None):
    """
    Siapa saja yang ada di rekaman ini, dari wajahnya — bukan dari kursinya.

    Mengembalikan (peta nomor_jejak -> nomor orang, jumlah orang) atau None
    bila sidiknya terlalu sedikit untuk menyimpulkan apa pun. Urutannya belum
    ditetapkan di sini; pemanggil yang mengurutkannya kiri ke kanan supaya
    "orang 1" tetap berarti orang paling kiri seperti yang dilihat pengguna.
    """
    if not embeds or len(embeds) < 2:
        return None

    berat: dict[int, int] = {}
    for r in raw:
        for _x, _m, tid in r:
            berat[tid] = berat.get(tid, 0) + 1
    total = sum(berat.values())
    if total < 16:
        return None

    kelompok = _cluster_identities(embeds, berat)
    if not kelompok:
        return None

    bobot = [(sum(berat.get(t, 0) for t in mem), mem) for mem in kelompok]
    bobot.sort(key=lambda x: -x[0])

    # Kelompok yang hampir tidak pernah terlihat dibuang. Satu jejak sepanjang
    # satu sampel bukan orang keenam di ruangan — itu pantulan, atau separuh
    # wajah yang lewat di tepi bingkai. Ambangnya sama dengan ambang lama untuk
    # jumlah orang, jadi keduanya bercerita hal yang sama.
    ambang = max(2, int(total * ROSTER_MIN_SHARE))
    dipakai = [mem for w, mem in bobot if w >= ambang][:max_people]
    if not dipakai:
        return None

    if roster is None:
        return {t: i for i, mem in enumerate(dipakai) for t in mem}, len(dipakai)

    # --- Nomor diambil dari daftar tetap video ini ----------------------------
    import numpy as np

    posisi: dict[int, list[float]] = {}
    for r in raw:
        for x, _m, tid in r:
            posisi.setdefault(tid, []).append(x)

    peta: dict[int, int] = {}
    for mem in dipakai:
        vecs = [embeds[t] for t in mem if t in embeds]
        if not vecs:
            continue
        rata = np.mean(np.stack(vecs), axis=0)
        rata = rata / max(float(np.linalg.norm(rata)), 1e-9)
        xs = [x for t in mem for x in posisi.get(t, [])]
        nomor = _match_roster(roster, rata, float(np.median(xs)) if xs else 0.0,
                              max_people)
        for t in mem:
            peta[t] = nomor
    if not peta:
        return None
    return peta, len(roster["emb"])


def group_people(raw: list[list[tuple[float, float, int]]], source_w: int,
                 embeds: Optional[dict] = None,
                 roster: Optional[dict] = None,
                 max_people: int = 6
                 ) -> tuple[list[list[Optional[float]]], list[list[float]],
                            list[list[bool]]]:
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

    Mengembalikan (jejak posisi, jejak gerakan mulut, kehadiran) per orang, urut
    kiri ke kanan.

    Jejak posisi MENAHAN nilai terakhir saat wajahnya hilang — tanpa itu crop
    melompat ke tengah tiap kali kepala menoleh sebentar. Yang membedakan
    "sedang tidak terdeteksi" dari "sudah tidak di kamera" adalah daftar
    kehadiran, bukan celah pada jejaknya.
    """
    import numpy as np

    counts = [len(r) for r in raw if r]
    if not counts:
        return [], [], []

    # --- Jalur pertama: kenali wajahnya ---------------------------------------
    #
    # Kalau sidiknya ada, DIA yang memutuskan siapa ini — bukan letaknya di
    # layar. Bedanya paling terasa persis di tempat cara lama gagal: bidikan
    # dekat berisi dua orang. Di situ tidak ada satu pun petunjuk posisi yang
    # benar, karena kameranya sudah memindahkan keduanya.
    kenal = _identities_from_faces(raw, embeds or {}, max_people, roster)
    if kenal is not None:
        tid2id, k = kenal
        # Tempat duduk tiap nomor, untuk menjodohkan wajah yang tidak bersidik.
        #
        # Nomornya sendiri TIDAK diurutkan ulang di sini. Versi sebelumnya
        # mengurutkannya kiri ke kanan tiap klip, dan itulah yang membuat orang
        # yang sama berpindah nomor antar klip — urutan kiri-ke-kanan hanya
        # berarti sesuatu bila semua orang kebetulan terlihat, dan di klip yang
        # kameranya dekat hampir tidak pernah begitu. Urutan ditetapkan sekali
        # saat daftar video ini pertama dibentuk, lalu dipegang.
        centroids = np.array(
            [(roster["x"][i] if roster and i < len(roster["x"]) else 0.0)
             for i in range(k)], dtype=np.float64)
        return _trace_people(raw, centroids, k, tid2id)

    # --- Jalur cadangan: tebak dari tempat duduknya ----------------------------
    #
    # Dipakai bila model pengenal tidak terpasang, atau bila tidak satu wajah
    # pun cukup besar untuk disidik sepanjang klip. Hasilnya tetap benar untuk
    # bidikan lebar berkamera diam — hanya bidikan dekatlah yang membingungkannya.
    tid2id = {}

    # Berapa ORANG yang ada di ruangan — bukan berapa wajah yang paling sering
    # terlihat sekaligus.
    #
    # Dulu ini modus, dan itu salah untuk rekaman berpotong kamera. Podcast lima
    # orang menghabiskan sebagian besar waktunya pada close-up satu atau dua
    # wajah; bidikan lebar yang memperlihatkan kelimanya cuma muncul sesekali.
    # Terukur pada dua menit rekaman: 608 sampel berisi 2 wajah, 77 sampel
    # berisi 5. Modusnya 2, jadi sistem hanya mengenal dua orang — dan pengguna
    # yang ingin mengambil orang di sebelah kanan tidak punya nomor untuk
    # ditunjuk sama sekali.
    #
    # Yang dipakai sekarang: jumlah terbesar yang benar-benar bertahan. Sebuah
    # bidikan yang memperlihatkan lima wajah pada 8% sampel adalah bidikan yang
    # sungguh ada; satu sampel berisi enam wajah adalah pantulan atau salah
    # deteksi, dan tidak boleh menciptakan orang keenam.
    total = len(counts)
    arr = np.array(counts)
    k = 1
    for c in range(1, max_people + 1):
        if float((arr >= c).sum()) / total >= ROSTER_MIN_SHARE:
            k = c
    k = min(max_people, max(1, k))
    # Posisi duduknya diambil dari BIDIKAN LEBAR saja.
    #
    # Ini yang membuat nomor orang berarti. Close-up menaruh wajah siapa pun di
    # tengah layar, jadi mencampurnya ke dalam pengelompokan menggeser tiap
    # centroid ke tengah sampai dua orang yang duduk berjauhan punya centroid
    # berjarak 45 piksel — dan nomor 1 bisa jatuh ke orang yang duduk kedua dari
    # kiri. Hanya pada bidikan yang memperlihatkan semua orang sekaligus posisi
    # duduk mereka benar-benar terbaca.
    lebar = [r for r in raw if len(r) >= k]
    sumber = lebar if len(lebar) >= 3 else [r for r in raw if r]
    points = np.array([x for r in sumber for x, _ in r], dtype=np.float64)
    if len(points) < k or k < 1:
        return [], [], []

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
    return _trace_people(raw, centroids, k, tid2id)


def _trace_people(raw: list, centroids, k: int, tid2id: dict):
    """
    Menjejak tiap orang sampel demi sampel.

    Dua sumber keterangan dipakai berurutan, dan urutannya yang penting:

    1. **Sidik wajah**, bila jejak wajah itu memang dikenali. Ini mengalahkan
       segalanya, karena ia satu-satunya yang tetap benar setelah kamera
       berpindah.
    2. **Tempat duduk**, untuk wajah yang tidak bersidik — biasanya wajah kecil
       di bidikan lebar. Di situlah posisi justru paling bisa dipercaya, karena
       semua orang memang sedang duduk di tempatnya.

    Pencocokan sisa memakai pasangan TERBAIK secara keseluruhan, bukan siapa
    cepat dia dapat. Versi lama menjodohkan tiap wajah ke centroid terdekatnya
    lalu membuang wajah kedua yang jatuh ke centroid yang sama; pada bidikan
    lebar itu berarti kehilangan orang — terukur, lima wajah terdeteksi tapi
    hanya tiga yang sampai ke jejak.

    Posisinya DITAHAN saat wajahnya hilang, supaya bingkai tidak melompat ke
    tengah tiap kali kepala menoleh. Yang membedakan "sedang tidak terdeteksi"
    dari "sudah tidak di kamera" adalah `seen`, bukan celah pada jejaknya.
    """
    tracks: list[list[Optional[float]]] = [[] for _ in range(k)]
    motions: list[list[float]] = [[] for _ in range(k)]
    seen: list[list[bool]] = [[] for _ in range(k)]
    last: list[Optional[float]] = [None] * k

    for r in raw:
        taken: dict[int, float] = {}
        used_face: set[int] = set()

        # 1. Yang dikenali dari wajahnya.
        for j, (x, m, tid) in enumerate(r):
            i = tid2id.get(tid)
            if i is None or i in taken:
                continue
            taken[i] = m
            used_face.add(j)
            last[i] = x

        # 2. Sisanya dijodohkan dengan tempat duduk yang belum terisi.
        sisa = [i for i in range(k) if i not in taken]
        if sisa and len(used_face) < len(r):
            pairs = sorted(
                ((abs(x - centroids[i]), i, j)
                 for j, (x, _m, _t) in enumerate(r) if j not in used_face
                 for i in sisa),
                key=lambda t: t[0],
            )
            for _d, i, j in pairs:
                if i in taken or j in used_face:
                    continue
                x, m, _t = r[j]
                taken[i] = m
                used_face.add(j)
                last[i] = x

        for i in range(k):
            tracks[i].append(last[i])
            motions[i].append(taken.get(i, 0.0))
            seen[i].append(i in taken)
    return tracks, motions, seen


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
    Menahan target selama pembicara hanya bergoyang kecil, lalu MEMBUNTUTINYA
    begitu ia benar-benar berpindah.

    Dijalankan SEBELUM penghalusan, bukan sesudah: kalau sesudah, hasilnya
    berupa tangga yang justru harus dihaluskan lagi. Di sini deadzone hanya
    membentuk sinyal niat — filter berikutnya yang membuat perpindahannya mulus.

    Bentuk lamanya menahan sampai simpangannya melewati ambang, lalu melompat ke
    posisi baru dan menahan lagi. Dua akibatnya sama-sama terlihat. Wajahnya
    hampir tidak pernah di tengah: selama menahan, kotaknya tertinggal sampai
    sejauh satu deadzone penuh — 5,5% lebar, sekitar 70 piksel pada sumber
    1280 — dan itu persis "bingkainya tidak pas di tengah muka orangnya".
    Lalu tangga lompat-tahan-lompat itu, meski dihaluskan sesudahnya, tetap
    terbaca sebagai sentakan kecil yang berulang.

    Yang dipakai sekarang punya dua keadaan dengan histeresis. Saat MENAHAN,
    goyangan kecil diabaikan seperti sebelumnya. Begitu simpangannya melewati
    ambang masuk, ia berpindah ke MEMBUNTUTI dan targetnya menjadi posisi wajah
    yang sebenarnya — jadi kotaknya betul-betul di tengah, bukan tertinggal.
    Ia kembali menahan hanya setelah wajahnya diam kembali di dalam ambang
    keluar yang lebih rapat. Ambang keluar yang lebih kecil itulah yang mencegah
    keduanya bergantian tiap sampel di perbatasan.

    Diukur sendirian, perubahan bentuk ini kecil saja — galat p90 turun dari
    5,01% ke 4,9% lebar. Yang benar-benar memindahkan angkanya adalah lebar
    deadzone dan alpha di atasnya. Bentuk ini tetap dipakai karena ia menyatakan
    maksud yang benar: begitu orangnya sungguh berpindah, kotaknya menuju wajah
    itu sendiri, bukan ke tempat wajah itu berada satu ambang yang lalu.
    """
    if not values:
        return []
    exit_zone = deadzone * DEADZONE_EXIT_RATIO
    out = [values[0]]
    held = values[0]
    tracking = False
    for v in values[1:]:
        if tracking:
            # Berhenti membuntuti hanya setelah ia benar-benar tenang lagi.
            if abs(v - held) <= exit_zone:
                tracking = False
            held = v
        elif abs(v - held) > deadzone:
            tracking = True
            held = v
        out.append(held)
    return out


def _settle_subject(subject: list[Optional[int]]) -> list[Optional[int]]:
    """
    Membuang pergantian subjek yang terlalu pendek untuk dipercaya.

    Sela satu kata di tengah giliran orang lain bukan pergantian giliran, dan
    memperlakukannya sebagai pergantian membuat bingkai berkedip bolak-balik.
    Subjek baru baru diakui setelah bertahan MIN_SUBJECT_HOLD detik.
    """
    need = max(1, int(round(MIN_SUBJECT_HOLD * SAMPLE_FPS)))
    out: list[Optional[int]] = list(subject)
    n = len(subject)
    i = 0
    current: Optional[int] = subject[0] if subject else None
    while i < n:
        j = i
        while j < n and subject[j] == subject[i]:
            j += 1
        # Rentang [i, j) berisi satu nilai. Diterima kalau cukup panjang, atau
        # kalau ia memang kelanjutan dari subjek yang sedang berlaku.
        if subject[i] == current or (j - i) >= need:
            current = subject[i]
        for k in range(i, j):
            out[k] = current
        i = j
    return out


def _smooth(centers: list[Optional[float]], cuts: list[bool], *,
            source_w: int, crop_w: int,
            subject: Optional[list] = None) -> list[float]:
    """
    Mengubah jejak wajah mentah menjadi gerakan kamera yang enak dilihat.

    Rantainya: tahan-saat-hilang -> median -> deadzone -> EMA dua arah ->
    plafon kecepatan. Tiap potongan adegan difilter SENDIRI-SENDIRI, karena
    menghaluskan melewati potongan adegan berarti kamera akan mem-pan
    menyeberangi pergantian kamera — persis yang membuat hasilnya terlihat
    seperti melayang, bukan berpindah.

    Pergantian ORANG diperlakukan sama dengan potongan adegan, dan itu
    perbaikan yang paling terasa di seluruh berkas ini. Sebelumnya penghalus
    hanya mengenal potongan adegan, jadi ketika penutur berganti di dalam satu
    bidikan yang sama, plafon kecepatan memaksa kamera MEM-PAN dari wajah yang
    satu ke wajah yang lain: 0,10 lebar per detik berarti 128 piksel per detik
    pada sumber 1280, sehingga menyeberangi jarak 430 piksel antara dua kursi
    memakan 3,4 detik. Selama detik-detik itu bingkai tidak memuat siapa pun —
    ia menatap mikrofon di antara mereka.

    Terukur pada podcast empat orang sebelum perbaikan: 13,2% sampel punya
    kotak yang lebih dekat ke titik tengah dua wajah daripada ke wajah mana
    pun. Orang tidak mem-pan kepalanya dari satu lawan bicara ke lawan bicara
    lain; ia menoleh. Maka bingkainya berpindah, bukan meluncur.
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

    # Pecah menjadi rentang antar potongan adegan DAN pergantian subjek.
    breaks = {i for i, is_cut in enumerate(cuts) if is_cut and i > 0}
    if subject is not None:
        settled = _settle_subject(list(subject) + [None] * (len(filled) - len(subject)))
        for i in range(1, min(len(settled), len(filled))):
            if settled[i] != settled[i - 1]:
                breaks.add(i)
    bounds = sorted(breaks)
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


def _centers_from_speakers(centers, people, mapping, speaker_turns, n,
                           seen=None, cuts=None):
    """
    Jejak pusat crop yang mengikuti penutur aktif.

    Saat orangnya sedang tidak terlihat, posisinya ditahan — tapi hanya
    SEBENTAR, dan itu pembedaan yang menentukan.

    `_trace_people` menahan posisi terakhir tiap orang tanpa batas, jadi
    `people[p][i]` tidak pernah kosong setelah orang itu sekali terlihat.
    Pemeriksaan "kalau orangnya tidak terlihat, pakai aturan cadangan" karena
    itu tidak pernah sekali pun berjalan: yang dibaca selalu posisi lama yang
    ditahan. Akibatnya paling parah justru pada kasus yang paling mudah —
    close-up satu orang. Kamera memotong ke wajah A, penutur yang terpetakan
    adalah B, dan bingkai dengan patuh menunjuk kursi tempat B duduk beberapa
    detik lalu, yang di dalam bidikan ini hanya dinding. Terukur: dari 992
    sampel berwajah tunggal, 37,7% kotaknya tidak memuat wajah yang ada.

    Dengan `seen`, dua keadaan itu akhirnya bisa dibedakan. Kepala yang menoleh
    sesaat: tahan. Kamera yang sudah pindah: bingkai apa yang sungguh ada di
    layar, dan lepaskan subjeknya supaya penghalus memperlakukannya sebagai
    perpindahan, bukan sebagai pan.
    """
    active: list = [None] * n
    for t0, t1, sp in speaker_turns:
        lo = max(0, int(t0 * SAMPLE_FPS))
        hi = min(n, int(t1 * SAMPLE_FPS) + 1)
        for i in range(lo, hi):
            active[i] = sp

    grace = max(1, int(round(UNSEEN_GRACE * SAMPLE_FPS)))

    # Awal bidikan yang sedang berjalan, per sampel. Masa tenggang tidak boleh
    # menyeberanginya: tenggang itu ada untuk menjembatani kepala yang menoleh
    # DI DALAM satu bidikan, dan sebuah potongan mengakhiri bidikan itu. Di
    # seberang potongan, posisi lama seseorang bukan keterangan yang usang —
    # ia bukan keterangan sama sekali.
    shot_start = [0] * n
    if cuts:
        awal = 0
        for i in range(n):
            if i < len(cuts) and cuts[i] and i > 0:
                awal = i
            shot_start[i] = awal

    def terlihat(person: int, i: int) -> bool:
        """Terlihat sekarang, atau baru saja di dalam bidikan yang sama."""
        if seen is None or person >= len(seen):
            return people[person][i] is not None
        lane = seen[person]
        lo = max(shot_start[i] if i < len(shot_start) else 0, i - grace + 1)
        return any(lane[j] for j in range(max(0, lo), min(i + 1, len(lane))))

    out: list[Optional[float]] = []
    subject: list[Optional[int]] = []
    held: Optional[int] = None
    for i in range(n):
        sp = active[i]
        if sp is not None and sp in mapping:
            person = mapping[sp]
            if terlihat(person, i):
                held = person
            elif held is not None and not terlihat(held, i):
                held = None
            if held is not None and people[held][i] is not None:
                out.append(people[held][i])
                subject.append(held)
            else:
                out.append(centers[i])
                subject.append(None)
        else:
            held = None
            out.append(centers[i])
            subject.append(None)
    return out, subject


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

    # Nilainya dinyatakan sebagai statistik-t: selisih rata-rata DIBAGI galat
    # bakunya, bukan selisih mentah.
    #
    # Bedanya bukan kosmetik. Selisih mentah pada giliran yang cuma berisi
    # empat kalimat terlihat persis sama besarnya dengan selisih pada giliran
    # sepanjang dua menit, padahal yang pertama hampir seluruhnya kebetulan.
    # Dengan galat baku ikut dibagi, bukti yang tipis menghasilkan angka kecil
    # dengan sendirinya — dan itulah yang membuat ambang di bawah bisa berarti
    # "cukup bukti", bukan sekadar "cukup besar".
    # Sampel berturutan TIDAK saling bebas, dan mengabaikannya membuat setiap
    # pasangan terlihat jauh lebih meyakinkan daripada yang sebenarnya.
    # Gerakan mulut sudah dihaluskan 0,75 detik sebelum sampai ke sini;
    # terukur pada 41 klip, autokorelasi lag-1-nya +0,34. Jumlah sampel bebas
    # yang sesungguhnya karena itu hanya (1-r)/(1+r) kali jumlah bingkai —
    # sekitar separuhnya. Tanpa koreksi ini, ambang bukti di bawah akan
    # meluluskan hampir semua pasangan, termasuk yang lahir dari kebetulan.
    def n_efektif(v) -> float:
        if len(v) < 8:
            return float(len(v))
        a, b = v[:-1], v[1:]
        sa, sb = a.std(), b.std()
        if sa < 1e-9 or sb < 1e-9:
            return float(len(v))
        r = float(np.clip(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb),
                          -0.95, 0.95))
        return max(2.0, len(v) * (1.0 - r) / (1.0 + r))

    score = np.full((k, len(speakers)), -np.inf)
    for i in range(k):
        for j in range(len(speakers)):
            inside = mot[i][active[j] & vis[i]]
            outside = mot[i][(~active[j]) & vis[i]]
            if len(inside) < 8 or len(outside) < 8:
                continue
            galat = math.sqrt(inside.var() / n_efektif(inside)
                              + outside.var() / n_efektif(outside))
            beda = float(inside.mean() - outside.mean())
            score[i][j] = beda / galat if galat > 1e-9 else 0.0

    # Susunan TERBAIK secara keseluruhan, bukan serakah. Serakah mengunci
    # pasangan terkuat lebih dulu dan pasangan berikutnya tinggal menerima
    # sisanya, yang bisa keliru padahal susunan lain memberi total lebih tinggi.
    # Dengan dua sampai enam orang, mencoba semuanya hanya beberapa ratus
    # kemungkinan.
    #
    # Dicacah dari sisi yang LEBIH SEDIKIT, dan itu bukan kerapian.
    # `permutations(range(k), n)` menghasilkan daftar KOSONG begitu n > k, jadi
    # versi sebelumnya menyerah diam-diam setiap kali suaranya lebih banyak
    # daripada wajahnya — keadaan yang biasa saja: diarisasi memecah satu orang
    # jadi dua, atau ada yang bicara dari luar kamera. Terukur pada klip empat
    # penutur dengan tiga wajah: pemetaannya kembali kosong, sehingga bingkai
    # kehilangan petunjuk siapa-bicara-kapan dan editor kehilangan lajur per
    # orang. Sekarang yang lebih sedikit yang dicacah, dan sisi yang berlebih
    # sekadar tidak kebagian pasangan.
    ns = len(speakers)
    best, best_total = None, None
    if ns <= k:
        for perm in itertools.permutations(range(k), ns):
            vals = [score[perm[j]][j] for j in range(ns)]
            if any(not np.isfinite(v) for v in vals):
                continue
            total = float(sum(vals))
            if best_total is None or total > best_total:
                best, best_total = {j: perm[j] for j in range(ns)}, total
    else:
        # Lebih banyak suara daripada wajah: yang dipilih adalah k penutur mana
        # yang paling meyakinkan, sisanya sengaja tidak dipetakan.
        for perm in itertools.permutations(range(ns), k):
            vals = [score[i][perm[i]] for i in range(k)]
            if any(not np.isfinite(v) for v in vals):
                continue
            total = float(sum(vals))
            if best_total is None or total > best_total:
                best, best_total = {perm[i]: i for i in range(k)}, total
    if not best:
        return {}

    # Tiap penutur diterima sendiri-sendiri: satu pasangan lemah tidak ikut
    # terbawa hanya karena pasangan lain di susunan yang sama kuat.
    #
    # Ambangnya jauh lebih tinggi daripada "lebih besar dari nol", dan itu
    # perubahan yang paling penting di fungsi ini.
    #
    # Diukur dengan uji belah-dua pada 41 klip dari tiga podcast — pemetaan
    # dihitung terpisah di paruh pertama dan paruh kedua tiap klip, lalu
    # diperiksa apakah keduanya menunjuk orang yang sama. Dengan ambang lama,
    # pemetaan dibuat untuk 31% penutur dan hanya 50% yang sepakat: untuk
    # pilihan antara dua wajah, itu persis selemah lempar koin. Pemetaan
    # seperti itu bukan bantuan — ia mengunci bingkai ke orang yang salah
    # sepanjang klip, dengan keyakinan penuh.
    #
    # Yang hilang karena ambang ini tidak sebesar kelihatannya. Diukur pada
    # 8.953 sampel dari tiga video, mengikuti penutur TIDAK memperbaiki
    # komposisi sama sekali dibandingkan mengikuti bidikan penyuntingnya
    # sendiri (98,7% lawan 99,8% wajah di dalam kotak). Podcast yang sudah
    # dipotong rapi memang sudah menjawab pertanyaannya: saat A bicara,
    # penyuntingnya memotong ke A. Mengikuti penutur hanya perlu mengambil
    # alih ketika ia benar-benar tahu sesuatu yang belum dikatakan gambar.
    dipakai = {speakers[j]: i for j, i in best.items()
               if score[i][j] >= MIN_SPEAKER_EVIDENCE}
    if not dipakai:
        log.info("Bukti wajah↔suara terlalu tipis (t maks %.1f) — bingkai "
                 "mengikuti bidikan aslinya",
                 max((score[i][j] for j, i in best.items()
                      if np.isfinite(score[i][j])), default=float("nan")))
    return dipakai


def _hold_person(centers: list, track: list) -> list:
    """
    Titik tengah yang selalu menunjuk satu orang.

    Saat orangnya tidak terlihat, posisi terakhirnya DITAHAN — bukan melompat
    ke wajah lain, yang justru hal yang sedang dihindari.
    """
    held: Optional[float] = None
    out: list = []
    for i in range(len(centers)):
        v = track[i] if i < len(track) else None
        if v is not None:
            held = v
        out.append(held if held is not None else centers[i])
    return out


def _apply_person_keys(centers: list, people: list, keys: list,
                       subject: list) -> tuple[list, list]:
    """
    Menerapkan tanda linimasa: dari tiap tanda sampai tanda berikutnya, bingkai
    menunjuk orang yang disebut tanda itu.

    Tanda dengan `person` kosong berarti "kembalikan ke otomatis di sini", jadi
    pengguna bisa membetulkan satu bagian yang meleset lalu melepaskannya lagi
    tanpa menandai ulang sisa klipnya.
    """
    clean = sorted(
        ({"t": max(0.0, float(k.get("t", 0.0))), "person": k.get("person")}
         for k in keys if isinstance(k, dict)),
        key=lambda k: k["t"],
    )
    if not clean:
        return centers, subject

    # Tiap orang ditahan lebih dulu di seluruh klip, lalu potongannya diambil.
    # Menghitungnya per sampel akan kehilangan posisi terakhir yang ditahan
    # setiap kali tanda berganti.
    held = {}
    out = list(centers)
    subj = list(subject)
    for idx, key in enumerate(clean):
        person = key["person"]
        start = int(math.floor(key["t"] * SAMPLE_FPS))
        stop = (int(math.floor(clean[idx + 1]["t"] * SAMPLE_FPS))
                if idx + 1 < len(clean) else len(centers))
        if person is None or not (0 <= int(person) < len(people)):
            # Tanda kosong berarti "lepaskan kembali ke otomatis di sini".
            # Subjeknya ikut dikosongkan supaya penghalus tahu kendalinya
            # berpindah tangan dan memperlakukannya sebagai perpindahan.
            for i in range(max(0, start), min(stop, len(centers))):
                subj[i] = None
            continue
        person = int(person)
        if person not in held:
            held[person] = _hold_person(centers, people[person])
        for i in range(max(0, start), min(stop, len(centers))):
            out[i] = held[person][i]
            subj[i] = person
    log.info("Bingkai memakai %d tanda linimasa dari pengguna", len(clean))
    return out, subj


# Hasil pemindaian wajah, dikunci pada berkas dan susunan segmennya.
#
# Memindai ulang setiap kali rencana diminta adalah pemborosan yang terasa:
# lima detik per permintaan, sementara satu-satunya yang berubah biasanya adalah
# tanda arah bingkai dari pengguna — dan tanda itu tidak mengubah satu pun wajah
# yang terdeteksi. Memisahkan kedua tahap membuat menandai terasa seketika,
# bukan seperti memulai analisis baru.
_SCAN_CACHE: "OrderedDict[tuple, tuple]" = OrderedDict()
_SCAN_CACHE_MAX = 6

# Berapa detik di luar batas klip yang ikut dipindai.
#
# Menggeser batas klip adalah pekerjaan yang dilakukan berkali-kali berturut-
# turut — beberapa detik ke sana, beberapa detik ke sini, sampai kalimatnya
# jatuh pas. Tanpa bantalan ini, tiap geseran sekecil apa pun berarti memindai
# ulang seluruh wajah dari nol, dan lajur bingkainya lenyap selama enam detik
# tiap kali. Dengan bantalan, geseran di dalam rentang ini hanya memotong
# hasil yang sudah ada.
SCAN_PAD_SECONDS = 6.0


def _slice_scan(value: tuple, cached: list[dict], wanted: list[dict]):
    """
    Mengambil bagian hasil pindai yang sesuai rentang klip yang lebih pendek.

    Sah karena penjejakan berjalan maju: keadaan penjejak pada sampel ke-k sama
    saja apakah pemindaian berhenti sesudahnya atau tidak. Memotong ujung berarti
    membuang ekornya; memotong awal berarti membuang kepalanya, dan jejak yang
    tersisa justru sudah matang karena sempat melihat bagian sebelumnya.
    """
    if len(cached) != len(wanted):
        return None
    centers, cuts, people, motion, seen, _ = value

    keep: list[int] = []
    base = 0
    for c, w in zip(cached, wanted):
        n = max(1, int(round((c["end"] - c["start"]) * SAMPLE_FPS)))
        if w["start"] < c["start"] - 1e-6 or w["end"] > c["end"] + 1e-6:
            return None
        lo = base + int(round((w["start"] - c["start"]) * SAMPLE_FPS))
        hi = base + int(round((w["end"] - c["start"]) * SAMPLE_FPS))
        keep.extend(range(max(base, lo), min(base + n, max(lo + 1, hi))))
        base += n

    if not keep or keep[-1] >= len(centers):
        return None

    def pick(seq):
        return [seq[i] for i in keep]

    sub_centers = pick(centers)
    sub_cuts = pick(cuts)
    # Sampel pertama rentang baru selalu awal adegan: tidak ada yang mendahului
    # di dalam klip ini, jadi crop tidak boleh mem-pan masuk dari mana pun.
    if sub_cuts:
        sub_cuts[0] = True
    ada = sum(1 for c in sub_centers if c is not None)
    return (sub_centers, sub_cuts,
            [pick(t) for t in people], [pick(t) for t in motion],
            [pick(t) for t in seen],
            ada / len(sub_centers) if sub_centers else 0.0)


def _scan_scene(src: Path, segments: list[dict], source_w: int, source_h: int,
                duration: float = 0.0):
    """
    Memindai wajah pada klip, lalu mengelompokkannya jadi orang.

    Tahap ini mahal dan sepenuhnya ditentukan oleh berkas dan susunan segmennya,
    jadi hasilnya disimpan. Tahap sesudahnya — mencocokkan dengan penutur,
    menerapkan tanda pengguna, menghaluskan — murah dan dihitung ulang tiap kali.

    Yang dipindai sengaja LEBIH PANJANG dari yang diminta, lalu dipotong. Dengan
    begitu, menggeser batas klip beberapa detik — pekerjaan yang dilakukan
    berulang-ulang sampai kalimatnya jatuh pas — memakai hasil yang sudah ada
    alih-alih memindai ulang dari nol.
    """
    try:
        stamp = src.stat().st_mtime_ns
    except OSError:
        stamp = 0
    head = (str(src), stamp, source_w, source_h)

    # Sudah ada pindaian yang MENCAKUP rentang ini? Potong saja.
    for key in reversed(list(_SCAN_CACHE)):
        if key[:4] != head:
            continue
        cached = [{"start": a, "end": b} for a, b in key[4]]
        got = _slice_scan(_SCAN_CACHE[key], cached, segments)
        if got is not None:
            _SCAN_CACHE.move_to_end(key)
            return got

    # Belum ada: pindai dengan bantalan, supaya geseran berikutnya tertampung.
    limit = duration if duration > 0 else float("inf")
    padded = [{"start": max(0.0, s["start"] - SCAN_PAD_SECONDS),
               "end": min(limit, s["end"] + SCAN_PAD_SECONDS)} for s in segments]

    try:
        centers, cuts, raw, embeds = _detect_centers(src, padded, source_w, source_h)
    except Exception as e:  # deteksi tidak boleh menjatuhkan render
        log.warning("Deteksi wajah gagal, memakai blur-pad: %s", e)
        return None
    if not centers:
        return None

    coverage = sum(1 for c in centers if c is not None) / len(centers)
    try:
        # Daftar wajah tetap milik VIDEO ini, bukan milik klipnya: nomor orang
        # harus sama di klip mana pun, karena tanda arah bingkai menyimpan nomor.
        people, motion, seen = group_people(raw, source_w, embeds,
                                            roster=_roster_for(head))
    except Exception as e:      # pengelompokan tidak boleh menjatuhkan render
        log.warning("Pengelompokan orang gagal: %s", e)
        people, motion, seen = [], [], []

    value = (centers, cuts, people, motion, seen, coverage)
    key = head + (tuple((round(s["start"], 3), round(s["end"], 3)) for s in padded),)
    _SCAN_CACHE[key] = value
    while len(_SCAN_CACHE) > _SCAN_CACHE_MAX:
        _SCAN_CACHE.popitem(last=False)

    got = _slice_scan(value, padded, segments)
    return got if got is not None else value


def plan_reframe(source_video_path: str, segments: list[dict], *,
                 aspect_ratio: str = "9:16",
                 track_only: bool = False,
                 speaker_turns: Optional[list] = None,
                 lock_person: Optional[int] = None,
                 person_keys: Optional[list] = None) -> Optional[ReframePlan]:
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

    scene = _scan_scene(src, segments, source_w, source_h,
                        duration=float(info.get("duration") or 0.0))
    if scene is None:
        return None
    centers, cuts, people, motion, seen, coverage = scene

    # Pengguna menunjuk sendiri. Ini mengalahkan segalanya, dan memang harus:
    # pencocokan otomatis bisa keliru — mulut yang tertutup mikrofon hampir
    # tidak bergerak di gambar — dan saat itu terjadi, yang dibutuhkan bukan
    # tebakan yang lebih pintar melainkan cara untuk membetulkannya.

    # Siapa penutur mana dihitung LEBIH DULU, di luar percabangan.
    #
    # Bukan sekadar kerapian: editor memakai peta ini untuk menaruh baris
    # subtitle pada lajur orangnya, dan lajur itu harus tetap benar meskipun
    # pengguna sedang mengunci bingkainya ke satu orang. Dihitung di dalam salah
    # satu cabang, ia akan lenyap persis saat penggunanya paling banyak melihat
    # linimasa.
    mapping: dict[int, int] = {}
    if speaker_turns and people:
        mapping = assign_faces_to_speakers(people, motion, speaker_turns,
                                           len(centers))

    # Siapa yang sedang dibidik, per sampel. Inilah yang membedakan "orang ini
    # bergerak" dari "sekarang giliran orang lain" — dua hal yang terlihat sama
    # dari deretan angka saja, tapi menuntut gerakan kamera yang berlawanan.
    subject: list = [None] * len(centers)

    if lock_person is not None and 0 <= lock_person < len(people):
        centers = _hold_person(centers, people[lock_person])
        subject = [lock_person] * len(centers)
        log.info("Bingkai dikunci ke orang %d oleh pengguna", lock_person + 1)

    # Kalau kita tahu siapa bicara kapan, crop mengikuti WAJAH ORANG ITU dan
    # bukan wajah yang kebetulan paling besar. Tanpa data itu — atau kalau
    # pasangannya tidak meyakinkan — aturan lama tetap berlaku, jadi rekaman
    # berpotong kamera yang sudah benar tidak ikut diubah.
    elif mapping:
        centers, subject = _centers_from_speakers(centers, people, mapping,
                                                  speaker_turns, len(centers),
                                                  seen=seen, cuts=cuts)
        log.info("Wajah dicocokkan ke penutur: %s",
                 {f"penutur {k}": f"orang {v + 1}" for k, v in mapping.items()})

    # Tanda tangan pengguna di linimasa mengalahkan keduanya, tapi hanya pada
    # rentang yang benar-benar ditandainya. Di luar rentang itu hasil otomatis
    # di atas tetap berlaku — membetulkan satu kesalahan tidak boleh berarti
    # mengambil alih seluruh klip dengan tangan.
    if person_keys and people:
        centers, subject = _apply_person_keys(centers, people, person_keys, subject)

    smoothed = _smooth(centers, cuts, source_w=source_w, crop_w=crop_w,
                       subject=subject)

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
    plan.people, plan.people_motion, plan.people_seen = people, motion, seen
    plan.speaker_faces = mapping
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
