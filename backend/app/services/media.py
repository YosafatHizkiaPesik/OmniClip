"""Utilitas media berbasis ffmpeg: probe, ekstraksi audio, jejak energi, waveform."""

import json
import logging
import math
import re
import subprocess
from pathlib import Path

log = logging.getLogger("omniclip.media")


def probe(path: str | Path) -> dict:
    """Metadata dasar sebuah file media."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate",
             "-show_entries", "format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        if out.returncode != 0:
            return {}
        data = json.loads(out.stdout or "{}")
        info: dict = {"duration": float(data.get("format", {}).get("duration") or 0) or None}
        for st in data.get("streams", []):
            if st.get("codec_type") == "video" and "width" not in info:
                info.update(width=st.get("width"), height=st.get("height"), vcodec=st.get("codec_name"))
                rate = st.get("r_frame_rate") or "0/1"
                try:
                    num, den = rate.split("/")
                    info["fps"] = round(int(num) / int(den), 3) if int(den) else None
                except (ValueError, ZeroDivisionError):
                    info["fps"] = None
            elif st.get("codec_type") == "audio" and "acodec" not in info:
                info["acodec"] = st.get("codec_name")
        return info
    except Exception as e:
        log.warning("ffprobe gagal untuk %s: %s", path, e)
        return {}


def extract_audio_wav(src: str | Path, dest: str | Path, *, sample_rate: int = 16000) -> bool:
    """
    Mengekstrak audio mono PCM 16 kHz — format yang memang diminta Whisper.
    File 30 menit hanya sekitar 57 MB.
    """
    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-loglevel", "error",
           "-i", str(src), "-vn", "-ac", "1", "-ar", str(sample_rate),
           "-c:a", "pcm_s16le", str(dest)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            log.error("Ekstraksi audio gagal: %s", r.stderr[-400:])
            return False
        return Path(dest).exists()
    except subprocess.TimeoutExpired:
        log.error("Ekstraksi audio timeout untuk %s", src)
        return False


_RMS_RE = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+|-inf)")


def energy_track(src: str | Path, *, duration: float) -> list[float]:
    """
    Jejak kekerasan suara, satu nilai RMS dB per detik.

    Satu pass ffmpeg, tanpa dependensi tambahan. Dipakai oleh mesin heuristik
    untuk mengenali bagian yang disampaikan dengan energi tinggi.
    """
    cmd = [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(src),
        "-af", "aresample=8000,asetnsamples=8000,astats=metadata=1:reset=1,"
               "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
        "-f", "null", "-",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=max(300, duration * 0.5))
    except subprocess.TimeoutExpired:
        log.warning("Analisis energi timeout; dilewati")
        return []

    values: list[float] = []
    for m in _RMS_RE.finditer(r.stdout or ""):
        raw = m.group(1)
        values.append(-90.0 if raw == "-inf" else float(raw))
    return values


def zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    sd = math.sqrt(var)
    if sd < 1e-6:
        return [0.0] * n
    return [(v - mean) / sd for v in values]


def waveform_peaks(src: str | Path, *, bins: int = 2000,
                   duration: float | None = None) -> list[int]:
    """
    Puncak amplitudo untuk digambar di timeline editor.

    PCM dibaca secara mengalir, bukan ditampung seluruhnya: menahan audio 3 jam
    di memori berarti ~165 MB plus salinannya — pola yang persis membuat
    transkripsi memicu OOM killer sebelumnya.

    Menghasilkan angka 0-255 per bin (bukan PNG seperti `showwavespic`, karena
    gambar tidak bisa di-zoom ulang di sisi klien).
    """
    import array

    if duration is None:
        duration = probe(src).get("duration") or 0.0
    if duration <= 0:
        return []

    sample_rate = 8000
    total_samples = int(duration * sample_rate)
    per_bin = max(1, total_samples // max(1, bins))

    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(src),
           "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-"]

    peaks: list[int] = []
    carry = b""
    acc_peak = 0
    acc_count = 0

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        while True:
            chunk = proc.stdout.read(1 << 20)  # 1 MB
            if not chunk:
                break
            if carry:
                chunk = carry + chunk
                carry = b""
            if len(chunk) % 2:
                carry = chunk[-1:]
                chunk = chunk[:-1]

            samples = array.array("h")
            samples.frombytes(chunk)
            for v in samples:
                a = -v if v < 0 else v
                if a > acc_peak:
                    acc_peak = a
                acc_count += 1
                if acc_count >= per_bin:
                    peaks.append(min(255, acc_peak * 255 // 32768))
                    acc_peak = 0
                    acc_count = 0
                    if len(peaks) >= bins:
                        break
            if len(peaks) >= bins:
                break
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        proc.stdout.close()

    if acc_count and len(peaks) < bins:
        peaks.append(min(255, acc_peak * 255 // 32768))
    return peaks


def poster_frame(src: str | Path, dest: str | Path, *,
                 at: float | None = None, width: int = 480) -> bool:
    """
    Satu bingkai dari sebuah video, untuk dipakai sebagai sampul di daftar.

    Diambil dari berkasnya sendiri, bukan dari thumbnail YouTube: halaman
    Unduhan justru menampilkan apa yang tersedia tanpa internet, jadi sampul
    yang harus diambil dari jaringan akan kosong persis ketika daftar itu
    paling berguna. Bingkai lokal juga jujur — ia memperlihatkan isi berkas
    yang benar-benar ada di cakram.

    Dicari mundur dari `at`: bingkai pertama video kerap hitam atau bumper
    kanal, jadi pemanggil memberi titik di tengah durasi.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    detik = max(0.0, float(at if at is not None else 10.0))

    # -ss sebelum -i: pencarian keyframe, cukup untuk gambar diam dan jauh
    # lebih cepat daripada mendekode dari awal pada berkas satu jam.
    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-loglevel", "error",
           "-ss", f"{detik:.2f}", "-i", str(src), "-frames:v", "1",
           "-vf", f"scale={int(width)}:-2:flags=bilinear",
           "-q:v", "4", str(dest)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not dest.is_file():
            # Pencarian bisa melewati akhir berkas bila durasinya salah baca;
            # coba sekali lagi dari awal sebelum menyerah.
            if detik > 0:
                return poster_frame(src, dest, at=0.0, width=width)
            log.warning("Sampul gagal dibuat untuk %s: %s", src, (r.stderr or "")[-300:])
            return False
        return True
    except subprocess.TimeoutExpired:
        log.warning("Sampul timeout untuk %s", src)
        return False
