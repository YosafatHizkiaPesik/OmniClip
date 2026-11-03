"""
Token bertanda tangan untuk bahan Montase yang dibaca TANPA sesi masuk.

Dua pembaca tidak membawa cookie sesi OmniClip:
  - iframe kotak pasir pratinjau (asal `null`, JOB-4.md bagian 20);
  - Chrome headless milik Mesin Montase saat merender (bagian 19).
Keduanya membaca bahan lewat `/api/montase/t/<token>/...`. Token membuktikan
bahwa alamat itu dibuat oleh OmniClip untuk satu lingkup tertentu (misalnya
"uji" atau "proyek:mt_8f3a2c"), dan kedaluwarsa dengan sendirinya.

Rahasianya lahir sekali per proses dan tidak pernah disimpan. Akibatnya token
mati saat backend dijalankan ulang, dan itu disengaja: pratinjau yang masih
terbuka cukup meminta token baru, sementara tidak ada rahasia di cakram yang
bisa dicuri bersama salinan cadangan basis data.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

_RAHASIA = secrets.token_bytes(32)
BERLAKU_BAWAAN = 6 * 3600


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _dari_b64(teks: str) -> bytes:
    return base64.urlsafe_b64decode(teks + "=" * (-len(teks) % 4))


def _tanda(isi: bytes) -> str:
    return _b64(hmac.new(_RAHASIA, isi, hashlib.sha256).digest()[:24])


def buat(lingkup: str, berlaku_detik: int = BERLAKU_BAWAAN) -> str:
    """Token untuk `lingkup`, berlaku `berlaku_detik` dari sekarang."""
    if not lingkup or "|" in lingkup:
        raise ValueError("lingkup token tidak sah")
    isi = f"{lingkup}|{int(time.time()) + int(berlaku_detik)}".encode("utf-8")
    return f"{_b64(isi)}.{_tanda(isi)}"


def lingkup(token: str) -> str | None:
    """Lingkup token bila tanda tangannya sah dan belum kedaluwarsa, selain itu None."""
    try:
        bagian_isi, tanda = token.split(".", 1)
        isi = _dari_b64(bagian_isi)
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(_tanda(isi), tanda):
        return None
    try:
        nama, kedaluwarsa = isi.decode("utf-8").rsplit("|", 1)
        if int(kedaluwarsa) < time.time():
            return None
    except (ValueError, UnicodeDecodeError):
        return None
    return nama


def sah(token: str, untuk: str) -> bool:
    """Token sah DAN lingkupnya persis `untuk`."""
    return lingkup(token) == untuk
