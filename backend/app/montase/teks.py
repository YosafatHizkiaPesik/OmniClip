"""
Gaya teks Montase (JOB-4 M3.1): tema judul OmniClip dan font bawaan.

Satu sumber kebenaran: tema diambil dari `services/tema_judul.py`, tempat yang
sama yang dipakai kartu judul Studio Klip, lalu diterjemahkan ke bentuk
`item.gaya` dokumen Montase. Komposisi tidak menyimpan salinan tema; ia
menggambar angka-angka `gaya` apa adanya, jadi tema yang diubah di sini tidak
mengubah proyek lama diam-diam (gaya sudah tertulis di dokumennya).

Font disajikan lewat alamat bertoken (`/api/montase/t/<token>/font/<keluarga>`)
karena iframe kotak pasir beralamat `null`: hanya rute bertoken yang menjawab
CORS untuknya, dan mesin render memakai alamat yang sama.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import FONTS_DIR

# Kolom `gaya` yang dikenal komposisi (komposisi/item/ItemTeks.jsx).
LATAR = ("tanpa", "pelat", "sorot", "pita", "label")
GERAK = ("muncul", "pop", "hentak", "naik", "turun", "geser", "lempar", "getar", "kedip", "pelan")
PERATAAN = ("kiri", "tengah", "kanan")
UKURAN_DASAR = 96


def font_bawaan() -> list[dict]:
    from ..services.subtitles import BUNDLED_FONTS
    return [{"keluarga": f["family"], "berat": f.get("weight", 400)} for f in BUNDLED_FONTS]


def jalur_font(keluarga: str) -> Optional[Path]:
    """Berkas font bawaan untuk satu keluarga; None bila bukan font bawaan."""
    from ..services.subtitles import BUNDLED_FONTS
    for f in BUNDLED_FONTS:
        if f["family"].lower() == (keluarga or "").lower():
            jalur = FONTS_DIR / f["file"]
            return jalur if jalur.is_file() else None
    return None


def gaya_dari_tema(tema) -> dict:
    """Tema judul -> `item.gaya` Montase. `besar` sudah dikalikan ke ukuran."""
    return {
        "tema": tema.id,
        "font": tema.font,
        "ukuran": round(UKURAN_DASAR * tema.besar),
        "warna": tema.teks,
        "kapital": tema.kapital,
        "latar": tema.latar,
        "warna_latar": tema.warna_latar,
        "alfa_latar": tema.alfa_latar,
        "radius": tema.radius,
        "pad_x": tema.pad_x,
        "pad_y": tema.pad_y,
        "garis": tema.garis,
        "warna_garis": tema.warna_garis,
        "bayang": tema.bayang,
        "kabur": tema.kabur,
        "cip": tema.cip,
        "warna_cip": tema.warna_cip,
        "teks_cip": tema.teks_cip,
        "gerak": tema.gerak if tema.gerak in GERAK else "muncul",
    }


def daftar_gaya() -> list[dict]:
    from ..services import tema_judul
    return [{"id": t.id, "gaya": gaya_dari_tema(t)} for t in tema_judul.TEMA.values()]


def font_dipakai(dokumen: dict) -> list[str]:
    """
    Keluarga font untuk `sumber.font`: yang dipakai item teks, ditambah SEMUA
    font bawaan bila ada animasi buatan AI (kontrak bagian 21 mengizinkannya
    memakai font bawaan mana pun, dan kodenya tidak bisa dibaca dari sini).
    """
    ada_ai = any(i.get("jenis") == "motion" and not str(i.get("komponen", "")).startswith("ko_")
                 for l in dokumen.get("lajur", []) for i in l.get("item", []))
    if ada_ai:
        return [f["keluarga"] for f in font_bawaan() if jalur_font(f["keluarga"])]
    hasil = []
    for lajur in dokumen.get("lajur", []):
        for item in lajur.get("item", []):
            font = (item.get("gaya") or {}).get("font")
            if item.get("jenis") == "teks" and font and font not in hasil and jalur_font(font):
                hasil.append(font)
    return hasil
