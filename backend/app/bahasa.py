"""
Pesan server dalam bahasa antarmuka yang dipilih (JOB-3 J3-11).

Backend menulis pesannya dalam bahasa Indonesia di ratusan tempat: galat,
kabar pekerjaan, baris kesehatan, temuan analitik. Mengubah setiap titik itu
menjadi panggilan terjemahan berarti menyentuh seluruh backend, dan kabar dari
pekerjaan latar bahkan tidak punya permintaan yang bisa ditanyai bahasanya.

Jadi terjemahan dikerjakan di BATAS RESPONS. Frontend mengirim bahasanya
(`Accept-Language`, atau `?lang=` untuk aliran SSE yang tidak bisa membawa
header), dan setiap string di JSON yang keluar dicocokkan dengan katalog
`kamus_en.KATALOG`: kalimat tetap dicocokkan utuh, kalimat berisi angka atau
nama dicocokkan lewat templat `{nama}`. String yang tidak ada di katalog
(judul video, nama kanal, isi transkrip) dibiarkan apa adanya, jadi tidak
ada data pengguna yang ikut berubah.
"""

from __future__ import annotations

import contextvars
import re
from functools import lru_cache
from typing import Any

BAWAAN = "id"
DIDUKUNG = ("id", "en")
_kini: contextvars.ContextVar[str] = contextvars.ContextVar("omniclip_bahasa", default=BAWAAN)


def kini() -> str:
    return _kini.get()


def setel(kode: str):
    return _kini.set(kode if kode in DIDUKUNG else BAWAAN)


def pulihkan(token) -> None:
    _kini.reset(token)


def dari_permintaan(lang_query: str | None, accept_language: str | None) -> str:
    """`?lang=` menang atas header; selain bahasa yang didukung jatuh ke bawaan."""
    for calon in (lang_query, accept_language):
        if not calon:
            continue
        kode = calon.split(",")[0].split(";")[0].strip().lower()[:2]
        if kode in DIDUKUNG:
            return kode
    return BAWAAN


@lru_cache(maxsize=1)
def _katalog():
    from .kamus_en import KATALOG

    tetap: dict[str, str] = {}
    templat: list[tuple[re.Pattern, str]] = []
    for sumber, sasaran in KATALOG:
        if "{" not in sumber:
            tetap[sumber] = sasaran
            continue
        bagian = re.split(r"\{(\w+)\}", sumber)
        pola = ""
        for i, b in enumerate(bagian):
            pola += re.escape(b) if i % 2 == 0 else f"(?P<{b}>.+?)"
        templat.append((re.compile("^" + pola + "$", re.S), sasaran))
    # Templat yang lebih panjang dicoba lebih dulu: lebih spesifik.
    templat.sort(key=lambda x: -len(x[0].pattern))
    return tetap, templat


def teks(s: str, kode: str | None = None) -> str:
    """Satu string ke bahasa `kode` (bawaan: bahasa permintaan ini)."""
    kode = kode or kini()
    if kode == BAWAAN or not s or not isinstance(s, str):
        return s
    tetap, templat = _katalog()
    if s in tetap:
        return tetap[s]
    for pola, sasaran in templat:
        m = pola.match(s)
        if m:
            # Isian templat ikut diterjemahkan bila ia sendiri kalimat yang
            # dikenal, misalnya alasan galat di dalam "Unduhan gagal: {alasan}".
            isi = {k: teks(v, kode) for k, v in m.groupdict().items()}
            return sasaran.format(**isi)
    return s


def terjemahkan(obj: Any, kode: str | None = None) -> Any:
    """Menerjemahkan seluruh string di dalam struktur JSON, tanpa mengubah kuncinya."""
    kode = kode or kini()
    if kode == BAWAAN:
        return obj
    if isinstance(obj, str):
        return teks(obj, kode)
    if isinstance(obj, list):
        return [terjemahkan(x, kode) for x in obj]
    if isinstance(obj, dict):
        return {k: terjemahkan(v, kode) for k, v in obj.items()}
    return obj
