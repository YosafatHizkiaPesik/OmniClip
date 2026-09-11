"""
Kartu judul di awal klip.

Bentuk yang dikenal penonton: judul besar menahan layar sebentar, dibacakan
suara, lalu klipnya jalan. Yang membuatnya bekerja bukan tulisannya — melainkan
bahwa penonton sudah tahu klip ini tentang apa sebelum sempat menggulir pergi.

Tiga cara menampilkannya, dan ketiganya berbeda bukan sekadar hiasan:

- `overlay` — klipnya langsung mulai, judul menutupi sebagiannya beberapa detik.
  Tidak ada waktu yang terbuang, dan cocok untuk klip yang pembukaannya sendiri
  sudah kuat.
- `freeze`  — satu bingkai klip dibekukan sebagai latar, judul di atasnya, baru
  klipnya mulai dari awal. Klipnya utuh, tapi jadi lebih panjang.
- `zoom`    — sama seperti `freeze`, hanya gambarnya merayap membesar selama
  judul dibaca. Gerakan kecil itu yang membedakan "kartu judul" dari "video ini
  macet".

Kartunya disusun DI DALAM graf yang sama dengan klipnya, bukan dirender jadi
berkas lalu disambung. Dua alasan: menyambung berkas berarti mengkodekan ulang
dua kali, dan — yang lebih penting — dua jalur kode yang berbeda antara
pratinjau dan hasil akhir adalah persis cara pratinjau mulai berbohong.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .subtitles import escape_ass, hex_to_ass

log = logging.getLogger("omniclip.titlecard")

MODES = ("overlay", "freeze", "zoom")

# Ragam gaya kartu. Kembaran dari frontend/src/features/studio/cardStyles.js —
# `id` dan angka-angkanya HARUS sama, karena dua berkas inilah yang menentukan
# apakah judul di pratinjau sama dengan judul di MP4.
#
# `border` adalah BorderStyle ASS: 1 = garis tepi + bayangan, 3 = kotak buram
# yang warnanya diambil dari BackColour. `outline` dan `shadow` ditulis dalam
# satuan kanvas 1920 lalu diskalakan ke tinggi kanvas sebenarnya, sama seperti
# ukuran hurufnya.
VARIANTS: dict[str, dict] = {
    "garis":  {"border": 1, "outline": 9,  "shadow": 4,  "kotak": False},
    "kotak":  {"border": 3, "outline": 14, "shadow": 0,  "kotak": True},
    "bayang": {"border": 1, "outline": 0,  "shadow": 11, "kotak": False},
    "polos":  {"border": 1, "outline": 3,  "shadow": 2,  "kotak": False},
}
DEFAULT_VARIANT = "garis"

# Jeda sesudah suara selesai, supaya kartunya tidak berganti tepat di suku kata
# terakhir. Diukur dengan telinga, bukan dihitung.
VOICE_TAIL_SECONDS = 0.55
MIN_SECONDS = 1.2
MAX_SECONDS = 12.0

# Seberapa jauh gambar membesar selama kartu tampil, dari ujung ke ujung.
ZOOM_TOTAL = 0.12


@dataclass
class TitleCardSpec:
    enabled: bool = False
    text: str = ""
    mode: str = "freeze"
    seconds: float = 3.0          # dipakai bila tanpa suara
    voice: bool = True
    voice_id: str = "piper-news"
    rate: float = 1.05
    size: int = 104               # pada kanvas tinggi 1920
    color: str = "#FFFFFF"
    shadow: str = "#000000"
    # Letak judul di dalam kanvas, dalam PERSEN — bukan piksel. Kanvasnya bisa
    # 1080 lebar (9:16) atau 1920 (16:9), jadi piksel berarti tempat yang
    # berbeda-beda per rasio; persen tidak. pos_x/pos_y adalah titik TENGAH
    # kotak teks, box_w lebarnya sekaligus lebar pembungkus barisnya.
    pos_x: float = 50.0
    pos_y: float = 50.0
    box_w: float = 84.0
    variant: str = DEFAULT_VARIANT
    # Font kartu mengikuti font subtitle klipnya kecuali disetel sendiri.
    # Dua font berbeda dalam satu klip terbaca sebagai dua tangan yang berbeda,
    # dan pratinjau memang menggambar keduanya dengan font yang sama.
    font: str = "Montserrat"

    @classmethod
    def from_payload(cls, data: Optional[dict]) -> "TitleCardSpec":
        if not isinstance(data, dict):
            return cls()
        mode = str(data.get("mode") or "freeze")
        return cls(
            enabled=bool(data.get("enabled")),
            text=str(data.get("text") or "").strip(),
            mode=mode if mode in MODES else "freeze",
            seconds=max(MIN_SECONDS, min(MAX_SECONDS, float(data.get("seconds") or 3.0))),
            voice=bool(data.get("voice", True)),
            voice_id=str(data.get("voice_id") or "piper-news"),
            rate=max(0.6, min(1.6, float(data.get("rate") or 1.05))),
            size=max(28, min(220, int(data.get("size") or 104))),
            color=str(data.get("color") or "#FFFFFF"),
            shadow=str(data.get("shadow") or "#000000"),
            pos_x=max(0.0, min(100.0, float(data.get("pos_x") or 50.0))),
            pos_y=max(0.0, min(100.0, float(data.get("pos_y") or 50.0))),
            box_w=max(20.0, min(100.0, float(data.get("box_w") or 84.0))),
            variant=(str(data.get("variant") or DEFAULT_VARIANT)
                     if str(data.get("variant") or "") in VARIANTS
                     else DEFAULT_VARIANT),
            font=str(data.get("font") or "Montserrat"),
        )


@dataclass
class CardPlan:
    mode: str
    seconds: float
    text: str
    ass_path: Optional[Path] = None
    wav_path: Optional[Path] = None
    voice_seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def adds_time(self) -> bool:
        return self.mode in ("freeze", "zoom")


def _wrap(text: str, per_line: int = 18) -> str:
    """
    Memecah judul jadi beberapa baris pendek.

    Judul kartu dibaca dari jarak satu lengan di layar sekecil telapak tangan;
    baris panjang memaksa hurufnya mengecil, dan judul yang harus dieja bukan
    lagi judul. Pemecahannya di batas kata, dan angka tidak pernah dipisah dari
    satuannya.
    """
    words = (text or "").split()
    if not words:
        return ""
    lines: list[str] = []
    cur = ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > per_line:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return r"\N".join(lines[:4])


def card_ass(spec: TitleCardSpec, seconds: float, out_w: int, out_h: int) -> str:
    """
    Berkas ASS untuk kartunya sendiri: satu judul besar di tengah layar.

    Terpisah dari ASS subtitle klip karena waktunya juga terpisah — kartu
    dimulai dari nol pada linimasanya sendiri, sebelum klipnya ada.
    """
    factor = (out_h or 1920) / 1920.0
    size = max(24, int(round(spec.size * factor)))
    v = VARIANTS.get(spec.variant, VARIANTS[DEFAULT_VARIANT])
    outline = max(0, int(round(v["outline"] * factor)))
    shadow = max(0, int(round(v["shadow"] * factor)))
    primary = hex_to_ass(spec.color)
    outline_c = hex_to_ass(spec.shadow)
    # Gaya "kotak isi" memakai BackColour sebagai pelatnya, jadi warnanya harus
    # buram. Gaya lain memakai BackColour hanya untuk bayangan, dan di situ
    # setengah tembus justru yang benar.
    back_c = (hex_to_ass(spec.shadow) if v["kotak"] else "&H80000000")
    body = _wrap(escape_ass(spec.text.strip().upper()),
                 per_line=max(10, int(round(18 * spec.box_w / 84.0))))

    # Kotak pembungkus baris, dari lebar yang disetel pengguna. MarginL/MarginR
    # pada ASS menjepit kotak tempat teks dipusatkan, jadi keduanyalah yang
    # menentukan di lebar berapa barisnya dibungkus — sama seperti subtitle.
    half = max(10.0, min(100.0, spec.box_w)) / 2.0
    center = max(half, min(100.0 - half, spec.pos_x))
    margin_l = max(0, int(round((center - half) / 100.0 * out_w)))
    margin_r = max(0, int(round((100.0 - center - half) / 100.0 * out_w)))
    # \pos menaruh titik tengah teks persis di tempat yang diseret pengguna.
    # Tanpa itu judul selalu duduk di tengah kanvas dan seretan di pratinjau
    # jadi kebohongan yang baru ketahuan setelah render.
    pos_x = int(round(center / 100.0 * out_w))
    pos_y = int(round(max(0.0, min(100.0, spec.pos_y)) / 100.0 * out_h))

    # Muncul dan hilangnya dilembutkan, dan hurufnya sedikit membesar saat
    # masuk — sama seperti sorotan kata di subtitle, supaya keduanya terbaca
    # sebagai satu tangan yang sama.
    fade_out = 320
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {out_w}
PlayResY: {out_h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kartu,{spec.font},{size},{primary},&H000000FF,{outline_c},{back_c},-1,0,0,0,100,100,0,0,{v["border"]},{outline},{shadow},5,{margin_l},{margin_r},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{_ts(0.0)},{_ts(seconds)},Kartu,,0,0,0,,{{\\an5\\pos({pos_x},{pos_y})\\fad(260,{fade_out})\\fscx104\\fscy104\\t(0,220,\\fscx100\\fscy100)}}{body}
"""


def _ts(t: float) -> str:
    t = max(0.0, float(t))
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def plan_card(spec: TitleCardSpec, workdir: Path, out_w: int, out_h: int) -> Optional[CardPlan]:
    """
    Menyiapkan kartu: membacakan judulnya bila diminta, lalu menulis ASS-nya.

    Panjang kartu MENGIKUTI panjang bacaan, bukan angka yang disetel pengguna.
    Kartu yang berganti sebelum kalimatnya selesai terdengar seperti kesalahan,
    dan itu satu-satunya hal yang pasti diperhatikan penonton.
    """
    if not spec.enabled or not spec.text.strip():
        return None

    notes: list[str] = []
    seconds = max(MIN_SECONDS, min(MAX_SECONDS, spec.seconds))
    wav_path: Optional[Path] = None
    voice_seconds = 0.0

    if spec.voice:
        from . import tts

        if tts.voice_by_id(spec.voice_id)["engine"] == "edge" or tts.available():
            try:
                wav_path = workdir / "title.wav"
                voice_seconds = tts.synthesize(spec.text, wav_path, rate=spec.rate,
                                               voice=spec.voice_id)
                seconds = max(MIN_SECONDS,
                              min(MAX_SECONDS, voice_seconds + VOICE_TAIL_SECONDS))
            except Exception as e:
                log.warning("Pembacaan judul gagal, kartu dibuat tanpa suara: %s", e)
                wav_path = None
                voice_seconds = 0.0
                notes.append("Suara pembaca gagal dibuat — kartu dibuat tanpa suara.")
        else:
            notes.append("Suara pembaca belum terpasang — kartu dibuat tanpa suara.")

    ass_path = workdir / "titlecard.ass"
    ass_path.write_text(card_ass(spec, seconds, out_w, out_h), encoding="utf-8")

    return CardPlan(mode=spec.mode, seconds=round(seconds, 3), text=spec.text.strip(),
                    ass_path=ass_path, wav_path=wav_path,
                    voice_seconds=round(voice_seconds, 3), notes=notes)


def video_filters(plan: CardPlan, in_label: str, card_label: str, main_label: str,
                  out_w: int, out_h: int, fps: int = 30,
                  fontsdir: Optional[str] = None) -> str:
    """
    Bagian graf yang membuat kartunya dari bingkai pertama klip, lalu
    menyambungnya di depan.

    Latarnya diambil dari aliran klip yang SUDAH dipotong dan diskalakan, jadi
    gambar di kartu persis gambar yang akan dilihat penonton sedetik kemudian —
    bukan bingkai mentah 16:9 yang tidak pernah muncul di hasil.
    """
    ass = _ass_arg(plan.ass_path, fontsdir)
    frames = max(2, int(round(plan.seconds * fps)))
    if plan.mode == "zoom":
        still = (
            f"trim=end_frame=1,setpts=PTS-STARTPTS,"
            f"zoompan=z='1+{ZOOM_TOTAL}*on/{frames}':d={frames}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":s={out_w}x{out_h}:fps={fps}"
        )
    else:
        still = (
            f"trim=end_frame=1,setpts=PTS-STARTPTS,"
            f"loop=loop=-1:size=1:start=0,trim=duration={plan.seconds:.3f},"
            f"setpts=PTS-STARTPTS,fps={fps}"
        )
    return (
        f"{in_label}split[{card_label}_src][{main_label}];"
        f"[{card_label}_src]{still},setsar=1,{ass}[{card_label}]"
    )


def audio_filters(plan: CardPlan, wav_index: Optional[int], card_label: str) -> str:
    """
    Suara untuk bagian kartu: pembacaan judul, atau sunyi bila tanpa suara.

    Selalu dibuat sepanjang kartunya persis. Aliran yang lebih pendek dari
    gambarnya membuat `concat` memotong gambar ikut audio, dan kartunya
    berkedip lewat.
    """
    if wav_index is None:
        return (f"anullsrc=r=48000:cl=stereo,atrim=duration={plan.seconds:.3f},"
                f"asetpts=PTS-STARTPTS[{card_label}]")
    return (
        f"[{wav_index}:a]aresample=48000,aformat=channel_layouts=stereo,"
        f"apad=whole_dur={plan.seconds:.3f},atrim=duration={plan.seconds:.3f},"
        f"asetpts=PTS-STARTPTS[{card_label}]"
    )


def overlay_filter(plan: CardPlan, fontsdir: Optional[str] = None) -> str:
    """Mode `overlay`: judulnya digambar di atas klip yang sedang berjalan."""
    return _ass_arg(plan.ass_path, fontsdir)


def _ass_arg(path: Optional[Path], fontsdir: Optional[str]) -> str:
    if path is None:
        return "null"
    arg = str(path).replace("\\", "/").replace(":", r"\:")
    out = f"ass=filename='{arg}'"
    if fontsdir:
        out += f":fontsdir='{fontsdir}'"
    return out
