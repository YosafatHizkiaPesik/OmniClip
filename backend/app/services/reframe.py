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

import itertools
import logging
import math
import statistics
import os
import subprocess
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..config import MODELS_DIR
from .proses import popen
from .paths import ffpath

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
SFACE_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_recognition_sface/face_recognition_sface_2021dec.onnx")


def _pastikan_sface() -> bool:
    """
    Mengunduh pengenal wajah saat pertama dipakai. 37 MB, sekali seumur
    pemasangan.

    Dulu berkas ini hanya bisa didapat lewat perintah curl yang tertulis di
    requirements.txt — cukup saat satu-satunya pengguna adalah orang yang
    menulis kodenya. Begitu OmniClip dibagikan sebagai aplikasi, "ada perintah
    di sebuah berkas teks" berarti pengenal wajah tidak akan pernah menyala di
    komputer siapa pun, dan penomoran orang selamanya memakai tempat duduk.
    Modelnya terlalu besar untuk ikut dibundel, jadi ia diambil seperti model
    penutur: sendiri, sekali, saat pertama dibutuhkan.
    """
    if SFACE_PATH.is_file() and SFACE_PATH.stat().st_size > 1_000_000:
        return True
    import urllib.request
    tmp = SFACE_PATH.with_suffix(".part")
    try:
        log.info("Mengunduh model pengenal wajah (37 MB)…")
        SFACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(SFACE_URL, timeout=180) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        os.replace(tmp, SFACE_PATH)
        log.info("Model pengenal wajah siap.")
        return True
    except Exception as e:                       # jaringan mati, disk penuh, dst.
        log.warning("Gagal mengunduh pengenal wajah: %s", str(e)[:200])
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False

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

# --- Wajah yang tidak hidup ---------------------------------------------------
# Detektor menemukan BENTUK wajah, bukan orang. Logo bergambar wajah, lukisan
# dan foto di dinding, sampul buku, bahkan rimbun daun yang kebetulan berpola
# dua mata dan satu mulut, semuanya lolos — dan bila kebetulan lebih besar atau
# lebih dekat ke posisi sebelumnya, bingkai mengikutinya.
#
# Keyakinan detektor TIDAK bisa memisahkannya: terukur pada 283 jejak dari 12
# video, daun tercatat 0,65 dan 0,69, sementara wajah asli yang menoleh turun
# sampai 0,69. Yang memisahkannya bersih adalah tanda hidup: seberapa berubah
# petak wajah itu terhadap dirinya sendiri setengah detik sebelumnya, setelah
# kecerahannya dinormalkan. Orang yang diam mendengarkan tetap berkedip,
# bernapas, dan bergeser sedikit; gambar tidak.
HIDUP_JEDA = 4              # sampel antar perbandingan: 0,5 detik pada 8 Hz
HIDUP_PETAK = 24            # sisi petak abu-abu yang dibandingkan
HIDUP_MIN_N = 6             # perbandingan minimum sebelum jejak dinilai (±3 dtk)
# Median di bawah ini = bukan orang hidup. Diukur di kotak yang tetap (lihat
# blok "Tanda hidup"), orang sungguhan yang diam mendengarkan terendah 0,07 pada
# 30 klip dari 10 video; gambar 0,00-0,05. Ambang diletakkan di bawah celah itu
# supaya orang tidak pernah ikut terbuang — gambar yang lolos ditangkap oleh
# aturan tempat di bawah.
HIDUP_AMBANG = 0.05
# Jejak yang terlalu pendek untuk dinilai sendiri ikut dinyatakan mati bila ia
# berada TEPAT di tempat jejak yang sudah terbukti mati. Kamera di atas tripod
# kembali ke bidikan yang sama berulang kali, dan lukisan di belakangnya
# muncul di koordinat yang sama setiap kali — seringkali hanya dua detik.
HIDUP_TEMPAT = 0.012        # jarak pusat, pecahan lebar bingkai
# Aturan tempat juga berlaku untuk jejak PANJANG yang tampak hidup, asal
# posisinya diam seperti gambar. Wajah pada iklan sponsor yang ditempel di
# pojok video terukur 0,07-0,11 — mikrofon dan kepala orang di depannya
# sesekali menutupi bagian bawahnya — padahal jejak lain di koordinat yang
# sama persis bernilai 0,00. Orang sungguhan tidak duduk tepat di koordinat
# dan ukuran sebuah gambar lalu diam di situ tanpa bergeser sepiksel pun.
HIDUP_DIAM = 0.003          # sebaran posisi maksimum, pecahan lebar bingkai
HIDUP_UKURAN = 0.25         # beda lebar wajah maksimum terhadap gambar mati
# Tempat gambar yang sudah terbukti mati, per video. Iklan yang sama muncul
# berkali-kali sepanjang video; klip berikutnya tidak perlu membuktikannya lagi.
_TEMPAT_MATI: dict[str, list[tuple[float, float, float]]] = {}

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
# Plafon kecepatan pan, lebar-per-detik.
#
# Naik dari 0,10 ke 0,16 pada 25 September 2026, karena 0,10 terukur MENAHAN
# kamera di belakang wajahnya. Terlapor sebagai "ada 1 detik bingkai tidak
# mengikuti wajah", dan angkanya persis itu: pada podcast Dokter Tirta, tujuh
# sampel berturut-turut (0,88 detik) meleset lebih dari 8% lebar layar, dan
# pada ketujuhnya kamera berjalan tepat di plafonnya. Perpindahan yang diminta
# 15,9% lebar; pada 0,10 itu butuh 1,6 detik.
#
# Diukur pada empat podcast, 30 detik tiap klip:
#
#   plafon   lepas >8%   galat rata2   p90     kekasaran
#   0,10        2,9%        1,72%      3,63%     0,4124
#   0,16        2,5%        1,59%      3,44%     0,4187
#   0,22        2,5%        1,59%      3,44%     0,4200
#
# Di atas 0,16 tidak ada yang berubah lagi: plafonnya berhenti mengikat. Tiga
# klip lain tidak terpengaruh sama sekali, karena di sana ia memang tidak
# pernah mengikat. Ongkosnya 1,5% kekasaran, dan yang dibeli adalah hampir
# satu detik bingkai yang tidak lagi tertinggal.
MAX_SPEED_RATIO = 0.16
SCENE_CUT_DISTANCE = 0.5   # jarak Bhattacharyya histogram HSV
MEDIAN_WINDOW = 7          # buang deteksi meleset sesaat sebelum difilter
# Jarak minimum antar BATAS bidikan, dalam detik.
#
# Tiap batas (potongan adegan atau pergantian penutur) memulai rentang filter
# yang baru, dan rentang baru berarti kamera berpindah seketika. Itu memang
# yang diinginkan sekali-sekali. Yang tidak diinginkan: batas yang datang
# beruntun.
#
# Terukur 25 September 2026 pada tiga podcast, 30 detik tiap klip, dengan
# kekasaran = rata-rata |percepatan| bingkai sebagai persen lebar sumber:
#
#   podcast Tirta, 12 batas dalam 30 dtk, sela terpendek 0,38 dtk
#     tanpa jarak minimum   galat 1,59%  p90 3,56%  kekasaran 0,5722
#     jarak minimum 2 dtk   galat 1,72%  p90 3,63%  kekasaran 0,4124
#     jarak minimum 3 dtk   galat 2,18%  p90 5,30%  kekasaran 0,1998
#
# Dua detik menurunkan getaran 28% dengan ongkos ketepatan 0,13 poin persen.
# Tiga detik menurunkannya 65%, tapi ongkosnya naik jadi 0,59 poin dan p90
# melewati 5% — itu kembali ke keluhan lama, "bingkainya tidak pas di muka
# orangnya". Jadi dua.
#
# Yang menentukan getaran BUKAN filternya. Diukur tahap demi tahap pada klip
# yang sama: satu rentang utuh yang difilter penuh berkekasaran 0,0416,
# sedangkan hasil `_smooth` yang memecahnya per bidikan berkekasaran 0,5722.
# Empat belas kali lipat, dan seluruhnya datang dari batas rentangnya.
JEDA_BATAS_MIN = 2.0
# Perpindahan target yang terlalu jauh untuk di-PAN, sebagai pecahan lebar
# sumber. Di atas ini bingkainya berpindah seketika, bukan meluncur.
#
# Inilah "ada 1 detik bingkai tidak mengikuti wajah" yang dilaporkan 25
# September 2026. Ditelusuri sampel demi sampel pada podcast Dokter Tirta:
#
#   detik   wajah   kotak   galat
#   22,50     474     496    1,2%
#   23,50     488     588    5,2%
#   24,00     470     717   12,8%
#   24,12    1013     755   13,4%   <- penutur berganti, 543 px, 28% lebar
#   24,62     967     888    4,1%
#
# Dua hal sekaligus. Penuturnya berganti DI DALAM satu bidikan, tanpa potongan
# adegan, jadi tidak ada yang menandainya sebagai perpindahan. Dan penghalus
# dua arah bersifat non-kausal: ia mulai bergerak 1,6 detik SEBELUM
# perpindahannya, jadi kotaknya sudah meninggalkan orang pertama sebelum orang
# kedua mulai bicara. Sepanjang itu bingkainya tidak memuat siapa pun.
#
# Modul ini sudah memegang aturannya untuk pergantian penutur yang diketahui:
# orang tidak mem-pan kepalanya dari satu lawan bicara ke lawan bicara lain, ia
# menoleh. Yang kurang hanya cara mengenalinya tanpa label penutur, dan jejak
# wajahnya sendiri sudah cukup: 28% lebar dalam satu sampel bukan gerakan
# kepala, itu orang lain.
#
# Diukur pada empat podcast, 30 detik tiap klip. Ambang 5%, 8%, dan 12%
# memberi hasil yang sama persis, karena yang dipisahkan memang berjarak jauh:
#
#            lepas >8%   galat rata2   p90
#   tanpa       2,5%        1,59%     3,44%
#   dengan      0,0%        1,18%     2,28%
#
# Tiga klip lain tidak berubah sama sekali: di sana memang tidak ada
# perpindahan sebesar itu. Angka "kekasaran" naik dari 0,42 ke 0,62, dan itu
# BUKAN kemunduran: ukuran itu menghitung percepatan, dan sebuah potongan yang
# disengaja memang percepatan tak hingga. Yang dibeli dengan itu adalah nol
# detik bingkai yang tidak memuat siapa pun.
LOMPAT_POTONG = 0.10
# Sebuah bidikan harus muncul di sekian bagian sampel sebelum jumlah wajahnya
# dianggap menentukan berapa orang yang ada.
ROSTER_MIN_SHARE = 0.05

# Seberapa terpisah sidik wajah harus, sebelum JUMLAH orang boleh ditentukan
# olehnya dan bukan oleh apa yang sungguh terlihat di layar.
#
# Diukur sebagai koherensi di dalam kelompok dikurangi kemiripan antar
# kelompok, pada klip pertama tiga rekaman:
#
#   podcast empat orang : dalam 0,727  antar 0,165  selisih 0,562
#   podcast dua dokter  : dalam 0,670  antar 0,264  selisih 0,406
#   rekaman lapangan    : dalam 0,470  antar 0,209  selisih 0,261
#
# Yang terakhir itu rekaman sungai: wajahnya kecil, sering menyamping, kadang
# buram karena gerakan. Di situ pengenalan wajah memecah DUA orang menjadi
# lima, dan kekeliruannya tidak bisa diperbaiki dengan menggeser ambang —
# terukur, kemiripan antar nomor yang ternyata orang yang sama adalah 0,133,
# 0,140, dan 0,175, sementara antar orang yang benar-benar berbeda 0,262,
# 0,274, dan 0,279. Kedua sebaran itu bertumpang tindih seluruhnya, jadi tidak
# ada satu pun garis yang memisahkannya.
IDENTITY_TRUST_MARGIN = 0.35

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

# Bukti potongan kamera untuk pemetaan penutur — lihat assign_faces_to_speakers.
# Berapa lama bingkai tetap pada pembicara terakhir saat tidak ada yang bicara.
JEDA_TAHAN_SECONDS = 2.5
SOLO_MIN_SECONDS = 2.0       # minimal sekian detik tampil sendirian saat ia bicara
SOLO_PORSI_PENUTUR = 0.7     # dari bidikan tunggal selama gilirannya, porsi orang ini
SOLO_PORSI_ORANG = 0.6       # dari saat orang ini sendirian, porsi giliran penutur ini

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
    # Tinggi dan ukuran wajah tiap orang per sampel, sejajar dengan `people`:
    # (pusat_y, lebar_wajah) dalam piksel sumber, atau None saat tidak terlihat.
    #
    # `people` hanya menyimpan posisi mendatar — cukup untuk menggeser crop
    # setinggi bingkai, tapi tidak cukup untuk MEMBINGKAI seseorang: bidikan
    # reaksi satu wajah, atau layar terbagi yang menumpuk wajah beberapa orang,
    # butuh tahu setinggi dan sebesar apa wajahnya.
    people_box: list[list[Optional[tuple[float, float]]]] = field(default_factory=list)
    # Detik (waktu klip) tempat kamera berpindah. Sudah dihitung untuk
    # penghalusan; dibawa keluar karena momen — jumpscare, pergantian bidikan
    # ke reaksi — sering jatuh tepat di situ.
    cut_times: list[float] = field(default_factory=list)
    # Siapa yang sedang dibingkai pada tiap sampel, sejajar dengan `people`.
    # None berarti "tidak menunjuk siapa-siapa" — bingkai memakai titik tengah
    # semua wajah. Dikeluarkan supaya keputusan yang paling sering salah di
    # seluruh sistem ini bisa DIUKUR dari luar, bukan hanya dirasakan.
    subject: list[Optional[int]] = field(default_factory=list)

    def kotak_orang(self, person: int, t0: float, t1: float,
                    aspek: float = 9 / 16, tinggi_wajah: float = 3.6,
                    seluruh_klip: bool = False) -> Optional[dict]:
        """
        Kotak sumber (persen) yang membingkai wajah dan bahu satu orang.

        `aspek` = lebar/tinggi sel tujuan, supaya kotaknya tidak perlu diregang.
        Tingginya `tinggi_wajah` kali lebar wajah; pusat wajah diletakkan di 45%
        atas kotak. Dengan 3,0 dan 40%, topi terpotong dan orang yang bersandar
        sambil tertawa keluar separuh dari bidikan 9:16 — terlihat pada pita
        uji podcast Sule.
        Posisinya median selama [t0, t1]. Bila orang itu tidak terlihat di
        rentang itu hasilnya None — kecuali `seluruh_klip`, yang memakai
        seluruh klip. Jangan pakai itu untuk bidikan di tengah klip berpindah
        kamera: posisi dari bidikan lain menaruh kotaknya di tempat orang lain.
        Rentangnya juga sebaiknya tidak melintasi perpindahan kamera — lihat
        `sutradara_ai._potongan`.
        """
        if not (0 <= person < len(self.people_box)) or not self.source_w:
            return None
        xs = self.people[person] if person < len(self.people) else []
        kotak = self.people_box[person]

        def ambil(lo: int, hi: int):
            return [(xs[i], kotak[i][0], kotak[i][1]) for i in range(max(0, lo), min(hi, len(kotak)))
                    if kotak[i] is not None and i < len(xs) and xs[i] is not None]

        titik = ambil(int(t0 * SAMPLE_FPS), int(t1 * SAMPLE_FPS) + 1)
        if not titik and seluruh_klip:
            titik = ambil(0, len(kotak))
        if not titik:
            return None
        cx = statistics.median(p[0] for p in titik)
        cy = statistics.median(p[1] for p in titik)
        lebar_wajah = statistics.median(p[2] for p in titik)
        sw, sh = float(self.source_w), float(self.source_h)
        h = min(sh, max(lebar_wajah * tinggi_wajah, 48.0))
        w = h * aspek
        if w > sw:                      # sel yang sangat lebar: batasi lebarnya
            w = sw
            h = w / aspek
        x = min(max(cx - w / 2, 0.0), sw - w)
        y = min(max(cy - 0.45 * h, 0.0), sh - h)
        return {"x": round(100 * x / sw, 3), "y": round(100 * y / sh, 3),
                "w": round(100 * w / sw, 3), "h": round(100 * h / sh, 3)}

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
    # Salinan analisis 1280 px bila sudah ada — lihat services/proksi.py.
    # Pada sumber 4K VP9 inilah beda antara setengah menit dan dua detik.
    from .proksi import untuk_analisis
    dibaca = untuk_analisis(src)
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
           "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(dibaca),
           "-vf", f"fps={SAMPLE_FPS},scale={width}:{height}",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    frame_bytes = width * height * 3
    proc = popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
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
                 "misses", "tid", "emb", "emb_n", "emb_at", "tajam", "yakin",
                 "rujukan", "rujukan_at", "rujukan_kotak")

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
        # Ketajaman dan keyakinan detektor, dihaluskan sepanjang jejak.
        # Dipakai untuk membedakan orangnya dari PANTULANNYA di kaca.
        self.tajam = 0.0
        self.yakin = 0.0
        # Petak wajah setengah detik lalu, pembanding tanda hidup.
        self.rujukan = None
        self.rujukan_at = -10**9
        # Kotak tempat petak pembanding itu diambil.
        self.rujukan_kotak = None


def _petak_hidup(frame, f, sw: int, sh: int):
    """Petak abu-abu wajah yang kecerahan dan kontrasnya dinormalkan, atau None."""
    import cv2
    import numpy as np

    x, y, w, h = float(f[0]), float(f[1]), float(f[2]), float(f[3])
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(sw, int(x + w)), min(sh, int(y + h))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    abu = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    p = cv2.resize(abu, (HIDUP_PETAK, HIDUP_PETAK),
                   interpolation=cv2.INTER_AREA).astype(np.float32)
    return (p - float(p.mean())) / (float(p.std()) + 1e-6)


def _wajah_mati(hidup: dict, tempat: dict, sebaran: Optional[dict] = None,
                tempat_lama: Optional[list] = None) -> set:
    """
    Nomor jejak yang bukan orang hidup — lihat HIDUP_AMBANG.

    `hidup[tid]` berisi selisih petak per setengah detik; `tempat[tid]` berisi
    (cx, cy, lebar) rata-rata jejak itu dalam pecahan lebar bingkai;
    `sebaran[tid]` berisi (sx, sy) simpangan posisinya; `tempat_lama` berisi
    tempat gambar mati yang sudah ditemukan di klip lain dari video yang sama.
    """
    import statistics

    sebaran = sebaran or {}
    mati = {tid for tid, d in hidup.items()
            if len(d) >= HIDUP_MIN_N and statistics.median(d) < HIDUP_AMBANG}
    titik = [tempat[m] for m in mati if m in tempat] + list(tempat_lama or [])
    if not titik:
        return mati

    def di_tempat_mati(t) -> bool:
        cx, cy, lebar = t
        return any(abs(cx - mx) < HIDUP_TEMPAT and abs(cy - my) < HIDUP_TEMPAT
                   and abs(lebar - ml) < HIDUP_UKURAN * max(ml, 1e-6)
                   for mx, my, ml in titik)

    for tid, t in tempat.items():
        if tid in mati or not di_tempat_mati(t):
            continue
        d = hidup.get(tid) or []
        med = statistics.median(d) if d else 0.0
        if len(d) < HIDUP_MIN_N:
            # Jejak pendek: kamera di atas tripod kembali ke bidikan yang sama
            # berulang kali, dan lukisan di belakangnya muncul di koordinat
            # yang sama setiap kali — seringkali hanya dua detik.
            if med < HIDUP_AMBANG * 2:
                mati.add(tid)
            continue
        sx, sy = sebaran.get(tid, (1.0, 1.0))
        if sx < HIDUP_DIAM and sy < HIDUP_DIAM and med < HIDUP_AMBANG * 3:
            mati.add(tid)
    return mati


def _ketajaman(frame, f, sw: int, sh: int) -> float:
    """
    Seberapa tajam petak wajah ini, lewat ragam Laplacian.

    Ini yang memisahkan orangnya dari bayangannya di kaca. Sebuah pantulan
    adalah wajah sungguhan bagi detektor — bentuknya benar, proporsinya benar,
    dan kalau kebetulan lebih besar di layar ia menang atas orang aslinya.
    Yang TIDAK pernah sama adalah ketajamannya: kaca menyebarkan cahaya, jadi
    tepi pantulan selalu lebih lembut dan kontrasnya lebih rendah daripada
    wajah yang dipantulkannya, di bingkai yang sama dan pencahayaan yang sama.

    Nilainya tidak dipakai sebagai ambang mutlak — apa yang "tajam" berbeda
    antara kamera ponsel dan kamera studio. Ia hanya dibandingkan antar wajah
    di dalam satu bingkai, di tempat pemilihannya.
    """
    import cv2

    x, y, w, h = float(f[0]), float(f[1]), float(f[2]), float(f[3])
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(sw, int(x + w)), min(sh, int(y + h))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return 0.0
    abu = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(abu, cv2.CV_64F).var())


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


def _mouth_openness(full, face, scale: float) -> Optional[float]:
    """
    Seberapa TERBUKA mulut seseorang pada satu bingkai.

    Menggantikan pengukuran "berapa banyak piksel mulut berubah" yang dipakai
    sebelumnya, dan perbedaannya bukan penyetelan — ia mengubah hasil dari
    tidak berguna menjadi berguna. Diukur pada klip dua orang duduk berdampingan
    yang giliran bicaranya sudah diperiksa dengan mata, sebagai selisih nilai
    seseorang saat DIA bicara dikurangi saat orang lain bicara, dalam simpangan
    baku:

        beda piksel, petak lama      0,023      (setara nol)
        beda piksel, petak benar     0,181
        bukaan mulut                 0,512
        bukaan + ragamnya            1,074
    
    Dua hal yang diperbaiki, dan yang pertama menanggung sebagian besarnya:

    1. **Petaknya diskalakan LEBAR WAJAH, bukan jarak mata.** Dua orang yang
       duduk saling menghadap hampir selalu terlihat menyamping: terukur pada
       klip itu, jarak mata cuma 0,30 dari lebar wajah (wajah menghadap kamera
       sekitar 0,45), dan angkanya bergoyang dari bingkai ke bingkai. Petak
       yang diskalakan olehnya ikut bergoyang, dan yang terukur lalu bukan
       mulut melainkan dinding di belakangnya. Lebar kotak wajah stabil.

    2. **Yang diukur BUKAAN, bukan perubahan.** Beda piksel antar bingkai
       menyala untuk apa pun yang bergerak — kepala mengangguk, kamera
       bergoyang, bayangan lewat. Bukaan mulut adalah besaran mutlak: rongga
       mulut lebih gelap daripada bibir dan kulit di sekitarnya, dan
       kegelapannya bertambah persis ketika mulut membuka.

    Sudutnya diambil dari dua sudut MULUT, bukan dari garis mata, dan dibatasi
    +/-25 derajat: pada wajah menyamping sudut mata adalah derau.
    """
    import cv2
    import numpy as np

    w = float(face[2]) * scale
    if w < 20.0:
        return None
    lm = [(float(face[4 + 2 * i]) * scale, float(face[5 + 2 * i]) * scale)
          for i in range(5)]
    (ax, ay), (bx, by) = lm[3], lm[4]
    lebar_mulut = float(np.hypot(bx - ax, by - ay))
    sudut = (float(np.degrees(np.arctan2(by - ay, bx - ax)))
             if lebar_mulut > 4.0 else 0.0)
    sudut = max(-25.0, min(25.0, sudut))
    mx, my = (ax + bx) / 2.0, (ay + by) / 2.0

    bw, bh = w * 0.62, w * 0.40
    M = cv2.getRotationMatrix2D((mx, my), sudut, 1.0)
    M[0, 2] += bw / 2.0 - mx
    M[1, 2] += bh / 2.0 - my
    crop = cv2.warpAffine(full, M, (max(6, int(bw)), max(6, int(bh))),
                          flags=cv2.INTER_AREA)
    if crop.size == 0:
        return None
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = cv2.resize(g, (64, 40), interpolation=cv2.INTER_AREA)
    sd = float(g.std())
    if sd < 1e-3:
        return None
    g = (g - float(g.mean())) / sd
    # Bagian tengah petak: di situ rongga mulut berada. Tepinya berisi bibir
    # atas, dagu, dan kulit pipi — semuanya terang, dan memasukkannya hanya
    # mengencerkan yang sedang dicari.
    tengah = g[12:30, 12:52]
    return float(-np.percentile(tengah, 15))


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


# Hasil penilaian tanda hidup dari pindaian terakhir — untuk diagnosis saja.
_HIDUP_TERAKHIR: dict = {}
_TEMPAT_TERAKHIR: dict = {}


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
    if _pastikan_sface():
        try:
            recognizer = cv2.FaceRecognizerSF.create(str(SFACE_PATH), "")
        except Exception as e:
            log.warning("Pengenal wajah tidak bisa dimuat: %s", e)

    embeds: dict[int, "np.ndarray"] = {}
    next_tid = 0
    sample_i = -1

    # Rata-rata bergerak gerakan mulut, sebagai bobot per sampel.
    decay = math.exp(-1.0 / max(1e-6, MOUTH_SMOOTH_SECONDS * SAMPLE_FPS))

    cuts: list[bool] = []
    raw: list[list[float]] = []
    # Tinggi dan lebar tiap wajah per sampel, {tid: (cy, w)} dalam piksel
    # sumber. Terpisah dari `raw` karena seluruh kode sesudahnya membongkar
    # isi `raw` sebagai tiga angka.
    geo: list[dict] = []
    prev_hist = None
    tracks: list[_FaceTrack] = []
    # Pemilihan wajah utama DITUNDA sampai seluruh klip terpindai: apakah
    # sebuah jejak orang hidup atau gambar baru bisa dinilai setelah beberapa
    # detik, dan saat itu bingkai yang sudah memilihnya tidak bisa ditarik lagi.
    # Per sampel disimpan calonnya: (tid, cx, luas, tajam, yakin).
    calon: list[list[tuple]] = []
    hidup: dict[int, list[float]] = {}
    tempat: dict[int, list[float]] = {}
    waktu_jejak: dict[int, list[float]] = {}     # diagnosa: detik tiap jejak terlihat

    for seg in segments:
        start = float(seg["start"])
        duration = max(0.05, float(seg["end"]) - start)
        # Potongan adegan selalu ditandai di sambungan antar segmen: menit 10
        # dan menit 50 adalah adegan berbeda, crop tidak boleh mem-pan ke sana.
        first_of_segment = True
        awal_segmen = sample_i + 1

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
            # Jejak yang terlihat tepat di sampel sebelumnya — pembanding untuk
            # mengenali potongan kamera yang lolos dari histogram, di bawah.
            barusan = {id(t) for t in tracks if t.misses == 0}
            for t in tracks:
                t.misses += 1
            matched: list[_FaceTrack] = []
            max_dist = TRACK_MAX_DIST * sw

            for f in detections:
                x, y, w, h = float(f[0]), float(f[1]), float(f[2]), float(f[3])
                cx, cy = x + w / 2.0, y + h / 2.0
                buka = _mouth_openness(full, f, full_scale)
                mouth, brow = _aligned_patches(full, f, full_scale)
                if mouth is None:
                    mouth, brow = _face_patches(frame, f, sw, sh)
                tajam = _ketajaman(frame, f, sw, sh)
                # Elemen terakhir keluaran YuNet adalah skor keyakinannya.
                yakin = float(f[-1]) if len(f) >= 15 else 1.0

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
                    best_t.tajam, best_t.yakin = tajam, yakin
                    if buka is not None:
                        best_t.motion = buka
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
                    gerak = 0.0 if dm is None else dm - (db or 0.0)
                    # Bukaan mulut kalau terukur; beda piksel hanya sebagai
                    # cadangan saat wajahnya terlalu kecil untuk diukur.
                    motion = gerak if buka is None else buka
                    best_t.motion = motion
                    best_t.energy = best_t.energy * decay + motion * (1.0 - decay)
                    # Dihaluskan: satu bingkai buram karena orangnya bergerak
                    # tidak boleh membuatnya dikira pantulan.
                    best_t.tajam = 0.7 * best_t.tajam + 0.3 * tajam
                    best_t.yakin = 0.7 * best_t.yakin + 0.3 * yakin
                    best_t.cx, best_t.cy, best_t.w, best_t.h = cx, cy, w, h
                    best_t.mouth, best_t.brow = mouth, brow
                best_t.misses = 0
                matched.append(best_t)

                # --- Tanda hidup ---------------------------------------------
                #
                # Pembandingnya diambil di KOTAK YANG SAMA dengan setengah
                # detik lalu, bukan di kotak deteksi sekarang. Kotak detektor
                # bergoyang satu-dua piksel dari sampel ke sampel; pada wajah
                # selebar dua puluh piksel — foto di iklan sponsor, poster di
                # dinding belakang — goyangan itu menggeser petaknya 5-10%, dan
                # tepi kontrasnya (kacamata, batas latar) terbaca sebagai
                # "berubah". Terukur: wajah iklan yang sama sekali diam dinilai
                # 0,19-0,34, setara orang yang bicara, dan bingkai mengikutinya.
                # Di tempat yang tetap, gambar diam cuma menyisakan derau
                # kompresi; orang sungguhan tetap berubah karena ia berkedip,
                # bernapas, dan bergeser — pergeseran itu justru ikut terukur.
                if sample_i - best_t.rujukan_at >= HIDUP_JEDA:
                    if (best_t.rujukan is not None
                            and sample_i - best_t.rujukan_at <= 2 * HIDUP_JEDA):
                        petak_sama = _petak_hidup(frame, best_t.rujukan_kotak, sw, sh)
                        if petak_sama is not None:
                            hidup.setdefault(best_t.tid, []).append(
                                float(np.abs(petak_sama - best_t.rujukan).mean()))
                    petak = _petak_hidup(frame, f, sw, sh)
                    if petak is not None:
                        best_t.rujukan, best_t.rujukan_at = petak, sample_i
                        best_t.rujukan_kotak = tuple(float(v) for v in f[:4])
                waktu_jejak.setdefault(best_t.tid, []).append(
                    start + (sample_i - awal_segmen) / SAMPLE_FPS)
                jumlah = tempat.setdefault(best_t.tid, [0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0])
                jumlah[0] += cx / sw
                jumlah[1] += cy / sw
                jumlah[2] += w / sw
                jumlah[3] += 1
                jumlah[4] += (cx / sw) ** 2
                jumlah[5] += (cy / sw) ** 2
                jumlah[6] += yakin

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

            # Potongan kamera yang tidak terbaca dari warna.
            #
            # Histogram hanya menangkap potongan yang mengubah warna gambar.
            # Studio podcast memotong antara kamera yang menghadap ruangan yang
            # SAMA — close-up satu orang lalu bidikan berdua — dan warnanya
            # nyaris tidak berubah. Terlewat, bingkai menunggu 0,8 detik di
            # tempat orang yang sudah tidak ada (dikira kepalanya menoleh), lalu
            # menggeser pelan ke orang lain alih-alih berpindah. Terukur pada
            # klip Yono 4: 22 kali per menit. Bila tidak satu pun wajah yang
            # terlihat barusan berlanjut, dan wajah yang terlihat sekarang semuanya
            # baru, kameranya sudah pindah.
            if (not is_cut and barusan and matched
                    and not any(id(t) in barusan for t in matched)):
                is_cut = True
                tracks = [t for t in tracks if id(t) not in barusan]
            tracks = [t for t in tracks if t.misses <= TRACK_MAX_MISSES]

            calon.append([(t.tid, t.cx, (t.w * t.h) / (sw * sh), t.tajam, t.yakin)
                          for t in matched])
            cuts.append(is_cut)
            # (posisi, gerakan mulut) tiap wajah pada sampel ini. Gerakannya
            # ikut dibawa keluar karena yang menentukan siapa pemiliknya bukan
            # nilai sesaatnya, melainkan KAPAN ia naik — dan itu hanya bisa
            # dinilai terhadap suara, di luar sini.
            raw.append(sorted((t.cx * scale_back, t.motion, t.tid) for t in matched))
            geo.append({t.tid: (t.cy * scale_back, t.w * scale_back) for t in matched})

    rerata = {tid: (a / n, b / n, c / n) for tid, (a, b, c, n, *_r) in tempat.items() if n}
    sebaran = {tid: (math.sqrt(max(0.0, xx / n - (a / n) ** 2)),
                     math.sqrt(max(0.0, yy / n - (b / n) ** 2)))
               for tid, (a, b, c, n, xx, yy, _yk) in tempat.items() if n}
    global _TEMPAT_TERAKHIR
    _TEMPAT_TERAKHIR = {
        tid: {"n": n,
              "sx": math.sqrt(max(0.0, xx / n - (a / n) ** 2)),
              "sy": math.sqrt(max(0.0, yy / n - (b / n) ** 2)),
              "yakin": yk / n}
        for tid, (a, b, c, n, xx, yy, yk) in tempat.items() if n}
    kunci_video = str(src)
    mati = _wajah_mati(hidup, rerata, sebaran, _TEMPAT_MATI.get(kunci_video))
    # Diingat hanya yang terbukti sendiri (panjang dan diam), bukan yang ikut
    # mati karena tempatnya — supaya satu kekeliruan tidak menular.
    import statistics as _st
    bukti = [rerata[t] for t in mati
             if t in rerata and len(hidup.get(t, ())) >= HIDUP_MIN_N
             and _st.median(hidup[t]) < HIDUP_AMBANG]
    if bukti:
        simpan = _TEMPAT_MATI.setdefault(kunci_video, [])
        for b in bukti:
            if not any(abs(b[0] - x) < HIDUP_TEMPAT / 2 and abs(b[1] - y) < HIDUP_TEMPAT / 2
                       for x, y, _l in simpan):
                simpan.append(b)
        del simpan[:-40]
    if mati:
        log.info("%d jejak wajah bukan orang hidup (gambar, logo, pola) diabaikan",
                 len(mati))
        # Gambar tidak ikut dikelompokkan jadi "orang": ia tidak pernah bicara,
        # dan sebagai orang ia akan ditawarkan untuk ditunjuk dan dicocokkan
        # dengan suara.
        raw = [[r for r in baris if r[2] not in mati] for baris in raw]
        for tid in mati:
            embeds.pop(tid, None)
    global _HIDUP_TERAKHIR
    _HIDUP_TERAKHIR = {"hidup": hidup, "tempat": rerata, "mati": mati,
                       "waktu": waktu_jejak}

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
    centers: list[Optional[float]] = []
    prev_center: Optional[float] = None
    for cands, is_cut in zip(calon, cuts):
        best = None
        cands = [c for c in cands if c[0] not in mati]
        if cands:
            best_score = -1e9
            # Ketajaman tertinggi di BINGKAI INI jadi pembanding, bukan
            # ambang tetap: apa yang tajam di kamera studio berbeda dari
            # kamera ponsel, tapi di dalam satu bingkai wajah asli selalu
            # lebih tajam daripada pantulannya di kaca.
            tajam_puncak = max((c[3] for c in cands), default=0.0)
            for _tid, cx, area, tajam, yakin in cands:
                # Suku kontinuitas inilah yang mencegah crop melompat
                # bolak-balik antara dua narasumber setiap kali wajah yang
                # lebih kecil kebetulan lebih terang.
                penalty = 0.0
                if prev_center is not None and not is_cut:
                    penalty = 0.6 * abs(cx - prev_center / scale_back) / sw
                # Bobot mutu: pantulan kaca dihukum, wajah asli tidak.
                #
                # Pantulan adalah wajah sungguhan bagi detektor, jadi
                # luas + kontinuitas saja bisa memenangkannya — persis yang
                # terjadi ketika orangnya menggerakkan tangan dan wajah
                # aslinya sesaat terhalang atau mengecil. Dikalikan, bukan
                # dikurangi, supaya pengaruhnya sebanding dengan besar
                # wajahnya dan tidak pernah membuat skor jadi negatif.
                rel = (tajam / tajam_puncak) if tajam_puncak > 1e-6 else 1.0
                mutu = 0.40 + 0.60 * min(1.0, rel)
                mutu *= 0.75 + 0.25 * min(1.0, max(0.0, yakin))
                score = area * mutu - penalty
                if score > best_score:
                    best_score, best = score, cx

        if best is not None:
            prev_center = best * scale_back
            centers.append(prev_center)
        else:
            centers.append(None)

    return centers, cuts, raw, embeds, geo


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

    # --- Boleh atau tidaknya sidik wajah menentukan JUMLAH orang -------------
    #
    # Batas yang dipakai saat sidiknya tidak bisa dipercaya adalah jumlah wajah
    # terbanyak yang pernah terlihat BERSAMAAN. Itu satu-satunya bukti yang
    # tidak butuh pengenalan wajah sama sekali: dua wajah di layar pada detik
    # yang sama pasti dua orang. Selebihnya adalah kesimpulan dari embedding,
    # dan di rekaman yang wajahnya kecil, kesimpulan itu derau.
    #
    # Bukan pengganti pengenalan wajah, hanya pagarnya. Pada rekaman yang
    # sidiknya jelas, selisihnya jauh di atas ambang dan pagar ini tidak pernah
    # mengikat — podcast berpotong close-up tetap boleh mengenali lima orang
    # meski tidak pernah ada dua wajah sekaligus.
    import numpy as _np

    jumlah = [len(r) for r in raw if r]
    batas_terlihat = 1
    if jumlah:
        arr = _np.asarray(jumlah)
        for c in range(1, max_people + 1):
            if float((arr >= c).sum()) / len(jumlah) >= ROSTER_MIN_SHARE:
                batas_terlihat = c

    dalam, pusat = [], []
    for mem in kelompok:
        v = [embeds[t] for t in mem if t in embeds]
        if len(v) >= 2:
            M = _np.stack(v)
            sim = M @ M.T
            dalam.append(float(sim[_np.triu_indices(len(v), 1)].mean()))
        if v:
            m = _np.mean(_np.stack(v), axis=0)
            pusat.append(m / max(1e-9, float(_np.linalg.norm(m))))
    antar = []
    if len(pusat) >= 2:
        P = _np.stack(pusat)
        sp = P @ P.T
        antar = sp[_np.triu_indices(len(P), 1)].tolist()
    selisih = ((float(_np.mean(dalam)) - float(_np.mean(antar)))
               if dalam and antar else 0.0)

    if selisih < IDENTITY_TRUST_MARGIN and batas_terlihat < max_people:
        if len(bobot) > batas_terlihat:
            log.info("Sidik wajah lemah (selisih %.3f), jumlah orang dibatasi ke %d, "
                     "sebanyak wajah yang pernah terlihat bersamaan (dari %d kelompok)",
                     selisih, batas_terlihat, len(bobot))
        max_people = max(1, batas_terlihat)

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
                 max_people: int = 6,
                 geo: Optional[list] = None,
                 kotak_keluar: Optional[list] = None,
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
        return _trace_people(raw, centroids, k, tid2id, geo, kotak_keluar)

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
    # Tiap deteksi berisi (posisi, gerak mulut, nomor jejak). Membongkarnya
    # sebagai pasangan membuat jalur ini selalu gagal, dan karena galatnya
    # ditangkap di _scan_scene, bidikan lebar berwajah kecil diam-diam
    # kehilangan seluruh daftar orangnya.
    points = np.array([d[0] for r in sumber for d in r], dtype=np.float64)
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
    return _trace_people(raw, centroids, k, tid2id, geo, kotak_keluar)


def _trace_people(raw: list, centroids, k: int, tid2id: dict,
                  geo: Optional[list] = None, kotak_keluar: Optional[list] = None):
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
    # Jejak wajah tak bersidik yang sudah dijodohkan lewat tempat duduk, dan
    # ke siapa. Perjodohan itu DIPEGANG selama jejaknya berlanjut, bukan diundi
    # ulang tiap sampel — lihat langkah 2.
    lekat: dict[int, int] = {}
    # Wajah mana (nomor jejak) yang dijodohkan ke tiap orang di sampel ini —
    # untuk mengambil tinggi dan ukurannya dari `geo`.
    kotak: list[list] = [[] for _ in range(k)]

    for s_i, r in enumerate(raw):
        taken: dict[int, float] = {}
        wajah_dari: dict[int, int] = {}
        used_face: set[int] = set()

        # 1. Yang dikenali dari wajahnya.
        #
        # Dua wajah di sampel yang sama bisa jatuh ke nomor yang sama — sidik
        # wajah kecil tidak cukup membedakan, dan daftar orang video ini bisa
        # sudah penuh dari klip sebelumnya. Dulu yang menang selalu wajah paling
        # KIRI, dan karena urutan deteksi berubah-ubah, "orang 1" melompat
        # antara dua orang di sisi berlawanan hampir tiap detik. Terukur pada
        # klip dr. Tirta & dr. Gia: posisinya berganti 328 → 985 → 1037 → 260
        # piksel, dan bingkai yang mengikutinya — dibatasi kecepatan gesernya —
        # melayang di TENGAH, di ruang kosong di antara keduanya. Sekarang yang
        # menang adalah wajah yang paling dekat dengan posisi orang itu
        # sebelumnya; wajah lainnya dijodohkan lewat tempat duduk di bawah.
        calon: dict[int, list[int]] = {}
        for j, (x, m, tid) in enumerate(r):
            i = tid2id.get(tid)
            if i is not None:
                calon.setdefault(i, []).append(j)
        for i, js in calon.items():
            if len(js) > 1 and last[i] is not None:
                js = sorted(js, key=lambda j, i=i: abs(r[j][0] - last[i]))
            j = js[0]
            x, m, _t = r[j]
            taken[i] = m
            wajah_dari[i] = _t
            used_face.add(j)
            last[i] = x

        # 2. Sisanya dijodohkan dengan tempat duduk yang belum terisi.
        #
        # Wajah yang SUDAH dijodohkan di sampel sebelumnya tetap pada orangnya.
        # Tanpa ini, dua wajah yang jaraknya ke kursi seseorang hampir sama
        # bergantian memenangkannya: terukur pada klip dr. Tirta & dr. Gia,
        # kursi "orang 1" tercatat di tengah (x=640, dari close-up) sementara
        # dua tamu kecil di kiri dan kanan berjarak 312 dan 333 piksel darinya
        # — pemenangnya berganti hampir tiap setengah detik, dan bingkai yang
        # mengikutinya melayang di ruang kosong di antara keduanya.
        for j, (x, m, tid) in enumerate(r):
            i = lekat.get(tid)
            if j in used_face or i is None or i in taken:
                continue
            taken[i] = m
            wajah_dari[i] = tid
            used_face.add(j)
            last[i] = x
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
                x, m, t = r[j]
                taken[i] = m
                wajah_dari[i] = t
                used_face.add(j)
                last[i] = x
                if tid2id.get(t) is None:
                    lekat[t] = i

        g = geo[s_i] if geo is not None and s_i < len(geo) else {}
        for i in range(k):
            tracks[i].append(last[i])
            motions[i].append(taken.get(i, 0.0))
            seen[i].append(i in taken)
            kotak[i].append(g.get(wajah_dari[i]) if i in wajah_dari else None)
    if kotak_keluar is not None:
        kotak_keluar[:] = kotak
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
            subject: Optional[list] = None,
            motion: str = "smooth") -> list[float]:
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
    # Perpindahan target yang terlalu jauh untuk di-pan diperlakukan sama
    # dengan potongan adegan. Dibaca dari jejak yang SUDAH dimedian, supaya
    # satu deteksi nyasar tidak memotong bingkai tanpa alasan.
    lompat_min = LOMPAT_POTONG * source_w
    dimedian = _median([min(max(v, lo), hi) for v in filled], MEDIAN_WINDOW)
    for i in range(1, len(dimedian)):
        if abs(dimedian[i] - dimedian[i - 1]) > lompat_min:
            breaks.add(i)
    if subject is not None:
        settled = _settle_subject(list(subject) + [None] * (len(filled) - len(subject)))
        for i in range(1, min(len(settled), len(filled))):
            if settled[i] != settled[i - 1]:
                breaks.add(i)
    # Batas yang datang beruntun disaring: yang pertama menang, yang menyusul
    # dalam JEDA_BATAS_MIN detik dibuang. Kamera yang berpindah dua kali dalam
    # satu detik tidak pernah disengaja siapa pun, dan itulah yang terbaca
    # sebagai goyang.
    jeda_min = max(1, int(round(JEDA_BATAS_MIN * SAMPLE_FPS)))
    bounds: list[int] = []
    terakhir = -(10 ** 9)
    for b in sorted(breaks):
        if b - terakhir >= jeda_min:
            bounds.append(b)
            terakhir = b
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

        # Gaya "potong": kamera sama sekali tidak bergerak di dalam satu
        # bidikan, lalu berpindah seketika di batasnya.
        #
        # Ini bukan versi kasar dari yang mulus — ia bahasa yang berbeda.
        # Kamera yang mengikuti orang bergeser terus-menerus, dan pada klip
        # pendek gerakan itu terbaca sebagai gelisah. Potongan keras adalah
        # cara penyunting sungguhan berpindah antar orang, dan di rekaman meja
        # yang orangnya duduk diam, tidak ada yang hilang karena tidak diikuti.
        #
        # Satu nilai untuk seluruh rentang: mediannya, bukan nilai awalnya —
        # deteksi yang meleset di bingkai pertama sebuah bidikan tidak boleh
        # menentukan ke mana kamera menatap selama sepuluh detik berikutnya.
        if motion == "cut":
            tetap = sorted(chunk)[len(chunk) // 2]
            out.extend([min(max(tetap, lo), hi)] * len(chunk))
            continue

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

    # Jeda di antara kalimat bukan pergantian giliran. Dulu setiap celah tanpa
    # suara melepas subjeknya, jadi di bidikan lebar bingkai melompat ke wajah
    # terbesar selama pembicaranya menarik napas lalu kembali lagi — terukur
    # pada klip Yono, tiga lompatan bolak-balik dalam tujuh detik. Kamera
    # sungguhan tetap diam pada pembicaranya sampai orang lain mulai bicara.
    tahan_jeda = max(1, int(round(JEDA_TAHAN_SECONDS * SAMPLE_FPS)))

    out: list[Optional[float]] = []
    subject: list[Optional[int]] = []
    held: Optional[int] = None
    diam = 0
    for i in range(n):
        sp = active[i]
        if sp is not None and sp in mapping:
            diam = 0
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
        elif (sp is None and held is not None and diam < tahan_jeda
              and people[held][i] is not None
              # Benar-benar terlihat SEKARANG — bukan sekadar dalam masa
              # tenggang. Tenggang itu untuk kepala yang menoleh selagi ia
              # bicara; di jeda, orang yang sudah keluar bidikan tidak ditunggu.
              and (seen is None or held >= len(seen) or seen[held][i])):
            diam += 1
            out.append(people[held][i])
            subject.append(held)
        else:
            held = None
            diam = 0
            out.append(centers[i])
            subject.append(None)
    return out, subject


# Seberapa jauh bukaan mulut seseorang harus mengungguli yang lain sebelum
# bidikan berisi banyak orang boleh dipakai sebagai bukti siapa yang bicara.
#
# Diukur pada bidikan dua orang yang giliran bicaranya diperiksa dengan mata:
# pada sepertiga baris dengan selisih tertinggi, pilihan visualnya sepakat 90%
# dengan diarisasi; pada sepertiga terendah cuma 27%. Selisihnya sendiri yang
# menentukan layak-tidaknya dipercaya, bukan nilai mutlaknya.
MOUTH_EVIDENCE_MARGIN = 0.8


def speaking_evidence(people, motion, seen, n_samples):
    """
    Siapa yang terlihat SEDANG BICARA pada tiap sampel, beserta keyakinannya.

    Dua sumber bukti, dan keduanya perlu karena masing-masing buta di tempat
    yang satunya melihat:

    1. **Hanya satu wajah di layar.** Penyuntingnya sendiri yang menjawab —
       rekaman yang dipotong rapi memotong ke orang yang bicara. Bukti
       terkuat yang ada, dan tidak butuh menebak apa pun dari gambar.
    2. **Beberapa wajah sekaligus.** Di situ sumber pertama diam, dan yang
       dipakai bukaan mulut: siapa yang mulutnya paling terbuka dan paling
       sering membuka-menutup.

    Terukur pada empat rekaman, keduanya memang saling menutup. Podcast yang
    berpotong close-up memberi 177 dan 73 detik "sendirian di layar" untuk dua
    orangnya; rekaman meja statis memberi 1,4 detik saja — tapi di sanalah
    kedua wajah justru selalu terlihat bersamaan, tempat sumber kedua bekerja.

    Mengembalikan daftar sepanjang `n_samples` berisi (orang, keyakinan) atau
    None bila tidak ada bukti yang layak.
    """
    import numpy as np

    k = len(people)
    if k < 1 or n_samples < 1:
        return [None] * max(0, n_samples)

    mot = np.array([m[:n_samples] for m in motion], dtype=np.float64)
    vis = np.array([[bool(v) for v in s[:n_samples]] for s in seen])
    for i in range(k):
        v = mot[i][vis[i]]
        if len(v) > 4:
            sd = float(v.std())
            mot[i] = (mot[i] - float(v.mean())) / (sd if sd > 1e-6 else 1.0)

    jendela = max(3, int(round(0.4 * SAMPLE_FPS)) | 1)
    setengah = jendela // 2
    nilai = np.full((k, n_samples), -np.inf)
    for i in range(k):
        for t in range(n_samples):
            if not vis[i][t]:
                continue
            lo, hi = max(0, t - setengah), min(n_samples, t + setengah + 1)
            m = vis[i][lo:hi]
            if int(m.sum()) < 3:
                continue
            nilai[i][t] = float(mot[i][t] + mot[i][lo:hi][m].std())

    keluar: list = []
    hadir = vis.sum(axis=0)
    for t in range(n_samples):
        if hadir[t] == 1:
            keluar.append((int(np.argmax(vis[:, t])), 1.0))
            continue
        if hadir[t] < 2:
            keluar.append(None)
            continue
        kolom = nilai[:, t]
        jadi = [x for x in kolom if np.isfinite(x)]
        if len(jadi) < 2:
            keluar.append(None)
            continue
        best = int(np.argmax(kolom))
        selisih = float(kolom[best] - sorted(jadi)[-2])
        keluar.append((best, selisih) if selisih >= MOUTH_EVIDENCE_MARGIN else None)
    return keluar


def assign_faces_to_speakers(people, motion, speaker_turns, n_samples, seen=None):
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
    if k < 1 or not speakers or n_samples < 16:
        return {}
    ns = len(speakers)

    # Statistik gerak mulut butuh dua orang dan dua penutur untuk dibandingkan;
    # bukti potongan kamera di bawahnya tidak. Dulu fungsi ini menyerah begitu
    # hanya SATU orang yang dikenali — keadaan biasa pada klip pendek yang
    # dibuka close-up pembicara lalu memotong ke bidikan lebar berisi wajah-
    # wajah kecil yang tidak bisa disidik. Di situ bingkai jatuh ke wajah
    # terbesar: tamu yang sedang mendengarkan.
    dipakai = (_peta_dari_mulut(people, motion, speaker_turns, n_samples,
                                speakers, itertools, np)
               if k >= 2 and ns >= 2 else {})
    if dipakai is None:
        return {}

    # Keterlihatan SEBENARNYA per sampel. Jejak posisi `people` menahan nilai
    # terakhirnya, jadi "tidak None" di sana berarti "pernah terlihat", bukan
    # "terlihat sekarang" — dan dengan itu tidak ada yang pernah sendirian.
    if seen is not None and len(seen) == k:
        vis = np.array([[bool(v) for v in s_[:n_samples]] for s_ in seen])
    else:
        vis = np.array([[v is not None for v in p[:n_samples]] for p in people])
    if vis.shape[1] < n_samples:
        return dipakai
    active = np.zeros((ns, n_samples), dtype=bool)
    for t0, t1, sp in speaker_turns:
        lo = max(0, int(t0 * SAMPLE_FPS))
        hi = min(n_samples, int(t1 * SAMPLE_FPS) + 1)
        if hi > lo:
            active[speakers.index(sp), lo:hi] = True
    # --- Bukti kedua: siapa yang SENDIRIAN di layar saat seseorang bicara ----
    #
    # Statistik di atas membandingkan mulut seseorang saat penutur bicara
    # dengan saat TIDAK bicara. Orang yang hanya pernah muncul di layar ketika
    # ia sendiri bicara — pola paling lazim di podcast, karena penyuntingnya
    # memotong ke close-up siapa pun yang sedang bicara — tidak punya sampel
    # "saat tidak bicara" sama sekali, jadi ia tidak pernah bisa dipetakan.
    #
    # Terukur pada klip Apa Kabar Yono: penutur utama bicara hampir sepanjang
    # klip, kamera menyorot close-up satu orang selama 35 detik giliran itu,
    # dan pemetaannya tetap kosong. Di bidikan lebar sesudahnya bingkai jatuh
    # ke wajah terbesar — tamu yang sedang TERTAWA mendengarkannya. Gerak
    # mulut pun menunjuk tamu yang sama, karena tawa terbaca sebagai bicara.
    #
    # Potongan kamera adalah keputusan penyunting yang sudah menonton seluruh
    # rekamannya, jadi ia dipakai sebagai bukti — dengan dua syarat supaya
    # potongan ke wajah pendengar yang bereaksi tidak ikut terhitung: selama
    # giliran penutur itu sebagian besar bidikan tunggal menampilkan orang
    # yang sama, dan saat orang itu tampil sendirian sebagian besar yang
    # terdengar memang penutur itu.
    sendiri = vis.sum(axis=0) == 1
    solo = np.zeros((k, ns))
    for j in range(ns):
        m = active[j] & sendiri
        for i in range(k):
            solo[i][j] = float((m & vis[i]).sum())
    for j, sp in enumerate(speakers):
        if sp in dipakai:
            continue
        i = int(np.argmax(solo[:, j]))
        banyak = solo[i][j]
        if banyak < SOLO_MIN_SECONDS * SAMPLE_FPS:
            continue
        if banyak / max(1.0, solo[:, j].sum()) < SOLO_PORSI_PENUTUR:
            continue
        if banyak / max(1.0, solo[i, :].sum()) < SOLO_PORSI_ORANG:
            continue
        if i in dipakai.values():
            continue
        dipakai[sp] = i
        log.info("Penutur %s dipetakan ke orang %d dari potongan kamera "
                 "(%.1f dtk tampil sendirian saat ia bicara)",
                 sp, i + 1, banyak / SAMPLE_FPS)

    if not dipakai:
        log.info("Tidak ada penutur yang terpetakan ke wajah, bingkai "
                 "mengikuti bidikan aslinya")
    return dipakai


def _peta_dari_mulut(people, motion, speaker_turns, n_samples, speakers,
                     itertools, np):
    """
    Pemetaan penutur→orang dari gerak mulut — bukti pertama di
    assign_faces_to_speakers. None bila datanya tidak utuh.
    """
    k = len(people)
    mot = np.array([m[:n_samples] for m in motion], dtype=np.float64)
    vis = np.array([[v is not None for v in p[:n_samples]] for p in people])
    if mot.shape[1] < n_samples:
        return None

    # Dinormalkan per orang: wajah yang lebih besar di layar, kulit yang lebih
    # gelap, atau lampu yang lebih keras semuanya menggeser angka bukaannya,
    # dan tanpa normalisasi yang menang adalah orang yang kebetulan paling
    # kontras — bukan yang bicara.
    for i in range(k):
        seen = mot[i][vis[i]]
        if len(seen) > 4:
            sd = float(seen.std())
            mot[i] = (mot[i] - float(seen.mean())) / (sd if sd > 1e-6 else 1.0)

    # Dua keterangan, bukan satu, dan keduanya perlu.
    #
    # BUKAAN menjawab "mulutnya sedang terbuka?" — benar saat bicara, tapi juga
    # benar saat menguap atau tertawa. RAGAM bukaan menjawab "mulutnya sedang
    # membuka-menutup berulang?" — itulah bentuk bicara, dan diam dengan mulut
    # sedikit terbuka tidak menghasilkannya.
    #
    # Terukur pada klip dua orang berdampingan: sendiri-sendiri keduanya memberi
    # pemisahan 0,53 dan 0,54 simpangan baku; dijumlahkan, 1,07. Keduanya
    # menangkap hal yang berbeda, jadi menjumlahkannya menambah, bukan
    # mengulang.
    jendela = max(3, int(round(0.4 * SAMPLE_FPS)) | 1)
    setengah = jendela // 2
    fitur = np.zeros_like(mot)
    for i in range(k):
        ragam = np.zeros(n_samples)
        for t in range(n_samples):
            lo, hi = max(0, t - setengah), min(n_samples, t + setengah + 1)
            m = vis[i][lo:hi]
            if int(m.sum()) >= 3:
                ragam[t] = float(mot[i][lo:hi][m].std())
        r = ragam[vis[i]]
        if len(r) > 4:
            sd = float(r.std())
            ragam = (ragam - float(r.mean())) / (sd if sd > 1e-6 else 1.0)
        fitur[i] = mot[i] + ragam
    mot = fitur

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
    # Tanpa susunan terbaik pun bukti potongan kamera di bawah tetap dicoba.

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
    dipakai = ({speakers[j]: i for j, i in best.items()
                if score[i][j] >= MIN_SPEAKER_EVIDENCE} if best else {})
    if not dipakai:
        log.info("Bukti wajah↔suara dari gerak mulut terlalu tipis (t maks %.1f)",
                 max((score[i][j] for j, i in (best or {}).items()
                      if np.isfinite(score[i][j])), default=float("nan")))
    return dipakai


PETA_MULUT_MIN_SAMPEL = 12   # bukti mulut minimum (1,5 dtk) untuk memetakan penutur
PETA_MULUT_PORSI = 0.6       # porsi bukti untuk satu orang


def _lengkapi_peta_dari_mulut(mapping, people, motion, seen, speaker_turns, n,
                              boxes=None, source_w=0):
    """
    Penutur yang TIDAK terpetakan ke wajah dicarikan wajahnya dari mulut yang
    paling sering bergerak selama giliran penutur itu.

    `assign_faces_to_speakers` sengaja ketat (statistik-t >= 2), dan di klip
    pendek penutur utamanya bisa gagal lolos. Terukur di Sule klip D (18 dtk):
    peta {1: 2} — Sule, yang bicara 11 dari 18 detik, tanpa wajah — sehingga
    di separuh gilirannya bingkai menyorot orang yang mendengarkan. Syarat di
    sini: bukti mulut kuat (selisih >= MOUTH_EVIDENCE_MARGIN) di bidikan
    beberapa orang, minimal 1,5 dtk, dan satu orang memegang >= 60%-nya; wajah
    yang sudah dipakai penutur lain tidak diambil.
    """
    from collections import Counter
    bukti = speaking_evidence(people, motion, seen, n)
    terpakai = set(mapping.values())
    hasil = dict(mapping)
    penutur = sorted({sp for _, _, sp in speaker_turns if sp not in mapping},
                     key=lambda sp: -sum(b - a for a, b, s in speaker_turns if s == sp))
    for sp in penutur:
        suara: Counter = Counter()
        for a, b, s in speaker_turns:
            if s != sp:
                continue
            for i in range(max(0, int(a * SAMPLE_FPS)), min(n, int(b * SAMPLE_FPS) + 1)):
                vis = sum(1 for p in range(len(people)) if p < len(seen) and i < len(seen[p]) and seen[p][i])
                if vis >= 2 and bukti[i] is not None:
                    p = bukti[i][0]
                    kotak = boxes[p][i] if boxes and p < len(boxes) and i < len(boxes[p]) else None
                    if source_w and kotak is not None and float(kotak[1]) < MULUT_WAJAH_MIN * source_w:
                        continue
                    suara[p] += 1
        jumlah = sum(suara.values())
        if jumlah < PETA_MULUT_MIN_SAMPEL:
            continue
        p, v = suara.most_common(1)[0]
        if v >= PETA_MULUT_PORSI * jumlah and p not in terpakai:
            hasil[sp] = p
            terpakai.add(p)
            log.info("Penutur %d dipetakan ke orang %d dari gerak mulut (%d/%d)", sp, p + 1, v, jumlah)
    return hasil


# Lama bicara minimum (detik) sebelum seorang penutur boleh dipasangkan lewat
# penyisihan. Penutur yang cuma menyela dua patah kata tidak cukup jadi dasar
# untuk mengunci sebuah wajah sepanjang klip.
SISIH_DETIK_MIN = 6.0


def _lengkapi_peta_dengan_penyisihan(mapping, people, speaker_turns, seen=None):
    """
    Satu penutur tersisa, satu wajah tersisa: pasangkan.

    Bukti mulut sengaja ketat, dan akibatnya penutur yang paling banyak bicara
    pun bisa gagal lolos. Terukur pada klip "Sistem Poin Pernikahan" milik
    pemiliknya: tiga penutur, tiga wajah, dua terpasang — dan yang tidak
    terpasang adalah penutur yang bicara 104 dari 158 detik. Selama 831 sampel
    bingkai tidak menunjuk siapa-siapa atau menunjuk orang yang salah, padahal
    jawabannya tinggal satu-satunya yang tersisa.

    Penyisihan hanya sah kalau benar-benar tinggal SATU di kedua sisi. Dua
    penutur dan dua wajah tersisa berarti ada dua kemungkinan pasangan, dan
    menebak salah satunya persis selemah lempar koin — itu yang membuat
    pemetaan berbahaya, bukan yang membuatnya berguna.
    """
    sisa_penutur = sorted({sp for _, _, sp in speaker_turns if sp not in mapping})
    sisa_orang = [i for i in range(len(people)) if i not in set(mapping.values())]
    if len(sisa_penutur) != 1 or len(sisa_orang) != 1:
        return mapping
    sp, orang = sisa_penutur[0], sisa_orang[0]
    lama = sum(b - a for a, b, s in speaker_turns if s == sp)
    if lama < SISIH_DETIK_MIN:
        return mapping
    # Wajah yang tidak pernah terlihat bukan jawaban, ia hanya sisa daftar.
    if seen is not None and orang < len(seen) and not any(seen[orang]):
        return mapping
    log.info("Penutur %d dipasangkan ke orang %d lewat penyisihan "
             "(satu-satunya yang tersisa, bicara %.1f dtk)", sp, orang + 1, lama)
    return {**mapping, sp: orang}


MULUT_JENDELA = 0.75        # detik ke kiri dan kanan untuk pemungutan suara
MULUT_SUARA_MIN = 4         # sampel berbukti minimum di jendela
MULUT_PORSI_MIN = 0.6       # porsi suara untuk satu orang agar dianggap bicara
MULUT_PORSI_TIMPA = 0.8     # ... dan untuk menimpa subjek dari peta suara-wajah
# Wajah lebih sempit dari ini (pecahan lebar bingkai) tidak dinilai dari
# mulutnya. Di bidikan lebar enam orang yang tertawa bersama, wajah selebar
# ±40 piksel memberi "bukti" yang lebih banyak deraunya daripada isinya.
MULUT_WAJAH_MIN = 0.045


def _ikuti_mulut(centers, subject, people, motion, seen, n, boxes=None, source_w=0):
    """
    Di bidikan berisi beberapa orang, bingkai pindah ke wajah yang mulutnya
    JELAS bergerak — bila peta suara tidak tahu siapa yang bicara, atau
    menunjuk orang lain.

    Diukur 21 September 2026 pada 7 klip podcast: di sampel yang bukti mulutnya
    kuat (selisih >= MOUTH_EVIDENCE_MARGIN, yang sebelumnya terukur 90% sepakat
    dengan pemeriksaan mata), bingkai menyorot orang LAIN 46% waktunya. Dua
    sebab: penutur yang tidak berhasil dipetakan ke wajah (ohJbKVkrZ4U: tiga
    penutur, satu terpetakan) jatuh ke wajah cadangan; dan diarisasi yang
    menukar giliran dua orang bersuara mirip.

    Hanya bidikan dengan dua wajah atau lebih yang disentuh: di close-up satu
    orang, potongan penyuntingnya sendiri sudah menjawab siapa yang bicara.
    Pemungutan suara per jendela ±MULUT_JENDELA membuat anggukan dan tawa
    sesaat pendengar tidak memindahkan kamera.
    """
    bukti = speaking_evidence(people, motion, seen, n)
    k = len(people)
    banyak = [sum(1 for p in range(k) if p < len(seen) and i < len(seen[p]) and seen[p][i]) >= 2
              for i in range(n)]
    lebar = max(1, int(round(MULUT_JENDELA * SAMPLE_FPS)))
    pilih: list[Optional[int]] = [None] * n
    for i in range(n):
        if not banyak[i]:
            continue
        suara: dict[int, int] = {}
        jumlah = 0
        for j in range(max(0, i - lebar), min(n, i + lebar + 1)):
            if banyak[j] and bukti[j] is not None:
                suara[bukti[j][0]] = suara.get(bukti[j][0], 0) + 1
                jumlah += 1
        if jumlah < MULUT_SUARA_MIN:
            continue
        p, v = max(suara.items(), key=lambda kv: kv[1])
        dipetakan = subject[i] if i < len(subject) else None
        if dipetakan is not None and dipetakan != p:
            # Subjek dari peta suara ke wajah hanya ditimpa bila mulut orang
            # itu sama sekali tidak terbaca bergerak di jendela ini, dan orang
            # lain jelas mendominasi. Terukur di Sule klip D: tanpa syarat ini
            # anggukan pendengar menimpa peta yang benar di dua dari enam titik.
            if suara.get(dipetakan, 0) > 0 or v < MULUT_PORSI_TIMPA * jumlah:
                continue
        if v >= MULUT_PORSI_MIN * jumlah and seen[p][i] and people[p][i] is not None:
            kotak = (boxes[p][i] if boxes and p < len(boxes) and i < len(boxes[p]) else None)
            if source_w and kotak is not None and float(kotak[1]) < MULUT_WAJAH_MIN * source_w:
                continue
            pilih[i] = p
    # Pilihan yang bertahan kurang dari MIN_SUBJECT_HOLD dibuang.
    pilih = _settle_subject(pilih)
    out, subj = list(centers), list(subject)
    ganti = 0
    for i in range(n):
        p = pilih[i]
        if p is None or not banyak[i] or people[p][i] is None or not seen[p][i]:
            continue
        if subj[i] != p:
            ganti += 1
        out[i] = people[p][i]
        subj[i] = p
    if ganti:
        log.info("Gerak mulut membetulkan %.1f dtk bingkai ke orang yang bicara",
                 ganti / SAMPLE_FPS)
    return out, subj


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
    centers, cuts, people, motion, seen, _, boxes = value

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
            ada / len(sub_centers) if sub_centers else 0.0,
            [pick(t) for t in boxes])


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
        centers, cuts, raw, embeds, geo = _detect_centers(src, padded, source_w, source_h)
    except Exception as e:  # deteksi tidak boleh menjatuhkan render
        log.warning("Deteksi wajah gagal, memakai blur-pad: %s", e)
        return None
    if not centers:
        return None

    coverage = sum(1 for c in centers if c is not None) / len(centers)
    try:
        # Daftar wajah tetap milik VIDEO ini, bukan milik klipnya: nomor orang
        # harus sama di klip mana pun, karena tanda arah bingkai menyimpan nomor.
        boxes: list = []
        people, motion, seen = group_people(raw, source_w, embeds,
                                            roster=_roster_for(head),
                                            geo=geo, kotak_keluar=boxes)
    except Exception as e:      # pengelompokan tidak boleh menjatuhkan render
        log.warning("Pengelompokan orang gagal: %s", e)
        people, motion, seen, boxes = [], [], [], []
    if len(boxes) != len(people):
        boxes = [[None] * len(centers) for _ in people]

    value = (centers, cuts, people, motion, seen, coverage, boxes)
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
                 person_keys: Optional[list] = None,
                 frame_motion: str = "smooth",
                 # "wajah" = ikuti wajah manusia (YuNet). "gerak" = ikuti pusat
                 # massa perubahan antar bingkai, untuk tokoh yang bukan
                 # manusia: kartun, maskot, hewan, rekaman layar.
                 subjek: str = "wajah") -> Optional[ReframePlan]:
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
    if subjek != "gerak" and not MODEL_PATH.is_file():
        log.info("Model YuNet tidak ada di %s, reframe dilewati", MODEL_PATH)
        return None

    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        log.info("opencv/numpy tidak terpasang, reframe dilewati")
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

    if subjek == "gerak":
        hasil = _scan_gerak(src, segments, source_w, source_h, crop_w)
        if hasil is None:
            return None
        centers, cuts, coverage = hasil
        # Tidak ada "orang" di mode ini, dan itu jujur: yang diikuti adalah
        # gerakan, bukan seseorang. Lajur orang di editor akan kosong, dan
        # memang tidak ada yang bisa ditunjuk di sana.
        people, motion, seen, boxes = [], [], [], []
    else:
        scene = _scan_scene(src, segments, source_w, source_h,
                            duration=float(info.get("duration") or 0.0))
        if scene is None:
            return None
        centers, cuts, people, motion, seen, coverage, boxes = scene

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
                                           len(centers), seen=seen)
        mapping = _lengkapi_peta_dari_mulut(mapping, people, motion, seen,
                                            speaker_turns, len(centers), boxes, source_w)
        # Terakhir, dan hanya kalau tinggal satu di kedua sisi.
        mapping = _lengkapi_peta_dengan_penyisihan(mapping, people, speaker_turns, seen)

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

    if lock_person is None and people and len(people) >= 2:
        centers, subject = _ikuti_mulut(centers, subject, people, motion, seen,
                                        len(centers), boxes=boxes, source_w=source_w)

    # Tanda tangan pengguna di linimasa mengalahkan keduanya, tapi hanya pada
    # rentang yang benar-benar ditandainya. Di luar rentang itu hasil otomatis
    # di atas tetap berlaku — membetulkan satu kesalahan tidak boleh berarti
    # mengambil alih seluruh klip dengan tangan.
    if person_keys and people:
        centers, subject = _apply_person_keys(centers, people, person_keys, subject)

    smoothed = _smooth(centers, cuts, source_w=source_w, crop_w=crop_w,
                       subject=subject, motion=frame_motion)

    plan = ReframePlan(crop_w=crop_w, crop_h=crop_h, source_w=source_w,
                       source_h=source_h, face_coverage=round(coverage, 3),
                       subject=list(subject))
    if coverage < MIN_FACE_COVERAGE:
        log.info("Wajah hanya terlihat di %.0f%% frame, memakai blur-pad", coverage * 100)
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
        if frame_motion == "cut":
            # Tangga, bukan spline. Catmull-Rom melewati tiap titik dengan
            # tangen bersambung — justru sifat yang membuatnya bagus untuk
            # gerakan halus, dan justru yang merusak potongan keras: ia akan
            # melandaikan lompatan setinggi 400 piksel menjadi luncuran
            # sepertiga detik, yang terbaca sebagai sentakan, bukan potongan.
            cx = at(i)
        else:
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
    plan.people_box = boxes
    plan.cut_times = [round(i / SAMPLE_FPS, 3) for i, c in enumerate(cuts) if c and i > 0]
    plan.speaker_faces = mapping
    log.info("Reframe siap: crop %dx%d, wajah terlihat %.0f%%, %d titik perintah",
             crop_w, crop_h, coverage * 100, len(keyframes))
    return plan


# Batas perbesaran bingkai wajah. Di atas 2x, sumber 1080p tinggal 540 piksel
# tinggi sebelum diskalakan ke 1920, dan yang terlihat bubur.
ZOOM_MAKS = 2.0


def petak_zoom(plan: ReframePlan, zoom: float = 1.0, geser_y: float = 0.0,
               ) -> tuple[int, int, int]:
    """
    (lebar, tinggi, y) potongan bingkai wajah sesudah diperbesar dan digeser.

    Bingkai wajah memakai SELURUH tinggi sumber, jadi secara tegak tidak ada
    yang bisa digeser: potongannya sudah setinggi gambarnya. Satu-satunya cara
    memberi ruang tegak adalah memperbesar, yaitu memotong lebih sedikit dari
    tingginya, dan barulah ada sisa untuk memilih bagian mana yang dipakai.

    Diminta 25 September 2026: sisipan ditaruh di atas dan menutupi wajahnya,
    dan wajahnya tidak bisa dipindahkan ke bawah.

    `geser_y` menyatakan ke mana GAMBARNYA pindah, bukan ke mana jendelanya
    pindah, dan itu perbedaan yang menentukan. Keduanya berlawanan: menurunkan
    jendela berarti mengambil bagian bawah sumber, dan wajah yang tadinya di
    tengah lalu naik ke atas layar. Yang diminta pemiliknya adalah "wajahnya
    pindah ke bawah supaya sisipan di atas tidak menutupinya", jadi itu yang
    dijadikan arti angkanya: 100 menurunkan wajah, -100 menaikkannya, 0 di
    tengah persis seperti sebelum setelan ini ada.

    zoom = 1 mengembalikan ukuran yang sama persis dengan sebelumnya, jadi klip
    yang tidak menyentuh setelan ini tidak berubah sedikit pun.
    """
    zoom = max(1.0, min(ZOOM_MAKS, float(zoom or 1.0)))
    target = plan.crop_w / plan.crop_h if plan.crop_h else 9 / 16
    h = _even(max(16, min(plan.source_h, plan.source_h / zoom)))
    w = _even(max(16, min(h * target, plan.source_w)))
    sisa = max(0, plan.source_h - h)
    bagian = max(0.0, min(1.0, 0.5 - max(-100.0, min(100.0, float(geser_y or 0.0))) / 200.0))
    y = int(round(sisa * bagian))
    return w, h, max(0, min(y, sisa))


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
    arg = ffpath(cmd_path)
    chain = (
        f"sendcmd=f='{arg}',"
        f"crop@{name}=w={w}:h={h}:x={track[0][1]}:y={crop_y}"
    )
    if scale:
        chain += f",scale={out_w}:{out_h}:flags=lanczos,setsar=1"
    return chain


# ---------------------------------------------------------------------------
# Facecam: menemukan kotak wajah pemain di video gameplay
#
# Video orang bermain game punya bentuk yang khas dan sangat berbeda dari
# podcast: wajahnya KECIL dan DIAM di satu sudut, sementara sisa layar adalah
# permainan yang bergerak terus. Pelacak wajah biasa memperlakukan itu dengan
# buruk — `face_coverage` jatuh di bawah ambang, lalu seluruh klip dipotong
# jadi bilah kabur dan wajah pemainnya hilang sama sekali.
#
# Padahal justru dua-duanya yang membuat klip gameplay layak ditonton: reaksi
# di wajah, dan apa yang sedang terjadi di permainannya. Yang dicari di sini
# bukan "wajah terbesar" melainkan "wajah yang tidak ke mana-mana": sekumpulan
# deteksi kecil yang posisinya nyaris tidak berubah sepanjang klip.
# ---------------------------------------------------------------------------

# Lebar wajah relatif bingkai. Di atas ini yang terekam adalah orang berbicara
# menghadap kamera, bukan facecam di pojok layar permainan.
FACECAM_LEBAR_MAKS = 0.20
# Wajah harus muncul di setidaknya sekian bagian sampel. Wajah yang hanya
# lewat — penonton di layar permainan, tokoh dalam game — tidak lolos.
#
# Naik dari 0,30 ke 0,45 pada 26 September 2026. Pada video Minecraft milik
# pemiliknya, jendela di menit ke-300 — bagian video yang facecam-nya BELUM
# menyala — tetap menghasilkan kotak dengan kehadiran 31%, dibangun dari wajah
# penduduk dan hewan dalam permainan. Kotak itu lalu jadi bidang reaksi yang
# isinya bukan siapa-siapa.
#
# Aman dinaikkan karena diukur, bukan ditebak: 60 jendela dari lima video (tiga
# gameplay berfacecam jelas, satu Minecraft yang facecam-nya muncul belakangan,
# satu podcast) TIDAK ADA satu pun yang jatuh di antara 30% dan 45%. Yang nyata
# berada di 100%, facecam Minecraft di 50-64%, dan sisanya tidak menghasilkan
# kotak sama sekali.
#
# Jendela yang ditolak pun tidak kehilangan apa-apa: `deteksi_facecam_waktu`
# mewarisi letak dari jendela tetangga, yang memang jawaban yang benar saat
# pemain menutup mukanya atau keluar sebentar dari kamera.
FACECAM_KEHADIRAN_MIN = 0.45
# Ukuran maksimum AWAN deteksi: kotak yang memuat semua wajah sepanjang klip.
#
# Ini menggantikan pengukuran "semua wajah berbagi satu titik tengah" yang saya
# coba lebih dulu, dan yang salah. Facecam sering memuat LEBIH DARI SATU orang —
# dua streamer duduk berdampingan di satu panel. Diukur pada bahan uji: sebaran
# tegaknya 0,005 (praktis diam) sementara sebaran mendatarnya 0,061, bukan
# karena panelnya bergerak melainkan karena ada dua wajah di dalamnya, di
# 0,745 dan 0,91. Yang menandai facecam bukan wajah yang berhimpit, melainkan
# wajah yang semuanya terkurung di petak kecil yang sama.
FACECAM_AWAN_LEBAR_MAKS = 0.42
FACECAM_AWAN_TINGGI_MAKS = 0.38
# Pergeseran petak itu antara sepertiga awal dan sepertiga akhir klip. Panel
# facecam terpasang mati; orang yang berjalan di bidikan tidak.
FACECAM_HANYUT_MAKS = 0.12
# Kelonggaran di sekeliling awan wajah: ruang untuk rambut di atas dan bahu di
# bawah, tanpa ikut menarik masuk permainan di sebelahnya.
FACECAM_KELONGGARAN = 1.85
# Mendatar dilonggarkan lebih banyak: wajah jauh lebih sempit daripada bahu,
# dan panel facecam hampir selalu memuat keduanya.
FACECAM_KELONGGARAN_X = 2.2

# Luas petak hasilnya, sebagai pecahan bingkai. Syarat TERAKHIR, dan yang
# paling menentukan.
#
# Syarat awan wajah di atas memeriksa sebaran wajahnya, bukan besar petak yang
# akhirnya dipotong. Podcast dua orang dengan bidikan lebar lolos dari situ:
# wajahnya memang berdekatan, tapi petak hasilnya memakan separuh layar, dan
# separuh layar bukan panel di sudut.
#
# Akibatnya bukan sekadar potongan yang meleset. `sutradara.susun` memakai
# "ada facecam" sebagai SATU-SATUNYA bukti bahwa klip ini rekaman permainan,
# lalu menyusunnya sebagai wajah di atas dan permainan di bawah. Terlapor 24
# September 2026 pada podcast Kajian Kitab Rongawi: petak 59%x55%, disusun
# sebagai gameplay, dan separuh bawah kanvasnya berisi dinding ruangan yang
# diberi label "Main game".
#
# Diukur pada sebelas video di penyimpanan, luas petak sebagai pecahan bingkai:
#
#   gameplay berfacecam   yqtdCouprBc 6,3%   MYXRsvydCb4 6,4%   jBQT3uYP2C4 11,9%
#   podcast / bicara      OcpInDT2jKc 23,7%  Q0vs4W03yBI 38,6%  rBg0ZcwjVKQ 32,5%
#
# Jurangnya lebar, 11,9% lawan 23,7%, jadi 16% memberi margin ke dua arah dan
# tidak menyentuh satu pun facecam sungguhan.
FACECAM_LUAS_MAKS = 0.16


def _persentil(nilai: list[float], q: float) -> float:
    if not nilai:
        return 0.0
    urut = sorted(nilai)
    i = min(len(urut) - 1, max(0, int(round(q * (len(urut) - 1)))))
    return urut[i]


def _tengah_sebaran(nilai: list[float]) -> tuple[float, float]:
    """Median dan sebaran mutlak median — tahan terhadap deteksi nyasar."""
    if not nilai:
        return 0.0, 1.0
    urut = sorted(nilai)
    med = urut[len(urut) // 2]
    simpang = sorted(abs(v - med) for v in nilai)
    return med, simpang[len(simpang) // 2]


# Tepi panel: puncak gradien rata-rata waktu harus sekian kali median jalurnya.
PANEL_TEPI_KALI = 2.5
PANEL_CARI = 2.5               # jarak cari dari awan wajah, dalam lebar/tinggi awan
PANEL_TEPI_UTUH = 0.7          # bagian sisi panel yang harus ikut kuat


def _tepi_panel(gx, gy, kotak, awan):
    """
    Batas panel facecam yang sebenarnya, dari garis yang DIAM sepanjang waktu.

    Panel yang ditempel di atas permainan punya tepi lurus di kolom dan baris
    yang sama di setiap bingkai; gambar permainan di sebelahnya bergerak, jadi
    garis-garisnya luntur saat dirata-rata. Terukur pada rekaman sungguhan
    (96GQgDkHC64, tiga potongan): tepi kanan di kolom 18,1% dengan kekuatan
    4-5x median jalurnya, tepi atas di baris 71,1% dengan 50x — sementara
    perkiraan dari awan wajah memberi 20% dan meloloskan sepotong permainan ke
    bidang wajah, yang terlihat sebagai jalur gelap di samping wajah.

    Tiap sisi dicari sendiri, hanya di antara awan wajah dan sejauh
    `PANEL_CARI` kali ukurannya ke luar; sisi yang tidak punya puncak cukup
    jelas memakai perkiraan lama. Mengembalikan (x0, y0, x1, y1) pecahan, atau
    None bila tidak ada satu sisi pun yang ditemukan.
    """
    import numpy as np

    sh, sw1 = gx.shape
    sh1, sw = gy.shape
    kx0, ky0, kx1, ky1 = kotak
    ax0, ay0, ax1, ay1 = awan
    aw, ah = max(ax1 - ax0, 0.02), max(ay1 - ay0, 0.02)
    ry0, ry1 = int(max(0, ky0) * sh), int(min(1, ky1) * sh)
    rx0, rx1 = int(max(0, kx0) * sw), int(min(1, kx1) * sw)
    if ry1 - ry0 < 4 or rx1 - rx0 < 4:
        return None
    kol = gx[ry0:ry1].mean(0)            # profil kolom di pita panel
    bar = gy[:, rx0:rx1].mean(1)         # profil baris di pita panel
    med_k = float(np.median(kol)) + 1e-3
    med_b = float(np.median(bar)) + 1e-3

    def puncak(profil, med, a, b, n, lintas):
        """`lintas(i)` = nilai gradien sepanjang garis ke-i di pita panel."""
        a, b = max(1, int(a * n)), min(len(profil) - 1, int(b * n) + 1)
        if b - a < 2:
            return None
        # Calon diurut dari yang terkuat; yang pertama lolos uji garis menang.
        for i in (a + np.argsort(profil[a:b])[::-1][:6]):
            if profil[i] < PANEL_TEPI_KALI * med:
                return None
            # Garis LURUS UTUH: tepi panel kuat hampir di sepanjang sisinya.
            # Kursi, mikrofon, atau bahu orang pada facecam tanpa bingkai
            # (orang yang dipotong dari latarnya) memberi puncak yang sama
            # tinggi, tapi hanya sepotong — terukur pada Devour, kotaknya
            # menciut dari 27% jadi 8% lebar karena garis kursi.
            nilai = lintas(int(i))
            if len(nilai) and float(np.mean(nilai >= PANEL_TEPI_KALI * med)) >= PANEL_TEPI_UTUH:
                return (int(i) + 1) / n
        return None

    def lintas_kol(i):
        return gx[ry0:ry1, max(0, i - 1):i + 2].max(axis=1)

    def lintas_bar(i):
        return gy[max(0, i - 1):i + 2, rx0:rx1].max(axis=0)

    # Sisi yang menempel di pinggir bingkai tidak dicari: di sana tidak ada
    # tepi panel, hanya grafis di dalamnya (angka, logo) yang bisa terbaca
    # sebagai tepi dan memangkas panelnya.
    kanan = None if kx1 > 0.97 else puncak(kol, med_k, ax1, ax1 + PANEL_CARI * aw, sw, lintas_kol)
    kiri = None if kx0 < 0.03 else puncak(kol, med_k, ax0 - PANEL_CARI * aw, ax0, sw, lintas_kol)
    bawah = None if ky1 > 0.97 else puncak(bar, med_b, ay1, ay1 + PANEL_CARI * ah, sh, lintas_bar)
    atas = None if ky0 < 0.03 else puncak(bar, med_b, ay0 - PANEL_CARI * ah, ay0, sh, lintas_bar)
    if all(v is None for v in (kanan, kiri, bawah, atas)):
        return None
    x0 = kiri if kiri is not None else (0.0 if kx0 < 0.03 else kx0)
    x1 = kanan if kanan is not None else (1.0 if kx1 > 0.97 else kx1)
    y0 = atas if atas is not None else (0.0 if ky0 < 0.03 else ky0)
    y1 = bawah if bawah is not None else (1.0 if ky1 > 0.97 else ky1)
    if x1 - x0 < 0.05 or y1 - y0 < 0.05:
        return None
    # Panel selalu jauh lebih besar dari wajah di dalamnya. Kotak yang nyaris
    # hanya selebar wajah berarti yang ditemukan adalah garis DI DALAM gambar
    # kamera (sandaran kursi), bukan tepi panelnya: terukur pada Devour, 8%
    # lebar untuk awan wajah 6%.
    if aw / (x1 - x0) > 0.55 or ah / (y1 - y0) > 0.65:
        return None
    return x0, y0, x1, y1


def deteksi_facecam(src, start: float, duration: float,
                    source_w: int, source_h: int,
                    rasio_potongan: float = 1080 / 691) -> Optional[dict]:
    """
    Kotak facecam dalam PERSEN bingkai sumber, atau None kalau bukan gameplay.

    `rasio_potongan` adalah lebar/tinggi bidang tujuan di kanvas hasil. Ia ikut
    menentukan bentuk potongan supaya tidak ada yang perlu diregangkan nanti.
    """
    if not MODEL_PATH.is_file():
        return None
    sw = SAMPLE_WIDTH
    sh = _even(SAMPLE_WIDTH * source_h / source_w)
    return _facecam_dari_bingkai(_sample_frames(src, start, duration, sw, sh),
                                 sw, sh, rasio_potongan)


def _facecam_dari_bingkai(bingkai, sw: int, sh: int,
                          rasio_potongan: float = 1080 / 691) -> Optional[dict]:
    """
    Inti pencarian facecam, dari bingkai yang SUDAH dibaca orang lain.

    Dipisahkan dari pembacaannya supaya satu proses ffmpeg bisa memberi makan
    banyak jendela sekaligus. Menjalankan ffmpeg untuk tiap jendela 8 detik
    memakan ongkos tetap ±0,9 detik per jendela hanya untuk hidup dan melompat
    ke detiknya; terukur pada klip 32 detik, empat jendela: 7,8 detik dengan
    empat proses melawan 5,2 detik dengan satu. Yang dihitungnya sama persis,
    jadi kotak yang keluar pun sama persis.
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return None

    try:
        detector = cv2.FaceDetectorYN.create(
            str(MODEL_PATH), "", (sw, sh), DETECT_SCORE, DETECT_NMS, 5000)
    except Exception as e:
        log.warning("Detektor facecam tidak bisa dibuat: %s", e)
        return None

    kiri: list[float] = []
    kanan: list[float] = []
    atas: list[float] = []
    bawah: list[float] = []
    # Pusat mendatar per sampel, dipakai memeriksa apakah petaknya hanyut.
    pusat_per_sampel: list[Optional[float]] = []
    total = 0
    # Gradien rata-rata lintas waktu, untuk menemukan tepi panel (`_tepi_panel`).
    gx_jumlah = None
    gy_jumlah = None
    n_grad = 0
    for buf in bingkai:
        total += 1
        frame = np.frombuffer(buf, dtype=np.uint8).reshape((sh, sw, 3))
        if total % 2 == 1:
            abu = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            gx = np.abs(np.diff(abu, axis=1))
            gy = np.abs(np.diff(abu, axis=0))
            gx_jumlah = gx if gx_jumlah is None else gx_jumlah + gx
            gy_jumlah = gy if gy_jumlah is None else gy_jumlah + gy
            n_grad += 1
        try:
            _, faces = detector.detect(frame)
        except Exception:
            faces = None
        if faces is None:
            pusat_per_sampel.append(None)
            continue
        px: list[float] = []
        for f in faces:
            x, y, w, h = float(f[0]), float(f[1]), float(f[2]), float(f[3])
            if w <= 0 or h <= 0 or w / sw > FACECAM_LEBAR_MAKS:
                continue
            kiri.append(x / sw)
            kanan.append((x + w) / sw)
            atas.append(y / sh)
            bawah.append((y + h) / sh)
            px.append((x + w / 2) / sw)
        pusat_per_sampel.append(sum(px) / len(px) if px else None)

    if total == 0 or len(kiri) < max(3, total * FACECAM_KEHADIRAN_MIN):
        return None

    # Petak yang memuat wajah-wajahnya. Persentil, bukan nilai ekstrem: satu
    # deteksi nyasar di tengah layar permainan tidak boleh melebarkan petaknya.
    x1, x2 = _persentil(kiri, 0.05), _persentil(kanan, 0.95)
    y1, y2 = _persentil(atas, 0.05), _persentil(bawah, 0.95)
    lebar_awan, tinggi_awan = max(0.0, x2 - x1), max(0.0, y2 - y1)
    if lebar_awan > FACECAM_AWAN_LEBAR_MAKS or tinggi_awan > FACECAM_AWAN_TINGGI_MAKS:
        # Wajah tersebar di seluruh bingkai: ini orang berbicara menghadap
        # kamera, bukan panel kecil di sudut layar permainan.
        return None

    # Hanyut: panel facecam terpasang mati, orang yang berjalan tidak.
    ada = [v for v in pusat_per_sampel if v is not None]
    if len(ada) >= 6:
        n3 = max(1, len(ada) // 3)
        awal_med, _ = _tengah_sebaran(ada[:n3])
        akhir_med, _ = _tengah_sebaran(ada[-n3:])
        if abs(akhir_med - awal_med) > FACECAM_HANYUT_MAKS:
            return None

    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2

    # Potongan dibentuk dari petak wajahnya SAJA. `rasio_potongan` sengaja
    # tidak lagi dipakai untuk menentukan ukurannya.
    #
    # Versi sebelumnya memaksa potongan mengikuti rasio bidang tujuan supaya
    # tidak ada yang perlu diregangkan. Itu salah arah: panel facecam sering
    # TEGAK (pada video uji kira-kira 17% x 38% bingkai, rasio 0,8) sementara
    # bidang tujuannya melebar (rasio 1,48), jadi memaksakannya melebarkan
    # potongan sampai 28,5% — dan 11% kelebihan itu berisi gambar permainan,
    # yang lalu ikut diperbesar di bidang wajah. Terlihat di pratinjau sebagai
    # sepotong dinding di sebelah wajahnya.
    #
    # Yang benar: potong panelnya saja, lalu biarkan "cover" di tahap
    # penyusunan yang memangkasnya. Memangkas sedikit rambut atau bahu selalu
    # lebih baik daripada memasukkan permainan ke bidang yang seharusnya wajah.
    h_pot = min(1.0, max(tinggi_awan * FACECAM_KELONGGARAN, 0.12))
    w_pot = min(1.0, max(lebar_awan * FACECAM_KELONGGARAN_X, 0.10))

    # Digeser masuk supaya tidak keluar bingkai. Facecam hampir selalu menempel
    # di sudut, jadi menggeser ke dalam justru mendekatkan potongan ke panelnya.
    x0 = min(max(cx - w_pot / 2, 0.0), max(0.0, 1.0 - w_pot))
    y0 = min(max(cy - h_pot / 2, 0.0), max(0.0, 1.0 - h_pot))

    if n_grad >= 4:
        tepi = _tepi_panel(gx_jumlah / n_grad, gy_jumlah / n_grad,
                           (x0, y0, x0 + w_pot, y0 + h_pot), (x1, y1, x2, y2))
        if tepi is not None:
            x0, y0, xe, ye = tepi
            w_pot, h_pot = xe - x0, ye - y0

    if w_pot * h_pot > FACECAM_LUAS_MAKS:
        log.info("Petak wajah %.0f%%x%.0f%% memakan %.0f%% bingkai, terlalu besar "
                 "untuk panel facecam: ini bidikan kamera biasa, bukan gameplay",
                 w_pot * 100, h_pot * 100, w_pot * h_pot * 100)
        return None

    log.info("Facecam terdeteksi: %.0f%%x%.0f%% di (%.0f%%, %.0f%%), "
             "awan wajah %.2fx%.2f, %d deteksi dari %d sampel",
             w_pot * 100, h_pot * 100, x0 * 100, y0 * 100,
             lebar_awan, tinggi_awan, len(kiri), total)
    return {"x": x0 * 100, "y": y0 * 100, "w": w_pot * 100, "h": h_pot * 100,
            # Petak wajahnya sendiri, dipakai `batas_panel` sebagai titik mulai
            # memindai tepi. Kotak di atas sudah dilebarkan mengikuti rasio
            # bidang tujuan, jadi ia bisa MELUAP keluar panel — memindai dari
            # sana berarti memulai di sisi permainan dan langsung salah arah.
            "awan_kotak": [x1 * 100, y1 * 100, x2 * 100, y2 * 100],
            "awan": [lebar_awan, tinggi_awan], "kehadiran": len(kiri) / max(1, total)}


FACECAM_JENDELA = 8.0          # detik per potongan pemindaian
FACECAM_PINDAH = 0.08          # geser pusat (pecahan bingkai) yang dianggap pindah tempat


def deteksi_facecam_waktu(src, segments: list[dict], source_w: int, source_h: int,
                          rasio_potongan: float = 1080 / 768) -> list[dict]:
    """
    Letak facecam SEPANJANG klip: [{"t": detik_klip, "facecam": {...}}], urut.

    Streamer memindahkan kamera wajahnya di tengah siaran — dari kiri bawah ke
    kanan bawah, atau ke atas saat ada notifikasi. Terlapor: satu video yang
    sama, klip M dengan wajah di kiri bawah dibingkai di kiri ATAS, karena
    letaknya diambil sekali dari 30 detik pertama klip lain. Jadi klip dipindai
    per potongan `FACECAM_JENDELA` detik, dan letak baru dicatat hanya bila
    pusatnya bergeser jelas. Potongan tanpa wajah (pemain menutup muka saat
    jumpscare, kamera tertutup notifikasi) mewarisi letak sebelumnya.
    """
    potongan: list[tuple[float, float, float]] = []   # (detik klip, mulai sumber, panjang)
    t_klip = 0.0
    for sg in segments or []:
        a, b = float(sg["start"]), float(sg["end"])
        pos = a
        while b - pos > 0.5:
            panjang = min(FACECAM_JENDELA, b - pos)
            # Sisa pendek digabung ke potongan sebelumnya: 2 detik terlalu
            # sedikit untuk membedakan panel yang diam dari wajah yang lewat.
            if b - (pos + panjang) < 3.0:
                panjang = b - pos
            potongan.append((t_klip + (pos - a), pos, panjang))
            pos += panjang
        t_klip += b - a

    # Satu proses ffmpeg untuk tiap POTONGAN KLIP, bukan tiap jendela.
    #
    # Ongkos tetap menjalankan ffmpeg dan melompat ke detiknya ±0,9 detik, dan
    # dulu dibayar sekali per jendela 8 detik. Terukur pada klip 32 detik: 7,8
    # detik untuk empat proses melawan 5,2 detik untuk satu. Bingkainya dibagi
    # per jendela di sini, jadi jendelanya tetap ada — dan jendela itulah yang
    # menangkap facecam yang PINDAH TEMPAT di tengah klip, hal yang memang
    # terjadi: pada satu klip 30 detik video horor pemiliknya, panelnya pindah
    # dari tengah ke pojok pada detik ke-24.
    sw = SAMPLE_WIDTH
    sh = _even(SAMPLE_WIDTH * source_h / source_w)
    hasil: list[dict] = []
    for sg in segments or []:
        a, b = float(sg["start"]), float(sg["end"])
        milik = [q for q in potongan if a - 1e-6 <= q[1] < b]
        if not milik:
            continue
        aliran = _sample_frames(src, a, b - a, sw, sh)
        for t, mulai, panjang in milik:
            # Bingkai jendela ini saja. `fps` tetap, jadi jumlahnya bisa
            # dihitung, bukan ditebak.
            n = max(1, int(round(panjang * SAMPLE_FPS)))
            potong_bingkai = list(itertools.islice(aliran, n))
            fc = _facecam_dari_bingkai(iter(potong_bingkai), sw, sh,
                                       rasio_potongan=rasio_potongan)
            hasil.append({"t": round(t, 2), "facecam": fc})
        # Sisa bingkai potongan ini dibuang bersama alirannya.
        aliran.close()

    # Isi potongan kosong dari tetangga terdekat (yang sebelumnya dulu).
    ada = [h for h in hasil if h["facecam"]]
    if not ada:
        return []
    terakhir = None
    for h in hasil:
        if h["facecam"]:
            terakhir = h["facecam"]
        elif terakhir is not None:
            h["facecam"] = terakhir
    pertama = ada[0]["facecam"]
    for h in hasil:
        if h["facecam"] is None:
            h["facecam"] = pertama

    def pusat(f):
        return (f["x"] + f["w"] / 2) / 100.0, (f["y"] + f["h"] / 2) / 100.0

    def sama(f, g):
        (ax, ay), (bx, by) = pusat(f), pusat(g)
        return (abs(ax - bx) < FACECAM_PINDAH and abs(ay - by) < FACECAM_PINDAH
                and 0.4 < (f["w"] * f["h"]) / max(1e-6, g["w"] * g["h"]) < 2.5)

    ringkas: list[dict] = []
    for i, h in enumerate(hasil):
        if ringkas:
            if sama(ringkas[-1]["facecam"], h["facecam"]):
                continue
            # Pindah tempat harus DIBENARKAN potongan berikutnya. Satu potongan
            # yang menyimpang sendirian hampir selalu salah baca — wajah di
            # dalam permainan, atau orang yang bersandar pada facecam tanpa
            # bingkai. Terukur pada Devour: satu potongan 8 detik melompat ke
            # kotak 42x68% lalu kembali. Potongan terakhir tidak punya saksi,
            # jadi ia hanya dipercaya bila wajahnya hadir hampir di semua sampel.
            nanti = hasil[i + 1]["facecam"] if i + 1 < len(hasil) else None
            if nanti is not None:
                if not sama(h["facecam"], nanti):
                    continue
            elif float(h["facecam"].get("kehadiran") or 0) < 0.8:
                continue
        ringkas.append(h)
    ringkas[0]["t"] = 0.0
    if len(ringkas) > 1:
        log.info("Facecam berpindah dalam klip: %s", ", ".join(
            f"{h['t']:.0f}s→({h['facecam']['x']:.0f}%,{h['facecam']['y']:.0f}%)" for h in ringkas))
    return ringkas


# ---------------------------------------------------------------------------
# Catatan: menajamkan kotak facecam jadi batas panel yang sebenarnya
#
# Dicoba dua kali, keduanya dibuang, dan alasannya ditulis di sini supaya tidak
# dicoba untuk ketiga kalinya tanpa bahan uji yang lebih baik.
#
# (1) Kontras gerakan. Panel facecam dan layar permainan adalah dua sumber
#     gambar berbeda, jadi jumlah gerakannya berbeda; batas panel mestinya
#     terlihat sebagai tempat angka itu melompat. Hasilnya lebih buruk daripada
#     tidak menajamkan sama sekali: kotaknya melebar dari 22x25% jadi 30x54%
#     melawan panel sebenarnya 25x25%, karena ada bagian permainan yang
#     kebetulan setenang wajahnya dan perluasannya berjalan terus melewati tepi.
#
# (2) Tepi lurus yang tidak berpindah. Lebih menjanjikan: panel yang ditempel
#     punya garis di kolom dan baris yang persis sama di setiap bingkai, dan
#     rata-rata gradien lintas waktu memang menonjolkannya. Pada satu bahan uji
#     tepi kanan dan bawahnya ditemukan TEPAT (kolom 548 dan baris 305 melawan
#     548 dan 304 yang sebenarnya). Tapi pada bahan uji kedua tepi kirinya
#     meleset jauh — 54,6% melawan 72,9% — karena gambar permainan punya
#     garis-garisnya sendiri yang sama tajamnya, dan tepi atasnya meleset di
#     kedua bahan uji.
#
# Perkiraan sederhana dari awan wajah mengalahkan keduanya secara konsisten:
# 71,7-72,0% melawan 72,9% yang sebenarnya, pada kedua bahan uji. Jadi itu yang
# dipakai. Yang dibutuhkan sebelum mencoba lagi bukan algoritma yang lebih
# pintar melainkan rekaman gameplay SUNGGUHAN untuk diukur — kedua bahan uji di
# atas adalah facecam yang saya tempel sendiri di atas pola buatan, dan pola
# buatan tidak punya kebiasaan visual yang sama dengan permainan sungguhan.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Mengikuti GERAKAN, bukan wajah
#
# YuNet adalah pendeteksi wajah manusia. Pada kartun, maskot, hewan, atau
# rekaman layar ia tidak menemukan apa pun — `face_coverage` jatuh di bawah
# ambang dan seluruh klip berakhir sebagai bilah kabur. Untuk video Pinkfong di
# folder unduhan ini, itu berarti tokoh utamanya tidak pernah diikuti sama
# sekali, dan tidak ada setelan mana pun yang bisa memperbaikinya: modelnya
# memang tidak dilatih untuk wajah yang bukan wajah manusia.
#
# Yang dipakai di sini tidak memerlukan model apa pun: yang diikuti adalah
# perubahan antar bingkai. Tapi CARA membacanya sudah diganti sekali, dan
# selisihnya besar.
#
# Versi pertama memakai PUSAT MASSA seluruh gerakan di layar. Itu menjawab
# pertanyaan yang salah. Ketika dua tokoh bergerak di sisi berlawanan, pusat
# massanya jatuh persis di antara keduanya — bingkai memuat tepi kiri yang satu
# dan tepi kanan yang lain, dan tidak memuat satu pun secara utuh. Ketika latar
# ikut bergerak, pusatnya ditarik ke tengah layar. Hasilnya bingkai yang nyaris
# diam di tengah sambil bergetar sedikit: persis keluhan "belum mengikuti objek
# yang bergerak".
#
# Yang dipakai sekarang menjawab pertanyaan yang sungguh ditanyakan oleh crop:
# JENDELA selebar crop mana yang memuat gerakan paling banyak? Dijawab dengan
# jumlah berjalan di atas profil kolom, jadi ongkosnya tetap satu lintasan.
# Lalu pusatnya dihitung ULANG di dalam jendela pemenang saja, supaya tokohnya
# betul-betul di tengah dan bukan sekadar berada di dalam kotak.
#
# Terukur pada kartun Pinkfong (640x360, crop 9:16 = 202 px, 32% lebar), sebagai
# bagian energi gerak yang benar-benar masuk ke dalam kotak:
#
#                       t=90    t=300   t=550
#   pusat massa (lama)  60,6%   44,6%   63,7%
#   jendela dominan     68,6%   54,4%   71,0%
#
# Dan bingkainya benar-benar berpindah: simpangan posisi naik dari 46-87 px
# menjadi 126-139 px. Angka 32% adalah dasarnya — itulah yang akan didapat
# kotak yang diletakkan sembarangan pada gerakan yang tersebar rata.
#
# Pengurangan latar (membandingkan dengan rata-rata bergerak, bukan dengan
# bingkai sebelumnya) juga dicoba dan JUSTRU LEBIH BURUK di ketiga titik —
# 59,9% / 51,6% / 60,7% — karena kamera yang ikut bergeser membuat seluruh
# layar jadi latar depan. Tidak dipakai.
#
# Batasnya tetap jujur: pada bidikan diam tidak ada yang bisa diikuti, dan pada
# panning kamera seluruh layar bergerak sehingga jendela mana pun sama saja.
# Keduanya berakhir di tengah bingkai, yang memang jawaban yang benar saat
# tidak ada yang menonjol — dan penggunanya punya lajur Bingkai untuk
# membetulkannya per potongan waktu.
# ---------------------------------------------------------------------------

# Perubahan di bawah ini dianggap derau pengkodean, bukan gerakan.
GERAK_AMBANG = 10.0
# Bagian bingkai yang berubah, di atas mana perubahan itu dianggap potongan
# adegan dan bukan gerakan di dalam adegan yang sama.
GERAK_CUT_BAGIAN = 0.55
# Tarikan ke posisi jendela sebelumnya, sebagai pecahan lebar layar per piksel
# jarak. Ketika dua kelompok gerakan hampir sama kuat, tanpa ini jendela
# berkedip bolak-balik di antara keduanya tiap sampel. Terukur pada kartun:
# kekasaran turun dari 49,4 px menjadi 43,3 px per sampel, dengan ongkos
# ketepatan 0,2% — murah.
GERAK_TARIKAN = 0.35
# Di bawah bagian ini, gerakan di layar dianggap derau dan sampelnya dilewati.
GERAK_DIAM = 0.002
# Sampel bergerak minimum sebelum mode ini dianggap layak dipakai sama sekali.
GERAK_CAKUPAN_MIN = 0.10


def _profil_kolom(sebelum, kini, ambang: float):
    """
    (energi gerak per kolom, bagian layar yang berubah).

    Menjumlahkan ke bawah menghilangkan sumbu tegak, dan itu memang yang
    diinginkan: crop-nya setinggi sumber, jadi hanya x yang perlu diputuskan.
    """
    beda = abs(kini - sebelum)
    kuat = beda > ambang
    return (beda * kuat).sum(axis=0), float(kuat.mean())


def _jendela_terpadat(profil, lebar: int, sebelumnya, tarikan: float):
    """
    Pusat jendela selebar `lebar` yang memuat energi terbanyak.

    Jumlah berjalan (`cumsum`) membuat seluruh pencarian jadi satu pengurangan
    vektor: ks[a+lebar] - ks[a] adalah energi di setiap letak jendela sekaligus.

    Yang dikembalikan BUKAN titik tengah jendelanya, melainkan pusat massa di
    DALAM jendela itu. Bedanya terasa saat tokohnya berada di pinggir kumpulan
    gerakan: titik tengah jendela akan menaruhnya di tepi kotak, pusat massa di
    dalam jendela menaruhnya di tengah.
    """
    import numpy as np

    n = len(profil)
    lebar = max(1, min(lebar, n))
    ks = np.concatenate(([0.0], np.cumsum(profil)))
    awal = np.arange(0, n - lebar + 1)
    muatan = ks[awal + lebar] - ks[awal]

    if sebelumnya is not None and tarikan > 0:
        pusat_jendela = awal + lebar / 2.0
        muatan = muatan * (1.0 - tarikan * np.abs(pusat_jendela - sebelumnya) / n)

    a = int(np.argmax(muatan))
    potong = profil[a:a + lebar]
    total = float(potong.sum())
    if total <= 0:
        return None
    return a + float((potong * np.arange(lebar)).sum() / total)


def _scan_gerak(src: Path, segments: list[dict], source_w: int, source_h: int,
                crop_w: int):
    """
    (pusat_x per sampel, penanda potongan adegan, cakupan) dari gerakan layar.

    Bentuk kembaliannya sengaja sama dengan bagian yang dipakai `_scan_scene`,
    supaya seluruh penghalusan dan penyusunan keyframe di bawahnya tidak perlu
    tahu dari mana angkanya datang.

    `crop_w` ikut masuk karena lebar kotaklah yang menentukan jendela mana yang
    dicari. Tanpa itu, fungsi ini hanya bisa menjawab "di mana gerakannya" —
    pertanyaan yang jawabannya tidak cukup untuk menaruh sebuah kotak.
    """
    try:
        import numpy as np
    except ImportError:
        return None

    sw = SAMPLE_WIDTH
    sh = _even(SAMPLE_WIDTH * source_h / source_w)
    skala = source_w / sw
    lebar_sampel = max(1, int(round(crop_w / skala)))

    centers: list[Optional[float]] = []
    cuts: list[bool] = []
    terakhir: Optional[float] = None       # dalam piksel sampel

    for seg in segments:
        mulai = float(seg["start"])
        panjang = max(0.0, float(seg["end"]) - mulai)
        sebelum = None
        for buf in _sample_frames(src, mulai, panjang, sw, sh):
            kini = np.frombuffer(buf, dtype=np.uint8).reshape((sh, sw, 3)).mean(axis=2)
            if sebelum is None:
                sebelum = kini
                centers.append(None)
                cuts.append(False)
                continue

            profil, bagian = _profil_kolom(sebelum, kini, GERAK_AMBANG)
            sebelum = kini

            # Seluruh layar berubah = adegan berganti, bukan tokoh bergerak.
            # Ditandai supaya penghalusan MELOMPAT alih-alih menggeser kamera
            # melintasi potongan — geseran itu yang terlihat paling salah.
            potong = bagian > GERAK_CUT_BAGIAN
            cuts.append(potong)
            if potong:
                terakhir = None            # jangan tarik ke posisi adegan lama
                centers.append(None)
                continue
            if bagian < GERAK_DIAM:
                centers.append(None)       # tidak ada yang bisa diikuti
                continue

            pusat = _jendela_terpadat(profil, lebar_sampel, terakhir, GERAK_TARIKAN)
            if pusat is None:
                centers.append(None)
                continue
            terakhir = pusat
            centers.append(pusat * skala)

    if len(centers) < 4:
        return None
    terlihat = sum(1 for c in centers if c is not None) / len(centers)
    if terlihat < GERAK_CAKUPAN_MIN:
        # Hampir tidak ada gerakan sama sekali: bidikan diam, papan tulis,
        # layar menu. Mengikuti apa pun di situ hanya akan menggoyang gambar.
        log.info("Gerakan hanya terdeteksi di %.0f%% sampel, bingkai gerak dilewati",
                 terlihat * 100)
        return None
    return centers, cuts, terlihat
