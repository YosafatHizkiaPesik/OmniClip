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

# Ambang penerimaan, dinyatakan sebagai SELISIH kemiripan: rata-rata kemiripan
# di dalam kelompok terlemah dikurangi rata-rata kemiripan antar kelompok.
#
# Ukuran ini dipilih menggantikan skor siluet karena siluet menjawab pertanyaan
# yang salah — ia mengukur seberapa bulat bentuk kelompoknya, sementara yang
# ingin diketahui adalah seberapa jauh dua suara berbeda. Diukur pada podcast
# dua orang, siluetnya hanya 0,25 (terlihat seperti kegagalan) padahal
# selisihnya +0,11 dan pemisahannya benar saat diperiksa terhadap transkrip.
MIN_SEPARATION = 0.06

_session = None
_banks: Optional[np.ndarray] = None
_window: Optional[np.ndarray] = None


@dataclass
class Diarization:
    labels: list[int]          # satu label per span yang diminta
    speaker_count: int
    separation: float          # selisih kemiripan dalam-kelompok vs antar-kelompok

    @property
    def confident(self) -> bool:
        return self.speaker_count > 1 and self.separation >= MIN_SEPARATION


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

    Yang diambil adalah kelompok TERLEMAH, bukan reratanya: satu kelompok yang
    isinya campuran sudah cukup untuk membuat pewarnaan per penutur menyesatkan.
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
    return round(min(withins) - max(crosses), 4)


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

    if speakers and speakers >= 2:
        chosen_k = max(2, min(speakers, max_speakers, len(x) // 3))
        labels, _ = _kmeans(centered, chosen_k)
        score = _separation(x, labels, chosen_k)
    else:
        chosen_k, labels, score = 1, np.zeros(len(x), dtype=int), 0.0
        for k in range(2, min(max_speakers, len(x) // 3) + 1):
            cand, _ = _kmeans(centered, k)
            if len(np.unique(cand)) < k:
                continue
            gap = _separation(x, cand, k)
            # Kelompok yang lebih banyak hampir selalu menurunkan selisih, jadi
            # jumlah penutur bertambah hanya bila penambahannya benar-benar
            # tidak merusak pemisahan.
            if gap > score + 1e-9:
                chosen_k, labels, score = k, cand, gap
        if score < MIN_SEPARATION:
            log.info("Pemisahan suara lemah (selisih %.3f) — dianggap satu penutur", score)
            return Diarization(labels=[0] * len(spans), speaker_count=1,
                               separation=score)

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
    log.info("Pemisahan penutur: %d orang, selisih %.3f, %d jendela, %d pergantian",
             chosen_k, score, len(covers), switches)
    return Diarization(labels=smoothed, speaker_count=chosen_k, separation=score)
