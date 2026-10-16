"""
Bahasa teks yang ditulis AI (JOB-3 J3-12): judul klip, alasan, tagar, caption,
draf komentar, alasan tema dan bingkai.

Sampai 16 Oktober 2026 semua prompt mematok bahasa Indonesia, jadi orang yang
memakai OmniClip dalam English tetap menerima judul dan draf komentar
berbahasa Indonesia. Bahasanya kini dipilih per akun, di Pengaturan > Klip:

    ui       ikut bahasa antarmuka saat pekerjaan dimulai (bawaan)
    video    ikut bahasa videonya, bila Indonesia atau Inggris
    id, en   selalu bahasa itu

Bahasa antarmuka dibawa oleh setiap permintaan (`app/bahasa.py`) dan ikut
tersimpan di muatan pekerjaan (`bahasa_ui`, lihat jobs.enqueue), jadi
pekerjaan latar yang berjalan jauh sesudahnya tetap tahu bahasanya.

Prompt-nya sendiri tetap ditulis dalam bahasa Indonesia; yang diganti hanya
bahasa KELUARANNYA, lewat `sistem()` dan `perintah()`.
"""

from __future__ import annotations

import contextvars
from typing import Optional

# Video yang sedang dikerjakan pekerjaan latar ini (diisi jobs.py dari muatan),
# untuk pilihan "ikut bahasa video" di tempat yang tidak tahu video_id-nya.
video_kini: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "omniclip_video_ai", default=None)

PILIHAN = ("ui", "video", "id", "en")
NAMA = {"id": "bahasa Indonesia", "en": "bahasa Inggris (English)"}


def _video(video_id: Optional[str]) -> Optional[str]:
    if not video_id:
        return None
    try:
        from ..repos import transcripts as tx_repo
        tx = tx_repo.get_best(video_id) or {}
        kode = str(tx.get("language") or "").lower()[:2]
    except Exception:                                     # noqa: BLE001
        return None
    return kode if kode in NAMA else None


def kode(video_id: Optional[str] = None, video_lang: Optional[str] = None) -> str:
    """'id' atau 'en': bahasa keluaran AI untuk akun aktif."""
    from .. import bahasa
    try:
        from ..repos import profil as profil_repo
        from . import profil
        pilih = str(profil_repo.setelan(profil.kini(), "klip").get("bahasa_ai") or "ui")
    except Exception:                                     # noqa: BLE001
        pilih = "ui"
    if pilih in ("id", "en"):
        return pilih
    if pilih == "video":
        v = (video_lang or "").lower()[:2]
        v = v if v in NAMA else _video(video_id or video_kini.get())
        if v:
            return v
    k = bahasa.kini()
    return k if k in NAMA else "id"


def sistem(teks: str, kode_bahasa: str) -> str:
    """Instruksi sistem dengan bahasa keluaran `kode_bahasa`."""
    if kode_bahasa == "id":
        return teks
    nama = NAMA.get(kode_bahasa, kode_bahasa)
    teks = (teks.replace("berbahasa Indonesia", f"berbahasa {nama.replace('bahasa ', '')}")
                .replace("bahasa Indonesia", nama))
    return teks + perintah(kode_bahasa)


def perintah(kode_bahasa: str) -> str:
    """Kalimat penutup prompt yang mematok bahasa keluaran."""
    if kode_bahasa == "id":
        return ""
    nama = NAMA.get(kode_bahasa, kode_bahasa)
    return (f"\n\nBAHASA KELUARAN: semua teks yang akan dibaca orang (judul, alasan, "
            f"hook, caption, komentar, catatan, tagar) WAJIB ditulis dalam {nama}, "
            f"apa pun bahasa transkripnya. Kutipan ucapan dari transkrip boleh "
            f"tetap dalam bahasa aslinya. Nama kunci JSON tidak diubah.")
