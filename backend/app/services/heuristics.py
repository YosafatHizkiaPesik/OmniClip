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
# --- Leksikon hook bahasa Indonesia -------------------------------------------
#
# Daftar ini pernah berisi 17 pola, dan pada transkrip sungguhan ia hanya kena
# di 3-6% kalimat: 75 dari 1498, 96 dari 1605, 43 dari 1284. Dengan bobot
# terbesar di seluruh rumus, artinya komponen yang paling menentukan justru
# hampir tidak pernah bersuara — nilai rata-ratanya 0,057 dari 1,0, dan
# praktis semua kandidat diperingkat oleh komponen lain.
#
# Diperlebar di sini, dan yang lebih penting: `_hook_score` tidak lagi
# bergantung pada leksikon SAJA. Dua sinyal baru di sana rapat — berlaku pada
# setiap klip, bukan pada 4% — yaitu lonjakan energi suara di pembuka dan denda
# untuk pembuka yang jelas menyambung kalimat sebelumnya.
HOOK_PATTERNS = [
    # Pertanyaan
    (r"\bkenapa\b|\bngapain\b", "hook_question"),
    (r"\bmengapa\b", "hook_question"),
    (r"\bgimana\b|\bbagaimana\b|\bgmn\b", "hook_question"),
    (r"\bapa sih\b|\bapa itu\b|\bapakah\b", "hook_question"),
    (r"\bsiapa\b.{0,15}\byang\b", "hook_question"),
    (r"\bemang\b|\bemangnya\b|\bmemangnya\b", "hook_question"),
    # Pembukaan fakta
    (r"\bternyata\b", "hook_reveal"),
    (r"\bsebenarnya\b|\bsebenernya\b|\bsebetulnya\b", "hook_reveal"),
    (r"\bfaktanya\b|\bkenyataannya\b|\brealitanya\b", "hook_reveal"),
    (r"\brahasia\b|\bdiam-diam\b|\btersembunyi\b", "hook_reveal"),
    (r"\bbaru tahu\b|\bbaru sadar\b|\bbaru ngeh\b", "hook_reveal"),
    (r"\bjujur\b.{0,12}\b(aja|saja|ya|nih)\b|\bterus terang\b", "hook_reveal"),
    (r"\bpertama kali\b|\bbelum pernah\b|\bgak pernah cerita\b", "hook_reveal"),
    # Peringatan
    (r"\bjangan pernah\b|\bjangan sampai\b|\bjangan sekali\b", "hook_warning"),
    (r"\bsalah besar\b|\bsalah kaprah\b|\bkeliru\b", "hook_warning"),
    (r"\bhati-hati\b|\bawas\b|\bwaspada\b", "hook_warning"),
    (r"\bbahaya\b|\bberisiko\b|\bfatal\b", "hook_warning"),
    (r"\bmasalahnya\b|\bcelakanya\b|\bparahnya\b", "hook_warning"),
    # Reaksi kaget
    (r"\bgue kaget\b|\bsaya kaget\b|\bkaget banget\b", "hook_surprise"),
    (r"\bnggak nyangka\b|\bgak nyangka\b|\btidak menyangka\b", "hook_surprise"),
    (r"\bparah banget\b|\bgila sih\b|\bedan\b|\bngeri\b", "hook_surprise"),
    (r"\bastaga\b|\bya ampun\b|\bbusetd?\b|\banjir\b", "hook_surprise"),
    (r"\bsumpah\b|\bdemi apa\b|\bserius\b\?*", "hook_surprise"),
    # Menunjuk inti
    (r"\byang bikin\b|\bini yang\b|\byang paling\b", "hook_pointer"),
    (r"\bbanyak orang\b|\bkebanyakan orang\b|\borang-orang\b", "hook_pointer"),
    (r"\bcoba bayangin\b|\bbayangkan\b|\bcoba pikir\b", "hook_pointer"),
    (r"\bintinya\b|\bpoinnya\b|\bkuncinya\b", "hook_pointer"),
    (r"\bmakanya\b|\bitulah kenapa\b|\bkarena itu\b", "hook_pointer"),
    (r"\bdengerin\b|\bdengarkan\b|\bcatet\b|\bingat ya\b", "hook_pointer"),
    # Daftar & angka
    (r"\bpertama\b.{0,20}\bkedua\b", "hook_list"),
    (r"^\s*(ada\s+)?\d+\s+(hal|cara|alasan|tips|langkah|poin|tanda)", "hook_list"),
    (r"\bada (tiga|empat|lima|dua) (hal|cara|alasan|poin)\b", "hook_list"),
    # Cerita
    (r"\bjadi ceritanya\b|\bwaktu itu\b|\bsuatu hari\b", "hook_story"),
    (r"\bpernah nggak\b|\bpernah gak\b|\bpernah kan\b", "hook_story"),
]
HOOK_RE = [(re.compile(p, re.I), key) for p, key in HOOK_PATTERNS]

# Kata yang membuka SAMBUNGAN, bukan gagasan baru. Klip yang dimulai di sini
# menjatuhkan penontonnya di tengah pembicaraan — alasan paling umum sebuah
# klip terasa seperti potongan, dan sinyal yang jauh lebih rapat daripada
# leksikon hook mana pun.
PENYAMBUNG = {
    "jadi", "terus", "trus", "lalu", "kemudian", "dan", "tapi", "tetapi",
    "makanya", "soalnya", "pokoknya", "nah", "ya", "yang", "karena", "kalau",
    "kalo", "sedangkan", "sementara", "padahal", "apalagi", "selain",
    "makanya", "berarti", "artinya", "oh", "iya", "hmm", "eh", "he",
}

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
    Pengali untuk pembuka yang jelas bukan awal sebuah gagasan.

    Tiga sinyal, diurutkan dari yang paling kuat:

      - kalimat dibuka kata penyambung ("jadi", "terus", "tapi", "nah") ->
        hampir pasti lanjutan, jadi klip akan terdengar seperti masuk di tengah
        pembicaraan. Ini sinyal yang paling SERING kena — pada transkrip
        percakapan, seperempat kalimat dibuka begini — dan karenanya jauh lebih
        berguna daripada leksikon hook yang cuma kena di beberapa persen;
      - kalimat dimulai huruf kecil -> tanda yang sama, tapi hanya ada bila
        sumber transkripnya memakai huruf besar sama sekali;
      - kalimat sangat pendek ("Hah?", "Enggaklah.") -> potongan reaksi, bukan
        pembuka yang bisa berdiri sendiri.
    """
    text = first["text"].strip()
    if not text:
        return 0.2

    kata = text.split()
    penalty = 1.0
    head = kata[0]
    if head.lower().strip(".,!?;:\"'") in PENYAMBUNG:
        penalty *= 0.45
    if head[:1].islower():
        penalty *= 0.55
    if len(kata) <= 2:
        penalty *= 0.4
    elif len(kata) <= 4:
        penalty *= 0.7
    return penalty


def _lonjakan_energi(energy_z: list[float], start: float) -> float:
    """
    Seberapa naik suara si pembicara tepat di pembuka klip, dalam satuan z.

    Ini sinyal pembuka yang RAPAT: ia punya nilai untuk setiap kandidat, bukan
    untuk beberapa persen yang kebetulan memakai kata kunci. Orang menaikkan
    suara saat memulai sesuatu yang dianggapnya penting, dan naiknya terjadi
    tepat di perbatasan — persis titik yang sedang dinilai.
    """
    if not energy_z:
        return 0.0
    t = int(start)
    sesudah = energy_z[t:t + 3]
    sebelum = energy_z[max(0, t - 4):t]
    if not sesudah or not sebelum:
        return 0.0
    naik = (sum(sesudah) / len(sesudah)) - (sum(sebelum) / len(sebelum))
    return max(0.0, min(1.0, naik / 1.2))


def _hook_score(sentences: list[Sentence], i: int, j: int,
                silence_before: bool,
                energy_z: Optional[list[float]] = None) -> tuple[float, list[str]]:
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

    lonjak = _lonjakan_energi(energy_z or [], start_t)
    if lonjak > 0:
        score = min(1.0, score + 0.35 * lonjak)
        if lonjak > 0.5:
            keys.append("energy_lift")

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



# Seberapa jauh sebuah kata boleh mencari kembarannya saat kohesi dihitung.
# TETAP, dan itulah intinya: kohesi yang diukur di dalam jendela klip akan
# selalu naik bersama panjang jendela — terukur 0,53 pada klip 20 detik menjadi
# 0,99 pada klip 220 detik — sehingga ia bukan mengukur keterpaduan melainkan
# mengukur durasi dengan nama lain. Diukur di dalam lingkungan selebar tetap,
# angkanya berarti hal yang sama pada klip sepanjang apa pun.
KOHESI_JENDELA = 20.0


def _kohesi_kalimat(sentences: list[Sentence],
                    token_kalimat: list[list[str]]) -> list[float]:
    """
    Untuk tiap kalimat: berapa bagian kata isinya yang terulang di sekitarnya.

    Pembicaraan yang benar-benar membahas sesuatu mengulang istilahnya dalam
    hitungan detik. Deretan kata yang masing-masing cuma disebut sekali adalah
    tanda pembicaraan yang melompat-lompat, dan klip yang dipotong dari situ
    tidak akan terasa membahas apa pun.
    """
    from bisect import bisect_left, bisect_right

    waktu: dict[str, list[float]] = {}
    for k, s in enumerate(sentences):
        for w in token_kalimat[k]:
            waktu.setdefault(w, []).append(s["s"])
    for daftar in waktu.values():
        daftar.sort()

    keluar: list[float] = []
    for k, s in enumerate(sentences):
        toks = token_kalimat[k]
        if not toks:
            keluar.append(0.0)
            continue
        t = s["s"]
        kena = 0
        for w in toks:
            daftar = waktu[w]
            a = bisect_left(daftar, t - KOHESI_JENDELA)
            b = bisect_right(daftar, t + KOHESI_JENDELA)
            # >1 karena kemunculan kata ini sendiri selalu ikut terhitung.
            if b - a > 1:
                kena += 1
        keluar.append(kena / len(toks))
    return keluar


# --- Batas topik --------------------------------------------------------------
#
# Inilah yang benar-benar memutuskan di mana sebuah klip berhenti.
#
# Tanpa ini, semua komponen lain punya cacat yang sama: apa pun yang mengukur
# "apakah jendela ini memuat sesuatu" akan naik ketika jendelanya diperpanjang.
# Terukur pada podcast satu jam, nilai rata-rata per panjang jendela naik
# monoton dari 0,52 (20 detik) ke 0,63 (240 detik) — jadi jendela terpanjang
# hampir selalu menang, dan menghapus preset panjang cuma memindahkan batas
# kakunya, tidak menghilangkannya.
#
# Kekuatan batas topik tidak punya cacat itu. Ia milik SATU titik dalam
# transkrip, bukan milik sebuah rentang, jadi nilainya sama saja apakah jendela
# yang berakhir di situ panjangnya dua belas detik atau tiga menit. Itu membuat
# skor akhirnya benar-benar ditentukan oleh DI MANA klip dimulai dan berhenti,
# bukan oleh seberapa banyak yang dimuatnya.
#
# Caranya adalah TextTiling: bandingkan kosakata sebelum dan sesudah tiap
# perbatasan kalimat. Di tengah sebuah pembahasan, keduanya memakai kata yang
# sama dan kemiripannya tinggi. Di perbatasan topik, keduanya berbeda dan
# kemiripannya anjlok. Yang dipakai bukan kemiripan mentah melainkan KEDALAMAN
# lembahnya — seberapa turun dibanding puncak terdekat di kiri dan kanan —
# supaya percakapan yang kosakatanya memang selalu beragam tidak terbaca sebagai
# pergantian topik di setiap kalimat.
BATAS_JENDELA = 30.0


def _kekuatan_batas(sentences: list[Sentence],
                    token_kalimat: list[list[str]]) -> list[float]:
    """
    Untuk tiap perbatasan kalimat k (sebelum kalimat ke-k): 0..1.

    Panjangnya n+1: indeks 0 adalah awal transkrip dan indeks n akhirnya, dan
    keduanya batas sejati — sebuah klip yang dimulai di detik nol tidak sedang
    memotong apa pun.
    """
    import math
    from collections import Counter

    n = len(sentences)
    if n < 3:
        return [1.0] * (n + 1)

    waktu = [s["s"] for s in sentences]
    kemiripan: list[float] = []
    for k in range(n + 1):
        t = waktu[k] if k < n else sentences[-1]["e"]
        kiri: Counter = Counter()
        kanan: Counter = Counter()
        a = k - 1
        while a >= 0 and waktu[a] >= t - BATAS_JENDELA:
            kiri.update(token_kalimat[a])
            a -= 1
        b = k
        while b < n and waktu[b] <= t + BATAS_JENDELA:
            kanan.update(token_kalimat[b])
            b += 1
        if not kiri or not kanan:
            kemiripan.append(0.0)       # tepi transkrip = batas sejati
            continue
        bersama = set(kiri) & set(kanan)
        atas = sum(kiri[w] * kanan[w] for w in bersama)
        bawah = (math.sqrt(sum(v * v for v in kiri.values()))
                 * math.sqrt(sum(v * v for v in kanan.values())))
        kemiripan.append(atas / bawah if bawah else 0.0)

    # Kedalaman lembah: (puncak kiri - nilai) + (puncak kanan - nilai).
    dalam: list[float] = []
    for k in range(n + 1):
        v = kemiripan[k]
        kiri_puncak = v
        i = k - 1
        while i >= 0 and kemiripan[i] >= kiri_puncak:
            kiri_puncak = kemiripan[i]
            i -= 1
        kanan_puncak = v
        i = k + 1
        while i <= n and kemiripan[i] >= kanan_puncak:
            kanan_puncak = kemiripan[i]
            i += 1
        dalam.append((kiri_puncak - v) + (kanan_puncak - v))

    # Dipatok pada persentil 90, BUKAN pada nilai tertinggi. Satu perbatasan
    # ekstrem saja — pergantian segmen dengan jingle di tengahnya — cukup untuk
    # menekan semua batas lain menjadi sepersepuluh, dan komponen ini lalu
    # berhenti membedakan apa pun: terukur, rata-ratanya 0,096 dari 1,0.
    urut = sorted(dalam)
    acuan = urut[int(0.90 * (len(urut) - 1))] or (max(dalam) or 1.0)
    return [min(1.0, d / acuan) for d in dalam]

# --- Panjang klip: ditentukan isinya, bukan oleh preset ------------------------
#
# Dulu di sini ada tiga preset — pendek 15-40 dtk, sedang 20-60, panjang 35-110 —
# dan pengguna harus memilih salah satunya SEBELUM videonya dianalisis. Itu
# keliru di dua arah sekaligus. Ke bawah: sebuah pertanyaan yang dijawab dalam
# dua belas detik dipaksa menyeret dua puluh detik basa-basi supaya memenuhi
# batas minimum. Ke atas: sebuah cerita yang butuh delapan puluh detik dipotong
# di detik ke-60, jadi pertanyaannya masuk dan jawabannya tidak — persis keluhan
# "klip tidak menangkap konteks secara penuh".
#
# Sekarang tidak ada target panjang sama sekali. Yang ada hanya lantai dan
# langit-langit praktis, dan keduanya BUKAN gaya:
#
#   - lantai 10 detik: di bawah itu tidak ada ruang untuk pembuka dan penutup
#     sekaligus, jadi apa pun yang lolos akan terasa seperti potongan.
#   - langit-langit 240 detik: bukan karena empat menit itu panjang yang benar,
#     melainkan karena daftar kandidat harus berhenti tumbuh di suatu titik.
#
# Di antara keduanya, panjang klip adalah HASIL, bukan masukan. Yang
# menentukannya adalah `tuntas` — apakah kata-kata khas di pembuka klip muncul
# lagi di sisanya. Klip yang cuma melempar pertanyaan lalu berhenti tidak pernah
# memenuhinya; klip yang kembali ke pokoknya memenuhi. Itulah yang membuat klip
# memanjang saat isinya memang menuntut, dan berhenti saat tidak.
DURASI_MIN = 10.0
DURASI_MAKS = 240.0

# Dalam sebuah pembuka, sekian detik pertama itulah yang dianggap "janji" klip.
AWALAN_DETIK = 12.0

# Bagian janji yang sudah dianggap terjawab. Di atas ini `tuntas` tidak naik
# lagi, jadi memanjangkan klip tidak lagi membeli apa pun — dan digabung dengan
# `_sependek_mungkin`, klip berhenti persis di titik janjinya terpenuhi.
#
# Kedua angka di bawah ini dipilih dari sapuan pada lima transkrip nyata
# (podcast 23-74 menit, 60 klip per baris). Yang dilihat adalah SEBARAN
# panjangnya, bukan rata-ratanya, karena yang diminta memang keragaman:
#
#   toleransi  cukup   <30dtk  30-60  60-120  >120   median
#      0,02     0,6       7      7      24     22     102 dtk
#      0,04     0,6      13     15      22     10      66
#      0,04     0,4      15     20      18      7      48
#      0,06     0,4      22     21      12      5      35
#      0,09     0,4      40     13       6      1      22
#
# 0,02 menumpuk di atas dua menit — itu cuma memindahkan batas kaku yang lama.
# 0,09 meruntuhkan semuanya jadi klip pendek, dan momen yang memang butuh dua
# menit tidak pernah muncul. 0,04/0,4 adalah satu-satunya baris yang mengisi
# keempat ember dengan pantas.
TUNTAS_CUKUP = 0.4

# Selisih skor yang dianggap tidak berarti saat memilih panjang. Lihat
# `_sependek_mungkin`.
TOLERANSI_PANJANG = 0.04

WEIGHTS = {
    "hook": 0.22,
    "completeness": 0.14,
    "energy": 0.12,
    "density": 0.06,
    "salience": 0.12,
    "koherensi": 0.12,
    "tuntas": 0.10,
    "batas": 0.12,
}

REASON_LABELS.update({
    "payoff": "Janji di pembuka benar-benar dijawab",
    "one_topic": "Fokus pada satu pokok pembicaraan",
    "energy_lift": "Suara naik tepat di pembuka",
    "hook_story": "Dibuka sebagai cerita",
    "topic_edge": "Mulai dan berhenti di pergantian topik",
})


def _iou(a: "Candidate", b: "Candidate") -> float:
    lo = max(a.start, b.start)
    hi = min(a.end, b.end)
    inter = max(0.0, hi - lo)
    union = (a.end - a.start) + (b.end - b.start) - inter
    return inter / union if union > 0 else 0.0


def _sependek_mungkin(kandidat: list["Candidate"]) -> Optional["Candidate"]:
    """
    Dari semua jendela berawal sama, ambil yang TERPENDEK di antara yang terbaik.

    Ini pengganti `length_fit` yang lama, dan bekerja tanpa satu pun angka gaya.
    Beberapa komponen skor tetap naik perlahan seiring jendela memanjang — janji
    pembukanya makin mungkin terjawab — jadi tanpa rem, setiap klip akan tumbuh
    sampai langit-langit dan kita cuma mengganti satu batas kaku dengan batas
    kaku yang lain.

    Remnya: selisih skor di bawah `TOLERANSI_PANJANG` dianggap tidak berarti,
    dan di antara jendela-jendela yang sama baiknya itu, yang terpendek menang.
    Artinya klip hanya memanjang bila panjangnya benar-benar MEMBELI sesuatu.
    """
    if not kandidat:
        return None
    terbaik = max(c.score for c in kandidat)
    layak = [c for c in kandidat if c.score >= terbaik - TOLERANSI_PANJANG]
    return min(layak, key=lambda c: c.duration)


# --- Titik masuk utama --------------------------------------------------------
def generate_candidates(
    sentences: list[Sentence],
    words: list,
    energy_z: Optional[list[float]] = None,
    *,
    duration: float,
    max_out: int = 10,
    dur_min: float = DURASI_MIN,
    dur_max: float = DURASI_MAKS,
) -> list[Candidate]:
    """
    Menyusun kandidat klip dari transkrip, dengan panjang yang bebas.

    Setiap jendela WAJIB dimulai di awal kalimat dan berakhir di akhir kalimat.
    Aturan itu sendirian sudah menghilangkan artefak terburuk sistem lama:
    klip yang mulai dan berhenti di tengah kata.

    Perhitungannya INKREMENTAL. Versi sebelumnya membangun ulang seluruh teks
    jendela dan men-tokenisasinya untuk setiap pasangan (i, j); dengan rentang
    20-60 detik itu masih tertahan, tapi dengan 10-240 detik jumlah jendelanya
    berlipat dan biaya O(n^2) teksnya jadi tak masuk akal. Di sini setiap
    komponen diperbarui saat satu kalimat ditambahkan, bukan dihitung dari nol.
    """
    if not sentences:
        return []

    energy_z = energy_z or []
    tf_idf = _build_tfidf(sentences)
    n = len(sentences)

    # Pra-hitung sekali, dipakai ribuan kali.
    token_kalimat = [_tokenize(s["text"]) for s in sentences]
    kohesi = _kohesi_kalimat(sentences, token_kalimat)
    batas = _kekuatan_batas(sentences, token_kalimat)
    kata_kumulatif = [0] * (n + 1)
    for k, s in enumerate(sentences):
        kata_kumulatif[k + 1] = kata_kumulatif[k] + max(0, s["wi"][1] - s["wi"][0])

    semua: list[Candidate] = []

    for i in range(n):
        start = sentences[i]["s"]
        silence_before = (i == 0) or (start - sentences[i - 1]["e"]) >= 0.8

        # Hook hanya melihat ~3 detik pertama, jadi ia milik `i` — dihitung
        # sekali, bukan sekali per jendela.
        batas_hook = i
        while batas_hook < n and sentences[batas_hook]["s"] < start + 3.0:
            batas_hook += 1
        hook, hook_keys = _hook_score(sentences, i, max(batas_hook, i + 1),
                                      silence_before, energy_z)

        # "Janji" klip: kata khas yang diucapkan di awalan. Yang diukur nanti
        # adalah berapa banyak di antaranya kembali muncul sesudah itu.
        janji: set[str] = set()
        k = i
        while k < n and sentences[k]["s"] < start + AWALAN_DETIK:
            janji.update(token_kalimat[k])
            k += 1
        akhir_awalan = max(k, i + 1)

        # Hanya kata PALING khas di awalan yang dihitung sebagai janji.
        #
        # Semula seluruh kata isi di dua belas detik pertama ikut — sekitar dua
        # puluh lima kata — dan menuntut 60% di antaranya kembali muncul adalah
        # tuntutan yang tidak pernah terpenuhi: terukur, `tuntas` baru mencapai
        # 0,82 pada klip empat menit dan masih naik. Akibatnya komponen ini
        # berhenti mengukur "janjinya terjawab" dan berubah jadi pengukur durasi,
        # dan setiap klip tertarik ke langit-langit.
        #
        # Lima kata paling khas adalah pokok pembicaraannya. Kembalinya kelima
        # kata itu adalah tanda yang benar bahwa klip sudah membahas apa yang
        # dijanjikannya, dan ia jenuh di panjang yang masuk akal.
        janji = set(sorted((w for w in janji if tf_idf.get(w, 0.0) > 0),
                           key=lambda w: tf_idf[w], reverse=True)[:5])

        # Keadaan berjalan untuk jendela [i, j).
        jumlah_tfidf = 0.0
        jumlah_isi = 0
        jumlah_kohesi = 0.0
        janji_kembali: set[str] = set()
        per_awal: list[Candidate] = []

        for j in range(i + 1, n + 1):
            # Serap kalimat ke-(j-1) ke dalam keadaan berjalan.
            jumlah_kohesi += kohesi[j - 1]
            for w in token_kalimat[j - 1]:
                jumlah_isi += 1
                jumlah_tfidf += tf_idf.get(w, 0.0)
                if (j - 1) >= akhir_awalan and w in janji:
                    janji_kembali.add(w)

            end = sentences[j - 1]["e"]
            dur = end - start
            if dur < dur_min:
                continue
            if dur > dur_max:
                break

            gap_after = (sentences[j]["s"] - end) if j < n else 999.0
            comp, comp_keys = _completeness_score(sentences, j, gap_after)
            ener, ener_keys = _energy_score(energy_z, start, end)
            dens, dens_keys = _density_score(
                kata_kumulatif[j] - kata_kumulatif[i], dur)

            # Salience sebagai RATA-RATA, bukan jumlah lima teratas.
            #
            # Jumlah lima teratas naik bersama panjang jendela: dengan tujuh
            # ratus kata, kelima nilai tf-idf tertinggi di seluruh video pasti
            # ketemu; dengan tiga puluh kata, tidak. Dinormalisasi ke maksimum
            # global, hasilnya 0,91 pada klip pendek dan 0,97 pada klip panjang
            # — rentang yang terlalu sempit untuk membedakan apa pun, dan
            # arahnya pun cuma mengulang durasi. Rata-rata per kata isi tidak
            # punya kecenderungan itu.
            sal = (jumlah_tfidf / jumlah_isi) if jumlah_isi else 0.0
            koher = jumlah_kohesi / (j - i)
            tuntas = (len(janji_kembali) / len(janji)) if janji else 0.0

            # Batas topik di KEDUA ujung. Klip yang dimulai di pergantian
            # topik dan berhenti di pergantian berikutnya adalah satu
            # pembahasan utuh — dan itu, bukan angka detik mana pun, yang
            # menentukan panjangnya.
            tepi = 0.5 * (batas[i] + batas[j])

            kunci = list(hook_keys) + comp_keys + ener_keys + dens_keys
            if tepi > 0.35:
                kunci.append("topic_edge")
            # Ambang LABEL, bukan ambang skor. Sengaja lebih ketat daripada
            # titik jenuh komponennya: pada sepuluh klip terpilih, `koherensi`
            # jenuh di 1,0 untuk sembilan di antaranya dan `salience` di atas
            # 0,9 untuk sepuluh-sepuluhnya — label yang menyala di semua klip
            # tidak memberi tahu apa pun tentang klip mana yang berbeda.
            if tuntas >= TUNTAS_CUKUP:
                kunci.append("payoff")
            if koher > 0.75:
                kunci.append("one_topic")

            per_awal.append(Candidate(
                start=start, end=end, score=0.0,
                breakdown={
                    "hook": hook,
                    "completeness": comp,
                    "energy": ener,
                    "density": dens,
                    "salience": sal,          # diskalakan setelah loop
                    "koherensi": min(1.0, koher / 0.6),
                    "tuntas": min(1.0, tuntas / TUNTAS_CUKUP),
                    "batas": tepi,
                },
                sentence_span=(i, j),
                reason_keys=kunci,
            ))

        semua.extend(per_awal)

    if not semua:
        return []

    # Skala salience dipatok pada persentil 95, bukan pada nilai tertinggi.
    # Satu jendela menyimpang saja cukup untuk menekan semua yang lain ke
    # bawah kalau maksimum yang dipakai.
    urut = sorted(c.breakdown["salience"] for c in semua)
    acuan = urut[int(0.95 * (len(urut) - 1))] or 1.0

    for c in semua:
        c.breakdown["salience"] = min(1.0, c.breakdown["salience"] / acuan)
        if c.breakdown["salience"] > 0.97 and "topic_focus" not in c.reason_keys:
            c.reason_keys.append("topic_focus")
        c.score = sum(WEIGHTS[k] * c.breakdown[k] for k in WEIGHTS)

    # Satu wakil per titik awal: yang terpendek di antara yang sama baiknya.
    # Tanpa ini, NMS di bawah akan menerima jendela terpanjang lebih dulu
    # (skornya sedikit lebih tinggi) dan seluruh klip berakhir di dekat
    # langit-langit — batas kaku yang sama, cuma dengan nama lain.
    per_titik: dict[int, list[Candidate]] = {}
    for c in semua:
        per_titik.setdefault(c.sentence_span[0], []).append(c)
    wakil = [w for w in (_sependek_mungkin(v) for v in per_titik.values()) if w]

    # Non-maximum suppression: jangan tawarkan sepuluh varian dari momen sama.
    wakil.sort(key=lambda c: c.score, reverse=True)
    kept: list[Candidate] = []
    for cand in wakil:
        if any(_iou(cand, k) > 0.30 or abs(cand.start - k.start) < 8.0 for k in kept):
            continue
        a, b = cand.sentence_span
        cand.hook_text = make_hook_text(sentences, a, b)
        cand.text = " ".join(s["text"] for s in sentences[a:b])
        cand.score = round(cand.score, 4)
        cand.breakdown = {k: round(v, 4) for k, v in cand.breakdown.items()}
        kept.append(cand)
        if len(kept) >= max_out:
            break

    kept.sort(key=lambda c: c.start)
    return kept


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
                      duration: float, *,
                      max_duration: float = DURASI_MAKS) -> list[Candidate]:
    """
    Penjaga terakhir yang dilewati SEMUA mesin (heuristik maupun Gemini).

    Membuang klip di luar rentang video, terlalu pendek atau terlalu panjang,
    dan menarik batasnya ke batas kalimat terdekat.
    """
    out: list[Candidate] = []
    for c in candidates:
        c.start = max(0.0, min(c.start, duration))
        c.end = max(0.0, min(c.end, duration))
        if c.end - c.start < DURASI_MIN or c.end - c.start > max_duration:
            continue

        # Tarik ke batas kalimat terdekat dalam 1,5 detik.
        for attr, field_name in (("start", "s"), ("end", "e")):
            value = getattr(c, attr)
            nearest = min(sentences, key=lambda s: abs(s[field_name] - value), default=None)
            if nearest is not None and abs(nearest[field_name] - value) <= 1.5:
                setattr(c, attr, nearest[field_name])

        if c.end - c.start >= DURASI_MIN:
            out.append(c)

    out.sort(key=lambda c: c.score, reverse=True)
    deduped: list[Candidate] = []
    for c in out:
        if any(_iou(c, k) > 0.6 for k in deduped):
            continue
        deduped.append(c)
    deduped.sort(key=lambda c: c.start)
    return deduped
