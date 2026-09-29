"""
Menyensor kata kasar di subtitle: "anjing" jadi "anj*ng".

Diminta pemiliknya 29 September 2026. Alasannya praktis, bukan moral: klip yang
teksnya memuat umpatan utuh diturunkan jangkauannya oleh YouTube, TikTok, dan
Instagram, dan sebagian pengiklan menolaknya sama sekali. Suaranya tetap apa
adanya; yang disensor hanya TEKS yang terbakar di layar.

Yang ditutup hanya satu huruf di tengah, bukan seluruh kata. Penonton tetap
membaca kalimatnya dengan benar, dan mesin penyaring tidak menemukan kata
utuhnya. Itu sebabnya contoh yang diberikan pemiliknya persis seperti ini:
anjing -> anj*ng.

Daftar kata ini SENGAJA pendek dan hanya berisi umpatan yang jelas. Daftar yang
kepanjangan menyensor kata yang tidak salah apa-apa, dan subtitle yang penuh
bintang lebih buruk daripada satu umpatan yang lolos.
"""

from __future__ import annotations

import re
from typing import Iterable

# Kata dasar. Awalan dan akhiran umum (-nya, -lah, -mu, -ku, -an) ikut tertangkap
# lewat pola di bawah, jadi "anjingnya" tidak perlu ditulis sendiri.
#
# Ditulis huruf kecil; pencocokannya mengabaikan besar-kecil huruf, dan
# hasilnya mempertahankan bentuk aslinya (ANJING -> ANJ*NG).
DAFTAR_KASAR: tuple[str, ...] = (
    # --- Umpatan keras, Indonesia ---
    "anjing", "anjeng", "asu", "asw",
    "bangsat", "bajingan", "brengsek", "keparat", "bedebah",
    "goblok", "tolol", "sialan", "kampret", "bacot",
    # Kata badan dan seks. Ini yang paling cepat membuat klip dibatasi.
    "kontol", "memek", "pepek", "peler", "titit", "jembut", "itil", "silit",
    "toket", "ngentot", "entot", "kentot", "ngewe", "coli", "colmek", "bokep",
    # Merendahkan orang.
    "perek", "pelacur", "lonte", "sundal", "jalang", "bispak", "gigolo",
    # Jawa dan Sumatra, sering lewat di klip Indonesia.
    "jancok", "jancuk", "diancuk", "kimak", "pukimak", "puki", "bangke",
    "tai", "taik", "telek",
    # --- Inggris, yang paling sering lewat di klip Indonesia ---
    "fuck", "fucking", "fucker", "motherfucker", "shit", "bullshit",
    "bitch", "asshole", "bastard", "cunt", "whore", "slut", "nigga",
    "dickhead", "wanker", "twat", "pussy",
)
# Yang SENGAJA tidak masuk daftar, supaya subtitle tidak penuh bintang tanpa
# alasan, dan ini keputusan pemiliknya sendiri 29 September 2026 ("jika hanya
# babi atau cok cuk itu masih aman"): "babi", "cok", "cuk", "anjir", "anjay",
# "bodoh", "bego", "setan", "gila", "edan", "sinting", "idiot", "dick".
#
# Semuanya umpatan RINGAN atau kata sehari-hari yang jauh lebih sering dipakai
# dengan wajar. "cok"/"cuk"/"dick" juga terlalu pendek sehingga menabrak
# potongan kata lain. "pantek" dibuang sesudah uji sendiri menangkapnya pada
# "pantekan listrik", istilah kelistrikan yang tidak salah apa-apa.

# Akhiran yang boleh menempel tanpa mengubah maknanya.
_AKHIRAN = ("nya", "lah", "mu", "ku", "an", "in")

# Disusun sekali: kata terpanjang lebih dulu supaya "ngentot" tidak dipotong
# jadi "ngent" + sisanya oleh entri yang lebih pendek.
_POLA = re.compile(
    r"\b(" + "|".join(sorted((re.escape(k) for k in DAFTAR_KASAR), key=len, reverse=True))
    + r")(" + "|".join(_AKHIRAN) + r")?\b",
    re.IGNORECASE,
)


def _tutup(kata: str) -> str:
    """
    Menutup satu huruf di tengah kata, mempertahankan besar-kecil hurufnya.

    Huruf yang ditutup adalah yang di posisi tengah (`len // 2`): untuk
    "anjing" itu huruf keempat, jadi hasilnya "anj*ng" persis seperti contoh
    yang diminta. Kata yang terlalu pendek untuk punya "tengah" ditutup huruf
    keduanya, supaya huruf pertama dan terakhirnya tetap terbaca.
    """
    n = len(kata)
    if n < 3:
        return kata
    i = n // 2 if n >= 4 else 1
    return kata[:i] + "*" + kata[i + 1:]


def sensor_teks(teks: str) -> str:
    """Mengganti kata kasar di sebuah kalimat. Kata lain tidak disentuh."""
    if not teks:
        return teks

    def ganti(m: "re.Match[str]") -> str:
        dasar, akhiran = m.group(1), m.group(2) or ""
        return _tutup(dasar) + akhiran

    return _POLA.sub(ganti, teks)


def ada_kasar(teks: str) -> bool:
    """Apakah kalimat ini memuat kata yang akan disensor."""
    return bool(teks) and _POLA.search(teks) is not None


def sensor_kata_kata(kata_kata: Iterable[dict], medan: str = "w") -> list[dict]:
    """
    Menyensor daftar kata subtitle ({w, start, end, ...}) tanpa mengubah waktunya.

    Subtitle digambar per kata untuk sorotan karaoke, jadi penyensoran harus
    bekerja pada kata satuan juga, bukan hanya pada kalimat utuh.
    """
    keluar = []
    for k in kata_kata or []:
        teks = str(k.get(medan) or "")
        baru = sensor_teks(teks)
        keluar.append(k if baru == teks else {**k, medan: baru})
    return keluar
