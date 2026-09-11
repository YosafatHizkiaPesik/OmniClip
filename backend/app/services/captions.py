"""
Pengambilan transkrip dari caption YouTube, dengan timing per-kata.

Temuan yang menentukan desain modul ini: caption otomatis YouTube dalam format
`json3` SUDAH membawa timestamp per kata (`events[].segs[].tOffsetMs`). Versi
lama meminta `vtt` lalu melakukan dedupe berdasarkan teks untuk melawan
rolling caption — yang justru menghancurkan timing dan membuang kata sah yang
memang berulang seperti "iya" atau "nggak".

Konsekuensinya: faster-whisper hanya dipakai bila video benar-benar tidak punya
caption. Untuk video 68 menit, jalur ini selesai di bawah satu detik.
"""

import glob
import json
import logging
import os
import shutil
import tempfile
from typing import Any, Iterable, NotRequired, Optional, TypedDict

import yt_dlp

from ..config import CAPTION_LANGS
from .ytdlp import _base_opts

log = logging.getLogger("omniclip.captions")


class Word(TypedDict):
    w: str
    s: float
    e: float
    p: NotRequired[float]  # confidence, hanya dari whisper


class TranscriptResult(TypedDict):
    words: list[Word]
    language: str
    source: str  # 'youtube_manual' | 'youtube_asr' | 'whisper'


MIN_WORD_DURATION = 0.06


def _parse_json3(data: dict[str, Any]) -> list[Word]:
    """
    Mengubah caption json3 menjadi daftar kata bertimestamp.

    Bentuk datanya: setiap event punya `tStartMs`, dan tiap segmen di dalamnya
    punya `tOffsetMs` relatif terhadap event itu. Segmen berisi hanya newline
    ('\\n') adalah penanda tata letak, bukan ucapan.
    """
    words: list[Word] = []

    for event in data.get("events") or []:
        segs = event.get("segs")
        if not segs:
            continue
        base = (event.get("tStartMs") or 0) / 1000.0
        event_dur = (event.get("dDurationMs") or 0) / 1000.0

        # Segmen yang benar-benar berisi teks, beserta indeks aslinya.
        real = [(i, sg) for i, sg in enumerate(segs) if (sg.get("utf8") or "").strip()]
        for pos, (idx, seg) in enumerate(real):
            text = seg["utf8"].strip()
            start = base + (seg.get("tOffsetMs") or 0) / 1000.0

            # Akhir kata = awal kata berikutnya dalam event yang sama;
            # untuk kata terakhir, pakai durasi event.
            if pos + 1 < len(real):
                end = base + (real[pos + 1][1].get("tOffsetMs") or 0) / 1000.0
            else:
                end = base + event_dur if event_dur else start + 0.3

            words.append({
                "w": text,
                "s": round(start, 3),
                "e": round(max(end, start + MIN_WORD_DURATION), 3),
            })

    words.sort(key=lambda w: w["s"])
    return _clamp_overlaps(_dedupe(split_phrases(words)))


# Kecepatan bicara, karakter per detik. Dipakai hanya untuk menaksir sampai
# kapan sebuah kalimat takarir masih diucapkan ketika sumbernya tidak menyimpan
# waktu per kata. Bahasa Indonesia lisan berkisar 13-15; 14 diambil sebagai
# tengahnya, dan hasilnya selalu dijepit oleh mulainya cue berikutnya.
SPEAK_CPS = 14.0


def split_phrases(words: list[Word]) -> list[Word]:
    """
    Memecah cue yang berisi SATU KALIMAT PENUH menjadi kata-kata.

    Takarir resmi kanal (`youtube_manual`) berbeda bentuk dari takarir otomatis:
    ia berwaktu per-cue, bukan per-kata. Terukur pada satu video, 98% entrinya
    berisi spasi, panjang tengahnya 36 karakter, dan durasinya 1,2 detik —
    seluruhnya, karena `_clamp_overlaps` di bawah memang membatasi satu "kata"
    pada 1,2 detik.

    Selama entri itu diperlakukan sebagai kata, seluruh rantai di belakangnya
    ikut salah: pemecah baris melihat satu kata dan berhenti memecah, sehingga
    satu baris subtitle memuat 60 karakter dalam 1,8 detik — 33 karakter per
    detik, dua kali lipat kecepatan baca yang nyaman. Itulah "subtitle terlalu
    panjang dan cepat hilang" yang terlihat di hasil render.

    Waktunya dibagi menurut panjang tiap kata. Itu perkiraan — takarir resmi
    memang tidak menyimpan waktu per kata, dan tidak ada yang bisa
    mengembalikannya. Tapi perkiraan yang membuat barisnya terpecah wajar jauh
    lebih dekat ke kebenaran daripada satu kalimat yang mengaku satu kata.
    """
    out: list[Word] = []
    for i, w in enumerate(words):
        teks = (w.get("w") or "").strip()
        bagian = teks.split()
        if len(bagian) < 2:
            if teks:
                out.append({**w, "w": teks})
            continue

        mulai = float(w["s"])
        # Ujung cue yang tersimpan tidak bisa dipakai apa adanya.
        #
        # Pada takarir resmi ia sering sudah dipotong — `_clamp_overlaps` di
        # bawah membatasi satu entri pada 1,2 detik, dan kalimat 60 karakter
        # yang dipaksa masuk ke 1,2 detik menghasilkan 50 karakter per detik
        # betapapun rapi ia dipecah. Yang dipakai: perkiraan dari KECEPATAN
        # BICARA, dijepit oleh mulainya cue berikutnya — karena di situlah
        # kalimat ini pasti sudah selesai.
        berikut = float(words[i + 1]["s"]) if i + 1 < len(words) else None
        wajar = mulai + len(teks) / SPEAK_CPS
        selesai = max(float(w["e"]), wajar)
        if berikut is not None:
            selesai = min(selesai, max(berikut, mulai + 0.12 * len(bagian)))
        selesai = max(selesai, mulai + 0.12 * len(bagian))

        bobot = [len(b) + 1 for b in bagian]
        total = sum(bobot)
        jalan = mulai
        for b, bo in zip(bagian, bobot):
            lebar = (selesai - mulai) * bo / total
            out.append({**w, "w": b, "s": round(jalan, 3),
                        "e": round(jalan + lebar, 3)})
            jalan += lebar
    return out


def _clamp_overlaps(words: list[Word], max_word_duration: float = 1.2) -> list[Word]:
    """
    Merapikan akhir kata agar tidak menabrak kata berikutnya.

    Kata terakhir dalam sebuah event mewarisi `dDurationMs` event tersebut,
    padahal event berikutnya sering mulai lebih awal (rolling caption saling
    tumpang tindih). Tanpa perapian ini muncul durasi seperti 2,7 detik untuk
    satu kata dan jeda negatif sampai -5,7 detik — yang akan membuat sorotan
    karaoke menyala di kata yang salah.
    """
    for i, w in enumerate(words):
        limit = words[i + 1]["s"] if i + 1 < len(words) else None
        end = w["e"]
        if limit is not None:
            end = min(end, limit)
        end = min(end, w["s"] + max_word_duration)
        w["e"] = round(max(end, w["s"] + MIN_WORD_DURATION), 3)
    return words


def _dedupe(words: list[Word]) -> list[Word]:
    """
    Membuang kata yang benar-benar terduplikasi.

    Kuncinya adalah (waktu, teks) — BUKAN teks saja. Rolling caption mengulang
    kata pada waktu yang berbeda; membuang berdasarkan teks saja akan menghapus
    pengulangan yang sah di sepanjang video.
    """
    out: list[Word] = []
    for w in words:
        if out:
            prev = out[-1]
            if prev["w"] == w["w"] and abs(prev["s"] - w["s"]) < 0.05:
                continue
        out.append(w)
    return out


def _try_language(video_id: str, lang: str, tmpdir: str) -> Optional[TranscriptResult]:
    """
    Mengunduh caption untuk SATU bahasa.

    Meminta beberapa bahasa sekaligus terbukti memicu HTTP 429 dari YouTube:
    bahasa pertama berhasil, permintaan kedua langsung kena rate limit. Jadi
    bahasa dicoba satu per satu dan berhenti pada yang pertama berhasil.
    """
    opts = _base_opts()
    opts.update({
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [lang],
        "subtitlesformat": "json3",
        "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
    })

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
    except Exception as e:
        log.info("Caption '%s' tidak bisa diambil: %s", lang, str(e)[:160])
        return None

    matches = glob.glob(os.path.join(tmpdir, f"*.{lang}.json3"))
    if not matches:
        matches = [f for f in glob.glob(os.path.join(tmpdir, "*.json3"))]
    if not matches:
        return None

    try:
        with open(matches[0], encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log.warning("File caption rusak: %s", e)
        return None

    words = _parse_json3(data)
    if not words:
        return None

    # Caption tulisan manusia jauh lebih akurat daripada hasil ASR YouTube.
    is_manual = lang in (info.get("subtitles") or {})
    return {
        "words": words,
        "language": lang,
        "source": "youtube_manual" if is_manual else "youtube_asr",
    }


def fetch_youtube_captions(
    video_id: str, langs: Iterable[str] = CAPTION_LANGS
) -> Optional[TranscriptResult]:
    """
    Mengambil transkrip word-level dari caption YouTube.

    Mengembalikan None (bukan melempar exception) bila video tidak punya caption
    — pemanggil akan jatuh ke faster-whisper.
    """
    tmpdir = tempfile.mkdtemp(prefix=f"omni_sub_{video_id}_")
    try:
        seen: set[str] = set()
        for lang in langs:
            if lang in seen:
                continue
            seen.add(lang)
            result = _try_language(video_id, lang, tmpdir)
            if result:
                log.info("Transkrip dari caption %s (%s): %d kata",
                         lang, result["source"], len(result["words"]))
                return result
        return None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
