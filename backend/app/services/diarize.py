"""
Pengelompokan suara: menebak ADA BERAPA orang bicara dan siapa mengucapkan apa.

Ini bukan model diarisasi terlatih. Tidak ada torch, tidak ada pyannote — dua-
duanya butuh ratusan MB dan mesin ini punya anggaran memori ~2,9 GB yang sudah
dipakai Whisper. Yang dikerjakan di sini adalah pendekatan klasik:

  potongan suara -> MFCC -> rata-rata & simpangan per kalimat -> k-means

MFCC menangkap warna suara (bentuk saluran vokal), bukan kata-katanya, jadi dua
orang dengan timbre berbeda akan terpisah cukup rapi. Jumlah penutur dipilih
dengan skor siluet: bila pemisahannya lemah, sistem menjawab "satu orang"
alih-alih memaksakan pembagian.

Batasnya jujur dan perlu diketahui: suara yang mirip, bicara bertindih, musik
latar, atau rekaman satu mikrofon yang jauh akan membuatnya meleset. Karena itu
hasilnya selalu bisa disunting per baris di editor.
"""

import logging
import math
import wave
from dataclasses import dataclass
from typing import Optional

import numpy as np

log = logging.getLogger("omniclip.diarize")

SAMPLE_RATE = 16000
N_FFT = 512
WIN = 400          # 25 ms
HOP = 160          # 10 ms
N_MELS = 26
N_MFCC = 13        # koefisien 1..12 dipakai; c0 (energi) dibuang

# Potongan suara per kalimat yang dipakai untuk mengenali warna suara. Lebih
# panjang tidak menambah ketelitian, hanya waktu: identitas suara sudah terbaca
# dalam sekitar satu detik.
MAX_SPAN_SECONDS = 1.4
MIN_SPAN_SECONDS = 0.35

MAX_SPEAKERS = 4
# Di bawah ambang ini pemisahannya dianggap tidak meyakinkan dan seluruh video
# dinyatakan satu penutur. Memaksakan dua kelompok pada suara tunggal
# menghasilkan warna yang berkedip-kedip tanpa alasan.
MIN_SILHOUETTE = 0.14


@dataclass
class Diarization:
    labels: list[int]          # satu label per span yang diminta (-1 = tak terpakai)
    speaker_count: int
    silhouette: float

    @property
    def confident(self) -> bool:
        return self.speaker_count > 1 and self.silhouette >= MIN_SILHOUETTE


def _mel_filterbank(sr: int, n_fft: int, n_mels: int) -> np.ndarray:
    def hz_to_mel(f): return 2595.0 * np.log10(1.0 + f / 700.0)
    def mel_to_hz(m): return 700.0 * (10 ** (m / 2595.0) - 1.0)

    low, high = hz_to_mel(30.0), hz_to_mel(sr / 2.0)
    points = mel_to_hz(np.linspace(low, high, n_mels + 2))
    bins = np.floor((n_fft + 1) * points / sr).astype(int)
    bins = np.clip(bins, 0, n_fft // 2)

    fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for m in range(n_mels):
        a, b, c = bins[m], bins[m + 1], bins[m + 2]
        if b > a:
            fb[m, a:b] = (np.arange(a, b) - a) / (b - a)
        if c > b:
            fb[m, b:c] = (c - np.arange(b, c)) / (c - b)
    return fb


def _dct_matrix(n_out: int, n_in: int) -> np.ndarray:
    k = np.arange(n_out)[:, None]
    n = np.arange(n_in)[None, :]
    d = np.cos(np.pi * k * (2 * n + 1) / (2 * n_in))
    d *= math.sqrt(2.0 / n_in)
    d[0] *= 1.0 / math.sqrt(2.0)
    return d.astype(np.float32)


_FB = _mel_filterbank(SAMPLE_RATE, N_FFT, N_MELS)
_DCT = _dct_matrix(N_MFCC, N_MELS)
_WINDOW = np.hamming(WIN).astype(np.float32)


def _mfcc(signal: np.ndarray) -> Optional[np.ndarray]:
    """MFCC untuk satu potongan suara. Mengembalikan matriks (frame, 12)."""
    if signal.size < WIN * 2:
        return None
    # Pre-emphasis menonjolkan formant tinggi yang justru membedakan suara.
    sig = np.empty_like(signal)
    sig[0] = signal[0]
    sig[1:] = signal[1:] - 0.97 * signal[:-1]

    n_frames = 1 + (sig.size - WIN) // HOP
    if n_frames < 3:
        return None
    idx = np.arange(WIN)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = sig[idx] * _WINDOW

    spec = np.abs(np.fft.rfft(frames, N_FFT)) ** 2 / N_FFT
    mel = spec @ _FB.T
    mel = np.log(mel + 1e-10)
    coeffs = mel @ _DCT.T
    return coeffs[:, 1:]           # buang c0: itu kekerasan suara, bukan warnanya


def _embed(signal: np.ndarray) -> Optional[np.ndarray]:
    """Satu vektor identitas suara: rata-rata dan simpangan tiap koefisien."""
    m = _mfcc(signal)
    if m is None or m.shape[0] < 3:
        return None
    return np.concatenate([m.mean(axis=0), m.std(axis=0)]).astype(np.float32)


def _kmeans(x: np.ndarray, k: int, *, iters: int = 40, seed: int = 7):
    """k-means dengan inisialisasi k-means++ (deterministik lewat seed tetap)."""
    rng = np.random.default_rng(seed)
    n = x.shape[0]
    centers = [x[rng.integers(n)]]
    for _ in range(1, k):
        d = np.min(((x[:, None, :] - np.array(centers)[None, :, :]) ** 2).sum(-1), axis=1)
        total = d.sum()
        if total <= 0:
            centers.append(x[rng.integers(n)])
            continue
        centers.append(x[rng.choice(n, p=d / total)])
    c = np.array(centers)

    labels = np.zeros(n, dtype=int)
    for _ in range(iters):
        dist = ((x[:, None, :] - c[None, :, :]) ** 2).sum(-1)
        new = dist.argmin(axis=1)
        if np.array_equal(new, labels):
            break
        labels = new
        for j in range(k):
            members = x[labels == j]
            if members.size:
                c[j] = members.mean(axis=0)
    return labels, c


def _silhouette(x: np.ndarray, labels: np.ndarray, k: int) -> float:
    """
    Seberapa terpisah kelompoknya, rata-rata pada rentang [-1, 1].

    Dipakai untuk MEMILIH jumlah penutur. Tanpa ukuran seperti ini, k-means akan
    selalu patuh membelah data jadi berapa pun kelompok yang diminta — termasuk
    membelah suara satu orang jadi dua.
    """
    if k < 2 or x.shape[0] <= k:
        return -1.0
    dist = np.sqrt(((x[:, None, :] - x[None, :, :]) ** 2).sum(-1))
    scores = []
    for i in range(x.shape[0]):
        own = labels[i]
        same = dist[i][(labels == own)]
        same = same[same > 0]
        if same.size == 0:
            continue
        a = same.mean()
        b = min(
            dist[i][labels == j].mean()
            for j in range(k) if j != own and np.any(labels == j)
        )
        if max(a, b) > 0:
            scores.append((b - a) / max(a, b))
    return float(np.mean(scores)) if scores else -1.0


def _read_span_raw(wf: wave.Wave_read, start: float, end: float) -> Optional[np.ndarray]:
    """Membaca sepotong WAV dengan seek langsung, tanpa memuat seluruh berkas."""
    length = end - start
    if length < MIN_SPAN_SECONDS:
        return None
    if length > MAX_SPAN_SECONDS:
        mid = (start + end) / 2.0
        start, end = mid - MAX_SPAN_SECONDS / 2, mid + MAX_SPAN_SECONDS / 2
    a = int(max(0.0, start) * SAMPLE_RATE)
    n = int((end - start) * SAMPLE_RATE)
    if a >= wf.getnframes():
        return None
    wf.setpos(a)
    raw = wf.readframes(min(n, wf.getnframes() - a))
    if not raw:
        return None
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def _build_turns(spans: list[tuple[float, float]], gap: float) -> list[list[int]]:
    """
    Mengelompokkan span berdekatan menjadi satu giliran bicara.

    Span per kalimat terlalu pendek dan sering melintasi pergantian pembicara,
    sehingga sampelnya tercampur. Diukur pada podcast uji, mengelompokkannya
    per giliran menaikkan pemisahan dari 0,09 ke 0,14 — masih tidak besar, tapi
    arahnya jelas benar.
    """
    if not spans:
        return []
    turns: list[list[int]] = []
    current = [0]
    for i in range(1, len(spans)):
        if spans[i][0] - spans[i - 1][1] >= gap:
            turns.append(current)
            current = []
        current.append(i)
    turns.append(current)
    return [t for t in turns if t]


def _embed_turn(wf: wave.Wave_read, spans: list[tuple[float, float]],
                indexes: list[int], budget: float = 3.0) -> Optional[np.ndarray]:
    """Satu vektor suara untuk sebuah giliran, dari maksimal `budget` detik."""
    mats = []
    used = 0.0
    for i in indexes:
        s, e = spans[i]
        take = min(e - s, budget - used)
        if take < MIN_SPAN_SECONDS:
            continue
        chunk = _read_span_raw(wf, s, s + take)
        if chunk is None:
            continue
        m = _mfcc(chunk)
        if m is not None and m.shape[0] >= 3:
            mats.append(m)
            used += take
        if used >= budget:
            break
    if not mats:
        return None
    m = np.vstack(mats)
    # Buang frame paling sunyi: keheningan membuat semua suara terlihat mirip.
    energy = np.abs(m).sum(axis=1)
    keep = energy >= np.percentile(energy, 35)
    if keep.sum() >= 5:
        m = m[keep]
    v = np.concatenate([m.mean(axis=0), m.std(axis=0)]).astype(np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def _smooth_labels(labels: np.ndarray, k: int, window: int = 3) -> np.ndarray:
    """
    Median modus atas deret label.

    Giliran bicara berlangsung beberapa kalimat; label yang berganti setiap satu
    kalimat hampir pasti derau pengelompokan, bukan percakapan sungguhan.
    """
    if window < 3 or labels.size < window:
        return labels
    half = window // 2
    out = labels.copy()
    for i in range(labels.size):
        lo = max(0, i - half)
        hi = min(labels.size, i + half + 1)
        out[i] = np.bincount(labels[lo:hi], minlength=k).argmax()
    return out


def analyze_speakers(wav_path: str, spans: list[tuple[float, float]], *,
                     speakers: Optional[int] = None,
                     max_speakers: int = MAX_SPEAKERS,
                     turn_gap: float = 1.0) -> Diarization:
    """
    Menebak berapa orang bicara dan memberi label penutur untuk tiap span.

    `speakers` boleh diisi bila pengguna sudah tahu jumlahnya; itu menghapus
    bagian paling rapuh dari proses ini (menebak jumlah kelompok) dan biasanya
    memperbaiki hasilnya cukup banyak.

    Hasilnya adalah PERKIRAAN. Bacalah `silhouette` sebagai ukuran seberapa
    terpisah suaranya: di bawah ~0,15 hasilnya tidak bisa dipercaya, dan
    `confident` akan bernilai False.
    """
    if not spans:
        return Diarization(labels=[], speaker_count=0, silhouette=-1.0)

    turns = _build_turns(spans, turn_gap)
    vectors: list[np.ndarray] = []
    turn_of: list[list[int]] = []

    try:
        with wave.open(wav_path, "rb") as wf:
            if wf.getframerate() != SAMPLE_RATE or wf.getnchannels() != 1:
                log.warning("WAV bukan 16 kHz mono; diarisasi dilewati")
                return Diarization(labels=[0] * len(spans), speaker_count=0,
                                   silhouette=-1.0)
            for indexes in turns:
                v = _embed_turn(wf, spans, indexes)
                if v is not None:
                    vectors.append(v)
                    turn_of.append(indexes)
    except (OSError, wave.Error) as e:
        log.warning("Gagal membaca audio untuk diarisasi: %s", e)
        return Diarization(labels=[0] * len(spans), speaker_count=0, silhouette=-1.0)

    if len(vectors) < 12:
        log.info("Hanya %d giliran layak — diarisasi dilewati", len(vectors))
        return Diarization(labels=[0] * len(spans), speaker_count=1, silhouette=-1.0)

    x = np.vstack(vectors)
    x = (x - x.mean(axis=0)) / (x.std(axis=0) + 1e-6)

    if speakers and speakers >= 2:
        k = min(speakers, max_speakers, len(x) // 4)
        labels, _ = _kmeans(x, k)
        score = _silhouette(x, labels, k)
        chosen_k = k
    elif speakers == 1:
        return Diarization(labels=[0] * len(spans), speaker_count=1, silhouette=1.0)
    else:
        chosen_k, labels, score = 1, np.zeros(len(x), dtype=int), -1.0
        for k in range(2, min(max_speakers, len(x) // 4) + 1):
            cand, _ = _kmeans(x, k)
            if len(np.unique(cand)) < k:
                continue
            s = _silhouette(x, cand, k)
            if s > score:
                chosen_k, labels, score = k, cand, s
        if score < MIN_SILHOUETTE:
            log.info("Pemisahan suara lemah (siluet %.3f) — dianggap satu penutur", score)
            return Diarization(labels=[0] * len(spans), speaker_count=1,
                               silhouette=round(score, 3))

    labels = _smooth_labels(np.asarray(labels), chosen_k)

    # Penutur 0 = yang paling banyak bicara, supaya warnanya tidak bertukar
    # antar analisis.
    order = [c for c, _ in sorted(
        ((c, int((labels == c).sum())) for c in range(chosen_k)),
        key=lambda t: t[1], reverse=True)]
    remap = {c: i for i, c in enumerate(order)}

    out = [0] * len(spans)
    for pos, indexes in enumerate(turn_of):
        label = remap[int(labels[pos])]
        for i in indexes:
            out[i] = label

    log.info("Diarisasi: %d penutur, siluet %.3f, %d giliran",
             chosen_k, score, len(turn_of))
    return Diarization(labels=out, speaker_count=chosen_k, silhouette=round(score, 3))
