"""
Bentuk data klip yang dipakai bersama backend dan frontend.

Keputusan penting: sebuah klip adalah DAFTAR SEGMEN, bukan sepasang
start/end tunggal. Ini memungkinkan pengguna menggabungkan menit 10 dengan
menit 50 menjadi satu klip — sistem akan memotong tiap bagian lalu
menyambungnya. Klip hasil AI hampir selalu punya satu segmen; segmen kedua dan
seterusnya muncul saat pengguna mengedit.
"""

import re
import uuid
from typing import Any, Optional

from .captions import Word
from .heuristics import Candidate, REASON_LABELS
from .transcript import Sentence


def new_clip_id() -> str:
    return uuid.uuid4().hex[:12]


# --- Penanda non-ucapan --------------------------------------------------------
# Caption otomatis YouTube dan Whisper sama-sama menyisipkan penanda suara yang
# BUKAN ucapan: "[Musik]", "[Tertawa]", "[Tepuk tangan]", "(applause)", "♪".
# Penanda itu berguna untuk pembaca tunarungu di pemutar YouTube, tapi pada klip
# vertikal ia muncul sebagai baris subtitle utuh yang tidak ada yang
# mengucapkannya — dan ikut memakan jatah baris di layar.
_BRACKETED = re.compile(r"[\[\(（【][^\]\)）】]*[\]\)）】]")
_OPENERS = "[(（【"
_CLOSERS = "])）】"
# Tanda musik dan penanda ganti pembicara gaya broadcast ('>>').
_STRIP_CHARS = " \t♪♫♬>-–—"


def strip_non_speech(words: list[Word]) -> list[Word]:
    """
    Membuang penanda non-ucapan dari deretan kata.

    Penanda bisa datang sebagai satu token ("[Tertawa]") atau terpecah menjadi
    beberapa token ("[Tepuk", "tangan]"), tergantung sumber transkripnya. Karena
    itu kurung dihitung sebagai keadaan yang berjalan, bukan dicocokkan per
    token: begitu sebuah kurung terbuka, semua kata dibuang sampai ia tertutup.
    """
    out: list[Word] = []
    depth = 0

    for w in words:
        token = (w.get("w") or "").strip()
        if not token:
            continue

        if depth > 0:
            depth += sum(token.count(c) for c in _OPENERS)
            depth -= sum(token.count(c) for c in _CLOSERS)
            depth = max(0, depth)
            continue

        core = _BRACKETED.sub("", token)
        opens = sum(core.count(c) for c in _OPENERS)
        closes = sum(core.count(c) for c in _CLOSERS)
        if opens > closes:
            depth = opens - closes
            continue

        core = core.strip(_STRIP_CHARS)
        if not core:
            continue
        out.append({**w, "w": core})

    return out


def sanitize_caption_lines(lines: list[dict]) -> list[dict]:
    """
    Membersihkan baris subtitle yang SUDAH tersimpan.

    Analisis yang dijalankan sebelum penyaringan ini ada tetap menyimpan
    "[Musik]" di dalam hasilnya. Membersihkannya saat dibaca berarti project
    lama ikut membaik tanpa perlu dianalisis ulang.
    """
    out: list[dict] = []
    for line in lines:
        words = line.get("words") or []
        if words:
            kept = strip_non_speech(words)
            if not kept:
                continue
            out.append({**line, "words": kept,
                        "text": " ".join(w["w"] for w in kept).strip(),
                        "start": kept[0]["s"], "end": kept[-1]["e"]})
            continue
        text = _BRACKETED.sub("", line.get("text") or "").strip(_STRIP_CHARS)
        if text:
            out.append({**line, "text": text})
    return out


def slice_words(words: list[Word], start: float, end: float) -> list[Word]:
    """Kata yang jatuh di dalam sebuah rentang waktu."""
    return [w for w in words if w["e"] > start and w["s"] < end]


def words_to_caption_lines(words: list[Word], *, max_words: int = 5,
                           max_chars: int = 30, max_gap: float = 0.45) -> list[dict]:
    """
    Mengelompokkan kata menjadi baris subtitle pendek ala klip vertikal.

    Baris dipecah pada: batas jumlah kata, batas karakter, jeda bicara, atau
    tanda baca akhir kalimat.
    """
    words = strip_non_speech(words)
    lines: list[dict] = []
    buf: list[Word] = []

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        # Satu baris bisa memuat kata dari dua penutur bila giliran berganti di
        # tengah baris; yang dipakai adalah yang terbanyak, karena satu baris
        # hanya punya satu warna.
        labels = [w["sp"] for w in buf if "sp" in w]
        speaker = max(set(labels), key=labels.count) if labels else 0
        lines.append({
            "start": buf[0]["s"],
            "end": buf[-1]["e"],
            "text": " ".join(w["w"] for w in buf).strip(),
            "speaker": speaker,
            "words": [{"w": w["w"], "s": w["s"], "e": w["e"]} for w in buf],
        })
        buf = []

    for i, w in enumerate(words):
        buf.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        chars = sum(len(x["w"]) + 1 for x in buf)
        if (len(buf) >= max_words
                or chars >= max_chars
                or w["w"].endswith((".", "!", "?", "…"))
                or (nxt and nxt["s"] - w["e"] > max_gap)
                or nxt is None):
            flush()
    flush()
    return lines


def rebase_segments(segments: list[dict]) -> list[dict]:
    """
    Menghitung offset setiap segmen pada linimasa klip hasil gabungan.

    Segmen kedua yang aslinya dari menit 50 akan muncul tepat setelah segmen
    pertama pada klip jadinya, jadi subtitle harus digeser sesuai.
    """
    out: list[dict] = []
    offset = 0.0
    for seg in segments:
        dur = max(0.0, float(seg["end"]) - float(seg["start"]))
        out.append({"start": float(seg["start"]), "end": float(seg["end"]),
                    "offset": round(offset, 3), "duration": round(dur, 3)})
        offset += dur
    return out


def build_clip_payload(
    candidate: Candidate,
    *,
    words: list[Word],
    sentences: list[Sentence],
    index: int,
    video_title: str = "",
    channel: str = "",
) -> dict[str, Any]:
    """Mengubah kandidat heuristik menjadi klip yang siap dikirim ke UI."""
    segments = [{"start": round(candidate.start, 3), "end": round(candidate.end, 3)}]

    # `subtitles` memakai linimasa KLIP (mulai dari 0) karena itulah yang dipakai
    # pemutar preview dan file ASS saat render. `words` tetap memakai linimasa
    # video asli supaya editor bisa menghitung ulang subtitle ketika pengguna
    # menggeser batas klip atau menambah segmen dari menit lain.
    clip_subtitles, _ = rebuild_subtitles_for_segments(segments, words)
    clip_words = slice_words(words, candidate.start, candidate.end)

    return {
        "clip_id": new_clip_id(),
        "index": index,
        "segments": segments,
        # Dipertahankan agar kode lama yang membaca satu rentang tetap jalan.
        "start_seconds": segments[0]["start"],
        "end_seconds": segments[-1]["end"],
        "duration": round(candidate.duration, 2),
        # Skor ditampilkan 0-100 tapi berasal dari perhitungan nyata 0-1.
        "score": round(candidate.score * 100, 1),
        "score_breakdown": candidate.breakdown,
        "reasons": [REASON_LABELS.get(k, k) for k in candidate.reason_keys],
        "reason_keys": candidate.reason_keys,
        "hook_text": candidate.hook_text,
        # Field berikut hanya terisi bila Gemini ikut menajamkan hasil. UI
        # membedakan alasan terukur (reasons) dari tulisan model (ai_reason).
        # Judul dan tagar SELALU terisi. Sebelumnya keduanya hanya ada bila
        # Gemini ikut menajamkan, jadi klip dari mesin lokal keluar tanpa judul
        # sama sekali — dan judul berkasnya jatuh kembali ke judul video sumber
        # yang sama untuk kelima belas klipnya.
        "title": (getattr(candidate, "suggested_title", "")
                  or suggest_title(candidate.text, video_title)),
        # Gemini kadang menuliskannya tanpa pagar, kadang dengan. Disamakan di
        # satu tempat supaya UI tidak perlu menebak bentuk mana yang datang.
        "hashtags": normalize_hashtags(
            getattr(candidate, "hashtags", [])
            or suggest_hashtags(candidate.text, video_title, channel)),
        "ai_reason": getattr(candidate, "gemini_reason", "") or "",
        "transcript_text": candidate.text,
        "subtitles": clip_subtitles,
        "words": [{"w": w["w"], "s": w["s"], "e": w["e"]} for w in clip_words],
        "source": "gemini" if getattr(candidate, "gemini_reason", "") else "heuristic",
    }


def rebuild_subtitles_for_segments(
    segments: list[dict], words: list[Word]
) -> tuple[list[dict], list[Word]]:
    """
    Menyusun ulang subtitle setelah pengguna mengubah batas atau menambah segmen.

    Waktu dikembalikan dalam linimasa KLIP (dimulai dari 0), bukan linimasa
    video asli, karena itulah yang dilihat pemutar dan yang dipakai saat render.
    """
    based = rebase_segments(segments)
    all_lines: list[dict] = []
    all_words: list[Word] = []

    for seg in based:
        seg_words = slice_words(words, seg["start"], seg["end"])
        shift = seg["offset"] - seg["start"]
        shifted: list[Word] = [
            {"w": w["w"],
             "s": round(max(0.0, w["s"] + shift), 3),
             "e": round(max(0.0, w["e"] + shift), 3),
             # Label penutur ikut berpindah bersama katanya, supaya warna per
             # orang tetap benar setelah batas klip digeser atau potongan dari
             # menit lain disambungkan.
             **({"sp": w["sp"]} if "sp" in w else {})}
            for w in seg_words
        ]
        all_words.extend(shifted)
        all_lines.extend(words_to_caption_lines(shifted))

    return all_lines, all_words


# --- Judul dan tagar tanpa mengarang ------------------------------------------

# Kata yang tidak pernah jadi tagar. Bukan daftar lengkap bahasa Indonesia —
# hanya kata paling sering yang, kalau ikut, membuat tiap klip bertagar #yang.
_STOP = {
    "yang", "untuk", "dengan", "adalah", "tidak", "sudah", "akan", "bisa",
    "kalau", "karena", "tapi", "juga", "saya", "kamu", "kita", "mereka", "gue",
    "lu", "lo", "aku", "dia", "ini", "itu", "ada", "dari", "pada", "dalam",
    "atau", "jadi", "kayak", "gitu", "banget", "aja", "sih", "nya", "dong",
    "nggak", "enggak", "gak", "iya", "oke", "terus", "sama", "buat", "punya",
    "orang", "waktu", "tahun", "kalo", "emang", "memang", "harus", "lebih",
    "masih", "bikin", "pernah", "kenapa", "gimana", "apa", "siapa", "kapan",
    "mau", "udah", "bilang", "banyak", "sekali", "sangat", "salah", "benar",
    # Ditambahkan setelah melihat tagar yang benar-benar keluar: semuanya kata
    # sambung atau kata umum yang lolos hanya karena sering diucapkan, dan
    # sebagai tagar tidak menggambarkan apa pun. "#selain", "#awal", "#luar"
    # tidak membawa satu penonton pun.
    "selain", "awal", "akhir", "luar", "dalam", "habis", "langsung", "sekarang",
    "apalagi", "sebelum", "sesudah", "setelah", "sampai", "ketika", "begitu",
    "bagus", "gede", "kecil", "cuma", "hanya", "pertama", "kedua", "lagi",
    "sendiri", "semua", "setiap", "antara", "tentang", "menurut", "seperti",
    "misalnya", "contohnya", "intinya", "pokoknya", "soalnya", "makanya",
    "kemarin", "besok", "nanti", "tadi", "banget", "sekitar", "kurang",
    "cerita", "ngomong", "ngomongin", "bicara", "kelihatan", "ngelihat",
}

TITLE_MAX = 70


def _sentences(text: str) -> list[str]:
    """Memecah teks klip jadi kalimat, tanpa membuang apa pun."""
    import re
    parts = re.split(r"(?<=[.?!])\s+", " ".join((text or "").split()))
    return [p.strip() for p in parts if len(p.strip()) >= 12]


def suggest_title(text: str, fallback: str = "") -> str:
    """
    Judul dari kalimat TERBAIK di klip itu, bukan sekadar kalimat pertamanya.

    Tetap kutipan nyata — sistem ini tidak boleh menuliskan kalimat yang tidak
    pernah diucapkan. Yang berubah hanya kalimat mana yang dipilih: kalimat
    pembuka sering berupa sambungan dari kalimat sebelumnya ("Jadi aku yang
    paling gede…"), sementara beberapa detik kemudian ada kalimat yang
    benar-benar menyatakan isi klipnya.

    Dipilih dengan ukuran yang sama yang dipakai mesin klip untuk menilai
    pembuka: pertanyaan, kata pembuka yang menjanjikan sesuatu, angka, dan
    panjang yang pas untuk judul.
    """
    import re

    sents = _sentences(text)
    if not sents:
        body = " ".join((text or "").split())
        return (body or fallback)[:TITLE_MAX].strip()

    def score(sentence: str, index: int) -> float:
        low = sentence.lower()
        v = 0.0
        if "?" in sentence:
            v += 0.9
        for word in ("kenapa", "ternyata", "sebenarnya", "rahasia", "jangan",
                     "faktanya", "ini yang", "banyak orang", "nggak nyangka",
                     "gue kaget", "yang bikin", "salah besar", "paling"):
            if word in low:
                v += 0.7
                break
        if re.search(r"\b\d+\b", sentence):
            v += 0.35
        n = len(sentence)
        # Panjang yang pas: cukup untuk berdiri sendiri, cukup pendek untuk
        # tidak terpotong di daftar YouTube.
        #
        # Kalimat sangat pendek dihukum keras, bukan sekadar diberi nilai kecil.
        # Tanpa itu, "Aduh, kenapa?" menang atas kalimat yang sebenarnya
        # menyatakan isi klip — dua bonus kecil (tanda tanya dan kata "kenapa")
        # cukup mengalahkan selisih nilai panjangnya. Judul yang tidak memberi
        # tahu apa pun tentang isinya bukan judul.
        if n < 20:
            v -= 1.3
        elif n < 30:
            v += 0.45
        elif n <= TITLE_MAX:
            v += 1.0
        else:
            v += 0.25
        # Kalimat awal sedikit diunggulkan: klip yang baik biasanya memang
        # dibuka oleh kalimat yang membuatnya baik.
        v += max(0.0, 0.5 - index * 0.12)
        # Sambungan dari kalimat sebelumnya jarang berdiri sendiri sebagai judul.
        if re.match(r"^(jadi|terus|nah|dan|tapi|karena|yang|atau|kalau)\b", low):
            v -= 0.45
        return v

    best = max(range(len(sents)), key=lambda i: score(sents[i], i))
    body = sents[best].rstrip(".")
    if len(body) > TITLE_MAX:
        cut = body[:TITLE_MAX].rsplit(" ", 1)[0]
        body = (cut or body[:TITLE_MAX]).rstrip(" ,;:-") + "…"
    return body.strip()


def normalize_hashtags(tags) -> list[str]:
    """Selalu berpagar, selalu tanpa spasi, tanpa duplikat."""
    import re
    out: list[str] = []
    for t in tags or []:
        if not isinstance(t, str):
            continue
        clean = re.sub(r"[^0-9A-Za-zÀ-ÿ_]", "", t)
        if len(clean) < 2:
            continue
        tag = f"#{clean}"
        if tag.lower() not in {x.lower() for x in out}:
            out.append(tag)
    return out[:12]


def suggest_hashtags(text: str, video_title: str = "", channel: str = "",
                     limit: int = 8, duration: float = 0.0) -> list[str]:
    """
    Tagar dari kata yang BENAR-BENAR diucapkan di klip itu.

    Diambil dari kata paling sering di klipnya sendiri, bukan dari daftar tagar
    populer. Tagar yang tidak nyambung dengan isinya tidak membantu video naik —
    ia hanya membuat klip terlihat seperti spam, dan itu justru yang dihukum.

    Nama kanal ikut karena ia satu-satunya tagar yang pasti relevan dan pasti
    dicari orang.
    """
    import re
    from collections import Counter

    def slug(word: str) -> str:
        return re.sub(r"[^a-z0-9]", "", word.lower())

    counts: Counter = Counter()
    for w in re.findall(r"[A-Za-zÀ-ÿ']{5,}", text or ""):
        s = slug(w)
        # Lima huruf, bukan empat. Kata pendek dalam bahasa Indonesia hampir
        # selalu kata fungsi, dan menyaringnya lewat daftar henti saja tidak
        # pernah selesai.
        if len(s) >= 5 and s not in _STOP:
            counts[s] += 1

    tags: list[str] = []

    # Penanda format. Ini FAKTA tentang berkasnya, bukan tagar populer yang
    # ditempelkan asal: hasil render memang tegak, dan memang sependek ini.
    # YouTube memakai #shorts untuk menempatkan video di rak Shorts, jadi
    # mencantumkannya pada klip yang memenuhi syarat benar-benar menambah
    # tempat ia bisa muncul — sementara tagar yang tidak nyambung dengan isinya
    # justru menurunkan video.
    if 0 < duration <= 180:
        tags.append("#shorts")

    ch = slug(channel)
    if 3 <= len(ch) <= 22:
        tags.append(f"#{ch}")

    # Kata dari judul videonya sendiri lebih menggambarkan topik daripada kata
    # yang sering diucapkan di tengah percakapan — nama tamu, nama acara.
    from_title = 0
    for w in re.findall(r"[A-Za-zÀ-ÿ']{4,}", video_title or ""):
        s = slug(w)
        if len(s) >= 4 and s not in _STOP and f"#{s}" not in tags:
            tags.append(f"#{s}")
            from_title += 1
        if from_title >= 3:
            break

    for word, n in counts.most_common(30):
        # Sekali sebut bukan topik. Kata yang benar-benar jadi bahasan klip
        # muncul berkali-kali di dalamnya.
        if n < 3:
            break
        if f"#{word}" not in tags:
            tags.append(f"#{word}")
        if len(tags) >= limit:
            break

    return tags[:limit]
