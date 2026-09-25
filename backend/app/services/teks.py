"""
Menyambung kata jadi kalimat — dengan atau tanpa spasi, menurut aksaranya.

Bahasa Jepang dan Mandarin tidak memakai spasi antarkata, dan Whisper memecah
keduanya per huruf. Menyambungnya dengan spasi seperti bahasa Indonesia
menghasilkan "あ ぁ 白 で あ った" (terukur pada impor anime). Spasi hanya
disisipkan bila KEDUA sisinya bukan aksara CJK; bahasa Korea tetap berspasi
(Hangul memang memakai spasi).
"""

import re

_CJK = re.compile(
    "[　-〿"        # tanda baca CJK
    "぀-ゟ"         # Hiragana
    "゠-ヿ"         # Katakana
    "ㇰ-ㇿ"         # Katakana tambahan
    "㐀-䶿"         # Han perluasan A
    "一-鿿"         # Han
    "豈-﫿"         # Han kompatibilitas
    "＀-￯]"        # bentuk lebar penuh/setengah
)


def cjk(ch: str) -> bool:
    return bool(ch) and bool(_CJK.match(ch))


def pemisah(kiri: str, kanan: str) -> str:
    """
    Spasi di antara dua token, atau kosong bila KEDUA sisinya CJK.

    Aturan "salah satu sisinya CJK" yang dipakai sebelumnya benar untuk anime
    dan salah untuk kalimat campuran: "Cek 天井 mix" jadi "Cek天井mix" — dua
    kata Indonesia yang menempel pada kata Jepang di tengahnya. Ditemukan oleh
    pengujian, bukan oleh mata.

    Dengan syarat kedua sisi, cacat asalnya tetap tertutup: Whisper memecah
    bahasa Jepang per huruf, dan kedua sisi tiap sambungan memang CJK.
    Akibatnya yang tersisa kecil dan searah — "100日" ditulis "100 日" — dan itu
    masih terbaca, sedangkan kalimat campuran yang menempel tidak.
    """
    kiri, kanan = (kiri or "").rstrip(), (kanan or "").lstrip()
    if not kiri or not kanan:
        return ""
    return "" if cjk(kiri[-1]) and cjk(kanan[0]) else " "


def sambung(tokens) -> str:
    """" ".join untuk semua bahasa."""
    keluar = ""
    for t in tokens:
        t = (t or "").strip()
        if not t:
            continue
        keluar += pemisah(keluar, t) + t
    return keluar


def sambung_bagian(bagian: list[str], mentah: list[str], patah: frozenset = frozenset(),
                   sela: str = " ") -> str:
    """
    Seperti `sambung`, tapi `bagian` boleh berisi tag ASS; `mentah` teks
    polosnya. Sebelum token berindeks di `patah` disisipkan ganti baris ASS.

    `sela` menggantikan spasi biasa di antara kata — dipakai penyusun ASS untuk
    melebarkan jaraknya. Spasi Montserrat ExtraBold sempit, dan pada huruf
    kapital tebal dua kata bersebelahan terbaca sebagai satu kata panjang.
    """
    keluar, sebelum = "", ""
    for i, (b, m) in enumerate(zip(bagian, mentah)):
        if i in patah and keluar:
            keluar += "\\N" + b
        else:
            keluar += (sela if pemisah(sebelum, m) else "") if sebelum else ""
            keluar += b
        sebelum = m or sebelum
    return keluar


def titik_patah(mentah: list[str], per_baris: int) -> frozenset:
    """
    Indeks token tempat baris CJK harus dipatahkan supaya tiap baris muat.

    libass hanya membungkus baris di spasi, dan teks Jepang tidak berspasi:
    tanpa ini satu baris subtitle meluber keluar kanvas (terukur pada impor
    anime). Teks tanpa aksara CJK dikembalikan tanpa patahan — libass
    membungkusnya sendiri seperti biasa.
    """
    if per_baris < 2 or not any(cjk(c) for t in mentah for c in (t or "")):
        return frozenset()
    patah, isi = set(), 0.0
    for i, t in enumerate(mentah):
        lebar = sum(1.0 if cjk(c) else 0.55 for c in (t or ""))
        if isi and isi + lebar > per_baris:
            patah.add(i)
            isi = 0.0
        isi += lebar
    return frozenset(patah)


def bobot_kata(tokens) -> float:
    """
    Jumlah "kata" untuk batas panjang baris. Token CJK sepanjang satu huruf
    dihitung sepertiga kata — Whisper memecah bahasa Jepang per huruf, dan
    batas lima kata jadi baris lima huruf yang berkedip terlalu cepat.
    """
    n = 0.0
    for t in tokens:
        t = (t or "").strip()
        if not t:
            continue
        n += len(t) / 3.0 if all(cjk(c) for c in t) else 1.0
    return n


def lebar_teks(tokens) -> int:
    """Lebar tampil (satuan huruf Latin): huruf CJK selebar dua."""
    teks = sambung(tokens)
    return sum(2 if cjk(c) else 1 for c in teks)


AKHIR_KALIMAT = (".", "!", "?", "…", "。", "！", "？")


def patah_teks(teks: str, per_baris: int) -> str:
    """`titik_patah` untuk teks utuh (sudah di-escape): ganti baris ASS disisipkan."""
    huruf = list(teks or "")
    patah = titik_patah(huruf, per_baris)
    if not patah:
        return teks
    return "".join(("\\N" if i in patah else "") + c for i, c in enumerate(huruf))


_TOKEN = re.compile(
    "[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u31f0-\u31ff\u3400-\u4dbf"
    "\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
    "|[^\\s\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u31f0-\u31ff\u3400-\u4dbf"
    "\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]+")


def pecah(teks: str) -> list[str]:
    """Kebalikan `sambung`: huruf CJK satu per token, sisanya per spasi."""
    return _TOKEN.findall(teks or "")


# --- Tanda pisah panjang --------------------------------------------------------
# Em dash dan en dash hampir tidak pernah diketik orang Indonesia: papan ketik
# biasa tidak punya tombolnya. Karena itu kehadirannya di sebuah caption membuat
# tulisannya langsung terbaca sebagai hasil mesin, dan itulah keluhan yang
# memunculkan fungsi ini. Prompt sudah melarangnya, tapi larangan pada model
# bukan jaminan; ini jaringnya.
_PISAH = "—–‒―"


def tanpa_pisah(teks: str) -> str:
    """
    Mengganti tanda pisah panjang dengan tanda baca yang biasa diketik orang.

    Aturannya mengikuti maksud tandanya, bukan bentuknya:

    - di antara dua angka ia rentang, jadi jadi tanda hubung ("2-8 menit");
    - di antara dua kalimat ia jeda, jadi jadi koma;
    - di awal atau akhir potongan ia hiasan, jadi dibuang.
    """
    import re as _re

    if not teks:
        return teks
    kelas = f"[{_PISAH}]"
    t = _re.sub(rf"(?<=\d)\s*{kelas}\s*(?=\d)", "-", teks)
    # Koma ganda tidak pernah benar: bila sebelahnya sudah ada tanda baca,
    # tandanya cukup dibuang.
    t = _re.sub(rf"\s*{kelas}\s*(?=[,.;:!?])", "", t)
    t = _re.sub(rf"(?<=[,;:])\s*{kelas}\s*", " ", t)
    t = _re.sub(rf"\s+{kelas}\s+", ", ", t)
    t = _re.sub(rf"^\s*{kelas}\s*", "", t, flags=_re.M)
    t = _re.sub(rf"\s*{kelas}\s*$", "", t, flags=_re.M)
    t = _re.sub(kelas, "-", t)
    return _re.sub(r" {2,}", " ", t).strip()
