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

from dataclasses import dataclass
from typing import Literal, Optional

Position = Literal["top", "middle", "bottom"]


@dataclass
class CaptionStyle:
    font: str = "DejaVu Sans"
    size: int = 96
    primary: str = "#FFFFFF"
    highlight: str = "#FFE500"
    outline_px: int = 7
    shadow_px: int = 3
    position: Position = "bottom"
    margin_v: int = 300
    uppercase: bool = True
    animation: Literal["karaoke_pop", "block", "none"] = "karaoke_pop"
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
    """
    c = color.lstrip("#")
    if len(c) != 6:
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
    hook_color = hex_to_ass(hook.color) if hook else "&H0000E5FF&"
    align = ALIGNMENT.get(st.position, 2)

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{st.font},{st.size},{primary},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{st.outline_px},{st.shadow_px},{align},90,90,{st.margin_v},1
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
        words = line.get("words") or []
        raw_text = (line.get("text") or "").strip()
        if not raw_text:
            continue

        if st.animation == "karaoke_pop" and words:
            for idx, word in enumerate(words):
                parts = []
                for k, other in enumerate(words):
                    token = other["w"].upper() if st.uppercase else other["w"]
                    token = escape_ass(token)
                    if k == idx:
                        # Kata aktif: berganti warna dan memantul singkat.
                        parts.append(
                            f"{{\\c{highlight}\\fscx112\\fscy112"
                            f"\\t(0,90,\\fscx100\\fscy100)}}{token}{{\\r}}"
                        )
                    else:
                        parts.append(token)
                start = word["s"]
                end = words[idx + 1]["s"] if idx + 1 < len(words) else line["end"]
                if end <= start:
                    end = start + 0.08
                events.append(
                    f"Dialogue: 0,{_ts(start)},{_ts(end)},Caption,,0,0,0,,{' '.join(parts)}"
                )
        else:
            text = raw_text.upper() if st.uppercase else raw_text
            events.append(
                f"Dialogue: 0,{_ts(line['start'])},{_ts(line['end'])},Caption,,0,0,0,,"
                f"{escape_ass(text)}"
            )

    # --- Watermark -------------------------------------------------------------
    if watermark.strip() and clip_duration > 0:
        events.append(
            f"Dialogue: 0,{_ts(0)},{_ts(clip_duration)},Mark,,0,0,0,,"
            f"{escape_ass(watermark.strip())}"
        )

    return head + "\n".join(events) + "\n"
