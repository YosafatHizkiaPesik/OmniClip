"""
Sutradara bingkai yang MENONTON klipnya.

Tiga lapis:

1. Bukti lokal (`momen.cari_momen`): tawa/sorak/teriak yang didengar YAMNet,
   lonjakan suara, mulut bergerak bersamaan, perpindahan kamera — gratis dan
   tepat waktunya.
2. Model yang menonton proksi klip (360p, jam berjalan tertulis di pojoknya)
   beserta lembar wajah P0…Pn, lalu memilih momen dan bingkai dari MENU yang
   sudah bisa dirender. Ia tidak menulis filter dan tidak mengarang kotak.
3. Validasi: waktu ditempel ke bukti lokal terdekat, bidikan terlalu pendek
   dibuang, orang yang tidak terlihat saat itu tidak boleh dipilih, dan bingkai
   selalu kembali ke bingkai dasar sesudah momen.

Kenapa jam ditulis di gambar: tanpa itu, dari 70 detik video, model menaruh
satu momen tawa di detik 100-108 — di luar videonya. Dengan jam di pojok,
keempat momennya jatuh dalam ±3 detik dari tawa yang terdengar.

Hasilnya kunci bingkai biasa (`asal: "ai"`, `alasan`), jadi tetap terlihat di
lajur Bingkai dan bisa dihapus satu per satu.
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Callable, Optional

from .proses import jalankan

log = logging.getLogger("omniclip.sutradara_ai")

VERSI_PROMPT = 2
# Versi penyusunan kunci — dinaikkan setiap kali hasil yang sama dari model
# akan menghasilkan bingkai yang berbeda. Terpisah dari versi prompt karena
# keduanya berubah karena alasan yang berbeda, dan cache harus gugur untuk
# kedua-duanya.
VERSI_SUSUN = 2
PROKSI_TINGGI = 360
PROKSI_FPS = 2              # bingkai per detik yang ditonton model
PROKSI_MAKS_DETIK = 300.0
BIDIKAN_MIN = 0.6           # bidikan tersingkat yang masih terbaca
MOMEN_MAKS = 5.0            # momen reaksi terpanjang sebelum kembali normal
JARAK_MOMEN_MIN = 3.0       # jarak antar momen reaksi
TEMPEL_DETIK = 2.0          # waktu model ditempel ke bukti lokal sejauh ini
MENDAHULUI = 0.12           # bingkai mendahului puncak, seperti sutradara.py
KEKUATAN_MIN = 0.55         # momen yang lebih lemah dari ini tidak mengubah bingkai
# Wajah selebar ini (piksel sumber) atau lebih kecil tidak diperbesar jadi satu
# layar penuh: hasilnya bubur. Momennya jatuh ke bidikan lebar.
WAJAH_MIN_PX = 44

SISTEM = """Anda sutradara penyunting video pendek vertikal (TikTok/Reels/Shorts).

Anda menonton satu klip. Angka di pojok kanan atas setiap bingkai adalah DETIK
klip, pakai angka itu untuk semua waktu. Gambar kedua (bila ada) berisi wajah
orang-orang di klip, berlabel P0, P1, dst.

Tugas Anda: menentukan KAPAN bingkai perlu berubah untuk menonjolkan reaksi,
dan menjadi apa. Sebagian besar waktu bingkai tetap pada BINGKAI DASAR. Yang
diubah hanya momen yang benar-benar layak: tawa lepas sesudah punchline, kaget
karena jumpscare, sorak, reaksi terkejut. Obrolan biasa, senyum kecil, dan tawa
sopan TIDAK perlu diubah. Lebih baik sedikit momen yang kuat daripada bingkai
yang terus berpindah.

Yang ingin ditonjolkan adalah WAJAH yang bereaksi. Pakai "wajah" atau
"reaksi_terbagi" untuk orang-orang yang bereaksi. Bila wajah mereka tidak bisa
dibingkai sendiri-sendiri (terlalu kecil atau tertutup), lewati momen itu. Bila
bidikan kamera saat itu sudah close-up satu orang yang bereaksi, momen itu
tidak perlu diubah sama sekali. JANGAN PERNAH memakai latar kabur, gambar
selalu memenuhi layar.

kekuatan (0-1): 0,9 tawa pecah/kaget besar; 0,7 tawa lepas yang jelas; 0,5
tawa biasa; di bawah itu jangan dimasukkan.

Pilihan bingkai (hanya ini):
- "wajah": satu orang memenuhi layar (sebut satu label P di "orang").
- "reaksi_terbagi": 2-4 orang yang bereaksi ditumpuk dalam satu layar.
- "reaksi_penuh": (gameplay) wajah pemain dari facecam memenuhi layar.
- "gameplay": (gameplay) permainan + facecam seperti biasa.
- "ikuti_penutur": bingkai dasar podcast, mengikuti yang sedang bicara.
- "ikuti_gerakan": kamera mengikuti bagian yang paling banyak bergerak, untuk
  bidikan tanpa wajah (pemandangan, permainan tanpa facecam, kartun, hewan).

Satu momen boleh berisi beberapa bidikan berurutan ("gaya"):
- "potong_bergantian": wajah orang yang bereaksi satu per satu, masing-masing
  0,7-1,5 detik, cocok bila reaksinya bergiliran atau orangnya duduk berjauhan.
- "terbagi": semua yang bereaksi sekaligus dalam "reaksi_terbagi", cocok bila
  mereka bereaksi bersamaan.
- "tunggal": satu bidikan saja (misalnya "reaksi_penuh" saat jumpscare).

Aturan:
- Hanya pilih orang yang TERLIHAT di layar pada saat itu.
- Setiap momen paling lama 5 detik; sesudahnya bingkai kembali ke dasar.
- "mulai" adalah detik saat reaksi dimulai (bingkai berubah), "selesai" saat
  reaksinya reda.
- Bila momen itu sama dengan salah satu MOMEN TERUKUR, isi momen_id dengan
  nomornya; bila bukan, isi -1.
- alasan: satu kalimat bahasa Indonesia, sebutkan apa yang terjadi."""


def _schema() -> dict:
    """
    Bentuk jawaban yang diminta, sebagai dict netral.

    Bukan `types.Schema` milik google-genai lagi: jawaban yang sama harus bisa
    diminta ke OpenRouter juga, yang memakai JSON Schema biasa. `penyedia_ai`
    yang menerjemahkannya ke bentuk masing-masing.

    Urutan properti ikut penting dan karena itu ditulis eksplisit: "alasan"
    sengaja diminta SEBELUM angka-angkanya, supaya model menyusun kalimatnya
    lebih dulu dan waktunya menyusul — bukan sebaliknya.
    """
    bidikan = {
        "type": "OBJECT", "required": ["bingkai", "orang", "durasi"],
        "property_ordering": ["bingkai", "orang", "durasi"],
        "properties": {
            "bingkai": {"type": "STRING", "enum": [
                "wajah", "reaksi_terbagi", "reaksi_penuh", "gameplay",
                "ikuti_penutur", "ikuti_gerakan"]},
            "orang": {"type": "ARRAY", "items": {"type": "STRING"}},
            "durasi": {"type": "NUMBER"},
        }}
    momen = {
        "type": "OBJECT",
        "required": ["alasan", "momen_id", "mulai", "selesai", "kekuatan", "gaya", "bidikan"],
        "property_ordering": ["alasan", "momen_id", "mulai", "selesai", "kekuatan",
                              "gaya", "bidikan"],
        "properties": {
            "alasan": {"type": "STRING"},
            "momen_id": {"type": "INTEGER"},
            "mulai": {"type": "NUMBER"},
            "selesai": {"type": "NUMBER"},
            "kekuatan": {"type": "NUMBER"},
            "gaya": {"type": "STRING", "enum": ["potong_bergantian", "terbagi", "tunggal"]},
            "bidikan": {"type": "ARRAY", "items": bidikan},
        }}
    return {
        "type": "OBJECT", "required": ["jenis_video", "bingkai_dasar", "momen"],
        "property_ordering": ["jenis_video", "bingkai_dasar", "momen"],
        "properties": {
            "jenis_video": {"type": "STRING", "enum": ["podcast", "gameplay", "lainnya"]},
            "bingkai_dasar": {"type": "STRING",
                              "enum": ["ikuti_penutur", "gameplay", "ikuti_gerakan"]},
            "momen": {"type": "ARRAY", "items": momen},
        }}


# --- Bahan untuk model ----------------------------------------------------------
def _font() -> Optional[str]:
    from ..config import FONTS_DIR
    for nama in ("Montserrat-ExtraBold.ttf", "Oswald-Bold.ttf", "Anton-Regular.ttf"):
        p = FONTS_DIR / nama
        if p.is_file():
            return str(p)
    return None


def _ass_jam(durasi: float, keluar: Path) -> None:
    """
    Jam klip sebagai berkas subtitle ASS: satu teks per 0,1 detik di pojok kanan atas.

    Bukan `drawtext`: ffmpeg yang dibundel bersama aplikasi (build statis) tidak
    punya filter itu sama sekali — graf yang memakainya ditolak "Filter not
    found". libass ada di build yang sama karena subtitle klip bergantung
    padanya, jadi jam ditulis dengan jalan yang sama.
    """
    def ts(t: float) -> str:
        cs = int(round(t * 100))
        return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"

    baris = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 640", "PlayResY: 360",
             "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
             "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
             "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             "Style: Jam,Montserrat ExtraBold,22,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB0000000,"
             "-1,0,0,0,100,100,0,0,3,3,0,9,8,8,6,1", "",
             "[Events]",
             "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    n = int(durasi * 10) + 1
    for i in range(n):
        t0, t1 = i / 10, (i + 1) / 10
        baris.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Jam,,0,0,0,,{t0:.1f}")
    keluar.write_text("\n".join(baris) + "\n", encoding="utf-8")


def _proksi(src: Path, segments: list[dict], keluar: Path) -> Optional[bytes]:
    """Klip 360p bersuara mono, jam klip tertulis di pojok kanan atas."""
    from ..config import FONTS_DIR
    from .paths import ffpath

    durasi = min(PROKSI_MAKS_DETIK, sum(float(s["end"]) - float(s["start"]) for s in segments))
    ass = keluar.with_suffix(".ass")
    _ass_jam(durasi, ass)

    masukan: list[str] = []
    rantai: list[str] = []
    for i, s in enumerate(segments):
        masukan += ["-ss", f"{float(s['start']):.3f}", "-t",
                    f"{float(s['end']) - float(s['start']):.3f}", "-i", str(src)]
        rantai.append(f"[{i}:v:0]scale=-2:{PROKSI_TINGGI},setsar=1,fps=15[v{i}];"
                      f"[{i}:a:0]aresample=16000,aformat=channel_layouts=mono[a{i}]")
    n = len(segments)
    fonts = f":fontsdir='{ffpath(FONTS_DIR)}'" if FONTS_DIR.is_dir() else ""
    # Kanvas proksi dipaksa 640x360 supaya jam di ASS (PlayRes 640x360) jatuh
    # di pojok yang sama apa pun rasio sumbernya.
    jam = (f"scale=640:360:force_original_aspect_ratio=decrease,"
           f"pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black,"
           f"ass=filename='{ffpath(ass)}'{fonts}")
    graf = ";".join(rantai) + ";" + "".join(f"[v{i}][a{i}]" for i in range(n)) \
        + f"concat=n={n}:v=1:a=1[vc][ac];[vc]{jam}[vo]"
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *masukan,
           "-filter_complex", graf, "-map", "[vo]", "-map", "[ac]",
           "-t", f"{PROKSI_MAKS_DETIK:.0f}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "48k", str(keluar)]
    hasil = jalankan(cmd, rendah=True, timeout=300)
    if hasil.returncode != 0 or not keluar.is_file():
        log.warning("Proksi gagal: %s", (hasil.stderr or "")[-400:])
        return None
    return keluar.read_bytes()


def _bingkai_kunci(video: Path, durasi: float, tmp: Path, n: int = 12) -> list[bytes]:
    """
    Beberapa bingkai proksi sebagai JPEG, jarak waktunya sama.

    Untuk model yang tidak menerima video. Yang diambil adalah bingkai proksi,
    bukan bingkai sumber, karena di proksi sudah tertulis detik klipnya di
    pojok — tanpa itu model harus menebak waktu dari urutan gambar saja.
    """
    if durasi <= 0:
        return []
    pola = tmp / "kunci%03d.jpg"
    laju = max(n, 1) / max(durasi, 1.0)
    hasil = jalankan(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
                      "-i", str(video), "-vf", f"fps={laju:.6f}", "-frames:v", str(n),
                      "-q:v", "4", str(pola)], rendah=True, timeout=180)
    if hasil.returncode != 0:
        log.warning("Bingkai kunci gagal: %s", (hasil.stderr or "")[-300:])
        return []
    return [p.read_bytes() for p in sorted(tmp.glob("kunci*.jpg"))]


def _suara_klip(video: Path, keluar: Path) -> Optional[bytes]:
    """Suara proksi sebagai MP3 mono — tawa dan sorak terdengar di sini."""
    hasil = jalankan(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
                      "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                      "-c:a", "libmp3lame", "-b:a", "48k", str(keluar)],
                     rendah=True, timeout=180)
    if hasil.returncode != 0 or not keluar.is_file():
        log.warning("Suara klip gagal: %s", (hasil.stderr or "")[-300:])
        return None
    return keluar.read_bytes()


def _bingkai_sumber(src: Path, detik: float):
    """Satu bingkai video sumber sebagai larik BGR, atau None."""
    import cv2
    import numpy as np
    hasil = jalankan(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
                      "-ss", f"{detik:.3f}", "-i", str(src), "-frames:v", "1",
                      "-f", "image2pipe", "-vcodec", "png", "-"], text=False, timeout=60)
    if hasil.returncode != 0 or not hasil.stdout:
        return None
    return cv2.imdecode(np.frombuffer(hasil.stdout, np.uint8), cv2.IMREAD_COLOR)


def _lembar_wajah(src: Path, segments: list[dict], plan, keluar: Path
                  ) -> tuple[Optional[bytes], list[int]]:
    """
    Satu gambar berisi wajah tiap orang yang cukup sering terlihat, berlabel P.

    Disusun dengan OpenCV, bukan dengan `drawtext` ffmpeg — build statis yang
    dibundel aplikasi tidak punya filter itu.
    """
    import cv2
    import numpy as np
    from .reframe import SAMPLE_FPS

    if plan is None or not getattr(plan, "people_box", None):
        return None, []
    ubin, ada = [], []
    for p, kotak in enumerate(plan.people_box):
        terlihat = [i for i, b in enumerate(kotak) if b]
        if len(terlihat) < max(4, int(0.03 * len(kotak))):
            continue
        t = terlihat[len(terlihat) // 2] / SAMPLE_FPS
        r = plan.kotak_orang(p, t - 1, t + 1, aspek=1.0, tinggi_wajah=2.2)
        if not r:
            continue
        img = _bingkai_sumber(src, _ke_sumber(segments, t))
        if img is None:
            continue
        h, w = img.shape[:2]
        x0, y0 = int(r["x"] / 100 * w), int(r["y"] / 100 * h)
        x1, y1 = int((r["x"] + r["w"]) / 100 * w), int((r["y"] + r["h"]) / 100 * h)
        potong = img[max(0, y0):max(y0 + 1, y1), max(0, x0):max(x0 + 1, x1)]
        if potong.size == 0:
            continue
        potong = cv2.resize(potong, (200, 200), interpolation=cv2.INTER_AREA)
        cv2.rectangle(potong, (0, 0), (64, 40), (0, 0, 0), -1)
        cv2.putText(potong, f"P{p}", (6, 31), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (0, 255, 255), 2, cv2.LINE_AA)
        ubin.append(potong)
        ada.append(p)
    if not ada:
        return None, []
    ok, jpg = cv2.imencode(".jpg", np.hstack(ubin), [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        return None, []
    return jpg.tobytes(), ada


def _ke_sumber(segments: list[dict], t: float) -> float:
    """Detik klip -> detik video sumber."""
    sisa = t
    for s in segments:
        panjang = float(s["end"]) - float(s["start"])
        if sisa <= panjang:
            return float(s["start"]) + max(0.0, sisa)
        sisa -= panjang
    return float(segments[-1]["end"])


def _transkrip_klip(subtitles: list[dict]) -> str:
    baris = []
    for l in subtitles or []:
        teks = (l.get("text") or "").strip()
        if not teks:
            continue
        sp = l.get("speaker")
        baris.append(f"[{float(l.get('start', 0)):.1f}] "
                     + (f"(penutur {int(sp) + 1}) " if sp is not None else "") + teks)
    return "\n".join(baris) if baris else "(tidak ada transkrip)"


# --- Dari jawaban model ke kunci bingkai ---------------------------------------
def _terlihat(plan, p: int, t0: float, t1: float) -> bool:
    from .reframe import SAMPLE_FPS
    if plan is None or not (0 <= p < len(plan.people_seen)):
        return False
    s = plan.people_seen[p]
    a, b = max(0, int((t0 - 0.3) * SAMPLE_FPS)), min(len(s), int((t1 + 0.3) * SAMPLE_FPS) + 1)
    return b > a and sum(1 for v in s[a:b] if v) >= max(1, (b - a) // 3)


# Sepanjang apa layar boleh tanpa wajah sebelum bingkainya dilebarkan. Di
# bawah ini, melebarkan lalu menyempit lagi terbaca sebagai kedipan.
TANPA_WAJAH_MIN = 2.5
# Wajah yang terlihat kurang dari ini di antara dua bagian kosong diabaikan.
JEDA_WAJAH_MIN = 1.5


# Cara membingkai yang boleh dipakai sutradara. Bilah kabur, potong tengah,
# orisinal, dan kotak tetap tidak termasuk: pemiliknya menunggu lama lalu hanya
# mendapat bingkai kabur, dan memutuskan sutradara tidak boleh memakainya.
MODE_SUTRADARA = ("smart", "motion", "gaming", "layout")


def _tanpa_kabur(kunci: list[dict]) -> list[dict]:
    """
    Jaring terakhir: apa pun jalannya, hanya `MODE_SUTRADARA` yang keluar.
    Kotak tetap diubah jadi susunan satu bingkai (hasilnya sama persis); yang
    lain jadi "ikuti gerakan".
    """
    for k in kunci:
        mode = k.get("mode") or "smart"
        if mode == "box" and k.get("rect"):
            k["mode"] = "layout"
            k["layout"] = {"background": "black", "frames": [{
                "label": "Bingkai", "src": k.pop("rect"),
                "dst": {"x": 0, "y": 0, "w": 100, "h": 100}, "fit": "cover"}]}
        elif mode not in MODE_SUTRADARA:
            k["mode"] = "motion"
            k.pop("rect", None)
    return kunci


def _tanpa_wajah(plan, durasi: float) -> list[tuple[float, float]]:
    """Rentang waktu (detik klip) ketika tidak satu wajah pun terlihat."""
    from .reframe import SAMPLE_FPS
    if plan is None or not getattr(plan, "people_seen", None):
        return []
    n = min(len(s) for s in plan.people_seen)
    ada = [any(s[i] for s in plan.people_seen) for i in range(n)]
    keluar: list[tuple[float, float]] = []
    i = 0
    while i < n:
        if ada[i]:
            i += 1
            continue
        j = i
        while j < n and not ada[j]:
            j += 1
        a, b = i / SAMPLE_FPS, min(j / SAMPLE_FPS, durasi)
        # Wajah yang muncul sekejap di antara dua bagian kosong tidak layak
        # dikejar: kembali ke wajah 0,8 detik lalu pergi lagi terbaca sebagai
        # kedipan. Terukur pada klip Minecraft (27,1-27,9 dtk).
        if keluar and a - keluar[-1][1] < JEDA_WAJAH_MIN:
            keluar[-1] = (keluar[-1][0], b)
        elif b - a >= TANPA_WAJAH_MIN:
            keluar.append((a, b))
        i = j
    return [r for r in keluar if r[1] - r[0] >= TANPA_WAJAH_MIN]


def _lebar_wajah(plan, p: int, t0: float, t1: float) -> float:
    """Median lebar wajah orang `p` (piksel sumber) selama [t0, t1]."""
    from .reframe import SAMPLE_FPS
    if plan is None or not (0 <= p < len(plan.people_box)):
        return 0.0
    kotak = plan.people_box[p]
    a, b = max(0, int(t0 * SAMPLE_FPS)), min(len(kotak), int(t1 * SAMPLE_FPS) + 1)
    lebar = sorted(k[1] for k in kotak[a:b] if k)
    return lebar[len(lebar) // 2] if lebar else 0.0


def _potongan(plan, t0: float, t1: float, min_detik: float = 0.35) -> list[tuple[float, float]]:
    """[t0, t1] dibelah di setiap perpindahan kamera; serpihan pendek disatukan."""
    batas = [t for t in (getattr(plan, "cut_times", None) or []) if t0 + min_detik < t < t1 - min_detik]
    titik = [t0, *batas, t1]
    return [(titik[i], titik[i + 1]) for i in range(len(titik) - 1)]


def _label_ke_orang(label) -> Optional[int]:
    teks = str(label).strip().upper().lstrip("P")
    return int(teks) if teks.isdigit() else None


def _wajah_tunggal(plan, p: int, t0: float, t1: float, out_w: int, out_h: int
                   ) -> Optional[dict]:
    """
    Satu wajah memenuhi layar, MEMBUNTUTI orangnya.

    Bukan kotak diam: orang yang tertawa bersandar, menunduk, dan menoleh, dan
    kotak diam di posisi mediannya terukur hanya menangkap setengah wajah.
    Susunan satu bingkai yang mengikuti jejak orang itu tetap memakai ukuran
    dan tinggi dari kotaknya, tapi posisi mendatarnya berjalan bersama wajah.
    """
    src = plan.kotak_orang(p, t0, t1, aspek=out_w / out_h)
    if not src:
        return None
    return {"mode": "layout", "layout": {"background": "black", "frames": [
        {"label": f"P{p}", "src": src, "dst": {"x": 0, "y": 0, "w": 100, "h": 100},
         "fit": "cover", "follow": True, "person": p}]}}


def _saring_bersamaan(plan, orang: list[int], t0: float, t1: float) -> list[int]:
    """
    Orang yang BENAR-BENAR terlihat bersamaan selama momen, tanpa kembaran.

    Kamera yang berpindah di tengah momen membuat pelacak mencatat "P0" sebelum
    potongan dan "P1" sesudahnya — bisa orang yang sama dari sudut lain. Dua
    sel berisi wajah yang sama terlihat seperti galat. Jadi orang yang tidak
    pernah muncul bersama di layar (< 30% waktu bersama) atau kotaknya
    bertumpuk lebih dari separuh tidak dipasangkan.
    """
    from .reframe import SAMPLE_FPS
    i0, i1 = int(t0 * SAMPLE_FPS), max(int(t0 * SAMPLE_FPS) + 1, int(t1 * SAMPLE_FPS))

    def tampak(p):
        lane = plan.people_seen[p] if p < len(plan.people_seen) else []
        return {i for i in range(i0, min(i1, len(lane))) if lane[i]}

    def kotak(p):
        return plan.kotak_orang(p, t0, t1, aspek=1.0)

    def tumpuk(a, b):
        if not a or not b:
            return 0.0
        ix = max(0.0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
        iy = max(0.0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
        kecil = min(a["w"] * a["h"], b["w"] * b["h"]) or 1.0
        return ix * iy / kecil

    urut = sorted(dict.fromkeys(orang), key=lambda p: -len(tampak(p)))
    diambil: list[int] = []
    for p in urut:
        tp = tampak(p)
        if not tp:
            continue
        cocok = True
        for q in diambil:
            tq = tampak(q)
            bersama = len(tp & tq) / max(1, min(len(tp), len(tq)))
            if bersama < 0.3 or tumpuk(kotak(p), kotak(q)) > 0.5:
                cocok = False
                break
        if cocok:
            diambil.append(p)
    # Urutan asli dipertahankan (kiri ke kanan seperti yang diminta).
    return [p for p in orang if p in diambil]


def _susunan_terbagi(plan, orang: list[int], t0: float, t1: float,
                     out_w: int, out_h: int) -> Optional[dict]:
    orang = _saring_bersamaan(plan, orang, t0, t1)
    n = len(orang)
    if n < 2:
        return None
    n = min(n, 4)
    if n == 4:
        sel = [(0, 0, 50, 50), (50, 0, 50, 50), (0, 50, 50, 50), (50, 50, 50, 50)]
    else:
        tinggi = 100.0 / n
        sel = [(0, round(i * tinggi, 3), 100, round(tinggi, 3)) for i in range(n)]
    frames = []
    for (x, y, w, h), p in zip(sel, orang[:n]):
        aspek = (w / 100 * out_w) / (h / 100 * out_h)
        src = plan.kotak_orang(p, t0, t1, aspek=aspek)
        if not src:
            return None
        frames.append({"label": f"P{p}", "src": src,
                       "dst": {"x": x, "y": y, "w": w, "h": h},
                       "fit": "cover", "follow": True, "person": p})
    return {"background": "black", "frames": frames}


# --- Bingkai dasar per saat: game, wajah, atau gerakan ---------------------------
#
# Video campuran (MrBeast "100 Days on One Block") berganti jenis bidikan tiap
# beberapa detik: permainan dengan facecam kecil di pojok, permainan saja,
# rekaman kamera orang sungguhan, bidikan drone. Satu bingkai dasar untuk
# seluruh klip pasti salah di sebagian besar klipnya — dan facecam yang hanya
# muncul sebagian waktu tidak pernah lolos deteksi "facecam sepanjang klip",
# sehingga bagian game ikut dibingkai sebagai wajah. Aturan pemiliknya:
#
#   game + wajah terlihat bersamaan  -> bingkai game
#   hanya game (tanpa wajah)         -> ikuti gerakan
#   hanya wajah                      -> ikuti wajah
#
# Ciri facecam diukur dari rekaman itu sendiri (0-40 dtk): wajah pemain 6-12,6%
# lebar bingkai, selalu di pojok (x 9-20% atau 83-91%; y 24-27% atau 68-81%);
# wajah pada rekaman kamera orang ada di tengah (x 52-55%).
FACECAM_WAJAH_MAKS = 0.14      # lebar wajah maksimum, pecahan lebar bingkai
FACECAM_TEPI_X = 0.25          # pusat wajah di luar 25-75% lebar
FACECAM_ATAS_Y = 0.30          # ... dan di atas 30% atau
FACECAM_BAWAH_Y = 0.55         # ... di bawah 55% tinggi
# Facecam yang menempel di TEPI KIRI/KANAN, pada ketinggian berapa pun.
#
# Aturan di atas menuntut wajahnya dekat tepi mendatar DAN dekat tepi tegak.
# Itu benar untuk facecam pojok, dan salah untuk yang ditaruh di tengah tepi.
# Terukur pada video LaperGang pemiliknya (Minecraft, banyak POV YouTuber lain,
# tiap orang menaruh facecam-nya sendiri): facecam kiri ada di x 11,5% tapi
# y 50,2%, tepat di dalam celah 30-55% yang ditolak aturan lama. Akibatnya 87%
# sampel dilabeli "wajah", klipnya digolongkan podcast, dan bingkainya
# mengikuti wajah alih-alih permainannya.
#
# Dua angka ini lebih ketat daripada aturan pojok, justru karena ia melepas
# syarat tegaknya: wajah selebar 9% bingkai yang menempel 18% dari tepi bukan
# orang yang sedang diwawancara, ia panel kamera. Pengaman lama tetap berlaku
# di `_label_per_sampel`: "game" hanya bila wajah itu SATU-SATUNYA wajah.
FACECAM_KECIL = 0.09           # lebar wajah maksimum untuk jalur tepi ini
FACECAM_TEPI_KERAS = 0.18      # ... dan pusatnya di luar 18-82% lebar
# Potongan lebih pendek dari ini disatukan ke tetangganya. Dulu 1,5 detik, dan
# itu terlalu longgar: pada wawancara Bocor Alus, tiga potongan "game" selama
# 2-3 detik lolos dan bingkai dasarnya berganti enam kali dalam tiga puluh
# detik. Pergantian bingkai DASAR yang lebih singkat dari empat detik tidak
# terbaca sebagai keputusan, melainkan sebagai kedipan.
POTONGAN_DASAR_MIN = 4.0
# Batas yang jauh lebih longgar untuk potongan WAJAH yang wajahnya besar.
#
# Batas empat detik ada untuk menahan kedipan, dan itu benar selama kedua
# pilihannya sama-sama masuk akal. Tapi saat wajah orangnya memenuhi layar,
# bingkai game bukan pilihan yang kurang bagus melainkan SALAH: ia memotong
# kotak sebesar facecam dari wajah yang sedang besar-besarnya, lalu menaruh
# balok permainan di bidang bawah. Terukur pada klip LaperGang, penggolongnya
# sudah menandai detik 32,5-34,9 sebagai wajah — persis momen yang dikeluhkan
# pemiliknya 30 September 2026 — tapi 2,4 detik itu ditelan batas empat detik.
POTONGAN_WAJAH_BESAR_MIN = 1.5
# Batas TERLONGGAR di seluruh berkas ini, dan hanya untuk potongan yang lahir
# dari PANEL facecam yang besar.
#
# Dibenarkan oleh kekuatan sinyalnya. Wajah yang lebar bisa berarti macam-macam
# — orang mencondong ke kamera, deteksi yang meleset — tapi panel yang menempati
# seperlima layar hanya terjadi kalau streamer memang membesarkan kameranya,
# dan itu pernyataan yang jelas tentang apa yang sedang penting. Terukur pada
# klip LaperGang, momen seperti itu berlangsung 1,0 sampai 2,5 detik; batas 1,5
# detik menelan yang terpendek justru di saat bidang gamenya paling salah.
POTONGAN_PANEL_BESAR_MIN = 1.0
# Batas untuk kembali ke BINGKAI GAME, yaitu keadaan dasar klip gameplay.
#
# Batas empat detik ada untuk menahan kedipan, dan itu benar untuk BERPINDAH
# dari keadaan dasar ke sesuatu yang khusus: pindah seperti itu adalah
# keputusan, dan keputusan yang berumur dua detik terbaca sebagai kerusakan.
# Tapi KEMBALI ke keadaan dasar bukan keputusan — itu berhenti melakukan
# sesuatu yang khusus, dan menuntut bukti sebanyak itu untuk berhenti berarti
# klip terjebak di bingkai wajah lama sesudah alasannya lewat. Terukur pada
# klip LaperGang: 2,9 detik permainan di antara dua momen wajah diserap
# seluruhnya, dan yang terlihat pemiliknya adalah bingkai yang tidak pernah
# kembali ke game.
POTONGAN_GAME_MIN = 1.5
# Lebar wajah (pecahan lebar bingkai) yang membuat sebuah potongan wajah
# dianggap "besar".
#
# Angkanya diukur, bukan ditebak. Pada klip LaperGang, lebar wajah TENGAH tiap
# potongan memisah dengan bersih:
#
#   potongan "game"  : 3,6  3,6  4,0  4,4  5,4  5,9  8,3 %
#   potongan "wajah" : 10,3  11,6  13,4  14,1 %
#
# Sepersepuluh lebar bingkai ada di tengah jurang itu, dan artinya bisa
# diucapkan: wajah sebesar itu adalah bidikan medium close-up, bukan kamera
# pemain di sudut layar. Percobaan pertama memakai 0,17 dan tidak pernah
# memicu satu kali pun.
WAJAH_BESAR_MIN = 0.10


def _wajah_pojok(x: float, cy: float, w: float, sw: int, sh: int) -> bool:
    """Apakah wajah ini berbentuk kamera pemain, bukan orang yang direkam?"""
    fx, fy, fw = x / max(1, sw), cy / max(1, sh), w / max(1, sw)
    if fw > FACECAM_WAJAH_MAKS:
        return False
    if ((fx < FACECAM_TEPI_X or fx > 1 - FACECAM_TEPI_X)
            and (fy < FACECAM_ATAS_Y or fy > FACECAM_BAWAH_Y)):
        return True
    # Menempel di tepi kiri/kanan, seberapa pun tingginya. Lihat FACECAM_KECIL.
    return fw <= FACECAM_KECIL and (fx < FACECAM_TEPI_KERAS
                                    or fx > 1 - FACECAM_TEPI_KERAS)


# Lebar jendela penghalus label, dalam sampel. Pada 8 Hz, 5 sampel = 0,6 detik.
HALUS_JENDELA = 5


def _haluskan(label: list[str]) -> list[str]:
    """
    Membuang KEDIPAN label per sampel dengan suara terbanyak di jendela kecil.

    Deteksi wajah bekerja per bingkai dan sesekali meleset satu-dua bingkai:
    orangnya menoleh, tangannya menutupi muka, atau kotaknya bergeser melewati
    ambang "di pojok". Tanpa penghalusan, satu sampel yang meleset memecah
    potongan game 3 detik jadi empat potongan 0,4-0,8 detik — dan tiap pecahan
    lalu terlalu pendek untuk bertahan, sehingga SELURUHNYA diserap potongan
    wajah di sebelahnya. Terukur pada klip LaperGang detik 17,6-20,5, dan
    dilaporkan pemiliknya 1 Oktober 2026: "ketika kembali normal bingkai tidak
    kembali ke game".

    Yang dihaluskan hanya kedipan sependek setengah detik; pergantian yang
    benar-benar terjadi berlangsung jauh lebih lama dan tidak tersentuh.
    """
    n = len(label)
    if n < HALUS_JENDELA:
        return list(label)
    sisi = HALUS_JENDELA // 2
    keluar = []
    for i in range(n):
        jendela = label[max(0, i - sisi):min(n, i + sisi + 1)]
        keluar.append(max(set(jendela), key=jendela.count))
    return keluar


def _lebar_wajah_per_sampel(plan) -> list[float]:
    """Lebar wajah TERBESAR di tiap sampel, sebagai pecahan lebar bingkai."""
    sw = plan.source_w
    n = min((len(s) for s in plan.people_seen), default=0)
    keluar = []
    for i in range(n):
        lebar = 0.0
        for p in range(len(plan.people)):
            if not plan.people_seen[p][i]:
                continue
            kotak = (plan.people_box[p][i]
                     if p < len(plan.people_box) and i < len(plan.people_box[p]) else None)
            if kotak is None:
                continue
            lebar = max(lebar, float(kotak[1]) / max(1, sw))
        keluar.append(lebar)
    return keluar


def _label_per_sampel(plan) -> list[str]:
    """'game' / 'wajah' / 'gerak' untuk tiap sampel rencana wajah."""
    sw, sh = plan.source_w, plan.source_h
    n = min((len(s) for s in plan.people_seen), default=0)
    label = []
    for i in range(n):
        ada_pojok = ada_tengah = False
        for p in range(len(plan.people)):
            if not plan.people_seen[p][i]:
                continue
            kotak = plan.people_box[p][i] if p < len(plan.people_box) and i < len(plan.people_box[p]) else None
            x = plan.people[p][i]
            if kotak is None or x is None:
                continue
            if _wajah_pojok(float(x), float(kotak[0]), float(kotak[1]), sw, sh):
                ada_pojok = True
            else:
                ada_tengah = True
        # "game" hanya bila wajah di pojok itu SATU-SATUNYA wajah.
        #
        # Sebelumnya cukup ada wajah di pojok, dan itu keliru pada percakapan:
        # pada wawancara Bocor Alus, tamu yang duduk di tepi layar membuat 27%
        # klip dilabeli permainan, lalu dibingkai sebagai gameplay dengan panel
        # facecam yang tidak pernah ada. Pada gameplay sungguhan, wajah pemain
        # memang satu-satunya wajah di layar — itulah yang membedakannya.
        label.append("game" if ada_pojok and not ada_tengah
                     else "wajah" if ada_pojok or ada_tengah else "gerak")
    return label


# Potongan yang KEDUA batasnya jatuh pada potongan adegan boleh lebih pendek.
#
# Batas empat detik ada untuk menahan kedipan: bingkai dasar yang berganti tiap
# dua detik terbaca sebagai kerusakan, bukan sebagai keputusan. Tapi alasan itu
# hilang bila pergantiannya jatuh tepat pada POTONGAN ADEGAN video aslinya:
# di situ gambarnya memang berubah total, dan bingkai yang ikut berubah justru
# terbaca benar.
#
# Terlihat pada rekaman pemiliknya 29 September 2026: momen dua detik yang
# hanya menampilkan permainan dilebur ke potongan tetangganya, jadi bidang
# wajah berisi salju selama momen itu.
POTONGAN_DI_ADEGAN_MIN = 1.2
# Seberapa dekat sebuah batas boleh digeser supaya jatuh pada potongan adegan.
SNAP_ADEGAN = 0.6


def _snap_ke_adegan(runs: list[list], potongan_adegan: list[float]) -> list[list]:
    """
    Menggeser batas potongan ke potongan adegan terdekat.

    Label dihitung per sampel 8 Hz lalu dikelompokkan, jadi batasnya jatuh di
    mana saja dalam rentang seperdelapan detik dari pergantian yang sebenarnya,
    dan kadang meleset lebih jauh karena satu-dua sampel salah baca. Yang
    terlihat pemiliknya: "terkadang bingkai pindah lebih awal atau lebih
    lambat". Potongan adegan adalah titik yang benar-benar ada di videonya,
    jadi ke situlah batasnya ditarik.
    """
    if not potongan_adegan or len(runs) < 2:
        return runs
    runs = [r[:] for r in runs]
    for i in range(1, len(runs)):
        batas = runs[i][1]
        dekat = min(potongan_adegan, key=lambda c: abs(c - batas))
        if abs(dekat - batas) > SNAP_ADEGAN:
            continue
        # Tidak boleh menelan potongan tetangga seluruhnya.
        if dekat <= runs[i - 1][1] + 0.2 or dekat >= runs[i][2] - 0.2:
            continue
        runs[i - 1][2] = dekat
        runs[i][1] = dekat
    return runs


def _rapikan_potongan(runs: list[list], potongan_adegan: Optional[list] = None,
                      minimum: Optional[dict] = None) -> list[list]:
    """
    Potongan [label, a, b] yang terlalu pendek disatukan ke tetangga terpanjang.

    `minimum` memberi batas SENDIRI untuk potongan tertentu, dikunci pada
    (label, mulai) potongan itu sebelum apa pun disatukan. Dipakai untuk
    potongan wajah yang wajahnya memenuhi layar: lihat POTONGAN_WAJAH_BESAR_MIN.
    """
    runs = [r[:] for r in runs]
    adegan = list(potongan_adegan or [])
    khusus = dict(minimum or {})

    def batas(r) -> float:
        return khusus.get((r[0], round(r[1], 3)), POTONGAN_DASAR_MIN)

    def di_adegan(t: float) -> bool:
        return any(abs(c - t) <= 0.2 for c in adegan)

    while len(runs) > 1:
        pendek = min(range(len(runs)),
                     key=lambda i: (runs[i][2] - runs[i][1]) - batas(runs[i]))
        panjang = runs[pendek][2] - runs[pendek][1]
        if panjang >= batas(runs[pendek]):
            break
        # Potongan pendek yang berdiri di antara dua potongan adegan adalah
        # bidikan tersendiri, bukan kedipan.
        if (panjang >= POTONGAN_DI_ADEGAN_MIN
                and di_adegan(runs[pendek][1]) and di_adegan(runs[pendek][2])):
            sisa = [i for i in range(len(runs)) if i != pendek]
            if not sisa:
                break
            kedua = min(sisa, key=lambda i: (runs[i][2] - runs[i][1]) - batas(runs[i]))
            if runs[kedua][2] - runs[kedua][1] >= batas(runs[kedua]):
                break
            pendek = kedua
            panjang = runs[pendek][2] - runs[pendek][1]
            if panjang >= batas(runs[pendek]):
                break
        kiri = runs[pendek - 1] if pendek > 0 else None
        kanan = runs[pendek + 1] if pendek + 1 < len(runs) else None
        tuju = max((r for r in (kiri, kanan) if r is not None), key=lambda r: r[2] - r[1])
        if tuju is kiri:
            kiri[2] = runs[pendek][2]
        else:
            kanan[1] = runs[pendek][1]
        runs.pop(pendek)
        # Tetangga berlabel sama yang kini bersentuhan disatukan.
        gabung = [runs[0]]
        for r in runs[1:]:
            if r[0] == gabung[-1][0]:
                gabung[-1][2] = r[2]
            else:
                gabung.append(r)
        runs = gabung
    return runs


# Sebuah percakapan tidak berubah jadi permainan selama beberapa detik lalu
# kembali. Bila potongan "game" hanya sekelumit dari klip yang sebagian besar
# berisi wajah, yang terjadi hampir pasti bukan permainan melainkan satu wajah
# kecil yang kebetulan lewat di pojok layar — tamu yang duduk di tepi, atau
# orang di latar belakang.
GAME_PORSI_MIN = 0.25          # game harus mengisi seperempat klip untuk dipercaya
WAJAH_PORSI_JELAS = 0.5        # ... bila wajah mengisi separuhnya


def _buang_game_sekilas(runs: list[list], durasi: float) -> list[list]:
    """Label "game" yang hanya sekelumit dari klip berwajah diubah jadi "wajah"."""
    if durasi <= 0 or not runs:
        return runs
    porsi = {}
    for l, a, b in runs:
        porsi[l] = porsi.get(l, 0.0) + max(0.0, b - a)
    game, wajah = porsi.get("game", 0.0) / durasi, porsi.get("wajah", 0.0) / durasi
    if not game or game >= GAME_PORSI_MIN or wajah < WAJAH_PORSI_JELAS:
        return runs
    log.info("Potongan game hanya %.0f%% klip berwajah (%.0f%%), dianggap wajah",
             game * 100, wajah * 100)
    ubah = [["wajah" if l == "game" else l, a, b] for l, a, b in runs]
    gabung = [ubah[0]]
    for r in ubah[1:]:
        if r[0] == gabung[-1][0]:
            gabung[-1][2] = r[2]
        else:
            gabung.append(r)
    return gabung


# Luas panel facecam (pecahan luas bingkai) yang membuat sebuah potongan
# dianggap bidikan WAJAH, bukan permainan. Lihat catatan di `_dasar_per_waktu`.
PANEL_BESAR_MIN = 0.095


def _tandai_panel_besar(runs: list[list], facecam_waktu) -> tuple[list[list], set]:
    """
    Potongan "game" yang panelnya besar diubah jadi "wajah", dipecah tepat di
    tempat panelnya berubah besar atau mengecil lagi.

    Tanpa `facecam_waktu` tidak ada yang bisa dinilai, dan runs dikembalikan
    apa adanya — itu jalur yang dipakai pemanggil yang belum memindai panel.
    """
    pos = sorted((float(p["t"]), p["facecam"]) for p in (facecam_waktu or []))
    if not pos:
        return runs, set()

    def besar_pada(t: float) -> bool:
        f = pos[0][1]
        for tt, ff in pos:
            if tt <= t + 1e-6:
                f = ff
        return (float(f["w"]) * float(f["h"]) / 10000.0) >= PANEL_BESAR_MIN

    # Batas waktu yang perlu diperiksa: awal tiap potongan, plus tiap saat
    # panelnya berganti.
    keluar: list[list] = []
    dari_panel: set = set()
    for l, a, b in runs:
        if l != "game":
            keluar.append([l, a, b])
            continue
        titik = [a] + [tt for tt, _f in pos if a < tt < b] + [b]
        for i in range(len(titik) - 1):
            x, y = titik[i], titik[i + 1]
            if y - x <= 1e-6:
                continue
            nama = "wajah" if besar_pada(x) else "game"
            if keluar and keluar[-1][0] == nama and abs(keluar[-1][2] - x) < 1e-6:
                keluar[-1][2] = y
            else:
                keluar.append([nama, x, y])
                if nama == "wajah":
                    dari_panel.add((nama, round(x, 3)))
    return keluar, dari_panel


def _dasar_per_waktu(plan, src: Path, segments: list[dict], durasi: float,
                     out_w: int, out_h: int,
                     # Linimasa facecam yang sudah dipindai pemanggil. Tanpa ini
                     # fungsi ini memindainya lagi, pemindaian yang sama persis,
                     # dan pada klip 40 detik itu sepuluh detik terbuang
                     # sementara orangnya menunggu klipnya terbuka.
                     facecam_waktu: Optional[list] = None,
                     ) -> Optional[list[tuple[float, float, dict]]]:
    """
    Bingkai dasar per potongan waktu: [(mulai, akhir, kunci)], atau None bila
    tidak ada data wajah untuk menilainya.
    """
    from .reframe import SAMPLE_FPS, deteksi_facecam
    from .render import rasio_bidang_wajah, susun_layout_gaming

    if plan is None or not getattr(plan, "people_seen", None):
        return None
    label = _haluskan(_label_per_sampel(plan))
    if not label:
        return None
    runs: list[list] = []
    for i, l in enumerate(label):
        t = i / SAMPLE_FPS
        if runs and runs[-1][0] == l:
            runs[-1][2] = t + 1 / SAMPLE_FPS
        else:
            runs.append([l, t, t + 1 / SAMPLE_FPS])
    runs[-1][2] = durasi
    # PANEL FACECAM YANG BESAR berarti wajah, bukan permainan.
    #
    # Diminta pemiliknya 30 September 2026, dan ia mengoreksi pemahaman saya
    # yang sebelumnya: "jika facecam nya membesar maka sorot saja mukanya" —
    # bahkan saat permainannya masih 60% layar dan wajahnya sendiri tidak
    # besar. Yang menentukan bukan ukuran WAJAHNYA melainkan ukuran PANELNYA:
    # streamer yang membesarkan kameranya sedang menyatakan apa yang penting.
    #
    # Ambangnya diukur pada 68 bidikan dari empat klip LaperGang. Luas panel
    # terhadap luas bingkai memisah dengan jurang yang bersih:
    #
    #   panel besar : 15,0  14,9  14,9  14,6  13,2  11,6  11,4  10,3 %
    #   panel biasa :  8,9   7,4   7,1   6,9   6,9   6,8 ... 1,4 %
    #
    # 9,5% duduk di tengah jurang itu. Panel sebesar itu lebarnya 27-40% layar.
    runs, panel_besar = _tandai_panel_besar(runs, facecam_waktu)
    # Batas ditarik ke potongan adegan SEBELUM yang pendek dilebur: batas yang
    # sudah benar membuat potongan pendek yang sah jadi terlihat sah.
    adegan = [float(c) for c in (getattr(plan, "cut_times", None) or [])]
    runs = _snap_ke_adegan(runs, adegan)
    # Potongan wajah yang wajahnya MENDOMINASI layar diberi batas sendiri yang
    # jauh lebih longgar, supaya tidak ditelan batas empat detik. Lihat
    # POTONGAN_WAJAH_BESAR_MIN.
    lebar = _lebar_wajah_per_sampel(plan)
    minimum = {k: POTONGAN_PANEL_BESAR_MIN for k in panel_besar}
    for l, a, _b in runs:
        if l == "game":
            minimum.setdefault((l, round(a, 3)), POTONGAN_GAME_MIN)
    for l, a, b in runs:
        if l != "wajah" or not lebar:
            continue
        i0 = max(0, int(round(a * SAMPLE_FPS)))
        i1 = min(len(lebar), max(i0 + 1, int(round(b * SAMPLE_FPS))))
        petak = sorted(lebar[i0:i1])
        if petak and petak[len(petak) // 2] >= WAJAH_BESAR_MIN:
            minimum[(l, round(a, 3))] = POTONGAN_WAJAH_BESAR_MIN
    runs = _rapikan_potongan(runs, adegan, minimum)
    runs = _buang_game_sekilas(runs, durasi)

    sw, sh = plan.source_w, plan.source_h
    # Klip ini memang klip permainan bila ada potongan yang dilabeli "game".
    # Dipakai untuk memutuskan apa yang benar bagi potongan TANPA wajah:
    # di klip permainan itu berarti permainannya sendiri, di klip lain itu
    # berarti sebuah bidikan tanpa orang.
    ada_game = any(l == "game" for l, _a, _b in runs)
    keluar: list[tuple[float, float, dict]] = []
    # Letak panel sepanjang klip, dihitung sekali dan hanya bila dibutuhkan:
    # potongan game yang pendek (±2 dtk) terlalu singkat untuk menemukan tepi
    # panelnya sendiri, dan kotak tebakan dari ukuran wajah ikut memuat tepi
    # panel. Panel yang sama hampir selalu terlihat di bagian lain klip.
    # Diberikan pemanggil bila ia sudah memindainya sendiri; lihat parameter
    # `klip_penuh` di tanda tangan fungsi ini.
    klip_penuh: list = list(facecam_waktu or [])
    sudah_dicari = bool(klip_penuh)

    def panel_di(t: float) -> Optional[dict]:
        nonlocal klip_penuh, sudah_dicari
        if not sudah_dicari:
            sudah_dicari = True
            try:
                from .reframe import deteksi_facecam_waktu
                klip_penuh = deteksi_facecam_waktu(src, segments, sw, sh,
                                                   rasio_potongan=rasio_bidang_wajah(out_w, out_h)) or []
            except Exception as e:
                log.info("Facecam sepanjang klip tidak terbaca: %s", str(e)[:120])
        pilih = None
        for p in klip_penuh:
            if float(p["t"]) <= t + 1e-6:
                pilih = p["facecam"]
        return pilih or (klip_penuh[0]["facecam"] if klip_penuh else None)

    for l, a, b in runs:
        if l == "game":
            # Panel facecam untuk potongan INI: dicari dari potongan itu saja,
            # karena letaknya bisa berbeda dari potongan game sebelumnya.
            fc = None
            # Pemindaian per potongan DILEWATI bila linimasa sepanjang klip
            # sudah diberikan pemanggil.
            #
            # Keduanya menjawab pertanyaan yang sama, dan linimasa itu justru
            # lebih halus: ia dipindai per dua detik, sementara pemindaian per
            # potongan menghasilkan satu kotak untuk seluruh potongan. Terukur
            # pada klip 78 detik milik pemiliknya, tiga potongan berarti tiga
            # pemindaian ffmpeg tambahan untuk jawaban yang sudah ada.
            if not facecam_waktu:
                try:
                    fc = deteksi_facecam(src, _ke_sumber(segments, a), max(0.5, b - a), sw, sh,
                                         rasio_potongan=rasio_bidang_wajah(out_w, out_h))
                except Exception as e:
                    log.info("Facecam potongan %.1f-%.1f tidak terbaca: %s", a, b, str(e)[:120])
            if fc is None:
                fc = panel_di(a)
            if fc is None:
                fc = _kotak_dari_wajah(plan, a, b)
            if fc is None:
                keluar.append((a, b, {"mode": "motion", "alasan": "Permainan, kamera mengikuti gerakan"}))
                continue
            # Letak facecam DI DALAM potongan ini, bukan satu kotak untuk
            # seluruh potongan.
            #
            # Sebelumnya potongan game memakai satu kotak saja, jadi bingkai
            # reaksinya diam sepanjang potongan itu. Pada video multi-POV
            # (LaperGang: banyak POV YouTuber lain, masing-masing menaruh
            # facecam-nya sendiri) POV berganti tiap dua detik, dan bingkai yang
            # diam berarti separuh waktunya menyorot tempat kosong. Dilaporkan
            # pemiliknya berulang kali: "bingkai game masih tidak bisa berpindah
            # mengikuti facecam".
            #
            # `panel_di` sudah memanggil pemindai sepanjang klip dan menyimpan
            # hasilnya, jadi ini tidak menambah satu pun pemindaian.
            panel_di(a)
            dalam = [{"t": max(0.0, float(q["t"]) - a), "facecam": q["facecam"]}
                     for q in klip_penuh if a - 1e-6 <= float(q["t"]) < b - 1e-6]
            if not dalam or dalam[0]["t"] > 1e-6:
                # Potongan selalu dimulai dengan letak yang berlaku saat itu.
                dalam.insert(0, {"t": 0.0, "facecam": fc})
            tata = susun_layout_gaming(dalam, src_w=sw, src_h=sh,
                                       out_w=out_w, out_h=out_h)
            keluar.append((a, b, {"mode": "gaming", "layout": tata,
                                  "alasan": "Permainan dan wajah pemain, bingkai game"}))
        elif l == "wajah":
            bidik = _bidikan_wajah(plan, a, b, out_w, out_h)
            if bidik is not None:
                keluar.append((a, b, {"mode": "box", "rect": bidik,
                                      "alasan": "Hanya wajah, dibidik dari ukuran wajahnya"}))
            else:
                keluar.append((a, b, {"mode": "smart", "alasan": "Hanya wajah, mengikuti wajah"}))
        elif ada_game:
            # Klip permainan yang sedang TIDAK memperlihatkan wajah pemainnya.
            #
            # Dulu potongan seperti ini diserahkan ke "ikut gerakan", dan itu
            # keliru untuk permainan: kamera yang mengejar ledakan dan ayunan
            # pedang membuat gambarnya bergoyang, sementara yang ingin dilihat
            # penonton adalah permainannya sendiri. Diminta pemiliknya:
            # "jika hanya menampilkan game maka bingkai facecam dihilangkan dan
            # susunan bingkai dibuat untuk bermain game".
            #
            # Satu bidang, seluruh layar permainan, tanpa bidang wajah sama
            # sekali. Bidangnya memakai `susun_layout_gaming` dengan tinggi
            # wajah nol supaya bentuknya dihitung penyusun yang sama.
            keluar.append((a, b, {
                "mode": "layout", "alasan": "Hanya permainan, satu bingkai penuh",
                "layout": _layout_permainan_penuh(sw, sh, out_w, out_h)}))
        else:
            keluar.append((a, b, {"mode": "motion",
                                  "alasan": "Tanpa wajah, kamera mengikuti gerakan"}))
    return keluar


def _layout_permainan_penuh(sw: int, sh: int, out_w: int, out_h: int) -> dict:
    """
    Satu bidang berisi permainannya saja, memenuhi kanvas.

    Potongan tengah dari gambar sumbernya: itulah yang dilakukan orang saat
    memotong gameplay lebar jadi tegak, dan tidak ada wajah yang perlu
    dihindari karena memang tidak ada yang terlihat.
    """
    rasio_sumber = sw / max(1, sh)
    rasio_tujuan = out_w / max(1, out_h)
    if rasio_sumber >= rasio_tujuan:
        lebar = 100.0 * rasio_tujuan / rasio_sumber
        src = {"x": round((100.0 - lebar) / 2, 2), "y": 0.0,
               "w": round(lebar, 2), "h": 100.0}
    else:
        tinggi = 100.0 * rasio_sumber / rasio_tujuan
        src = {"x": 0.0, "y": round((100.0 - tinggi) / 2, 2),
               "w": 100.0, "h": round(tinggi, 2)}
    return {"background": "black",
            "frames": [{"label": "Permainan", "src": src,
                        "dst": {"x": 0, "y": 0, "w": 100, "h": 100}, "fit": "cover"}]}


# Dinaikkan setiap kali ATURAN penggolongan berubah. Simpanannya tanpa batas
# umur, jadi tanpa nomor ini video yang sudah pernah digolongkan akan tetap
# memakai keputusan lama selamanya. v2: facecam di tepi kiri/kanan pada
# ketinggian berapa pun ikut terbaca (27 September 2026).
JENIS_VERSI = 2

JENIS_GAME_MIN = 0.30          # porsi sampel "wajah di pojok" untuk disebut klip game
JENIS_GAME_YAKIN = 0.70        # ... tanpa perlu memeriksa panel facecam
JENIS_GERAK_MIN = 0.60         # porsi sampel tanpa wajah untuk disebut klip tanpa wajah


def jenis_klip(src: Path, segments: list[dict]) -> dict:
    """
    Bingkai bawaan untuk SATU klip, dari isinya: {"mode", "alasan", "porsi"}.

    Studio dulu membuka setiap klip dengan "ikut wajah" — cara yang benar
    untuk podcast, tapi klip game jadi close-up wajah di kamera pojok, dan
    klip tanpa orang jadi pusat layar yang diam. Aturannya dari pemilik:
      - ada permainan dan wajah pemain (facecam)  → bingkai game;
      - tidak ada wajah                            → ikuti gerakan;
      - wajah jelas (podcast, vlog, wawancara)     → ikuti wajah.
    Penggolongnya sama dengan yang dipakai sutradara per momen
    (`_label_per_sampel`), jadi keduanya tidak saling membantah.
    """
    from .media import probe
    from .reframe import deteksi_facecam_waktu, plan_reframe
    from .render import rasio_bidang_wajah

    info = probe(str(src))
    sw, sh = int(info.get("width") or 1920), int(info.get("height") or 1080)

    def facecam() -> bool:
        try:
            return bool(deteksi_facecam_waktu(str(src), segments, sw, sh,
                                              rasio_potongan=rasio_bidang_wajah(1080, 1920)))
        except Exception as e:
            log.info("Facecam tidak terbaca: %s", str(e)[:120])
            return False

    # Rencana yang SAMA dengan yang diminta pratinjau (track_only, 9:16), jadi
    # pindaian wajahnya tersimpan di cache dan jejak ikut-wajah berikutnya
    # tidak menghitung ulang.
    plan = plan_reframe(str(src), segments, aspect_ratio="9:16", track_only=True)
    label = _label_per_sampel(plan) if plan is not None and plan.people else []
    if not label:
        # Tanpa satu wajah pun, facecam juga tidak ada. Pemindai panel tidak
        # ditanya di sini: pada kartun ia menemukan "panel" di mana-mana.
        return {"mode": "motion", "porsi": {"gerak": 1.0},
                "alasan": "Tidak ada wajah, kamera mengikuti gerakan"}

    n = len(label)
    porsi = {k: round(label.count(k) / n, 2) for k in ("game", "wajah", "gerak")}
    # Wajah kecil di pojok hampir sepanjang klip sudah cukup jadi bukti;
    # panelnya baru diperiksa bila buktinya setengah-setengah.
    if porsi["game"] >= JENIS_GAME_YAKIN or (porsi["game"] >= JENIS_GAME_MIN and facecam()):
        return {"mode": "gaming", "porsi": porsi,
                "alasan": "Klip game, permainan dan kamera wajah pemain"}
    if porsi["gerak"] + porsi["game"] >= JENIS_GERAK_MIN:
        # Wajah di pojok tanpa panel facecam yang terbaca dihitung sebagai
        # "tanpa wajah jelas": mengikuti wajah sekecil itu memotong gambarnya.
        return {"mode": "motion", "porsi": porsi,
                "alasan": "Wajah jarang terlihat, kamera mengikuti gerakan"}
    return {"mode": "smart", "porsi": porsi, "alasan": "Wajah terlihat jelas, mengikuti wajah"}


def jenis_klip_tersimpan(video_id: str, src: Path, segments: list[dict]) -> dict:
    """`jenis_klip` yang diingat: menghitungnya memakan 10-60 detik per klip."""
    from ..repos import cache as cache_repo

    kunci = f"jenis:v{JENIS_VERSI}:" + video_id + ":" + ",".join(
        f"{float(s['start']):.2f}-{float(s['end']):.2f}" for s in segments)
    try:
        lama = cache_repo.ambil(kunci, ttl=float("inf"))
        if lama:
            return lama
    except Exception:
        pass
    hasil = jenis_klip(src, segments)
    try:
        cache_repo.simpan(kunci, hasil)
    except Exception as e:
        log.info("Jenis klip tidak tersimpan: %s", e)
    return hasil


# Potongan "hanya wajah": seberapa tinggi bidikannya terhadap tinggi wajahnya.
#
# Wajah setinggi w piksel diberi bidikan setinggi 3,6w. Angka itu bukan selera:
# di bawah 3 kepala hampir menyentuh tepi atas, di atas 4,5 ruang kosong di
# sekeliling kepala lebih besar daripada kepalanya sendiri.
WAJAH_BIDIK_TINGGI = 3.6
# Mata duduk sedikit di atas tengah bidikan, seperti pada potret.
#
# 0,42 menyisakan sejalur tipis gambar di atas kepala pada sumber yang wajahnya
# berupa kotak di tengah gambar lain — terlihat di render uji sebagai pita
# hijau setinggi 4% di tepi atas. 0,36 menurunkan bidikannya sedikit tanpa
# memotong rambut.
WAJAH_BIDIK_ATAS = 0.36
# Bidikan tidak pernah lebih pendek dari ini terhadap tinggi bingkai sumber.
#
# Memperbesar berarti memperbesar pula setiap piksel yang sudah ada. Potongan
# setinggi 60% bingkai sumber sudah diperbesar 1,67 kali lipat lebih banyak
# daripada potongan setinggi bingkai penuh, dan di bawah itu wajahnya mulai
# terlihat lembek di layar ponsel.
WAJAH_BIDIK_PENDEK_MAKS = 0.60


def _bidikan_wajah(plan, a: float, b: float, out_w: int, out_h: int) -> Optional[dict]:
    """
    Bidikan untuk potongan "hanya wajah" yang wajahnya TIDAK memenuhi layar.

    Dibuat 7 Oktober 2026 sesudah pemiliknya mengirim satu kasus yang jelas:
    pada klip Mobile Legends-nya, video beralih ke gaya "webcam diperbesar di
    atas permainan yang diburamkan". Penggolong sudah benar menandainya "hanya
    wajah", tapi `smart` memotong satu kolom SETINGGI BINGKAI PENUH — dan di
    gambar seperti itu, separuh kolomnya berisi permainan buram di atas kepala.
    Terlihat di hasil render: wajahnya di bawah, latar hijau buram di atas.

    Jadi untuk potongan semacam ini bidikannya dihitung dari UKURAN WAJAHNYA,
    bukan dari tinggi bingkai. Bila wajahnya memang sudah besar — bidikan yang
    keluar setinggi bingkai — None dikembalikan dan `smart` tetap dipakai,
    karena di situ mengikuti wajah lebih baik daripada kotak yang diam.
    """
    from .reframe import SAMPLE_FPS

    sw, sh = plan.source_w, plan.source_h
    i0, i1 = int(a * SAMPLE_FPS), int(b * SAMPLE_FPS)
    titik: list[tuple[float, float, float]] = []
    for pi in range(len(plan.people)):
        for i in range(i0, min(i1, len(plan.people_seen[pi]))):
            kotak = plan.people_box[pi][i] if i < len(plan.people_box[pi]) else None
            x = plan.people[pi][i]
            if plan.people_seen[pi][i] and kotak and x is not None:
                titik.append((float(x), float(kotak[0]), float(kotak[1])))
    if len(titik) < 3:
        return None
    titik.sort(key=lambda t: t[2])
    x, cy, w = titik[len(titik) // 2]

    tinggi = WAJAH_BIDIK_TINGGI * w
    if tinggi >= sh * 0.92:
        # Wajahnya sudah memenuhi layar: tidak ada yang bisa diperbaiki dengan
        # memotong, dan mengikuti wajah lebih tahan terhadap gerakannya.
        return None
    tinggi = max(tinggi, sh * WAJAH_BIDIK_PENDEK_MAKS)
    lebar = tinggi * (out_w / max(1, out_h)) * (1.0)
    if lebar > sw:
        lebar = sw
        tinggi = min(sh, lebar * out_h / max(1, out_w))
    x0 = min(max(0.0, x - lebar / 2), max(0.0, sw - lebar))
    y0 = min(max(0.0, cy - tinggi * WAJAH_BIDIK_ATAS), max(0.0, sh - tinggi))
    return {"x": round(x0 / sw * 100, 2), "y": round(y0 / sh * 100, 2),
            "w": round(lebar / sw * 100, 2), "h": round(tinggi / sh * 100, 2)}


def _kotak_dari_wajah(plan, a: float, b: float) -> Optional[dict]:
    """Kotak facecam perkiraan dari wajah pojok yang paling sering terlihat."""
    from .reframe import SAMPLE_FPS
    sw, sh = plan.source_w, plan.source_h
    i0, i1 = int(a * SAMPLE_FPS), int(b * SAMPLE_FPS)
    terbaik = None
    for p in range(len(plan.people)):
        titik = []
        for i in range(i0, min(i1, len(plan.people_seen[p]))):
            kotak = plan.people_box[p][i] if i < len(plan.people_box[p]) else None
            x = plan.people[p][i]
            if plan.people_seen[p][i] and kotak and x is not None \
                    and _wajah_pojok(float(x), float(kotak[0]), float(kotak[1]), sw, sh):
                titik.append((float(x), float(kotak[0]), float(kotak[1])))
        if titik and (terbaik is None or len(titik) > len(terbaik)):
            terbaik = titik
    if not terbaik:
        return None
    titik = sorted(terbaik)
    x, cy, w = titik[len(titik) // 2]
    lebar, tinggi = 2.4 * w, 2.4 * w * 0.9
    x0 = min(max(0.0, x - lebar / 2), sw - lebar)
    y0 = min(max(0.0, cy - tinggi * 0.45), sh - tinggi)
    return {"x": x0 / sw * 100, "y": y0 / sh * 100, "w": lebar / sw * 100, "h": tinggi / sh * 100}


def _pasang_dasar_waktu(kunci: list[dict], dasar_waktu: list, terpilih: list[dict]) -> list[dict]:
    """
    Mengganti bingkai dasar tunggal dengan bingkai dasar per potongan waktu.
    Momen reaksi tetap di atasnya; sesudah momen, bingkai kembali ke dasar
    yang berlaku PADA DETIK ITU, bukan dasar awal klip.
    """
    rentang = [(float(u["mulai"]), float(u["selesai"])) for u in terpilih]

    def dasar_di(t: float) -> dict:
        for a, b, k in dasar_waktu:
            if a - 1e-6 <= t < b:
                return k
        return dasar_waktu[-1][2]

    baru: list[dict] = []
    for k in kunci:
        if k.get("_dasar"):
            continue
        if k.get("_kembali"):
            d = dasar_di(k["t"])
            k = {"t": k["t"], **{x: v for x, v in d.items() if x != "alasan"},
                 "asal": "otomatis", "alasan": d.get("alasan", "Kembali ke bingkai dasar")}
        baru.append(k)
    for a, b, d in dasar_waktu:
        if any(m0 - 1e-6 <= a < m1 for m0, m1 in rentang):
            continue
        baru.append({"t": round(a, 2), **{x: v for x, v in d.items() if x != "alasan"},
                     "asal": "otomatis", "alasan": d.get("alasan", "")})
    baru.sort(key=lambda k: k["t"])
    # Kunci berurutan dengan bingkai yang sama tidak mengubah apa pun.
    ringkas: list[dict] = []
    for k in baru:
        if ringkas and ringkas[-1].get("mode") == k.get("mode") \
                and ringkas[-1].get("layout") == k.get("layout") and not k.get("momen_id"):
            continue
        ringkas.append(k)
    if ringkas:
        ringkas[0]["t"] = 0.0
    return ringkas


def jadikan_kunci(hasil: dict, *, plan, facecam: Optional[dict], momen_lokal: list[dict],
                  durasi: float, src_w: int, src_h: int, out_w: int, out_h: int,
                  model: str, dasar_waktu: Optional[list] = None) -> tuple[list[dict], list[str]]:
    """(kunci bingkai, catatan) dari jawaban model — divalidasi, bukan dipercaya."""
    from .momen import jangkar_terdekat
    from .sutradara import kotak_reaksi

    catatan: list[str] = []
    gameplay = facecam is not None
    dasar_nama = hasil.get("bingkai_dasar") or ("gameplay" if gameplay else "ikuti_penutur")
    if dasar_nama == "gameplay" and not gameplay:
        dasar_nama = "ikuti_penutur"
    # Sutradara TIDAK memakai bilah kabur, di mana pun — keputusan pemiliknya,
    # setelah menunggu lama dan hanya mendapat bingkai kabur. Pilihannya
    # empat: ikuti wajah, ikuti gerakan, game, dan susunan. Wajah yang jarang
    # terlihat berarti yang diikuti adalah GERAKAN, bukan gambar utuh berlatar
    # kabur.
    dasar = {"gameplay": {"mode": "gaming"}, "ikuti_gerakan": {"mode": "motion"},
             "lebar": {"mode": "motion"}}.get(dasar_nama, {"mode": "smart"})
    if dasar["mode"] == "smart" and (plan is None or not plan.usable):
        dasar = {"mode": "motion"}

    def bingkai(b: dict, t0: float, t1: float) -> Optional[dict]:
        jenis = b.get("bingkai")
        orang = [p for p in (_label_ke_orang(x) for x in b.get("orang") or [])
                 if p is not None and _terlihat(plan, p, t0, t1)]
        cukup = [p for p in orang if _lebar_wajah(plan, p, t0, t1) >= WAJAH_MIN_PX]
        if jenis in ("wajah", "reaksi_terbagi") and orang and not cukup:
            return dict(dasar)                   # wajahnya terlalu kecil untuk diperbesar
        orang = cukup if jenis in ("wajah", "reaksi_terbagi") else orang
        if jenis in ("wajah", "reaksi_terbagi") and len(orang) == 1 and plan is not None:
            return _wajah_tunggal(plan, orang[0], t0, t1, out_w, out_h)
        if jenis == "wajah" and orang and plan is not None:
            return _wajah_tunggal(plan, orang[0], t0, t1, out_w, out_h)
        if jenis == "reaksi_terbagi" and plan is not None:
            orang = _saring_bersamaan(plan, orang, t0, t1)
            if len(orang) == 1:
                # Yang tersisa satu orang (sisanya kembaran dari bidikan lain):
                # wajah tunggal, bukan momen yang dibuang.
                return _wajah_tunggal(plan, orang[0], t0, t1, out_w, out_h)
            lay = _susunan_terbagi(plan, orang, t0, t1, out_w, out_h)
            return {"mode": "layout", "layout": lay} if lay else None
        if jenis == "reaksi_penuh" and facecam:
            # Satu bingkai susunan yang memenuhi layar — sama dengan "kotak
            # tetap" di hasilnya, tapi termasuk cara yang boleh dipakai sutradara.
            return {"mode": "layout", "layout": {"background": "black", "frames": [{
                "label": "Reaksi", "src": kotak_reaksi(facecam, src_w, src_h),
                "dst": {"x": 0, "y": 0, "w": 100, "h": 100}, "fit": "cover"}]}}
        if jenis == "gameplay" and gameplay:
            return {"mode": "gaming"}
        if jenis in ("ikuti_gerakan", "lebar"):
            return {"mode": "motion"}
        if jenis == "ikuti_penutur" and plan is not None and plan.usable:
            return {"mode": "smart"}
        return None

    usulan = []
    lemah = 0
    for m in hasil.get("momen") or []:
        try:
            mulai, selesai = float(m.get("mulai")), float(m.get("selesai"))
        except (TypeError, ValueError):
            continue
        if not (0 <= mulai < durasi) or selesai <= mulai:
            continue
        # Tempel ke bukti lokal: nomor momen yang disebut model dulu, lalu
        # bukti terdekat. Waktu model sendiri hanya dipakai bila tidak ada
        # bukti sama sekali di dekatnya.
        jangkar = None
        mid = m.get("momen_id")
        if isinstance(mid, int) and 0 <= mid < len(momen_lokal):
            kandidat = momen_lokal[mid]
            # Nomor yang disebut model hanya dipercaya bila waktunya memang
            # dekat: nomor yang tertukar menggeser momen ke tawa lain.
            if kandidat["mulai"] - TEMPEL_DETIK <= mulai <= kandidat["akhir"] + 0.5:
                jangkar = kandidat
        if jangkar is None:
            jangkar = jangkar_terdekat(momen_lokal, mulai, TEMPEL_DETIK)
        if jangkar is not None:
            geser = max(0.0, jangkar["mulai"] - MENDAHULUI) - mulai
            if abs(geser) <= TEMPEL_DETIK + 0.5:
                mulai, selesai = mulai + geser, selesai + geser
        selesai = min(selesai, mulai + MOMEN_MAKS, durasi)
        if selesai - mulai < BIDIKAN_MIN:
            continue
        try:
            kekuatan = float(m.get("kekuatan") or 0.5)
        except (TypeError, ValueError):
            kekuatan = 0.5
        if kekuatan > 1.0:                       # model yang menjawab 0-100
            kekuatan /= 100.0
        kekuatan = max(0.0, min(1.0, kekuatan))
        # Model memberi 1,0 hampir ke semua momen (terukur), jadi angkanya
        # sendirian tidak bisa memilih. Ia diimbangi bukti yang TERDENGAR:
        # tawa/sorak/lonjakan suara lokal di titik itu. Momen tanpa bukti apa
        # pun masih boleh lolos, tapi kalah dari yang terbukti saat berebut
        # tempat (JARAK_MOMEN_MIN).
        bukti = float(jangkar["kuat"]) if jangkar is not None else 0.35
        kekuatan = round(0.5 * kekuatan + 0.5 * bukti, 3)
        if kekuatan < KEKUATAN_MIN:
            lemah += 1
            continue
        usulan.append({"mulai": mulai, "selesai": selesai, "kekuatan": kekuatan,
                       "alasan": (m.get("alasan") or "").strip()[:200],
                       "bidikan": m.get("bidikan") or [], "berbukti": jangkar is not None,
                       "momen_id": jangkar["id"] if jangkar else -1})

    # Jarak minimum antar momen: yang lebih kuat menang.
    terpilih: list[dict] = []
    for u in sorted(usulan, key=lambda u: (-u["kekuatan"], -u["berbukti"])):
        if all(u["selesai"] + JARAK_MOMEN_MIN <= v["mulai"] or v["selesai"] + JARAK_MOMEN_MIN <= u["mulai"]
               for v in terpilih):
            terpilih.append(u)
    terpilih.sort(key=lambda u: u["mulai"])

    alasan_dasar = {"smart": "Mengikuti yang sedang bicara", "gaming": "Permainan + facecam",
                    "motion": "Wajah jarang terlihat, mengikuti gerakan"}.get(
                        dasar["mode"], "Bingkai dasar")
    kunci: list[dict] = [{"t": 0.0, **dasar, "asal": "ai", "alasan": alasan_dasar,
                          "_dasar": True}]
    for u in terpilih:
        t = u["mulai"]
        bidikan = []
        for b in u["bidikan"]:
            try:
                d = float(b.get("durasi") or 0)
            except (TypeError, ValueError):
                d = 0.0
            d = max(BIDIKAN_MIN, d or 1.0)
            if t + BIDIKAN_MIN > u["selesai"]:
                break
            akhir = min(u["selesai"], t + d)
            bidikan.append((t, b, akhir))
            t = akhir
        if not bidikan:
            continue
        # Kotak wajah dihitung per potongan KAMERA, bukan per bidikan: studio
        # podcast berpindah kamera di tengah tawa, dan kotak yang dihitung dari
        # dua bidikan sekaligus jatuh di tempat orang lain.
        pecah = []
        for tt, b, akhir in bidikan:
            for a0, a1 in _potongan(plan, tt, akhir):
                kk = bingkai(b, a0, a1)
                pecah.append((round(a0, 2), kk if kk is not None else dict(dasar)))
        if all(k == dasar for _t, k in pecah):
            continue                             # tidak ada yang bisa dibingkai
        bidikan = []
        for tt, k in pecah:                      # potongan berurutan yang sama disatukan
            if bidikan and bidikan[-1][1] == k:
                continue
            bidikan.append((tt, k))
        for i, (tt, k) in enumerate(bidikan):
            kunci.append({"t": tt, **k, "asal": "ai", "momen_id": u["momen_id"],
                          "alasan": u["alasan"] if i == 0 else f"{u['alasan']} (lanjutan)"})
        kunci.append({"t": round(u["selesai"], 2), **dasar, "asal": "ai",
                      "alasan": "Kembali ke bingkai dasar", "_kembali": True})

    # Bidikan terakhir yang terlalu pendek karena terpotong batas klip dibuang,
    # dan kunci yang jatuh persis di ujung klip tidak berguna.
    kunci = [k for k in kunci if k["t"] < durasi - BIDIKAN_MIN or k["t"] == 0.0]

    # Bagian tanpa wajah: kamera mengikuti GERAKAN.
    #
    # "Ikut wajah" pada bagian yang TIDAK ada wajahnya hanya membekukan
    # jendela sempit di tempat wajah terakhir terlihat — terlapor pada klip
    # Minecraft: bidikan drone atas menara, dan yang masuk klip cuma sepotong
    # rumput di tengah. Versi pertama melebarkannya jadi gambar utuh berlatar
    # kabur; itu juga ditolak — layar harus tetap penuh. Yang diikuti di
    # bagian itu adalah apa yang bergerak.
    if dasar_waktu:
        kunci = _pasang_dasar_waktu(kunci, dasar_waktu, terpilih)
        jenis_ada = {k["mode"] for _a, _b, k in dasar_waktu}
        nama = {"gaming": "game", "smart": "ikuti wajah", "motion": "ikuti gerakan"}
        catatan.append("Bingkai dasar per bagian: "
                       + ", ".join(f"{sum(1 for _a, _b, k in dasar_waktu if k['mode'] == m)}× {nama[m]}"
                                   for m in ("gaming", "smart", "motion") if m in jenis_ada) + ".")
    elif dasar["mode"] == "smart":
        n_gerak = 0
        for a, b in _tanpa_wajah(plan, durasi):
            alasan = f"Tidak ada wajah di layar ({b - a:.0f} dtk), kamera mengikuti gerakan"
            bentrok = [k for k in kunci if abs(k["t"] - a) < 0.4]
            if bentrok:
                # Klip yang DIBUKA tanpa wajah: kunci dasar di detik 0 yang
                # diganti, bukan bagiannya yang dilewati.
                awal = bentrok[0]
                if awal["t"] == 0.0 and awal.get("mode") == "smart" and not awal.get("momen_id"):
                    awal.update({"mode": "motion", "asal": "otomatis", "alasan": alasan})
                else:
                    continue
            else:
                kunci.append({"t": round(a, 2), "mode": "motion", "asal": "otomatis",
                              "alasan": alasan})
            if b < durasi - BIDIKAN_MIN:
                kunci.append({"t": round(b, 2), **dasar, "asal": "otomatis",
                              "alasan": "Wajah terlihat lagi"})
            n_gerak += 1
        if n_gerak:
            catatan.append(f"{n_gerak} bagian tanpa wajah mengikuti gerakan.")

    for k in kunci:
        k.pop("_dasar", None)
        k.pop("_kembali", None)
    _tanpa_kabur(kunci)
    kunci.sort(key=lambda k: k["t"])
    catatan.append(f"{len(terpilih)} momen disusun oleh {model}"
                   + (f" ({sum(1 for u in terpilih if u['berbukti'])} cocok dengan bukti suara/gambar)"
                      if terpilih else "") + ".")
    if lemah:
        catatan.append(f"{lemah} momen dilewati karena reaksinya kecil.")
    if len(usulan) > len(terpilih):
        catatan.append(f"{len(usulan) - len(terpilih)} usulan dibuang karena terlalu rapat "
                       "dengan momen yang lebih kuat.")
    return kunci, catatan


# --- Titik masuk ------------------------------------------------------------------
def susun_ai(src: Path, segments: list[dict], *, subtitles: list[dict],
             api_key: str, models: list[str], out_w: int = 1080, out_h: int = 1920,
             video_id: Optional[str] = None,
             kabar: Optional[Callable[[str, float], None]] = None,
             batal: Optional[Callable[[], None]] = None) -> dict:
    """
    {jenis, keys, layers, catatan, momen, model, pemakaian}. Melempar bila
    model tidak bisa dihubungi — pemanggil jatuh ke `sutradara.susun`.
    """
    from .media import probe
    from .momen import cari_momen, ringkas
    from .penyedia_ai import pekerjaan, tanya
    from .reframe import deteksi_facecam, plan_reframe
    from .render import rasio_bidang_wajah

    def lapor(pesan: str, bagian: float) -> None:
        if kabar is not None:
            kabar(pesan, bagian)
        if batal is not None:
            batal()

    src = Path(src)
    info = probe(src)
    sw, sh = int(info.get("width") or 1920), int(info.get("height") or 1080)
    durasi = sum(float(s["end"]) - float(s["start"]) for s in segments)
    turns = [(float(l["start"]), float(l["end"]), int(l["speaker"]))
             for l in subtitles or []
             if l.get("speaker") is not None and l.get("end") is not None]

    lapor("Memindai wajah dan orang di klip…", 0.05)
    plan = plan_reframe(str(src), segments, aspect_ratio="9:16", speaker_turns=turns)
    lapor("Mencari facecam…", 0.3)
    facecam = deteksi_facecam(src, float(segments[0]["start"]), min(durasi, 30.0), sw, sh,
                              rasio_potongan=rasio_bidang_wajah(out_w, out_h))
    lapor("Mendengarkan tawa, sorak, dan kejutan…", 0.4)
    kata = [{"s": float(l["start"]), "e": float(l["end"])}
            for l in subtitles or [] if l.get("start") is not None and l.get("end") is not None]
    momen_lokal = cari_momen(src, segments, plan=plan, words=kata)

    with tempfile.TemporaryDirectory(prefix="omniclip_sutradara_") as tmp:
        tmp = Path(tmp)
        lapor("Menyiapkan klip untuk ditonton…", 0.5)
        jalur_proksi = tmp / "proksi.mp4"
        video = _proksi(src, segments, jalur_proksi)
        if video is None:
            raise RuntimeError("Klip tidak bisa disiapkan untuk ditonton.")
        wajah, orang = _lembar_wajah(src, segments, plan, tmp / "wajah.jpg")

        jenis_tebakan = "gameplay (ada facecam pemain)" if facecam else (
            f"{len(orang)} orang terlihat" if orang else "tanpa wajah yang jelas")
        teks = (
            f"Durasi klip: {durasi:.1f} detik. Tebakan jenis: {jenis_tebakan}.\n"
            f"Orang di lembar wajah: {', '.join(f'P{p}' for p in orang) or '(tidak ada)'}.\n\n"
            f"=== MOMEN TERUKUR (dari suara dan gambar, waktunya tepat) ==="
            f"\n{ringkas(momen_lokal)}\n\n"
            f"=== TRANSKRIP (detik klip) ===\n{_transkrip_klip(subtitles)}\n\n"
            "Tentukan bingkai dasar dan momen-momen yang layak diubah bingkainya."
        )
        bahan = [{"video": video, "fps": PROKSI_FPS}]
        if wajah:
            bahan.append({"gambar": wajah})
        bahan.append({"teks": teks})

        def cadangan() -> list[dict]:
            """
            Bahan untuk model yang tidak bisa menonton video: gambar kunci,
            suara klip, dan teks yang sama. Dibuat hanya bila benar-benar
            dipakai — untuk Gemini ia tidak pernah dipanggil sama sekali.
            """
            gambar = _bingkai_kunci(jalur_proksi, durasi, tmp)
            suara = _suara_klip(jalur_proksi, tmp / "suara.mp3")
            isi: list[dict] = [{"gambar": g} for g in gambar]
            if wajah:
                isi.append({"gambar": wajah})
            if suara:
                isi.append({"suara": suara, "format": "mp3"})
            isi.append({"teks": teks + (
                f"\n\n(Anda menerima {len(gambar)} gambar berurutan dari klip ini, "
                "bukan videonya. Detik klip tertulis di pojok kanan atas tiap "
                "gambar, pakai angka itu.)" if gambar else "")})
            return isi

        # Ditandai supaya kartu Pemakaian AI menyebut pekerjaannya dengan
        # benar. Tanpa penanda, belasan panggilan per video tercatat sebagai
        # "ai" begitu saja, dan yang menghabiskan jatah harian jadi tidak
        # terlihat oleh siapa pun.
        with pekerjaan("bingkai", video_id):
            hasil, model, pakai = tanya(
                bahan, schema=_schema(), sistem=SISTEM, api_key=api_key, models=models,
                suhu=0.3, maks_keluaran=8192, cadangan=cadangan,
                kabar=lambda p: lapor(p, 0.6), batal=batal)

    lapor("Menyusun bingkai…", 0.95)
    # Facecam yang ada sepanjang klip memakai bingkai game untuk seluruhnya;
    # selain itu bingkai dasarnya dinilai per saat (game / wajah / gerakan).
    dasar_waktu = None if facecam else _dasar_per_waktu(plan, src, segments, durasi, out_w, out_h)
    kunci, catatan = jadikan_kunci(hasil, plan=plan, facecam=facecam,
                                   momen_lokal=momen_lokal, durasi=durasi,
                                   src_w=sw, src_h=sh, out_w=out_w, out_h=out_h, model=model,
                                   dasar_waktu=dasar_waktu)
    jenis = hasil.get("jenis_video") or ("gameplay" if facecam else "podcast")
    log.info("Sutradara AI (%s): %s, %d kunci, %d momen lokal, token %s",
             model, jenis, len(kunci), len(momen_lokal), pakai)
    return {"jenis": jenis, "keys": kunci, "layers": [], "catatan": catatan,
            "momen": [{k: v for k, v in m.items() if k != "bukti"} for m in momen_lokal],
            "model": model, "pemakaian": pakai, "versi": VERSI_PROMPT,
            "mentah": hasil}


# --- Tanpa AI: pola podcast dari bukti lokal --------------------------------------
def susun_lokal(src: Path, segments: list[dict], *, subtitles: list[dict],
                out_w: int = 1080, out_h: int = 1920) -> dict:
    """
    Sutradara tanpa model: gameplay lewat `sutradara.susun`, podcast lewat
    bukti lokal — tawa/sorak yang didengar YAMNet dan cukup kuat, dengan dua
    orang atau lebih yang wajahnya cukup besar dan terlihat → reaksi terbagi.
    Momen dengan satu wajah terlihat dibiarkan: bidikannya sudah close-up.
    """
    from . import sutradara
    from .media import probe
    from .momen import cari_momen
    from .reframe import plan_reframe

    hasil = sutradara.susun(src, segments, out_w=out_w, out_h=out_h)
    if hasil.get("keys"):
        hasil.pop("facecam", None)
        _tanpa_kabur(hasil["keys"])
        return hasil

    info = probe(src)
    sw, sh = int(info.get("width") or 1920), int(info.get("height") or 1080)
    durasi = sum(float(s["end"]) - float(s["start"]) for s in segments)
    turns = [(float(l["start"]), float(l["end"]), int(l["speaker"]))
             for l in subtitles or [] if l.get("speaker") is not None and l.get("end") is not None]
    plan = plan_reframe(str(src), segments, aspect_ratio="9:16", speaker_turns=turns)
    if plan is None or not plan.people:
        # Tidak ada wajah sama sekali (pemandangan, permainan tanpa facecam):
        # seluruh klip mengikuti gerakan — bukan gambar utuh berlatar kabur.
        return {**hasil, "jenis": "lainnya", "layers": [],
                "keys": [{"t": 0.0, "mode": "motion", "asal": "otomatis",
                          "alasan": "Tidak ada wajah, kamera mengikuti gerakan"}],
                "catatan": ["Tidak ada wajah di klip ini, kamera mengikuti gerakan."]}
    kata = [{"s": float(l["start"]), "e": float(l["end"])} for l in subtitles or []
            if l.get("start") is not None and l.get("end") is not None]
    momen = cari_momen(src, segments, plan=plan, words=kata)

    tiruan = {"bingkai_dasar": "ikuti_penutur", "momen": []}
    for m in momen:
        if not ({"tawa", "sorak", "teriak", "kejut"} & set(m["jenis"])) or m["kuat"] < 0.8:
            continue
        t0, t1 = m["mulai"], min(m["akhir"] + 0.5, m["mulai"] + 3.0)
        terlihat = [p for p in range(len(plan.people))
                    if _terlihat(plan, p, t0, t1) and _lebar_wajah(plan, p, t0, t1) >= WAJAH_MIN_PX]
        if len(terlihat) < 2:
            continue
        tiruan["momen"].append({
            "mulai": t0, "selesai": t1, "kekuatan": m["kuat"], "momen_id": m["id"],
            "alasan": "Terdengar " + ", ".join(j for j in m["jenis"] if j in ("tawa", "sorak", "teriak"))
                      + ", wajah yang terlihat ditumpuk",
            "bidikan": [{"bingkai": "reaksi_terbagi", "orang": [f"P{p}" for p in terlihat[:3]],
                         "durasi": t1 - t0}]})
    kunci, catatan = jadikan_kunci(tiruan, plan=plan, facecam=None, momen_lokal=momen,
                                   durasi=durasi, src_w=sw, src_h=sh, out_w=out_w, out_h=out_h,
                                   model="mesin lokal",
                                   dasar_waktu=_dasar_per_waktu(plan, src, segments, durasi,
                                                                out_w, out_h))
    for k in kunci:
        k["asal"] = "otomatis"
    if len(kunci) == 1 and kunci[0].get("mode") != "smart":
        # Satu kunci yang BUKAN ikut wajah tetap sebuah keputusan: wajahnya
        # jarang terlihat, jadi seluruh klip mengikuti gerakan.
        return {"jenis": "lainnya", "keys": kunci, "layers": [], "momen": [],
                "catatan": catatan}
    if len(kunci) <= 1:
        return {"jenis": "podcast", "keys": [], "layers": [], "momen": momen,
                "catatan": ["Tidak ada tawa atau sorak yang cukup kuat dengan beberapa wajah terlihat."]}
    momen = [{k: v for k, v in m.items() if k != "bukti"} for m in momen]
    return {"jenis": "podcast", "keys": kunci, "layers": [], "momen": momen, "catatan": catatan}


# --- Cache hasil ---------------------------------------------------------------------
def _kunci_cache(video_id: str, segments: list[dict], mesin: str) -> str:
    """
    Satu klip yang sama tidak perlu ditonton dua kali.

    Yang masuk kuncinya: video, rentang detiknya, mesin yang memakainya, dan
    kedua nomor versi. Versi ikut karena memperbaiki perintah atau cara
    menyusun bingkai berarti mengubah hasilnya — tanpa itu, perbaikan apa pun
    akan terus mengembalikan hasil lama sampai cachenya kedaluwarsa, yaitu
    sebulan.
    """
    import hashlib
    sidik = hashlib.sha1(
        json.dumps([[round(float(s["start"]), 2), round(float(s["end"]), 2)]
                    for s in segments]).encode()).hexdigest()[:12]
    return f"sutradara:{video_id}:{sidik}:{mesin}:v{VERSI_PROMPT}.{VERSI_SUSUN}"


# Sengaja panjang: hasil sutradara tidak basi selama klipnya tidak berubah, dan
# kuota model jauh lebih mahal daripada satu baris di basis data.
CACHE_HARI = 30


# --- Menerapkan hasil ke klip tersimpan ----------------------------------------------
def terapkan_ke_klip(video_id: str, clip_id: str, kunci: list[dict]) -> bool:
    """
    Menuliskan kunci bingkai ke klip di dalam analisis tersimpan.

    Dipakai jalur OTOMATIS, saat tidak ada siapa pun di Studio yang bisa
    menerapkannya. Kunci buatan pengguna tidak pernah ditimpa: bila klip itu
    sudah punya kunci yang asalnya bukan mesin, hasil AI dilewati.
    """
    from ..repos import analyses as analyses_repo

    cached = analyses_repo.latest_for_video(video_id)
    if not cached:
        return False
    hasil = dict(cached["result"])
    klip = list(hasil.get("clips") or [])
    for i, c in enumerate(klip):
        if str(c.get("clip_id")) != str(clip_id):
            continue
        lama = [k for k in (c.get("frame_keys") or []) if isinstance(k, dict)]
        if any((k.get("asal") or "pengguna") not in ("otomatis", "ai") for k in lama):
            log.info("Klip %s sudah disunting tangan, bingkai AI dilewati", clip_id)
            return False
        klip[i] = {**c, "frame_keys": kunci}
        hasil["clips"] = klip
        analyses_repo.replace_result(cached["id"], hasil)
        return True
    return False


# --- Job ----------------------------------------------------------------------------
def run_sutradara(ctx) -> dict:
    """
    Job "sutradara". payload: {video_id, segments, subtitles, aspect_ratio,
    mesin: "ai"|"lokal", gemini_model?, clip_id?, terapkan?}.

    Hasilnya usulan kunci bingkai. Saat diminta dari Studio, Studio yang
    menerapkannya ke klip supaya bisa dibatalkan seperti suntingan lain; saat
    dijadwalkan otomatis sesudah auto-klip (`terapkan`), job ini menuliskannya
    sendiri ke analisis tersimpan karena tidak ada siapa pun yang menunggunya.
    """
    from ..config import get_api_key, get_model_override
    from ..errors import JobCancelled
    from ..repos import cache as cache_repo
    from .paths import find_local_video
    from .peringkat_model import CADANGAN_KLIP, rantai
    from .render import PLAY_RES

    p = ctx.payload
    src = find_local_video(p["video_id"])
    if src is None:
        raise RuntimeError("Video sumber belum diunduh.")
    segments = [{"start": float(s["start"]), "end": float(s["end"])} for s in p["segments"]]
    subtitles = p.get("subtitles") or []
    out_w, out_h = PLAY_RES.get(p.get("aspect_ratio") or "9:16", (1080, 1920))

    def kabar(pesan: str, bagian: float) -> None:
        ctx.progress(min(0.97, bagian), stage="sutradara", message=pesan)
        ctx.check_cancelled()

    def selesai(hasil: dict, pesan: str) -> dict:
        if p.get("terapkan") and p.get("clip_id") and hasil.get("keys"):
            hasil["diterapkan"] = terapkan_ke_klip(p["video_id"], p["clip_id"], hasil["keys"])
        ctx.progress(1.0, stage="done", message=pesan)
        return hasil

    kunci_cache = _kunci_cache(p["video_id"], segments, p.get("mesin", "ai"))
    tersimpan = cache_repo.ambil(kunci_cache, ttl=CACHE_HARI * 24 * 3600)
    if tersimpan and tersimpan.get("keys"):
        log.info("Sutradara: memakai hasil tersimpan untuk %s", p["video_id"])
        return selesai(dict(tersimpan), "Bingkai diambil dari hasil sebelumnya.")

    from . import openrouter

    api_key = get_api_key()
    catatan_gagal = None
    # Kunci Gemini bukan lagi syarat: OpenRouter sendirian pun cukup untuk
    # menonton klip, dan sesudah kuota harian Gemini habis ia satu-satunya yang
    # tersisa.
    if p.get("mesin", "ai") == "ai" and (api_key or openrouter.aktif()):
        try:
            hasil = susun_ai(src, segments, subtitles=subtitles, api_key=api_key,
                             video_id=p.get("video_id"),
                             # `sisakan`: sutradara bingkai mengalah pada
                             # pemilihan klip. Ia punya mesin lokal yang
                             # hasilnya masih masuk akal; pemilihan klip tidak
                             # punya penggantinya. Lihat CADANGAN_KLIP.
                             models=(rantai(api_key, p.get("gemini_model")
                                            or get_model_override() or None,
                                            sisakan=CADANGAN_KLIP)
                                     if api_key else []),
                             out_w=out_w, out_h=out_h, kabar=kabar, batal=ctx.check_cancelled)
            hasil.pop("mentah", None)
            n = sum(1 for k in hasil["keys"] if k.get("alasan") and "Kembali" not in k["alasan"]) - 1
            cache_repo.simpan(kunci_cache, hasil)
            return selesai(hasil,
                           f"{max(0, n)} bidikan reaksi disusun oleh {hasil['model']}.")
        except JobCancelled:
            raise
        except Exception as e:
            log.warning("Sutradara AI gagal, memakai mesin lokal: %s", str(e)[:300])
            sibuk = any(x in str(e) for x in ("503", "UNAVAILABLE", "timeout", "batas waktu"))
            habis = any(x in str(e) for x in ("429", "RESOURCE_EXHAUSTED", "limit"))
            catatan_gagal = ("AI sedang sibuk" if sibuk else
                             "Kuota AI habis" if habis else "AI gagal") + ", disusun mesin lokal."
    elif p.get("mesin", "ai") == "ai":
        catatan_gagal = ("Kunci Gemini maupun OpenRouter belum diisi, "
                         "disusun mesin lokal.")

    kabar("Menyusun dari bukti suara dan wajah (mesin lokal)…", 0.4)
    hasil = susun_lokal(src, segments, subtitles=subtitles, out_w=out_w, out_h=out_h)
    hasil["model"] = None
    if catatan_gagal:
        hasil["catatan"] = [catatan_gagal, *hasil.get("catatan", [])]
    # Hasil mesin lokal TIDAK di-cache: ia murah dihitung ulang, dan menyimpannya
    # berarti klip ini tidak pernah lagi ditawarkan ke AI ketika kuotanya pulih.
    return selesai(hasil, catatan_gagal or "Disusun mesin lokal.")
