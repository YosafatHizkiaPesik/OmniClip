"""
Pemisahan penutur: menebak ADA BERAPA orang bicara dan siapa mengucapkan apa.

Versi pertama modul ini memakai MFCC + k-means yang ditulis dari nol. Itu jujur
tapi lemah: pada podcast dua orang yang jelas berbeda (satu pria, satu wanita)
skor siluetnya hanya 0,14 — tepat di ambang — dan sistem menyerah lalu menyebut
seluruh video satu penutur. Rata-rata MFCC memang menangkap sedikit warna
suara, tapi ia juga menangkap bunyi vokal yang sedang diucapkan, dan komponen
kedua itu jauh lebih besar daripada yang pertama.

Sekarang embedding-nya datang dari model verifikasi penutur sungguhan: CAM++
dari proyek 3D-Speaker, dijalankan lewat onnxruntime. 27 MB, satu berkas ONNX,
tanpa torch — jadi tetap muat di anggaran memori mesin ini. Model itu dilatih
justru untuk memisahkan identitas suara dari isi ucapannya, yang persis
kebalikan dari kelemahan MFCC.

Fitur masukannya adalah fbank 80 bin gaya Kaldi, dihitung di sini dengan numpy
supaya tidak perlu torchaudio. Rinciannya (jendela povey, praemfasis 0,97,
pembuangan DC per bingkai, spektrum daya) ditiru persis karena model ini hanya
pernah melihat fitur yang dibuat begitu.

Batasnya tetap perlu diketahui: suara bertindih, musik latar keras, atau
rekaman satu mikrofon yang jauh masih akan meleset. Karena itu hasilnya selalu
bisa disunting per baris di editor.
"""

import logging
import math
import os
import wave
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..config import MODELS_DIR

log = logging.getLogger("omniclip.diarize")

SAMPLE_RATE = 16000

# --- Fitur fbank gaya Kaldi ---------------------------------------------------
FBANK_BINS = 80
FRAME_LEN = 400        # 25 ms
FRAME_SHIFT = 160      # 10 ms
N_FFT = 512            # ukuran jendela dipadkan ke pangkat dua terdekat
PREEMPH = 0.97
LOW_FREQ = 20.0
HIGH_FREQ = 8000.0

# --- Model --------------------------------------------------------------------
MODEL_PATH = MODELS_DIR / "campplus_sv.onnx"
MODEL_URL = ("https://huggingface.co/csukuangfj/speaker-embedding-models/"
             "resolve/main/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx")
EMBED_DIM = 192

# Panjang satu jendela pengenalan, diukur bukan ditebak. Pada video satu
# penutur, kemiripan antar jendela orang yang sama naik tajam dengan panjangnya:
# 0,62 pada 2 detik, 0,70 pada 4 detik, 0,79 pada 8 detik. Di bawah tiga detik
# sebaran "orang yang sama" dan "orang berbeda" saling tindih terlalu banyak
# untuk dipisahkan; jauh di atasnya, satu jendela mulai sering memuat dua orang
# sekaligus dan justru mengaburkan batas giliran. 3,5 detik adalah titik temunya.
WINDOW_SECONDS = 3.5
MIN_WINDOW_SECONDS = 1.8
# Jeda selebar ini memutus jendela: keheningan panjang hampir selalu menandai
# pergantian pembicara, dan menyatukan seberangnya mencampur dua suara.
WINDOW_BREAK_GAP = 1.6
# Delapan, bukan empat. Empat memotong tepat pada bentuk yang paling sering
# dipakai: podcast meja panjang dengan pembawa acara dan empat tamu. Video
# seperti itu dijawab "4 penutur" apa pun isinya, dan orang kelima diam-diam
# digabungkan ke salah satu dari empat yang lain — kesalahan yang tidak
# terlihat sebagai kesalahan, hanya sebagai warna teks yang keliru.
#
# Batas ini juga yang membatasi pilihan manual: pengguna yang tahu ada lima
# orang pun tidak bisa mengatakannya.
MAX_SPEAKERS = 8

# Selisih kemiripan: rata-rata kemiripan DI DALAM kelompok dikurangi rata-rata
# kemiripan ANTAR kelompok. Angkanya bisa dibandingkan langsung dengan
# kalibrasi model — sekitar 0,70 untuk orang yang sama pada jendela sepanjang
# ini, sekitar 0,25 untuk orang berbeda.
#
# Versi sebelumnya memakai kelompok TERLEMAH lawan pasangan TERDEKAT
# (`min(dalam) - max(antar)`), dan itu keliru dengan cara yang mahal: jumlah
# pasangan antar-kelompok tumbuh kuadratik (k=2 punya satu pasang, k=5 punya
# sepuluh), sehingga `max(antar)` hampir pasti naik setiap kali k bertambah
# sementara `min(dalam)` hampir pasti turun. Ukuran itu karena itu TIDAK PERNAH
# bisa memilih k besar, apa pun isi rekamannya.
#
# Terukur pada podcast yang judulnya menyebut empat nama: ukuran lama memberi
# +0,074 di k=2 lalu jatuh ke -0,013 di k=4, sehingga sistem menjawab "2
# narasumber" untuk video berisi empat orang. Ukuran rata-rata pada rekaman
# yang sama memuncak justru di k=4 (0,238 lawan 0,151 di k=2).
MIN_SEPARATION = 0.06

# Seberapa runtut label itu dalam waktu, dibandingkan label acak berproporsi
# sama. Giliran bicara sungguhan berlangsung beberapa jendela berturut-turut;
# pengelompokan derau berpindah-pindah tiap jendela.
#
# Ini pembanding yang sepenuhnya BEBAS dari ukuran kemiripan di atas — ia tidak
# melihat embedding sama sekali, hanya urutan labelnya — jadi ketika keduanya
# menunjuk k yang sama, kesepakatan itu berarti. Pada podcast empat nama tadi,
# keduanya sama-sama memuncak di k=4.
#
# Acuan acaknya dihitung, bukan disimulasikan: untuk label bebas dengan
# proporsi p, peluang dua tetangga berbeda adalah 1 - sum(p^2), jadi panjang
# giliran yang diharapkan adalah kebalikannya.
MIN_COHERENCE = 1.35

# Nilai gabungan = pemisahan x keruntutan. Ambang bawahnya diukur terhadap
# kontrol negatif: rekaman stand-up satu orang memberi 0,064 (keruntutan hanya
# 1,08x, nyaris acak), sedangkan tiga rekaman banyak-orang memberi 0,318,
# 0,494, dan 0,690. Celahnya lebar; 0,15 duduk di dalamnya dengan jarak aman ke
# kedua sisi.
MIN_QUALITY = 0.15

# Penutur tidak ditambah hanya karena nilainya naik setitik. Tanpa syarat ini,
# rekaman dua orang terpilih sebagai tiga orang dengan selisih nilai 3% — beda
# yang tidak berarti apa-apa. Dengan 12%, ketiga rekaman uji terjawab benar.
K_MARGIN = 0.12

_session = None
_banks: Optional[np.ndarray] = None
_window: Optional[np.ndarray] = None


@dataclass
class Diarization:
    labels: list[int]          # satu label per span yang diminta
    speaker_count: int
    separation: float          # selisih kemiripan dalam-kelompok vs antar-kelompok
    coherence: float = 0.0     # keruntutan waktu, kelipatan acuan acak
    quality: float = 0.0       # pemisahan x keruntutan
    requested: Optional[int] = None   # jumlah yang diminta pengguna, bila ada

    @property
    def confident(self) -> bool:
        """
        Layak dipercaya bila DUA ukuran yang saling bebas sama-sama lulus.

        Bukan penjaga yang membatalkan hasil — labelnya tetap dikembalikan dan
        tetap bisa disunting. Ini hanya menentukan apakah antarmuka menuliskan
        "terdeteksi 4 narasumber" atau "± 4 narasumber".
        """
        return (self.speaker_count > 1
                and self.quality >= MIN_QUALITY
                and self.coherence >= MIN_COHERENCE)


# --- Fitur --------------------------------------------------------------------
def _mel(f: np.ndarray | float) -> np.ndarray | float:
    return 1127.0 * np.log(1.0 + np.asarray(f, dtype=np.float64) / 700.0)


def _mel_banks() -> np.ndarray:
    """
    Bank filter mel gaya Kaldi: segitiga yang dibagi rata di ranah mel.

    Berbeda dari bank filter librosa/HTK pada normalisasi luasnya — Kaldi tidak
    menormalkan, dan model ini dilatih dengan yang tidak dinormalkan.
    """
    global _banks
    if _banks is not None:
        return _banks
    n_bins = N_FFT // 2 + 1
    freqs = np.arange(n_bins) * (SAMPLE_RATE / N_FFT)
    mels = _mel(freqs)
    mel_low, mel_high = _mel(LOW_FREQ), _mel(HIGH_FREQ)
    delta = (mel_high - mel_low) / (FBANK_BINS + 1)

    banks = np.zeros((FBANK_BINS, n_bins), dtype=np.float32)
    for b in range(FBANK_BINS):
        left = mel_low + b * delta
        center = left + delta
        right = center + delta
        rising = (mels - left) / delta
        falling = (right - mels) / delta
        weight = np.minimum(rising, falling)
        banks[b] = np.where((mels > left) & (mels < right), weight, 0.0)
    _banks = banks
    return banks


def _povey() -> np.ndarray:
    """Jendela povey Kaldi: Hann dipangkatkan 0,85."""
    global _window
    if _window is None:
        i = np.arange(FRAME_LEN, dtype=np.float64)
        _window = ((0.5 - 0.5 * np.cos(2 * math.pi * i / (FRAME_LEN - 1))) ** 0.85
                   ).astype(np.float32)
    return _window


def kaldi_fbank(signal: np.ndarray) -> Optional[np.ndarray]:
    """
    fbank log-mel 80 bin, cocok dengan torchaudio.compliance.kaldi.fbank.

    `signal` berskala int16 (bukan [-1,1]): pilihan skala sebenarnya tidak
    penting karena normalisasi rerata di bawah menghapus penggeseran konstan
    yang ditimbulkan log, tapi skala besar menjauhkan nilai dari lantai epsilon.
    """
    n = signal.shape[0]
    if n < FRAME_LEN:
        return None
    n_frames = 1 + (n - FRAME_LEN) // FRAME_SHIFT

    idx = (np.arange(FRAME_LEN)[None, :]
           + FRAME_SHIFT * np.arange(n_frames)[:, None])
    frames = signal[idx].astype(np.float64)

    frames -= frames.mean(axis=1, keepdims=True)          # buang offset DC
    # Praemfasis; sampel pertama tiap bingkai memakai dirinya sendiri sebagai
    # tetangga kiri, persis seperti Kaldi.
    emph = np.empty_like(frames)
    emph[:, 1:] = frames[:, 1:] - PREEMPH * frames[:, :-1]
    emph[:, 0] = frames[:, 0] - PREEMPH * frames[:, 0]
    emph *= _povey()

    spectrum = np.fft.rfft(emph, n=N_FFT, axis=1)
    power = (spectrum.real ** 2 + spectrum.imag ** 2)
    mel = power @ _mel_banks().T
    return np.log(np.maximum(mel, np.finfo(np.float32).eps)).astype(np.float32)


# --- Model --------------------------------------------------------------------
def _ensure_model() -> bool:
    """Mengunduh model saat pertama dipakai. 27 MB, sekali seumur pemasangan."""
    if MODEL_PATH.is_file() and MODEL_PATH.stat().st_size > 1_000_000:
        return True
    import urllib.request
    tmp = MODEL_PATH.with_suffix(".part")
    try:
        log.info("Mengunduh model pengenal suara (27 MB)…")
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(MODEL_URL, timeout=120) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        os.replace(tmp, MODEL_PATH)
        return True
    except Exception as e:                       # jaringan mati, disk penuh, dst.
        log.warning("Gagal mengunduh model penutur: %s", str(e)[:200])
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _get_session():
    global _session
    if _session is not None:
        return _session
    if not _ensure_model():
        return None
    try:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        # Satu utas: modul ini berjalan di lane `cpu` yang memang sudah
        # dibatasi satu pekerjaan, dan pipeline lain masih butuh intinya.
        opts.intra_op_num_threads = 2
        opts.log_severity_level = 3
        _session = ort.InferenceSession(str(MODEL_PATH), opts,
                                        providers=["CPUExecutionProvider"])
    except Exception as e:
        log.warning("onnxruntime gagal memuat model penutur: %s", str(e)[:200])
        return None
    return _session


def _embed(features: np.ndarray) -> Optional[np.ndarray]:
    """Satu embedding 192 dimensi dari fbank [T, 80], sudah dinormalkan L2."""
    sess = _get_session()
    if sess is None or features is None or features.shape[0] < 40:
        return None
    # Normalisasi rerata global: kurangi rerata tiap bin sepanjang waktu.
    # Inilah `feature_normalize_type: global-mean` di metadata model.
    feats = features - features.mean(axis=0, keepdims=True)
    out = sess.run(["embedding"], {"x": feats[None, :, :].astype(np.float32)})[0][0]
    norm = float(np.linalg.norm(out))
    return out / norm if norm > 1e-8 else None


# --- Pembacaan audio ----------------------------------------------------------
def _read(wf: wave.Wave_read, start: float, end: float) -> Optional[np.ndarray]:
    """Membaca sepotong WAV dengan seek langsung, tanpa memuat seluruh berkas."""
    a = int(max(0.0, start) * SAMPLE_RATE)
    n = int(max(0.0, end - start) * SAMPLE_RATE)
    total = wf.getnframes()
    if n <= 0 or a >= total:
        return None
    wf.setpos(a)
    raw = wf.readframes(min(n, total - a))
    if not raw:
        return None
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32)


def _build_windows(spans: list[tuple[float, float]]) -> list[tuple[list, list]]:
    """
    Memotong seluruh ucapan menjadi jendela berdurasi tetap.

    Versi pertama mengelompokkan kalimat menjadi "giliran bicara" lewat jeda
    hening. Pada podcast itu gagal total: jeda selebar satu detik hampir tidak
    pernah ada, jadi seluruh video jatuh menjadi beberapa giliran raksasa,
    masing-masing diwakili empat detik audio dari tengahnya. Modelnya
    memisahkan dengan baik — siluet 0,357 — tapi hasilnya diberikan ke ribuan
    kalimat sekaligus, sehingga semuanya berakhir dengan satu label yang sama.

    Segmentasi seragam adalah cara diarisasi sungguhan bekerja: potong rata,
    kelompokkan potongannya, baru petakan balik ke kalimat. Batas pembicara
    ditemukan oleh pengelompokan, bukan ditebak lebih dulu dari keheningan.

    Mengembalikan daftar (potongan_waktu, indeks_kalimat_yang_tersentuh).
    """
    windows: list[tuple[list, list]] = []
    pieces: list[tuple[float, float]] = []
    touched: list[int] = []
    filled = 0.0
    prev_end: Optional[float] = None

    def flush(minimum: float) -> None:
        nonlocal pieces, touched, filled
        if filled >= minimum and pieces:
            windows.append((pieces, touched))
        pieces, touched, filled = [], [], 0.0

    for i, (s_, e_) in enumerate(spans):
        if e_ - s_ <= 0.05:
            continue
        if prev_end is not None and s_ - prev_end >= WINDOW_BREAK_GAP:
            flush(MIN_WINDOW_SECONDS)
        cursor = s_
        while cursor < e_ - 1e-6:
            take = min(e_ - cursor, WINDOW_SECONDS - filled)
            pieces.append((cursor, cursor + take))
            if not touched or touched[-1] != i:
                touched.append(i)
            filled += take
            cursor += take
            if filled >= WINDOW_SECONDS - 1e-6:
                flush(0.0)
        prev_end = e_

    flush(MIN_WINDOW_SECONDS)
    return windows


def _window_audio(wf: wave.Wave_read,
                  pieces: list[tuple[float, float]]) -> Optional[np.ndarray]:
    """Menyambung potongan-potongan sebuah jendela menjadi satu deret sampel."""
    chunks = []
    for s_, e_ in pieces:
        chunk = _read(wf, s_, e_)
        if chunk is not None and chunk.size:
            chunks.append(chunk)
    if not chunks:
        return None
    audio = np.concatenate(chunks)
    return audio if audio.size >= FRAME_LEN * 4 else None


# --- Pengelompokan ------------------------------------------------------------
def _kmeans(x: np.ndarray, k: int, *, iters: int = 60, seed: int = 7):
    """k-means++ pada vektor yang sudah dinormalkan L2 (jarak Euclid == kosinus)."""
    rng = np.random.default_rng(seed)
    centers = [x[rng.integers(len(x))]]
    for _ in range(1, k):
        d = np.min(((x[:, None, :] - np.array(centers)[None, :, :]) ** 2).sum(-1), axis=1)
        total = d.sum()
        probs = d / total if total > 0 else np.full(len(x), 1 / len(x))
        centers.append(x[rng.choice(len(x), p=probs)])
    c = np.array(centers)

    labels = np.zeros(len(x), dtype=int)
    for _ in range(iters):
        d = ((x[:, None, :] - c[None, :, :]) ** 2).sum(-1)
        new = d.argmin(axis=1)
        if np.array_equal(new, labels):
            break
        labels = new
        for j in range(k):
            members = x[labels == j]
            if len(members):
                v = members.mean(axis=0)
                n = np.linalg.norm(v)
                c[j] = v / n if n > 1e-8 else c[j]
    return labels, c


def _separation(x: np.ndarray, labels: np.ndarray, k: int) -> float:
    """
    Seberapa jauh suara antar kelompok, di ranah kemiripan kosinus asli.

    Dihitung pada embedding MENTAH, bukan yang reratanya sudah dibuang:
    angkanya jadi bisa dibandingkan langsung dengan kalibrasi model yang
    terukur — sekitar 0,70 untuk orang yang sama pada jendela sepanjang ini,
    dan sekitar 0,25 untuk orang berbeda.

    Rata-rata lawan rata-rata. Alasan lengkapnya ada di catatan MIN_SEPARATION:
    memakai kelompok terlemah lawan pasangan terdekat membuat ukuran ini
    mustahil memilih lebih dari dua penutur, karena jumlah pasangan yang
    dimaksimalkan bertambah kuadratik terhadap k.
    """
    if k < 2:
        return 0.0
    withins = []
    for c in range(k):
        members = x[labels == c]
        if len(members) < 2:
            return 0.0
        sim = members @ members.T
        withins.append(float(sim[np.triu_indices(len(sim), 1)].mean()))
    crosses = [float((x[labels == a] @ x[labels == b].T).mean())
               for a in range(k) for b in range(a + 1, k)]
    if not crosses:
        return 0.0
    return round(float(np.mean(withins)) - float(np.mean(crosses)), 4)


def _coherence(labels: np.ndarray, k: int) -> float:
    """
    Panjang giliran rata-rata, dibagi panjang yang akan muncul dari label acak
    berproporsi sama.

    Nilai 1,0 berarti labelnya tidak lebih runtut daripada lemparan dadu — yang
    persis seperti apa pengelompokan derau terlihat. Terukur: rekaman satu
    orang yang dipaksa jadi lima kelompok memberi 1,08; rekaman banyak orang
    yang benar memberi 1,9 sampai 2,8.
    """
    n = int(labels.size)
    if n < 2 or k < 2:
        return 0.0
    lengths: list[int] = []
    run = 1
    for a, b in zip(labels[:-1], labels[1:]):
        if a == b:
            run += 1
        else:
            lengths.append(run)
            run = 1
    lengths.append(run)
    share = np.bincount(labels, minlength=k) / n
    expected = 1.0 / max(1e-9, 1.0 - float((share ** 2).sum()))
    return round(float(np.mean(lengths)) / expected, 3)


def _quality(x: np.ndarray, labels: np.ndarray, k: int) -> tuple[float, float, float]:
    """Mengembalikan (nilai gabungan, pemisahan, keruntutan)."""
    sep = _separation(x, labels, k)
    coh = _coherence(labels, k)
    return round(sep * coh, 4), sep, coh


def _smooth(labels: np.ndarray, k: int, window: int = 3) -> np.ndarray:
    """
    Modus bergerak atas deret label.

    Giliran bicara berlangsung beberapa kalimat; label yang berganti setiap satu
    giliran hampir pasti derau pengelompokan, bukan percakapan sungguhan.
    """
    if window < 3 or labels.size < window:
        return labels
    half = window // 2
    out = labels.copy()
    for i in range(labels.size):
        lo, hi = max(0, i - half), min(labels.size, i + half + 1)
        out[i] = np.bincount(labels[lo:hi], minlength=k).argmax()
    return out


# Berapa banyak jendela bertambatan yang dibutuhkan sebelum suara seseorang
# boleh dimodelkan. Di bawah ini, reratanya ditentukan oleh satu-dua potongan
# yang kebetulan, dan model yang lahir darinya menarik semua orang kepadanya.
MIN_ANCHORS = 4

# Seberapa jauh jendela harus lebih dekat ke satu model suara daripada ke model
# terdekat berikutnya sebelum labelnya dipercaya.
MIN_VOICE_MARGIN = 0.04

# Seberapa benar model suara harus menebak potongan yang TIDAK dipakai
# membuatnya, sebelum labelnya boleh menggantikan hasil pengelompokan biasa.
#
# Ini penjaga yang paling penting di seluruh fungsi ini, dan alasannya terukur.
# Jangkar visual tidak selalu bersih: kamera juga memotong ke orang yang
# menyimak, dan bukaan mulut bisa keliru. Ketika jangkarnya tercemar, model
# suara kedua orang saling meleleh — dan label yang lahir darinya terlihat
# meyakinkan justru karena ia dibangun dari bukti yang sama yang dipakai
# menilainya.
#
# Uji silang memutus lingkaran itu: model dibangun dari separuh jangkar, lalu
# ditanyai separuh yang belum pernah dilihatnya. Diukur pada empat rekaman —
# podcast dua orang berpotong close-up lulus dengan 90%, sementara rekaman meja
# statis dan podcast yang wajahnya jarang sendirian hanya 50-58%, nyaris
# setara tebakan acak untuk dua orang. Ambang 0,70 memisahkan keduanya, dan
# yang tidak lulus kembali memakai pengelompokan suara seperti biasa.
MIN_HOLDOUT_ACCURACY = 0.70

# Berapa potongan uji minimal supaya angka di atas berarti sesuatu. Dengan
# empat potongan, satu tebakan beruntung sudah memindahkan akurasinya 25 poin.
MIN_HOLDOUT_SAMPLES = 8


def label_from_evidence(wav_path: str, spans: list[tuple[float, float]],
                        span_person: list, n_people: int) -> Optional[Diarization]:
    """
    Memberi label penutur dari SUARA, tapi diajari oleh GAMBAR.

    Ini membalik urutan yang dipakai `analyze_speakers`. Di sana pengelompokan
    suara berdiri sendiri, menebak sekaligus ada berapa orang dan siapa bicara
    kapan, lalu wajah dicocokkan belakangan. Dua tebakan bertumpuk, dan yang
    pertama rapuh: diukur pada rekaman taman berisi lima orang, kurva nilainya
    datar dari k=2 sampai k=8 (0,19 sampai 0,24) tanpa puncak, dan k=4
    diterima dengan selisih 0,0002 atas k=3 — jumlah penuturnya praktis
    ditentukan lemparan koin.

    Di sini gambar yang menjawab lebih dulu. Ketika layar hanya memuat satu
    wajah, penyuntingnya sendiri sudah mengatakan siapa yang bicara; ketika
    beberapa wajah terlihat, bukaan mulut yang menjawab. Potongan suara pada
    saat-saat itu menjadi CONTOH BERLABEL, dan dari contoh itu disusun satu
    model suara per orang. Sisa rekaman — termasuk saat penuturnya tidak
    terlihat kamera sama sekali — dilabeli dengan mencari model terdekat.

    Hasilnya bukan cuma lebih tepat, tapi juga lebih berguna: labelnya ADALAH
    nomor orang. Warna subtitle dan nomor wajah tidak perlu dicocokkan lagi
    karena keduanya memang satu hal yang sama.

    `span_person[i]` berisi (orang, keyakinan) atau None untuk tiap span.
    Mengembalikan None bila jangkarnya terlalu sedikit untuk dipercaya —
    pemanggil lalu memakai `analyze_speakers` seperti biasa.
    """
    if not spans or n_people < 2 or _get_session() is None:
        return None

    windows = _build_windows(spans)
    vectors: list[np.ndarray] = []
    covers: list[list[int]] = []
    try:
        with wave.open(wav_path, "rb") as wf:
            if wf.getframerate() != SAMPLE_RATE or wf.getnchannels() != 1:
                return None
            for pieces, touched in windows:
                audio = _window_audio(wf, pieces)
                if audio is None:
                    continue
                vec = _embed(kaldi_fbank(audio))
                if vec is not None:
                    vectors.append(vec)
                    covers.append(touched)
    except (OSError, wave.Error) as e:
        log.warning("Gagal membaca audio untuk penambatan wajah: %s", e)
        return None
    if len(vectors) < 8:
        return None

    x = np.vstack(vectors)
    centered = x - x.mean(axis=0)
    centered = centered / np.maximum(np.linalg.norm(centered, axis=1, keepdims=True), 1e-8)

    # Bukti per jendela: suara terbanyak dari span yang disentuhnya, ditimbang
    # keyakinannya. Satu jendela bisa menyeberangi batas kalimat, jadi tidak
    # ada satu jawaban yang otomatis benar.
    jangkar: dict[int, list[int]] = {}
    for pos, touched in enumerate(covers):
        suara: dict[int, float] = {}
        for i in touched:
            bukti = span_person[i] if i < len(span_person) else None
            if bukti is None:
                continue
            orang, yakin = int(bukti[0]), float(bukti[1])
            suara[orang] = suara.get(orang, 0.0) + max(0.0, yakin)
        if not suara:
            continue
        menang = max(suara, key=suara.get)
        # Bukti yang terbelah tidak dipakai: jendela yang separuhnya menunjuk
        # orang lain adalah jendela yang memuat pergantian giliran.
        if suara[menang] < 0.6 * sum(suara.values()):
            continue
        jangkar.setdefault(menang, []).append(pos)

    model = {orang: pos for orang, pos in jangkar.items() if len(pos) >= MIN_ANCHORS}
    if len(model) < 2:
        log.info("Hanya %d dari %d orang punya cukup jangkar suara "
                 "(%s dari %d jendela) — penambatan dilewati",
                 len(model), n_people,
                 {o: len(v) for o, v in sorted(jangkar.items())}, len(covers))
        return None

    # --- Model menguji dirinya sendiri sebelum dipercaya ---------------------
    def _pusat(pilihan: dict):
        keluar = {}
        for o, pos in pilihan.items():
            if len(pos) < 2:
                continue
            v = centered[pos].mean(axis=0)
            keluar[o] = v / max(1e-9, float(np.linalg.norm(v)))
        return keluar

    latih = {o: pos[0::2] for o, pos in model.items()}
    uji = {o: pos[1::2] for o, pos in model.items()}
    p_latih = _pusat(latih)
    if len(p_latih) >= 2:
        urut_l = sorted(p_latih)
        ML = np.stack([p_latih[o] for o in urut_l])
        benar = jumlah = 0
        for o, pos in uji.items():
            if o not in p_latih:
                continue
            for i in pos:
                jumlah += 1
                benar += int(urut_l[int(np.argmax(centered[i] @ ML.T))] == o)
        akurasi = benar / jumlah if jumlah else 0.0
        # Uji yang tidak bisa dijalankan BUKAN uji yang lulus.
        #
        # Versi pertama penjaga ini hanya menolak bila sampel ujinya cukup
        # banyak, dan diam-diam meluluskan sisanya — termasuk satu klip yang
        # menebak 1 dari 5 dengan benar. Padahal jangkar sesedikit itu justru
        # tanda bahwa modelnya memang belum layak dipercaya.
        if jumlah < MIN_HOLDOUT_SAMPLES:
            log.info("Jangkar terlalu sedikit untuk diuji silang (%d potongan) "
                     "— penambatan dilewati", jumlah)
            return None
        if akurasi < MIN_HOLDOUT_ACCURACY:
            log.info("Model suara gagal menebak potongan yang tak dilatihkan "
                     "(%d/%d = %.0f%%) — penambatan dilewati, kembali ke "
                     "pengelompokan suara", benar, jumlah, 100 * akurasi)
            return None
        log.info("Model suara lulus uji silang: %d/%d = %.0f%%",
                 benar, jumlah, 100 * akurasi)
    else:
        log.info("Kurang dari dua orang punya jangkar terpisah — penambatan dilewati")
        return None

    pusat = {}
    for orang, pos in model.items():
        v = centered[pos].mean(axis=0)
        pusat[orang] = v / max(1e-9, float(np.linalg.norm(v)))
    orang_urut = sorted(pusat)
    M = np.stack([pusat[o] for o in orang_urut])

    # Seberapa jauh model-model itu satu sama lain. Kalau dua orang menghasilkan
    # model yang nyaris sama, yang terjadi bukan dua suara melainkan satu suara
    # yang jangkarnya tercemar — dan melabeli seluruh rekaman dengan model
    # seperti itu hanya memindahkan kekeliruan ke mana-mana.
    iu = np.triu_indices(len(M), 1)
    jauh = float((1.0 - (M @ M.T)[iu]).min()) if len(M) > 1 else 0.0
    if jauh < 0.10:
        log.info("Model suara antar orang terlalu mirip (jarak %.3f) — "
                 "penambatan dilewati", jauh)
        return None

    sim = centered @ M.T
    pilih = sim.argmax(axis=1)
    urut = np.sort(sim, axis=1)
    margin = urut[:, -1] - urut[:, -2] if sim.shape[1] > 1 else np.ones(len(sim))

    # Suara terbanyak per span, hanya dari jendela yang pilihannya cukup tegas.
    votes = [{} for _ in spans]
    for pos, touched in enumerate(covers):
        if margin[pos] < MIN_VOICE_MARGIN:
            continue
        orang = orang_urut[int(pilih[pos])]
        for i in touched:
            votes[i][orang] = votes[i].get(orang, 0) + 1

    out: list[int] = []
    terakhir = orang_urut[0]
    for tally in votes:
        if tally:
            terakhir = max(tally, key=tally.get)
        out.append(int(terakhir))

    k = max(out) + 1
    smoothed = _smooth(np.asarray(out), k).tolist()
    ganti = sum(1 for a, b in zip(smoothed, smoothed[1:]) if a != b)
    # Mutu diukur di ranah JENDELA, tempat embedding-nya hidup. `smoothed`
    # panjangnya sepanjang daftar span, dan memakainya di sini akan
    # menyandingkan dua deret yang panjangnya berbeda.
    label_jendela = np.array([orang_urut[int(i)] for i in pilih])
    sep = (_separation(x, label_jendela, k)
           if len(set(label_jendela.tolist())) > 1 else 0.0)
    coh = _coherence(np.asarray(smoothed), k)
    log.info("Penutur ditambatkan ke wajah: %d orang bermodel, jarak antar model "
             "%.3f, %d jendela, %d pergantian", len(model), jauh, len(covers), ganti)
    return Diarization(labels=smoothed, speaker_count=k, separation=sep,
                       coherence=coh, quality=round(sep * coh, 4), requested=None)


def analyze_speakers(wav_path: str, spans: list[tuple[float, float]], *,
                     speakers: Optional[int] = None,
                     max_speakers: int = MAX_SPEAKERS,
                     turn_gap: float = 1.0) -> Diarization:
    """
    Menebak berapa orang bicara dan memberi label penutur untuk tiap span.

    Alurnya: potong ucapan jadi jendela 3,5 detik -> embedding CAM++ per
    jendela -> buang arah bersama -> k-means dengan jumlah kelompok dipilih
    lewat selisih kemiripan -> suara terbanyak per kalimat.

    `speakers` boleh diisi bila pengguna sudah tahu jumlahnya; itu menghapus
    bagian paling rapuh dari proses ini (menebak jumlah kelompok).

    `turn_gap` dipertahankan demi pemanggil lama, tapi tidak lagi dipakai:
    batas pembicara sekarang ditemukan oleh pengelompokan, bukan oleh jeda.

    Bacalah `separation` sebagai ukuran seberapa terpisah suaranya; `confident`
    bernilai False bila pemisahannya tidak layak dipercaya.
    """
    if not spans:
        return Diarization(labels=[], speaker_count=0, separation=0.0)
    if speakers == 1:
        return Diarization(labels=[0] * len(spans), speaker_count=1, separation=1.0)
    if _get_session() is None:
        log.info("Model penutur tidak tersedia — pemisahan dilewati")
        return Diarization(labels=[0] * len(spans), speaker_count=0, separation=0.0)

    windows = _build_windows(spans)
    vectors: list[np.ndarray] = []
    covers: list[list[int]] = []

    try:
        with wave.open(wav_path, "rb") as wf:
            if wf.getframerate() != SAMPLE_RATE or wf.getnchannels() != 1:
                log.warning("WAV bukan 16 kHz mono; pemisahan penutur dilewati")
                return Diarization(labels=[0] * len(spans), speaker_count=0,
                                   separation=0.0)
            for pieces, touched in windows:
                audio = _window_audio(wf, pieces)
                if audio is None:
                    continue
                vec = _embed(kaldi_fbank(audio))
                if vec is not None:
                    vectors.append(vec)
                    covers.append(touched)
    except (OSError, wave.Error) as e:
        log.warning("Gagal membaca audio untuk pemisahan penutur: %s", e)
        return Diarization(labels=[0] * len(spans), speaker_count=0, separation=0.0)

    if len(vectors) < 12:
        log.info("Hanya %d jendela layak — pemisahan penutur dilewati", len(vectors))
        return Diarization(labels=[0] * len(spans), speaker_count=1, separation=0.0)

    x = np.vstack(vectors)

    # Pengelompokan dilakukan pada embedding yang reratanya dibuang lalu
    # dinormalkan ulang. Embedding penutur punya satu arah bersama yang besar —
    # sisa rekaman, mikrofon, ruangan — dan arah itu sama untuk semua orang di
    # video yang sama. Selama ia ikut terbawa, jarak antar orang tenggelam di
    # dalamnya: diukur pada podcast uji, membuangnya menaikkan selisih
    # dekat-vs-jauh dari 0,174 ke 0,249.
    centered = x - x.mean(axis=0)
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    centered = centered / np.maximum(norms, 1e-8)

    # Pilihan otomatis SELALU dihitung, bahkan ketika pengguna sudah menyebut
    # jumlahnya — dipakai untuk melaporkan, bukan untuk membantah.
    #
    # Tangganya serakah dan menaik: k bertambah hanya selama tiap penambahan
    # memperbaiki nilai lebih dari K_MARGIN. Itu yang menjaga rekaman dua orang
    # tidak terpeleset jadi tiga karena kenaikan nilai 3%, sekaligus
    # membiarkan rekaman empat orang naik sampai empat (kenaikannya +61% lalu
    # +22%).
    auto_k, auto_labels = 1, np.zeros(len(x), dtype=int)
    auto_score, auto_sep, auto_coh = 0.0, 0.0, 0.0
    for k in range(2, min(max_speakers, len(x) // 3) + 1):
        cand, _ = _kmeans(centered, k)
        if len(np.unique(cand)) < k:
            continue
        value, sep, coh = _quality(x, cand, k)
        if value > auto_score * (1.0 + K_MARGIN):
            auto_k, auto_labels = k, cand
            auto_score, auto_sep, auto_coh = value, sep, coh

    if speakers and speakers >= 2:
        # Jumlah yang disebut pengguna DITURUTI.
        #
        # Versi sebelumnya memeriksanya dan diam-diam menggantinya ketika
        # pemisahannya dinilai kurang. Niatnya melindungi — label yang buruk
        # tetap terlihat seperti label — tapi akibatnya lebih buruk daripada
        # yang dicegah: pengguna yang menghitung sendiri orang di layar
        # memasukkan angkanya, sistem menjawab dengan angka lain tanpa
        # mengatakan apa-apa yang terbaca, dan panel subtitle lalu hanya
        # menawarkan sebanyak itu nomor untuk dipilih. Pengguna kehilangan
        # jalan otomatis DAN jalan manual sekaligus.
        #
        # Yang tersisa dari niat itu tetap dipertahankan, tapi sebagai
        # keterangan, bukan sebagai penolakan: `quality`, `coherence`, dan
        # `confident` ikut dikembalikan, dan antarmuka menuliskan "±" ketika
        # hasilnya lemah. Keputusannya tetap milik pengguna.
        chosen_k = max(2, min(speakers, max_speakers, len(x) // 3))
        labels, _ = _kmeans(centered, chosen_k)
        score, sep, coh = _quality(x, labels, chosen_k)
        if chosen_k != auto_k:
            log.info("Diminta %d penutur (nilai %.3f); tebakan otomatis %d "
                     "(nilai %.3f) — yang diminta yang dipakai",
                     chosen_k, score, auto_k, auto_score)
    else:
        chosen_k, labels = auto_k, auto_labels
        score, sep, coh = auto_score, auto_sep, auto_coh

    # Satu-satunya keadaan yang masih membatalkan pemisahan adalah ketika
    # pengguna TIDAK menyebut jumlah dan tebakan otomatisnya sendiri lemah.
    if chosen_k < 2 or (not speakers and (score < MIN_QUALITY
                                          or coh < MIN_COHERENCE)):
        log.info("Pemisahan suara lemah (pisah %.3f, runtut %.2fx) — "
                 "dianggap satu penutur", sep, coh)
        return Diarization(labels=[0] * len(spans), speaker_count=1,
                           separation=sep, coherence=coh, quality=score,
                           requested=speakers)

    # Dihaluskan di ranah JENDELA lebih dulu, saat urutannya masih berurut
    # waktu: satu jendela nyasar di tengah giliran orang lain adalah derau, dan
    # membetulkannya di sini mencegahnya mencemari suara terbanyak per kalimat.
    labels = _smooth(np.asarray(labels), chosen_k)

    # Penutur 0 = yang paling banyak bicara, supaya warnanya tidak bertukar
    # antar analisis.
    order = sorted(range(chosen_k), key=lambda c: int((labels == c).sum()), reverse=True)
    remap = {c: i for i, c in enumerate(order)}

    # Satu kalimat bisa tersentuh beberapa jendela — dan sebuah jendela bisa
    # menyeberangi batas kalimat. Suara terbanyak menyelesaikan keduanya.
    votes = [np.zeros(chosen_k, dtype=int) for _ in spans]
    for pos, touched in enumerate(covers):
        label = remap[int(labels[pos])]
        for i in touched:
            votes[i][label] += 1

    out: list[int] = []
    last = 0
    for tally in votes:
        if tally.any():
            last = int(tally.argmax())
        out.append(last)

    smoothed = _smooth(np.asarray(out), chosen_k).tolist()
    switches = sum(1 for a, b in zip(smoothed, smoothed[1:]) if a != b)
    log.info("Pemisahan penutur: %d orang, pisah %.3f, runtut %.2fx, nilai %.3f, "
             "%d jendela, %d pergantian",
             chosen_k, sep, coh, score, len(covers), switches)
    return Diarization(labels=smoothed, speaker_count=chosen_k, separation=sep,
                       coherence=coh, quality=score, requested=speakers)
