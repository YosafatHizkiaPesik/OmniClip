"""
Gerbang tinjau sebelum sebuah klip naik PUBLIK (JOB-2 F0-4).

Kebijakan YouTube untuk konten yang digunakan ulang menolak "zero-touch
generation": klip yang dipotong mesin lalu langsung terbit tanpa ada orang
yang meninjau atau menambah apa pun. Sampai 9 Oktober 2026 OmniClip memang
bisa begitu: render yang dimulai orang langsung diunggah publik oleh
`unggah.setelah_render`, tanpa `fyp.periksa`, tanpa kredit, dan tanpa batas.

Gerbangnya sengaja sederhana dan setiap alasannya bisa dibaca orang:

  1. Tidak ada temuan BERAT dari `fyp.periksa` (terlalu pendek, terlalu
     panjang, tiga detik pertama sunyi, tanpa subtitle).
  2. Kredit video sumber ada di deskripsinya (F0-2).
  3. Skor nilai tambah (F3-1) cukup. BELUM dipasang: skornya belum ada. Akan
     ditambahkan di sini begitu F3-1 selesai, dan sampai saat itu gerbang ini
     tidak berpura-pura menilainya.

Yang tidak lolos tidak dibuang: unggahan OTOMATIS diturunkan ke *private*
dengan alasannya dicatat, jadi klipnya tetap naik dan orangnya tinggal
memeriksa lalu menerbitkannya sendiri. Unggahan MANUAL tidak diubah, karena
orang yang menekan tombolnya sedang meninjau saat itu juga; yang ia dapat
adalah alasan yang sama, tampil di formulir.
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("omniclip.gerbang")


def nilai(meta: Optional[dict], *, sumber: Optional[dict] = None,
          pakai_kredit: bool = True) -> dict:
    """
    {lolos, alasan: [str], fyp: {...}} untuk satu klip.

    `meta` adalah sidecar klipnya. Tanpa sidecar, klip itu tidak bisa dinilai
    sama sekali, dan itu sendiri alasan untuk tidak menerbitkannya otomatis.
    """
    from . import fyp
    from .unggah import kredit

    alasan: list[str] = []
    hasil_fyp = None
    if not meta:
        alasan.append("Catatan isi klipnya tidak ada, jadi klip ini tidak bisa diperiksa.")
    else:
        hasil_fyp = fyp.periksa(meta)
        for c in hasil_fyp.get("catatan") or []:
            if c.get("berat") == "berat":
                alasan.append(f"{c.get('judul')}.")
    if not (pakai_kredit and kredit(sumber)):
        alasan.append("Deskripsinya tidak menyebut video sumber.")
    return {"lolos": not alasan, "alasan": alasan, "fyp": hasil_fyp}


def untuk_klip(clip_name: str, profil_id: int) -> dict:
    """`nilai()` untuk satu klip jadi, dengan setelan kredit profilnya."""
    from . import profil
    from .analitik import _sidecar
    from .unggah import sumber_klip

    setel = profil.unggah(profil_id)
    return nilai(_sidecar(clip_name, profil_id),
                 sumber=sumber_klip(clip_name, profil_id),
                 pakai_kredit=setel.get("kredit", True) is not False)
