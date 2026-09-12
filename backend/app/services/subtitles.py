"""
Pembuat file ASS untuk subtitle karaoke, teks hook, dan watermark.

Keputusan: ASS dengan event highlight per kata, bukan tag `\\k` dan bukan
drawtext per kata.

Tekniknya: untuk setiap baris caption, dikeluarkan N event Dialogue — satu per
kata — dan SETIAP event merender seluruh baris, hanya kata aktif yang dibungkus
override tag. Karena semua event memuat kata yang sama, tata letak baris tidak
pernah bergeser; hanya warna dan skala satu kata yang berubah. Itulah yang
membuatnya terbaca mulus, bukan meloncat.

Hook juga ditulis sebagai event ASS, bukan drawtext. Ini menghilangkan seluruh
masalah escaping drawtext dan memberi word-wrap gratis.
"""

import logging
from dataclasses import dataclass
from typing import Literal, Optional

log = logging.getLogger("omniclip.subtitles")

Position = Literal["top", "middle", "bottom"]


@dataclass
class CaptionStyle:
    # Montserrat ExtraBold dibundel di app/assets/fonts (SIL OFL). Tanpa font
    # display sendiri, libass jatuh ke DejaVu Sans lewat fontconfig — font teks
    # badan, bukan font judul, dan itulah kenapa hasilnya terlihat murah.
    font: str = "Montserrat"
    size: int = 96
    primary: str = "#FFFFFF"
    highlight: str = "#FFE500"
    outline_px: int = 7
    shadow_px: int = 3
    position: Position = "bottom"
    margin_v: int = 300
    # Penempatan mendatar, dalam PERSEN lebar kanvas — bukan piksel. Kanvas
    # bisa selebar 1080 (9:16) atau 1920 (16:9), jadi margin piksel tetap akan
    # berarti penempatan yang berbeda-beda per rasio. Persen tidak.
    #
    # pos_x adalah titik TENGAH kotak teks, box_w lebarnya. Keduanya bersama
    # membiarkan subtitle ditaruh di pojok kiri, pojok kanan, atau di mana pun,
    # sekaligus menentukan di lebar berapa barisnya mulai dibungkus.
    pos_x: float = 50.0
    box_w: float = 84.0
    uppercase: bool = True
    # karaoke_pop  : kata aktif berganti warna dan memantul (bawaan)
    # karaoke_wipe : kata aktif hanya berganti warna, tanpa memantul
    # fade         : baris masuk dengan pudar
    # slide_up     : baris naik dari bawah lalu diam
    # pop_in       : baris membesar dari kecil
    # block/none   : tanpa animasi apa pun
    animation: Literal["karaoke_pop", "karaoke_wipe", "fade",
                       "slide_up", "pop_in", "block", "none"] = "karaoke_pop"
    # Warna per penutur, DIINDEKS LANGSUNG: speaker_colors[0] milik orang
    # pertama, [1] orang kedua, dan seterusnya. Versi sebelumnya melewati indeks
    # 0 dan memaksa orang pertama memakai `primary`, sehingga warnanya tidak
    # bisa disetel sendiri dan penomoran di UI selalu meleset satu.
    #
    # Nilai bawaan menaruh putih di posisi pertama, jadi video satu narasumber
    # tetap tampil persis seperti sebelum fitur ini ada.
    # Delapan, sama persis dengan daftar di antarmuka.
    #
    # Dulu hanya empat di sini dan delapan di sana, dan selisihnya terlihat
    # persis pada video berpenutur lima: orang kelima berwarna emas di editor
    # dan putih di video. Gaya tersimpan milik pengguna bahkan bisa lebih
    # pendek lagi — `_lengkapi_warna` di bawah menambalnya dari daftar ini,
    # supaya palet yang kependekan tidak pernah berubah jadi putih diam-diam.
    speaker_colors: tuple[str, ...] = ("#FFFFFF", "#7CFFB2", "#FFB3C7", "#B39DFF",
                                       "#FFD166", "#5BC8FF", "#FF9F1C", "#B8FF3A")
    max_words_per_line: int = 5
    max_chars_per_line: int = 22


@dataclass
class HookSpec:
    text: str
    start: float = 0.0
    duration: float = 3.5
    size: int = 64
    color: str = "#00E5FF"


ALIGNMENT = {"bottom": 2, "middle": 5, "top": 8}


def hex_to_ass(color: str) -> str:
    """
    '#RRGGBB' -> '&HBBGGRR&'. ASS memakai urutan byte terbalik.

    Nilai yang tidak terbaca dikembalikan sebagai putih, TAPI dicatat ke log.
    Diamnya versi sebelumnya mahal: satu preset di antarmuka menyimpan
    `var(--danger)` sebagai warna sorotan — sah di peramban, tidak berarti
    apa-apa bagi ffmpeg — dan seluruh subtitle keluar putih di hasil render
    sementara pratinjau menampilkannya merah. Tidak ada satu pun pesan yang
    menunjukkan ada yang salah, jadi yang terlihat hanyalah "warnanya beda".
    """
    c = (color or "").strip().lstrip("#")
    if len(c) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in c):
        log.warning("Warna tidak terbaca: %r — dipakai putih", color)
        return "&H00FFFFFF&"
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H00{b}{g}{r}".upper() + "&"


def _ts(seconds: float) -> str:
    """Format waktu ASS: H:MM:SS.cc (perseratus detik)."""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def escape_ass(text: str) -> str:
    """Hanya tiga karakter yang bermakna khusus di dalam teks ASS."""
    return (text.replace("\\", "\\\\")
                .replace("{", "\\{")
                .replace("}", "\\}")
                .replace("\n", "\\N"))


def _wrap(text: str, max_chars: int = 17) -> str:
    """
    Membungkus teks hook jadi maksimal tiga baris.

    Batas 17 karakter disesuaikan dengan lebar kanvas 1080 dikurangi margin:
    pada ukuran font hook, baris yang lebih panjang akan dibungkus ulang oleh
    libass dan hasilnya menumpuk sampai enam baris.
    """
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\\N".join(lines[:3])


# Animasi yang hanya membungkus baris (bukan menyorot kata). Dipisah dari
# animasi karaoke karena keduanya bisa dipakai bersamaan: baris boleh masuk
# dengan pudar SEKALIGUS menyorot kata satu per satu.
LINE_ENTRY = {"fade", "slide_up", "pop_in"}
KARAOKE = {"karaoke_pop", "karaoke_wipe"}


def _entry_tag(animation: str, *, play_res: tuple[int, int], margin_v: int,
               align: int, budget: float, center_x: Optional[int] = None) -> str:
    """
    Tag ASS untuk animasi masuk satu baris.

    `budget` adalah lama tampil event pertama. Animasi dipotong agar selesai di
    dalam jendela itu: kalau lebih panjang, baris masih bergerak saat event
    berikutnya menggantikannya dan hasilnya terlihat patah.
    """
    if animation not in LINE_ENTRY:
        return ""
    ms = int(max(90, min(240, budget * 1000 * 0.8)))
    if animation == "fade":
        return rf"{{\fad({ms},0)}}"
    if animation == "pop_in":
        return (rf"{{\fscx62\fscy62\t(0,{ms},\fscx100\fscy100)"
                rf"\fad({ms // 2},0)}}")
    # slide_up butuh koordinat absolut, jadi posisinya dihitung dari alignment.
    w, h = play_res
    cx = center_x if center_x is not None else w // 2
    if align in (7, 8, 9):        # atas
        cy = margin_v
    elif align in (4, 5, 6):      # tengah
        cy = h // 2
    else:                         # bawah
        cy = h - margin_v
    return rf"{{\move({cx},{cy + 34},{cx},{cy},0,{ms})\fad({ms // 2},0)}}"


def reconcile_words(line: dict) -> list[dict]:
    """
    Menyelaraskan `words` sebuah baris dengan `text`-nya.

    Sorotan karaoke dibangun dari `words`, sedangkan penyuntingan di editor
    mengubah `text`. Selama keduanya tidak pernah didamaikan, setiap koreksi
    salah dengar hilang tanpa jejak: teksnya berubah di layar editor, lalu
    ffmpeg membakar kata lama ke dalam video — dan tidak ada satu pun pesan
    kesalahan, karena bagi renderer tidak ada yang salah.

    Didamaikan DI SINI, di lapisan yang benar-benar menggambar, supaya klien
    mana pun yang mengirim tidak bisa lagi membuat keduanya berbeda.
    """
    words = [w for w in (line.get("words") or []) if (w.get("w") or "").strip()]
    text = (line.get("text") or "").strip()
    if not text:
        return words
    tokens = text.split()
    if not words or [w["w"] for w in words] == tokens:
        return words if words else _spread(tokens, line)

    # Jumlah kata sama: hampir selalu satu kata salah dengar yang ditukar, jadi
    # waktu aslinya dipertahankan dan sorotan tetap jatuh tepat pada ucapannya.
    if len(words) == len(tokens):
        return [{**w, "w": t} for w, t in zip(words, tokens)]
    return _spread(tokens, line)


def _spread(tokens: list[str], line: dict) -> list[dict]:
    """Membagi rentang baris ke sejumlah kata, ditimbang panjang tiap kata."""
    if not tokens:
        return []
    start = float(line.get("start") or 0.0)
    end = max(float(line.get("end") or start), start + 0.25)
    weights = [len(t) + 1 for t in tokens]
    total = sum(weights)
    out: list[dict] = []
    cursor = start
    for token, weight in zip(tokens, weights):
        dur = (end - start) * weight / total
        out.append({"w": token, "s": round(cursor, 3), "e": round(cursor + dur, 3)})
        cursor += dur
    return out


WARNA_BAWAAN = ("#FFFFFF", "#7CFFB2", "#FFB3C7", "#B39DFF",
                "#FFD166", "#5BC8FF", "#FF9F1C", "#B8FF3A")


def _lengkapi_warna(warna) -> tuple[str, ...]:
    """
    Menambal palet yang kependekan, bukan membiarkannya jadi putih.

    Gaya tersimpan pengguna bisa berasal dari versi lama yang cuma punya tiga
    warna. Dengan lima penutur, dua orang terakhir lalu jatuh ke warna dasar —
    putih — sementara editor menampilkannya berwarna. Perbedaan itu tidak
    pernah terlihat sebagai kesalahan, cuma sebagai "warnanya beda".
    """
    keluar = list(warna or ())
    for i in range(len(keluar), len(WARNA_BAWAAN)):
        keluar.append(WARNA_BAWAAN[i])
    return tuple(keluar)


def build_ass(
    *,
    lines: list[dict],
    style: Optional[CaptionStyle] = None,
    hook: Optional[HookSpec] = None,
    watermark: str = "",
    play_res: tuple[int, int] = (1080, 1920),
    clip_duration: float = 0.0,
) -> str:
    """
    Menyusun file ASS lengkap.

    `lines` memakai bentuk keluaran clipmodel.words_to_caption_lines():
    [{start, end, text, words: [{w, s, e}]}] dengan waktu dalam linimasa KLIP
    (dimulai dari 0).
    """
    st = style or CaptionStyle()
    w, h = play_res

    primary = hex_to_ass(st.primary)
    highlight = hex_to_ass(st.highlight)
    speaker_ass = [hex_to_ass(c) for c in _lengkapi_warna(st.speaker_colors)]
    hook_color = hex_to_ass(hook.color) if hook else "&H0000E5FF&"
    align = ALIGNMENT.get(st.position, 2)

    # MarginL/MarginR pada ASS menjepit kotak tempat teks dipusatkan, jadi
    # menggeser keduanya secara tidak simetris memindahkan teksnya ke kiri atau
    # ke kanan — sekaligus mempersempit lebar pembungkus barisnya.
    half = max(4.0, min(100.0, st.box_w)) / 2.0
    center = max(half, min(100.0 - half, st.pos_x))
    margin_l = max(0, int(round((center - half) / 100.0 * w)))
    margin_r = max(0, int(round((100.0 - center - half) / 100.0 * w)))

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{st.font},{st.size},{primary},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{st.outline_px},{st.shadow_px},{align},{margin_l},{margin_r},{st.margin_v},1
Style: Hook,{st.font},{hook.size if hook else 64},{hook_color},&H000000FF,&H00000000,&HB4000000,-1,0,0,0,100,100,0,0,3,0,0,8,100,100,150,1
Style: Mark,{st.font},34,&H60FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,3,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: list[str] = []

    # --- Hook: sekarang benar-benar ter-render ---------------------------------
    # Versi lama menerima hook_text, menyimpannya ke JSON, lalu tidak pernah
    # menggambarnya — teks hook hanya ilusi CSS di preview.
    if hook and hook.text.strip():
        # Escape DULU, baru bungkus baris. Urutan terbalik membuat penanda
        # ganti baris '\N' ikut ter-escape jadi '\\N', sehingga backslash
        # muncul sebagai karakter di layar.
        text = _wrap(escape_ass(hook.text.strip().upper()))
        end = hook.start + max(1.0, hook.duration)
        events.append(
            f"Dialogue: 0,{_ts(hook.start)},{_ts(end)},Hook,,0,0,0,,"
            f"{{\\fad(250,350)}}{text}"
        )

    # --- Caption ---------------------------------------------------------------
    for line in lines:
        words = reconcile_words(line)
        raw_text = (line.get("text") or "").strip() or " ".join(w["w"] for w in words)
        if not raw_text:
            continue

        # Warna dasar baris ini. Baris yang ditandai pembicara kedua memakai
        # warnanya sendiri; kata yang sedang diucapkan tetap memakai highlight.
        sp = int(line.get("speaker") or 0)
        base = (speaker_ass[sp]
                if 0 <= sp < len(speaker_ass) else primary)
        base_tag = "" if base == primary else f"{{\\c{base}}}"

        # Sorotan per kata TIDAK lagi terikat pada animasi masuk.
        #
        # Dulu hanya mode `karaoke_*` yang menyorot kata, sedangkan pratinjau
        # menyorotnya pada mode apa pun. Akibatnya preset seperti "Papan"
        # (animasi `pop_in`) terlihat mengikuti ucapan kata demi kata di editor
        # lalu keluar sebagai blok diam di video — yang dibaca pengguna sebagai
        # "animasinya hilang". Keduanya memang dua hal yang berbeda: satu
        # mengatur cara BARIS masuk, satu lagi cara KATA disorot, dan tidak ada
        # alasan memilih salah satunya.
        #
        # Pantulan kata tetap khusus `karaoke_pop`, sama seperti di pratinjau.
        if st.animation not in ("none", "block") and words:
            bounce = st.animation == "karaoke_pop"
            masuk = _entry_tag(st.animation, play_res=play_res,
                               margin_v=st.margin_v, align=align,
                               center_x=int(round(center / 100.0 * w)),
                               budget=max(0.2, float(words[0]["e"]) - float(words[0]["s"])))
            for idx, word in enumerate(words):
                start = word["s"]
                end = words[idx + 1]["s"] if idx + 1 < len(words) else line["end"]
                if end <= start:
                    end = start + 0.08

                parts = []
                for k, other in enumerate(words):
                    token = other["w"].upper() if st.uppercase else other["w"]
                    token = escape_ass(token)
                    if k == idx:
                        pop = ("\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)"
                               if bounce else "")
                        parts.append(f"{{\\c{highlight}{pop}}}{token}"
                                     f"{{\\r}}{base_tag}")
                    else:
                        parts.append(token)
                events.append(
                    f"Dialogue: 0,{_ts(start)},{_ts(end)},Caption,,0,0,0,,"
                    # Animasi masuk hanya pada kejadian PERTAMA baris itu.
                    # Menaruhnya di tiap kata berarti barisnya memantul ulang
                    # setiap kali sorotan berpindah.
                    f"{masuk if idx == 0 else ''}{base_tag}{' '.join(parts)}"
                )
        else:
            text = raw_text.upper() if st.uppercase else raw_text
            entry = _entry_tag(st.animation, play_res=play_res,
                               margin_v=st.margin_v, align=align,
                               center_x=int(round(center / 100.0 * w)),
                               budget=max(0.2, line["end"] - line["start"]))
            events.append(
                f"Dialogue: 0,{_ts(line['start'])},{_ts(line['end'])},Caption,,0,0,0,,"
                f"{entry}{base_tag}{escape_ass(text)}"
            )

    # --- Watermark -------------------------------------------------------------
    if watermark.strip() and clip_duration > 0:
        events.append(
            f"Dialogue: 0,{_ts(0)},{_ts(clip_duration)},Mark,,0,0,0,,"
            f"{escape_ass(watermark.strip())}"
        )

    return head + "\n".join(events) + "\n"


# --- Font yang dibundel --------------------------------------------------------
# Satu daftar untuk dua pemakai: libass (lewat `fontsdir`) dan pratinjau di
# browser (lewat @font-face ke /api/fonts/...). Sebelumnya daftar font hanya ada
# di frontend sebagai teks, jadi pratinjau memakai font UI sementara hasil render
# memakai font display — mengganti font "tidak mengubah apa-apa" di layar, dan
# baru terlihat setelah render selesai.
#
# `family` HARUS sama persis dengan nama keluarga di dalam berkasnya, karena
# nilai itulah yang ditulis ke baris Style file ASS dan dicari libass.
BUNDLED_FONTS: list[dict] = [
    {"family": "Montserrat", "file": "Montserrat-ExtraBold.ttf", "weight": 800,
     "label": "Montserrat", "note": "tebal & bulat, gaya CapCut"},
    {"family": "Poppins", "file": "Poppins-ExtraBold.ttf", "weight": 800,
     "label": "Poppins", "note": "geometris, bersih"},
    {"family": "Anton", "file": "Anton-Regular.ttf", "weight": 400,
     "label": "Anton", "note": "sangat tebal dan rapat"},
    {"family": "Archivo Black", "file": "ArchivoBlack-Regular.ttf", "weight": 400,
     "label": "Archivo Black", "note": "blok tebal, sangat tegas"},
    {"family": "Bebas Neue", "file": "BebasNeue-Regular.ttf", "weight": 400,
     "label": "Bebas Neue", "note": "tinggi ramping, huruf besar"},
    {"family": "Oswald", "file": "Oswald-Bold.ttf", "weight": 700,
     "label": "Oswald", "note": "rapat, mudah dibaca"},
    {"family": "Fjalla One", "file": "FjallaOne-Regular.ttf", "weight": 400,
     "label": "Fjalla One", "note": "sempit, hemat ruang"},
    {"family": "Teko", "file": "Teko-Bold.ttf", "weight": 700,
     "label": "Teko", "note": "sangat sempit, banyak kata per baris"},
    {"family": "Lilita One", "file": "LilitaOne-Regular.ttf", "weight": 400,
     "label": "Lilita One", "note": "bulat ramah, gaya kartun"},
    {"family": "Luckiest Guy", "file": "LuckiestGuy-Regular.ttf", "weight": 400,
     "label": "Luckiest Guy", "note": "komik, main-main"},
    {"family": "Bungee", "file": "Bungee-Regular.ttf", "weight": 400,
     "label": "Bungee", "note": "papan reklame, sangat mencolok"},
    {"family": "Rubik", "file": "Rubik-ExtraBold.ttf", "weight": 800,
     "label": "Rubik", "note": "sudut membulat, modern"},
    {"family": "Playfair Display", "file": "PlayfairDisplay-Black.ttf", "weight": 900,
     "label": "Playfair Display", "note": "serif tebal, kesan mewah"},
]

FONT_FILES = {f["file"] for f in BUNDLED_FONTS}
FONT_FAMILIES = {f["family"] for f in BUNDLED_FONTS}
