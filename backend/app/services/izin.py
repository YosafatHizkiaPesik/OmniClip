"""
Catatan izin per kanal sumber (JOB-2 F0-3).

Pemilik menjawab 9 Oktober 2026: belum ada izin dari kreator mana pun yang ia
klip. Jadi berkas ini TIDAK memblokir apa pun. Gunanya dua:

- mengingatkan, saat sebuah klip disiapkan untuk diunggah, bahwa sumbernya
  belum tercatat ada izinnya, beserta akibatnya yang nyata: klaim Content ID
  bisa mengalihkan pendapatan klip ke pemilik aslinya, setransformatif apa pun
  klipnya;
- memberi tempat untuk mencatat izin begitu izin itu didapat, supaya
  peringatannya berhenti untuk kanal itu saja.

Disimpan di setelan global, bukan per profil: izin diberikan oleh pemilik
kanal SUMBER, dan berlaku untuk akun mana pun yang mengklipnya.

Kuncinya nomor kanal bila ada, nama kanal bila tidak. Nomor tidak berubah;
nama bisa. Baris `videos` lama memang tidak punya nomor kanal (lihat F0-1), dan
izin yang dicatat pada nama tetap terbaca untuk baris itu.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from ..repos import settings as settings_repo

log = logging.getLogger("omniclip.izin")

KUNCI = "sumber.izin"

DIIZINKAN = "diizinkan"
BELUM = "belum"


def _semua() -> dict:
    try:
        isi = json.loads(settings_repo.get(KUNCI, "") or "{}")
        return isi if isinstance(isi, dict) else {}
    except (TypeError, ValueError):
        return {}


def _kunci_sumber(sumber: Optional[dict]) -> list[str]:
    """Kunci yang mungkin dipakai untuk satu sumber, yang paling kuat dulu."""
    s = sumber or {}
    out = []
    cid = (s.get("channel_id") or "").strip()
    nama = (s.get("kanal") or "").strip().lower()
    if cid:
        out.append(f"id:{cid}")
    if nama:
        out.append(f"nama:{nama}")
    return out


def status(sumber: Optional[dict]) -> str:
    """`diizinkan` atau `belum`. Sumber yang tak dikenal selalu `belum`."""
    peta = _semua()
    for k in _kunci_sumber(sumber):
        if peta.get(k, {}).get("status") == DIIZINKAN:
            return DIIZINKAN
    return BELUM


def setel(sumber: Optional[dict], diizinkan: bool, catatan: str = "") -> str:
    """
    Mencatat izin untuk kanal sumber ini, di bawah SEMUA kunci yang dikenal.

    Dicatat pada nomor DAN nama sekaligus, supaya baris `videos` lama yang
    hanya punya nama tetap terbaca sebagai diizinkan.
    """
    import time

    kunci = _kunci_sumber(sumber)
    if not kunci:
        raise ValueError("Kanal sumbernya tidak dikenal, jadi izinnya tidak bisa dicatat.")
    peta = _semua()
    for k in kunci:
        if diizinkan:
            peta[k] = {"status": DIIZINKAN, "kanal": (sumber or {}).get("kanal") or "",
                       "catatan": (catatan or "")[:300], "pada": time.time()}
        else:
            peta.pop(k, None)
    settings_repo.set_value(KUNCI, json.dumps(peta, ensure_ascii=False))
    return status(sumber)


def peringatan(sumber: Optional[dict]) -> str:
    """
    Kalimat peringatan untuk layar, atau teks kosong bila tidak perlu.

    Ditulis untuk orang yang akan menekan tombol unggah, jadi ia menyebut
    kanalnya dan akibatnya, bukan pasal kebijakannya.
    """
    if status(sumber) == DIIZINKAN:
        return ""
    kanal = ((sumber or {}).get("kanal") or "").strip()
    siapa = f"kanal {kanal}" if kanal else "kanal sumbernya"
    return (f"Klip ini diambil dari {siapa}, dan belum tercatat ada izin darinya. "
            "Tanpa izin, klaim Content ID bisa mengalihkan pendapatan klip ini "
            "ke pemilik aslinya, seberapa pun besar suntingan Anda. Kredit di "
            "deskripsi membantu, tapi tidak menggantikan izin.")
