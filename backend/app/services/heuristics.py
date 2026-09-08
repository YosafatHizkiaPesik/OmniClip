"""
Mesin pemilih momen menarik berbasis transkrip nyata.

Modul ini menggantikan `generate_opus_fallback_clips()` yang lama, yang:
  - membagi durasi video secara rata dan menyebutnya "analisis",
  - memakai array skor literal [98,96,94,92,90,89,93,91],
  - memilih "alasan viral" bergiliran dari enam kalimat kaleng,
  - dan bila video tidak punya transkrip, MENGARANG lima kalimat Indonesia
    yang kemudian dibakar ke dalam MP4 seolah itu dialog asli.

Di sini tidak ada satupun angka yang dikarang. Setiap komponen skor dihitung
dari transkrip dan audio yang benar-benar ada, dan seluruh rinciannya dikirim
ke UI supaya bisa diperiksa.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from .transcript import Sentence, ends_dangling

# --- Leksikon hook bahasa Indonesia -------------------------------------------
# Frasa yang secara nyata membuka sebuah pernyataan menarik.
HOOK_PATTERNS = [
    (r"\bkenapa\b", "hook_question"),
    (r"\bmengapa\b", "hook_question"),
    (r"\bgimana\b|\bbagaimana\b", "hook_question"),
    (r"\bternyata\b", "hook_reveal"),
    (r"\bsebenarnya\b|\bsebenernya\b", "hook_reveal"),
    (r"\bfaktanya\b|\bkenyataannya\b", "hook_reveal"),
    (r"\brahasia\b", "hook_reveal"),
    (r"\bjangan pernah\b|\bjangan sampai\b", "hook_warning"),
    (r"\bsalah besar\b|\bsalah kaprah\b", "hook_warning"),
    (r"\bhati-hati\b|\bawas\b", "hook_warning"),
    (r"\bgue kaget\b|\bsaya kaget\b|\bnggak nyangka\b|\bgak nyangka\b", "hook_surprise"),
    (r"\bparah banget\b|\bgila sih\b|\bedan\b", "hook_surprise"),
    (r"\byang bikin\b|\bini yang\b", "hook_pointer"),
    (r"\bbanyak orang\b|\bkebanyakan orang\b", "hook_pointer"),
    (r"\bcoba bayangin\b|\bbayangkan\b", "hook_pointer"),
    (r"\bpertama\b.{0,20}\bkedua\b", "hook_list"),
    (r"^\s*\d+\s+(hal|cara|alasan|tips|langkah)", "hook_list"),
]
HOOK_RE = [(re.compile(p, re.I), key) for p, key in HOOK_PATTERNS]

# Kata yang terlalu umum untuk dianggap khas saat menghitung salience.
STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "untuk", "dengan", "pada",
    "adalah", "ada", "tidak", "nggak", "gak", "ya", "iya", "saya", "aku", "gue",
    "kamu", "kita", "dia", "mereka", "akan", "sudah", "udah", "juga", "bisa",
    "kalau", "kalo", "jadi", "atau", "tapi", "karena", "aja", "saja", "lagi",
    "banget", "sih", "nya", "kan", "kok", "deh", "dong", "nih", "tuh", "gitu",
    "gini", "apa", "mau", "buat", "punya", "orang", "satu", "dua", "kayak",
    "seperti", "lebih", "sangat", "harus", "masih", "biar", "oke", "nah",
}

# Label Indonesia untuk setiap alasan. UI merender teks tetap ini, bukan prosa
# yang dikarang model.
REASON_LABELS = {
    "hook_question": "Dibuka dengan pertanyaan",
    "hook_reveal": "Membuka fakta yang mengejutkan",
    "hook_warning": "Berisi peringatan yang kuat",
    "hook_surprise": "Reaksi spontan yang kuat",
    "hook_pointer": "Langsung menunjuk inti persoalan",
    "hook_list": "Disusun sebagai daftar poin",
    "clean_start": "Dimulai tepat setelah jeda bicara",
    "complete_ending": "Berakhir di kalimat yang utuh",
    "energy_peak": "Energi bicara tinggi",
    "dynamic_delivery": "Penyampaian naik-turun, tidak datar",
    "good_pace": "Tempo bicara pas untuk klip pendek",
    "topic_focus": "Topik paling khas di video ini",
}


@dataclass
class Candidate:
    start: float
    end: float
    score: float                      # 0..1
    breakdown: dict[str, float]
    sentence_span: tuple[int, int]
    reason_keys: list[str] = field(default_factory=list)
    hook_text: str = ""
    text: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start


# --- Komponen skor ------------------------------------------------------------
def _opening_penalty(first: Sentence) -> float:
    """
    Pengali untuk pembuka yang jelas bukan awal ucapan.

    Dua sinyal yang sangat kuat pada transkrip podcast:
      - kalimat dimulai huruf kecil -> hampir pasti sambungan kalimat sebelumnya,
        jadi klip akan terdengar seperti masuk di tengah pembicaraan;
      - kalimat sangat pendek ("Hah?", "Enggaklah.") -> potongan reaksi, bukan
        pembuka yang bisa berdiri sendiri.
    """
    text = first["text"].strip()
    if not text:
        return 0.2

    penalty = 1.0
    head = text.split()[0]
    if head[:1].islower():
        penalty *= 0.35
    n_words = len(text.split())
    if n_words <= 2:
        penalty *= 0.4
    elif n_words <= 4:
        penalty *= 0.7
    return penalty


def _hook_score(sentences: list[Sentence], i: int, j: int,
                silence_before: bool) -> tuple[float, list[str]]:
    """Seberapa kuat pembuka klip, dilihat dari ~3 detik pertama."""
    start_t = sentences[i]["s"]
    opening = " ".join(
        s["text"] for s in sentences[i:j] if s["s"] < start_t + 3.0
    ) or sentences[i]["text"]

    keys: list[str] = []
    for rx, key in HOOK_RE:
        if rx.search(opening) and key not in keys:
            keys.append(key)

    score = min(1.0, 0.45 * len(keys))
    if "?" in opening:
        score = min(1.0, score + 0.25)
        if "hook_question" not in keys:
            keys.append("hook_question")
    if silence_before:
        score = min(1.0, score + 0.15)
        keys.append("clean_start")

    penalty = _opening_penalty(sentences[i])
    if penalty < 0.6:
        keys = [k for k in keys if k != "clean_start"]
    return score * penalty, keys


def _completeness_score(sentences: list[Sentence], j: int,
                        gap_after: float) -> tuple[float, list[str]]:
    """Apakah klip berakhir sebagai pikiran yang utuh."""
    last = sentences[j - 1]
    score = 0.35
    keys: list[str] = []

    if re.search(r"[.!?…]$", last["text"].strip()):
        score = 1.0
        keys.append("complete_ending")
    elif gap_after >= 0.7:
        score = 0.8
        keys.append("complete_ending")

    if ends_dangling(last):
        score *= 0.35
        if "complete_ending" in keys:
            keys.remove("complete_ending")
    return score, keys


def _energy_score(energy_z: list[float], start: float, end: float) -> tuple[float, list[str]]:
    """Rata-rata energi + variasinya. Penyampaian dinamis mengalahkan monoton."""
    if not energy_z:
        return 0.5, []
    a, b = int(start), min(len(energy_z), int(end) + 1)
    window = energy_z[a:b]
    if not window:
        return 0.5, []

    mean = sum(window) / len(window)
    var = sum((v - mean) ** 2 for v in window) / len(window)
    sd = math.sqrt(var)

    raw = mean + 0.4 * sd
    score = max(0.0, min(1.0, (raw + 1.5) / 3.0))  # z sekitar -1.5..+1.5 -> 0..1

    keys: list[str] = []
    if mean > 0.4:
        keys.append("energy_peak")
    if sd > 0.8:
        keys.append("dynamic_delivery")
    return score, keys


def _density_score(word_count: int, duration: float) -> tuple[float, list[str]]:
    """Kata per detik, dengan dataran nyaman di 2,2-4,0 wps."""
    if duration <= 0:
        return 0.0, []
    wps = word_count / duration
    if 2.2 <= wps <= 4.0:
        return 1.0, ["good_pace"]
    if wps < 2.2:
        return max(0.0, wps / 2.2), []      # terlalu banyak diam
    return max(0.0, 1.0 - (wps - 4.0) / 3.0), []  # terlalu cepat


def _salience_score(tf_idf: dict[str, float], sentences: list[Sentence],
                    i: int, j: int, max_salience: float) -> tuple[float, list[str]]:
    """Seberapa terkonsentrasi kosakata khas video di jendela ini."""
    if max_salience <= 0:
        return 0.5, []
    words = _tokenize(" ".join(s["text"] for s in sentences[i:j]))
    top = sorted((tf_idf.get(w, 0.0) for w in set(words)), reverse=True)[:5]
    raw = sum(top)
    score = max(0.0, min(1.0, raw / max_salience))
    return score, (["topic_focus"] if score > 0.75 else [])


def _length_fit(duration: float, ideal: float) -> float:
    return math.exp(-((duration - ideal) ** 2) / (2 * 12.0 ** 2))


# --- Bantuan ------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[a-zA-ZÀ-ɏ']+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 3
            and t.lower() not in STOPWORDS]


def _build_tfidf(sentences: list[Sentence]) -> dict[str, float]:
    """TF-IDF dengan tiap kalimat sebagai satu dokumen."""
    n = len(sentences) or 1
    df = Counter()
    for s in sentences:
        df.update(set(_tokenize(s["text"])))
    tf = Counter()
    for s in sentences:
        tf.update(_tokenize(s["text"]))
    return {
        w: (1 + math.log(tf[w])) * math.log(n / (1 + df[w]))
        for w in tf if df[w] >= 2
    }


WEIGHTS = {
    "hook": 0.30,
    "completeness": 0.20,
    "energy": 0.15,
    "density": 0.10,
    "salience": 0.15,
    "length_fit": 0.10,
}


def _iou(a: Candidate, b: Candidate) -> float:
    lo = max(a.start, b.start)
    hi = min(a.end, b.end)
    inter = max(0.0, hi - lo)
    union = (a.end - a.start) + (b.end - b.start) - inter
    return inter / union if union > 0 else 0.0


def make_hook_text(sentences: list[Sentence], i: int, j: int,
                   min_words: int = 4, max_words: int = 7) -> str:
    """
    Hook diambil dari kalimat pembuka klip itu sendiri, huruf besar.

    Kalimat pertama transkrip podcast sering hanya fragmen reaksi ("Hah?"),
    jadi kalimat berikutnya ikut disambung sampai hook cukup bermakna.

    Ini kutipan nyata, bukan headline karangan. Kalau Gemini tersedia, ia boleh
    menulis ulang; tanpa Gemini, kutipan asli tetap hook yang baik — dan yang
    terpenting, isinya benar.
    """
    collected: list[str] = []
    for s in sentences[i:j]:
        collected.extend(s["text"].split())
        if len(collected) >= min_words:
            break
    text = " ".join(collected[:max_words]).strip(" ,;:-")
    return text.upper()


# --- Titik masuk utama --------------------------------------------------------
def generate_candidates(
    sentences: list[Sentence],
    words: list,
    energy_z: Optional[list[float]] = None,
    *,
    duration: float,
    target: tuple[float, float] = (20.0, 60.0),
    ideal: float = 35.0,
    max_out: int = 10,
) -> list[Candidate]:
    """
    Menyusun kandidat klip dari transkrip.

    Setiap jendela WAJIB dimulai di awal kalimat dan berakhir di akhir kalimat.
    Aturan itu sendirian sudah menghilangkan artefak terburuk sistem lama:
    klip yang mulai dan berhenti di tengah kata.
    """
    if not sentences:
        return []

    energy_z = energy_z or []
    tf_idf = _build_tfidf(sentences)
    max_salience = 0.0

    lo, hi = target
    raw: list[Candidate] = []

    for i in range(len(sentences)):
        # Jeda sebelum kalimat pembuka menandakan awal topik yang bersih.
        silence_before = (i == 0) or (sentences[i]["s"] - sentences[i - 1]["e"]) >= 0.8

        for j in range(i + 1, len(sentences) + 1):
            start = sentences[i]["s"]
            end = sentences[j - 1]["e"]
            dur = end - start
            if dur < lo:
                continue
            if dur > hi:
                break

            gap_after = (sentences[j]["s"] - end) if j < len(sentences) else 999.0

            hook, hook_keys = _hook_score(sentences, i, j, silence_before)
            comp, comp_keys = _completeness_score(sentences, j, gap_after)
            ener, ener_keys = _energy_score(energy_z, start, end)
            wcount = sentences[j - 1]["wi"][1] - sentences[i]["wi"][0]
            dens, dens_keys = _density_score(wcount, dur)

            sal_words = _tokenize(" ".join(s["text"] for s in sentences[i:j]))
            sal_raw = sum(sorted((tf_idf.get(w, 0.0) for w in set(sal_words)), reverse=True)[:5])
            max_salience = max(max_salience, sal_raw)

            breakdown = {
                "hook": hook,
                "completeness": comp,
                "energy": ener,
                "density": dens,
                "salience": sal_raw,          # dinormalisasi setelah loop
                "length_fit": _length_fit(dur, ideal),
            }
            raw.append(Candidate(
                start=start, end=end, score=0.0, breakdown=breakdown,
                sentence_span=(i, j),
                reason_keys=hook_keys + comp_keys + ener_keys + dens_keys,
                text=" ".join(s["text"] for s in sentences[i:j]),
            ))

    if not raw:
        return []

    # Normalisasi salience lalu hitung skor akhir.
    for c in raw:
        sal = c.breakdown["salience"] / max_salience if max_salience > 0 else 0.5
        c.breakdown["salience"] = round(min(1.0, sal), 4)
        if c.breakdown["salience"] > 0.75 and "topic_focus" not in c.reason_keys:
            c.reason_keys.append("topic_focus")
        c.score = round(sum(WEIGHTS[k] * c.breakdown[k] for k in WEIGHTS), 4)
        c.breakdown = {k: round(v, 4) for k, v in c.breakdown.items()}

    # Non-maximum suppression: jangan tawarkan sepuluh varian dari momen sama.
    raw.sort(key=lambda c: c.score, reverse=True)
    kept: list[Candidate] = []
    for cand in raw:
        if any(_iou(cand, k) > 0.30 or abs(cand.start - k.start) < 8.0 for k in kept):
            continue
        cand.hook_text = make_hook_text(sentences, cand.sentence_span[0], cand.sentence_span[1])
        kept.append(cand)
        if len(kept) >= max_out:
            break

    kept.sort(key=lambda c: c.start)
    return kept


# Preset panjang klip. Batas atas lamalah yang membuat klip hanya menangkap
# pembukaan sebuah pembahasan: pertanyaan masuk, jawabannya tidak. "panjang"
# memberi ruang untuk satu gagasan utuh — setup sekaligus penutupnya.
LENGTH_PRESETS = {
    "short":  {"target": (15.0, 40.0),  "ideal": 28.0, "max": 55.0},
    "medium": {"target": (20.0, 60.0),  "ideal": 35.0, "max": 80.0},
    "long":   {"target": (35.0, 110.0), "ideal": 65.0, "max": 135.0},
}


def auto_clip_count(duration: float) -> int:
    """
    Berapa klip yang masuk akal diambil dari video sepanjang ini.

    Batas 8 yang dulu dipatok membuat podcast dua jam diperlakukan sama dengan
    video sepuluh menit: dari 120 menit bahan, tujuh per delapan-nya tidak
    pernah ditawarkan. Sekarang jatahnya tumbuh bersama durasi — kira-kira satu
    klip tiap empat menit — dengan lantai 4 supaya video pendek tetap dapat
    beberapa pilihan, dan plafon 40 supaya daftarnya masih bisa ditinjau manusia.
    """
    if duration <= 0:
        return 8
    return int(max(4, min(40, round(duration / 60.0 / 4.0) + 2)))


def validate_and_snap(candidates: list[Candidate], sentences: list[Sentence],
                      duration: float, *, max_duration: float = 90.0) -> list[Candidate]:
    """
    Penjaga terakhir yang dilewati SEMUA mesin (heuristik maupun Gemini).

    Membuang klip di luar rentang video, terlalu pendek atau terlalu panjang,
    dan menarik batasnya ke batas kalimat terdekat.
    """
    out: list[Candidate] = []
    for c in candidates:
        c.start = max(0.0, min(c.start, duration))
        c.end = max(0.0, min(c.end, duration))
        if c.end - c.start < 8.0 or c.end - c.start > max_duration:
            continue

        # Tarik ke batas kalimat terdekat dalam 1,5 detik.
        for attr, field_name in (("start", "s"), ("end", "e")):
            value = getattr(c, attr)
            nearest = min(sentences, key=lambda s: abs(s[field_name] - value), default=None)
            if nearest is not None and abs(nearest[field_name] - value) <= 1.5:
                setattr(c, attr, nearest[field_name])

        if c.end - c.start >= 8.0:
            out.append(c)

    out.sort(key=lambda c: c.score, reverse=True)
    deduped: list[Candidate] = []
    for c in out:
        if any(_iou(c, k) > 0.6 for k in deduped):
            continue
        deduped.append(c)
    deduped.sort(key=lambda c: c.start)
    return deduped
