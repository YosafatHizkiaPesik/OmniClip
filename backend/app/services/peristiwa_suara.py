"""
Mendengar peristiwa suara di dalam klip: tawa, sorak/tepuk tangan, teriakan.

Pakai YAMNet (Google, AudioSet 521 kelas, MobileNetV1 3,7 juta parameter),
dalam konversi ONNX. Sekitar 0,4 detik untuk satu menit audio di CPU.

Kenapa perlu model, bukan aturan energi atau transkrip:

- Caption otomatis YouTube berbahasa Indonesia TIDAK pernah menandai tawa, dan
  meregangkan waktu kata sampai menutup seluruh klip — celah "tanpa kata" yang
  semestinya menandai tawa tidak pernah ada. Terukur pada obrolan stand-up
  ohJbKVkrZ4U: 100% waktu klip "ditempati" kata.
- Podcast yang berganti kamera tiap tiga detik jarang memperlihatkan dua wajah
  bersamaan, jadi "mulut bergerak bersamaan" tidak bisa diamati.
- Tawa di podcast hampir selalu bertumpuk dengan ucapan. Skor mutlak "Laughter"
  kecil (0,02-0,06) karena "Speech" mendominasi, tapi puluhan sampai ratusan
  kali di atas dasar klipnya sendiri (±0,0001). Yang dipakai adalah KEDUANYA:
  cukup tinggi dengan sendirinya, dan jauh di atas dasarnya.

Hasil uji: obrolan stand-up — tawa terkuat tepat sesudah punchline "Setelah di
smash mulu, harus ngapain?"; podcast Sule — tepuk tangan, tawa, dan sorak di
detik yang sama dengan yang terlihat di gambar.
"""

import hashlib
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from ..config import MODELS_DIR
from .proses import jalankan

log = logging.getLogger("omniclip.peristiwa")

MODEL_PATH = MODELS_DIR / "yamnet.onnx"
MODEL_URL = "https://huggingface.co/zeropointnine/yamnet-onnx/resolve/main/yamnet.onnx"
MODEL_SHA256 = "1510041dce24a2e9e84ec546807ac408ae496da6d1ed41bc3ccba649623f8e19"

LANGKAH = 0.48              # jarak antar bingkai YAMNet (detik)
# Nomor kelas dari yamnet_class_map.csv resmi (tensorflow/models).
KELAS = {
    "tawa": [13, 15, 16, 17, 18],        # Laughter, Giggle, Snicker, Belly laugh, Chuckle
    "sorak": [58, 61, 62, 64],           # Clapping, Cheering, Applause, Crowd
    "teriak": [6, 9, 11, 39],            # Shout, Yell, Screaming, Gasp
}
# Ambang per jenis: skor mutlak minimum DAN kelipatan minimum terhadap median
# klip itu. Dipilih dari tiga podcast uji; tawa yang tertangkap mata ada di
# 0,019-0,46, dasar klip 0,00001-0,0003.
AMBANG = {"tawa": (0.015, 20.0), "sorak": (0.03, 20.0), "teriak": (0.03, 20.0)}
GABUNG = 1.0                # bingkai berdekatan dalam jarak ini = satu peristiwa

_kunci = threading.Lock()
_sesi = None


def _pastikan_model() -> bool:
    if MODEL_PATH.is_file() and MODEL_PATH.stat().st_size > 1_000_000:
        return True
    import urllib.request
    tmp = MODEL_PATH.with_suffix(".part")
    try:
        log.info("Mengunduh pendengar peristiwa suara (16 MB)…")
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256()
        with urllib.request.urlopen(MODEL_URL, timeout=120) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 20):
                h.update(chunk)
                f.write(chunk)
        if h.hexdigest() != MODEL_SHA256:
            raise ValueError("sidik berkas model tidak cocok")
        os.replace(tmp, MODEL_PATH)
        return True
    except Exception as e:
        log.warning("Gagal mengunduh model YAMNet: %s", str(e)[:200])
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _dapatkan_sesi():
    global _sesi
    with _kunci:
        if _sesi is not None:
            return _sesi
        if not _pastikan_model():
            return None
        try:
            import onnxruntime as ort
            opsi = ort.SessionOptions()
            opsi.intra_op_num_threads = 2
            opsi.log_severity_level = 3
            _sesi = ort.InferenceSession(str(MODEL_PATH), opsi,
                                         providers=["CPUExecutionProvider"])
        except Exception as e:
            log.warning("YAMNet tidak bisa dimuat: %s", str(e)[:200])
            return None
        return _sesi


def _audio(src: Path, segments: list[dict]):
    import numpy as np
    potong = []
    for seg in segments:
        mulai = float(seg["start"])
        panjang = max(0.0, float(seg["end"]) - mulai)
        mentah = jalankan(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
                           "-ss", f"{mulai:.3f}", "-t", f"{panjang:.3f}", "-i", str(src),
                           "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                          text=False).stdout
        potong.append(np.frombuffer(mentah, np.float32))
    return np.concatenate(potong) if potong else np.zeros(0, np.float32)


def skor_klip(src: Path, segments: list[dict]) -> Optional[dict]:
    """{jenis: [skor per LANGKAH]} dalam waktu klip, atau None bila tak bisa."""
    sesi = _dapatkan_sesi()
    if sesi is None:
        return None
    x = _audio(src, segments)
    if len(x) < 16000:
        return None
    try:
        sk = sesi.run(["output_0"], {"waveform": x})[0]
    except Exception as e:
        log.warning("YAMNet gagal: %s", str(e)[:200])
        return None
    return {j: sk[:, ids].max(axis=1).tolist() for j, ids in KELAS.items()}


def peristiwa(skor: dict) -> list[dict]:
    """[{jenis, t, mulai, akhir, skor, kelipatan}] dari hasil `skor_klip`."""
    import numpy as np
    out: list[dict] = []
    for jenis, nilai in skor.items():
        v = np.asarray(nilai, dtype=np.float64)
        if not len(v):
            continue
        dasar = max(float(np.median(v)), 1e-5)
        mutlak, kali = AMBANG[jenis]
        lolos = np.where((v >= mutlak) & (v / dasar >= kali))[0]
        kelompok: list[list[int]] = []
        for i in lolos:
            if kelompok and (i - kelompok[-1][-1]) * LANGKAH <= GABUNG:
                kelompok[-1].append(int(i))
            else:
                kelompok.append([int(i)])
        for g in kelompok:
            puncak = max(g, key=lambda i: v[i])
            out.append({"jenis": jenis, "t": round(puncak * LANGKAH + 0.48, 2),
                        "mulai": round(g[0] * LANGKAH, 2),
                        "akhir": round(g[-1] * LANGKAH + 0.96, 2),
                        "skor": round(float(v[puncak]), 3),
                        "kelipatan": round(float(v[puncak] / dasar), 1)})
    out.sort(key=lambda p: p["mulai"])
    return out
