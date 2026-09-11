"""
Membacakan judul klip.

Kartu judul di awal klip biasanya dibacakan — itulah bentuk yang dikenal
penonton, dan judul yang hanya tertulis kehilangan separuh gunanya di feed yang
diputar sambil lalu.

Ada dua mesin di sini, dan pilihan di antaranya adalah pertukaran yang nyata,
bukan selera:

- **Piper**, satu berkas ONNX 63 MB, berjalan di CPU mesin ini. Judulnya tidak
  pernah meninggalkan komputer dan ia tetap bekerja tanpa internet. Tapi hanya
  ada satu suara Indonesia untuk Piper, dan suaranya bukan yang dikenal orang.
- **Suara Microsoft** lewat `edge-tts`. Inilah suara yang dipakai kebanyakan
  alat pembuat klip, jadi inilah yang terdengar "benar" bagi penonton. Harganya:
  judul klip dikirim ke server Microsoft untuk dibacakan, dan antarmukanya tidak
  resmi sehingga bisa berhenti bekerja sewaktu-waktu.

Bawaannya Piper — bukan karena lebih bagus, tapi karena mengirim teks pengguna
keluar dari mesinnya sendiri harus jadi pilihan yang diambil, bukan yang
kebetulan terjadi.

Model Piper dilepas setelah menganggur: ia memakan sekitar 200 MB, dan mesin ini
punya anggaran memori yang sudah diperebutkan whisper dan encoder x264.
"""
from __future__ import annotations

import logging
import subprocess
import threading
import time
import wave
from pathlib import Path
from typing import Optional

from ..config import MODELS_DIR

log = logging.getLogger("omniclip.tts")

TTS_DIR = MODELS_DIR / "tts"
VOICE_NAME = "id_ID-news_tts-medium"
VOICE_PATH = TTS_DIR / f"{VOICE_NAME}.onnx"

# Dari mana suaranya diambil bila belum ada. Diunduh sekali, lalu dipakai
# offline selamanya.
VOICE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    f"/id/id_ID/news_tts/medium/{VOICE_NAME}.onnx"
)

IDLE_UNLOAD_SECONDS = 600.0

# Suara yang bisa dipilih.
#
# Dua mesin, dan bedanya bukan sekadar selera. Piper berjalan di mesin ini:
# judulnya tidak pernah meninggalkan komputer, dan ia tetap bekerja tanpa
# internet. Suara Microsoft dibuat di server mereka — itulah suara yang dikenal
# orang dari kebanyakan alat pembuat klip, tapi memakainya berarti judul klip
# dikirim ke Microsoft untuk dibacakan, dan layanannya bisa berhenti bekerja
# sewaktu-waktu karena bukan antarmuka resmi.
VOICES = [
    {"id": "piper-news", "engine": "piper", "label": "Pembaca berita",
     "gender": "pria", "online": False, "model": VOICE_NAME, "pitch": 0,
     "note": "Berjalan di komputer ini. Judul tidak dikirim ke mana pun."},

    # Microsoft hanya menyediakan DUA suara Indonesia. Sisanya varian nada dari
    # keduanya — bukan suara orang lain, tapi cukup berbeda untuk dipakai
    # bergantian antar kanal supaya klipnya tidak terdengar dari satu pabrik.
    {"id": "edge-ardi", "engine": "edge", "label": "Ardi",
     "gender": "pria", "online": True, "model": "id-ID-ArdiNeural", "pitch": 0,
     "note": "Suara yang paling sering dipakai di alat pembuat klip."},
    {"id": "edge-ardi-berat", "engine": "edge", "label": "Ardi — berat",
     "gender": "pria", "online": True, "model": "id-ID-ArdiNeural", "pitch": -22,
     "note": "Nada lebih rendah; terdengar lebih tua dan tenang."},
    {"id": "edge-ardi-muda", "engine": "edge", "label": "Ardi — muda",
     "gender": "pria", "online": True, "model": "id-ID-ArdiNeural", "pitch": 22,
     "note": "Nada lebih tinggi; terdengar lebih muda dan bersemangat."},

    {"id": "edge-gadis", "engine": "edge", "label": "Gadis",
     "gender": "wanita", "online": True, "model": "id-ID-GadisNeural", "pitch": 0,
     "note": "Suara perempuan bawaan Microsoft."},
    {"id": "edge-gadis-lembut", "engine": "edge", "label": "Gadis — lembut",
     "gender": "wanita", "online": True, "model": "id-ID-GadisNeural", "pitch": -16,
     "note": "Nada lebih rendah; terdengar lebih kalem."},
    {"id": "edge-gadis-cerah", "engine": "edge", "label": "Gadis — cerah",
     "gender": "wanita", "online": True, "model": "id-ID-GadisNeural", "pitch": 20,
     "note": "Nada lebih tinggi; terdengar lebih ceria."},
]
DEFAULT_VOICE = "piper-news"


def voice_by_id(voice_id: str) -> dict:
    for v in VOICES:
        if v["id"] == voice_id:
            return v
    return VOICES[0]


def edge_available() -> bool:
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return False
    return True


def catalogue() -> list[dict]:
    """Daftar suara beserta apakah masing-masing benar-benar bisa dipakai."""
    siap_piper = available()
    siap_edge = edge_available()
    return [{**v, "ready": siap_edge if v["engine"] == "edge" else siap_piper}
            for v in VOICES]


def _synthesize_edge(text: str, out_path: Path, model: str, rate: float,
                     pitch: int = 0) -> float:
    """
    Membacakan lewat suara Microsoft, lalu menyimpannya sebagai WAV.

    Hasil aslinya MP3; diubah ke WAV supaya seluruh sisa sistem — pemutar
    pratinjau maupun graf ffmpeg — hanya perlu mengenal satu bentuk berkas.
    """
    import asyncio
    import subprocess

    import edge_tts

    # Microsoft menerima kecepatan sebagai persen relatif, bukan pengali.
    persen = int(round((rate - 1.0) * 100))
    tanda = "+" if persen >= 0 else "-"
    mp3 = out_path.with_suffix(".mp3")

    nada = f"{'+' if pitch >= 0 else '-'}{abs(int(pitch))}Hz"

    async def jalan():
        c = edge_tts.Communicate(text, model, rate=f"{tanda}{abs(persen)}%", pitch=nada)
        await c.save(str(mp3))

    asyncio.run(jalan())
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(mp3),
                    "-ar", "22050", "-ac", "1", str(out_path)],
                   check=True, timeout=120)
    mp3.unlink(missing_ok=True)
    with wave.open(str(out_path)) as w:
        return w.getnframes() / float(w.getframerate() or 1)

_lock = threading.Lock()
_voice = None
_last_used = 0.0


def available() -> bool:
    """Apakah suara siap dipakai tanpa mengunduh apa pun."""
    if not VOICE_PATH.is_file() or not VOICE_PATH.with_suffix(".onnx.json").is_file():
        return False
    try:
        import piper  # noqa: F401
    except ImportError:
        return False
    return True


def _load():
    global _voice, _last_used
    if _voice is None:
        from piper import PiperVoice

        t0 = time.time()
        _voice = PiperVoice.load(str(VOICE_PATH))
        log.info("Suara %s dimuat dalam %.2f dtk", VOICE_NAME, time.time() - t0)
    _last_used = time.time()
    return _voice


def release_if_idle(now: Optional[float] = None) -> bool:
    """
    Melepas model bila sudah lama tidak dipakai.

    Dipanggil penjaga di `lifespan`, sama seperti model whisper.
    """
    global _voice
    with _lock:
        if _voice is None:
            return False
        if (now or time.time()) - _last_used < IDLE_UNLOAD_SECONDS:
            return False
        _voice = None
        log.info("Suara dilepas setelah menganggur")
        return True


def synthesize(text: str, out_path: Path, *, rate: float = 1.0,
               voice: str = DEFAULT_VOICE) -> float:
    """
    Menulis pembacaan `text` ke WAV dan mengembalikan panjangnya dalam detik.

    `rate` di bawah 1 mempercepat — Piper menyebutnya length_scale, jadi angka
    yang dipakai adalah kebalikannya. Dinaikkan sedikit untuk kartu judul:
    pembacaan bertempo berita terasa lambat di atas potongan pendek.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Tidak ada teks untuk dibacakan.")

    spec = voice_by_id(voice)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if spec["engine"] == "edge":
        if not edge_available():
            raise RuntimeError("Suara Microsoft tidak tersedia di pemasangan ini.")
        return _synthesize_edge(text, out_path, spec["model"], rate,
                                spec.get("pitch", 0))

    if not available():
        raise RuntimeError("Suara pembaca judul belum terpasang.")
    with _lock:
        piper_voice = _load()
        kwargs = {}
        if rate and abs(rate - 1.0) > 1e-3:
            # Piper menamainya length_scale: lebih besar = lebih lambat.
            try:
                from piper import SynthesisConfig

                kwargs["syn_config"] = SynthesisConfig(length_scale=1.0 / rate)
            except Exception:      # versi lama tanpa SynthesisConfig
                kwargs = {}
        with wave.open(str(out_path), "wb") as wav:
            piper_voice.synthesize_wav(text, wav, **kwargs)

    with wave.open(str(out_path)) as wav:
        return wav.getnframes() / float(wav.getframerate() or 1)


def download_voice(on_progress=None) -> bool:
    """
    Mengunduh berkas suara bila belum ada.

    Dipisahkan dari `synthesize` supaya unduhan 63 MB tidak pernah terjadi
    diam-diam di tengah render — pengguna memintanya sendiri, dan melihat
    kemajuannya.
    """
    if VOICE_PATH.is_file() and VOICE_PATH.with_suffix(".onnx.json").is_file():
        return True
    TTS_DIR.mkdir(parents=True, exist_ok=True)
    for url, dest in ((VOICE_URL, VOICE_PATH),
                      (VOICE_URL + ".json", VOICE_PATH.with_suffix(".onnx.json"))):
        tmp = dest.with_suffix(dest.suffix + ".part")
        cmd = ["curl", "-sL", "--fail", "-o", str(tmp), url]
        proc = subprocess.run(cmd, capture_output=True, timeout=900)
        if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            log.warning("Gagal mengunduh %s", url)
            return False
        tmp.replace(dest)
        if on_progress:
            on_progress(dest.name)
    log.info("Suara %s siap dipakai", VOICE_NAME)
    return True
