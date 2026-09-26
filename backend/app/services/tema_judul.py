"""
Tema judul: huruf, warna, LATAR, dan gerak sebagai satu paket.

Dipakai dua tempat dengan rupa yang sama persis, kartu judul pembuka, dan
judul yang menempel di dalam video sepanjang klip. Kembarannya di
frontend/src/features/studio/temaJudul.js; `id`, warna, jenis latar, dan
fonnya HARUS sama, dan uji `test_tema_judul` menjaganya.

Diminta pemiliknya 27 September 2026: "tambahkan variasi bukan animasinya tapi
keseluruhan tema ada motion dan background". Sepuluh gaya sebelumnya hanya
berbeda gerak masuknya, diam, lima di antaranya terlihat sama: huruf putih
bergaris hitam. Pola yang dipakai di sini diambil dari yang lazim di klip
pendek: kartu judul berkontras tinggi di bingkai pertama, 5-8 kata, latar
padat di belakang teks supaya terbaca di atas gambar apa pun, dan diletakkan di
80% tengah bingkai supaya tidak tertutup tombol aplikasi.

UKURAN HURUF. libass mengartikan ukuran bukan sebagai tinggi em (seperti CSS)
melainkan tinggi "sel" = winAscent + winDescent fonnya. Terukur: Montserrat
ukuran 100 dirender selebar 436 piksel untuk "HALO DUNIA"; dari metrik `win`
dihitung 440,6, dari em 688,2. Jarak antar baris `\\N` tepat sama dengan
ukurannya. Pelat latar dihitung dari angka-angka itu, bukan ditebak, pelat
yang meleset 30% dari teksnya terlihat seperti kesalahan, bukan gaya.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ..config import FONTS_DIR

log = logging.getLogger("omniclip.tema_judul")


# --- Tema ---------------------------------------------------------------------

@dataclass(frozen=True)
class Tema:
    id: str
    label: str
    catatan: str
    font: str                   # nama KELUARGA, bukan nama berkas
    teks: str                   # #RRGGBB
    # "tanpa" | "pelat" (satu pelat untuk semua baris) | "sorot" (satu pelat
    # per baris, seperti stabilo) | "pita" (selebar kanvas) | "label" (pelat +
    # cip kecil di atasnya).
    latar: str = "tanpa"
    warna_latar: str = "#000000"
    alfa_latar: float = 1.0     # 1 = padat, 0 = tembus
    radius: float = 0.22        # pecahan dari ukuran huruf
    pad_x: float = 0.42         # pecahan dari ukuran huruf
    pad_y: float = 0.22
    garis: float = 0.0          # tebal garis tepi huruf, satuan kanvas 1920
    warna_garis: str = "#000000"
    bayang: float = 0.0         # jarak bayangan, satuan kanvas 1920
    kabur: float = 0.0          # \blur pada garis tepi: cahaya untuk tema neon
    kapital: bool = True
    # Cip kecil di atas pelat, untuk latar "label".
    cip: str = ""
    warna_cip: str = "#E11D2E"
    teks_cip: str = "#FFFFFF"
    # Gerak masuk. Satu dari `GERAK` di bawah.
    gerak: str = "muncul"
    # Pengali ukuran tema ini. Fon ramping (Bebas Neue, Anton) pada tinggi
    # kapital yang sama tampak kecil karena hurufnya sempit, terlihat pada
    # render pertama: pita hitam dan merah tebal tampak separuh ukuran kartu
    # putih walau tinggi hurufnya sama.
    besar: float = 1.0


TEMA: dict[str, Tema] = {t.id: t for t in (
    Tema("kartu-putih", "Kartu putih",
         "Pelat putih membulat, huruf hitam tebal. Rupa judul yang paling banyak "
         "dipakai pada klip podcast: terbaca di atas gambar apa pun.",
         font="Montserrat", teks="#111111", latar="pelat", warna_latar="#FFFFFF",
         gerak="pop"),
    Tema("pita-hitam", "Pita hitam",
         "Pita gelap selebar layar dengan huruf tinggi putih. Tegas, seperti "
         "judul tayangan televisi.",
         font="Bebas Neue", teks="#FFFFFF", latar="pita", warna_latar="#0B0B0F",
         alfa_latar=0.88, pad_y=0.30, gerak="turun", besar=1.45),
    Tema("sorot-kuning", "Stabilo kuning",
         "Tiap baris diberi pelat kuning seperti stabilo. Paling mencolok, "
         "cocok untuk klaim yang berani.",
         font="Montserrat", teks="#111111", latar="sorot", warna_latar="#FFE500",
         radius=0.14, pad_x=0.30, pad_y=0.12, gerak="hentak"),
    Tema("berita", "Berita viral",
         "Cip merah bertulisan VIRAL di atas pelat putih. Meniru kabar terkini, "
         "masuk dari samping.",
         font="Montserrat", teks="#111111", latar="label", warna_latar="#FFFFFF",
         radius=0.10, cip="VIRAL", warna_cip="#E11D2E", gerak="geser"),
    Tema("merah-tebal", "Merah tebal",
         "Pelat merah menyala, huruf putih. Untuk judul yang harus langsung "
         "menarik mata.",
         font="Anton", teks="#FFFFFF", latar="pelat", warna_latar="#E11D2E",
         radius=0.18, gerak="pop", besar=1.3),
    Tema("kaca-gelap", "Kaca gelap",
         "Pelat hitam setengah tembus. Tenang dan sinematik, gambar di "
         "belakangnya tetap terasa.",
         font="Montserrat", teks="#FFFFFF", latar="pelat", warna_latar="#000000",
         alfa_latar=0.55, radius=0.28, gerak="naik"),
    Tema("neon", "Neon malam",
         "Huruf biru muda bercahaya di atas pelat gelap. Untuk gaming dan "
         "suasana malam.",
         font="Bungee", teks="#7DF9FF", latar="pelat", warna_latar="#07070D",
         alfa_latar=0.72, garis=5.0, warna_garis="#00B7FF", kabur=6.0,
         gerak="kedip"),
    Tema("horor", "Horor",
         "Huruf merah darah bergaris hitam tebal, bergetar pelan. Untuk "
         "jumpscare dan cerita seram.",
         font="Anton", teks="#D10A0A", latar="pelat", warna_latar="#000000",
         alfa_latar=0.50, garis=7.0, warna_garis="#000000", bayang=4.0,
         gerak="getar", besar=1.35),
    Tema("stiker", "Stiker",
         "Huruf putih dengan garis merah tebal, masuk miring seperti stiker "
         "dilempar.",
         font="Luckiest Guy", teks="#FFFFFF", latar="tanpa", garis=10.0,
         warna_garis="#E11D2E", bayang=6.0, gerak="lempar"),
    Tema("kutipan", "Kutipan",
         "Huruf berkait berwarna krem, tanpa pelat, muncul perlahan. Untuk "
         "kalimat yang menyentuh.",
         font="Playfair Display", teks="#FFF4DC", latar="tanpa", bayang=5.0,
         kapital=False, gerak="pelan"),
)}

BAWAAN = "kartu-putih"


# Gerak masuk: tag ASS, dan lama gerak dalam milidetik (untuk CSS).
#
# Gerak dipasang pada SETIAP bagian judul, pelat, cip, dan tiap baris, dengan
# titik jangkarnya masing-masing. Karena itu yang dipakai hanya gerak yang
# tetap rapi bila tiap bagian bergerak sendiri: memudar, bergeser (semua
# bergeser sama jauh), membesar sedikit, dan berputar di sekitar SATU titik
# (`\org` di tengah blok, jadi seluruh blok berputar sebagai satu benda).
GERAK = {
    "muncul": r"\fad(220,260)",
    "pop": r"\fad(160,260)\fscx88\fscy88\t(0,160,\fscx104\fscy104)\t(160,280,\fscx100\fscy100)",
    "hentak": r"\fad(100,260)\fscx70\fscy70\t(0,130,\fscx110\fscy110)\t(130,250,\fscx100\fscy100)",
    "naik": r"\fad(240,280)",           # geserannya lewat \move, lihat `_gerak`
    "turun": r"\fad(200,280)",
    "geser": r"\fad(160,280)",
    "lempar": r"\fad(140,260)\frz9\fscx84\fscy84\t(0,280,\frz0\fscx100\fscy100)",
    "getar": r"\fad(200,300)\frz1.4\t(0,160,\frz-1.4)\t(160,320,\frz1.4)\t(320,480,\frz-1.2)\t(480,640,\frz0)",
    "kedip": r"\fad(80,260)\alpha&HFF&\t(0,60,\alpha&H00&)\t(60,120,\alpha&H90&)\t(120,200,\alpha&H00&)\t(200,260,\alpha&H60&)\t(260,340,\alpha&H00&)",
    "pelan": r"\fad(700,500)",
}
# Arah dan jarak geser, pecahan dari ukuran huruf.
GESER = {"naik": (0, 0.9), "turun": (0, -0.9), "geser": (-2.4, 0)}


# --- Fon ----------------------------------------------------------------------

@dataclass(frozen=True)
class Metrik:
    per_sel: float      # piksel per satuan fon pada ukuran 1: 1 / (winA + winD)
    naik: float         # winAscent, satuan fon
    turun: float        # winDescent
    kapital: float      # tinggi huruf kapital
    lebar: dict         # kode karakter -> lebar maju
    lebar_ganti: float  # untuk karakter yang tidak ada di fon
    upm: float = 1000.0


@lru_cache(maxsize=32)
def metrik(keluarga: str) -> Optional[Metrik]:
    """Metrik fon dari berkasnya sendiri, dicari lewat nama keluarganya."""
    try:
        from fontTools.ttLib import TTFont
    except Exception:                                # noqa: BLE001
        return None
    for f in sorted(Path(FONTS_DIR).glob("*.[ot]tf")):
        try:
            # Ditutup sesudah dibaca: dengan `lazy`, berkasnya tetap terbuka
            # selama objeknya hidup, dan pencarian ini membuka SEMUA fon.
            with TTFont(f, lazy=True) as t:
                m = _metrik_dari(t, keluarga)
            if m is not None:
                return m
        except Exception as e:                       # noqa: BLE001
            log.info("Fon %s tidak terbaca: %s", f.name, e)
    return None


def _metrik_dari(t, keluarga: str) -> Optional[Metrik]:
    if t["name"].getDebugName(1) != keluarga:
        return None
    os2, hm = t["OS/2"], t["hmtx"]
    cmap = t.getBestCmap() or {}
    lebar = {kode: hm[nama][0] for kode, nama in cmap.items() if nama in hm.metrics}
    upm = float(t["head"].unitsPerEm)
    kap = float(getattr(os2, "sCapHeight", 0) or 0.7 * upm)
    return Metrik(per_sel=1.0 / (os2.usWinAscent + os2.usWinDescent),
                  naik=float(os2.usWinAscent), turun=float(os2.usWinDescent),
                  kapital=kap, lebar=lebar,
                  lebar_ganti=float(lebar.get(ord("N"), 0.6 * upm)), upm=upm)


# Tinggi huruf kapital acuan: Montserrat, fon bawaan klip. Ukuran yang sama
# harus menghasilkan huruf yang SAMA TINGGI di tema mana pun.
_KAPITAL_ACUAN = "Montserrat"


def faktor_ukuran(keluarga: str) -> float:
    """
    Pengali ukuran supaya tinggi huruf kapital fon ini sama dengan acuannya.

    Metrik `win` tiap fon sangat berbeda: pada ukuran ASS yang sama, Bungee
    dirender dengan em 0,39x ukurannya sementara Montserrat 0,64x. Tanpa
    pengali ini, berganti dari tema "Kartu putih" ke "Neon" membuat judulnya
    mengecil hampir separuh, padahal penggeser ukurannya tidak disentuh.
    """
    m, acuan = metrik(keluarga), metrik(_KAPITAL_ACUAN)
    if m is None or acuan is None:
        return 1.0
    return (acuan.kapital * acuan.per_sel) / max(1e-9, m.kapital * m.per_sel)


def lebar_teks(teks: str, keluarga: str, ukuran: float) -> float:
    """Lebar `teks` dalam piksel pada ukuran ASS `ukuran`, seperti libass."""
    m = metrik(keluarga)
    if m is None:
        return 0.55 * ukuran * len(teks)
    return sum(m.lebar.get(ord(c), m.lebar_ganti) for c in teks) * ukuran * m.per_sel


# --- Tata letak ---------------------------------------------------------------

def bungkus(teks: str, per_baris: int) -> list[str]:
    """
    Memecah teks jadi baris-baris, paling banyak `per_baris` huruf.

    Berdasarkan JUMLAH HURUF, bukan lebar terukur, supaya pratinjau di peramban
    dan hasil render memecah di kata yang SAMA. Mesin fon peramban dan libass
    mengukur sedikit berbeda; pemecahan berdasarkan lebar akan berbeda tepat
    di kata yang berada di perbatasan.
    """
    kata = teks.split()
    baris: list[str] = []
    kini = ""
    for k in kata:
        calon = f"{kini} {k}".strip()
        if kini and len(calon) > per_baris:
            baris.append(kini)
            kini = k
        else:
            kini = calon
    if kini:
        baris.append(kini)
    return baris[:4] or [""]


def per_baris(box_w: float) -> int:
    """Huruf per baris dari lebar kotak (persen kanvas). Sama dengan JS."""
    return max(8, int(round(18 * max(20.0, min(100.0, box_w)) / 84.0)))


def _warna(hex_: str) -> str:
    h = (hex_ or "#000000").lstrip("#")
    if len(h) != 6:
        h = "000000"
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def _alfa(alfa: float) -> str:
    a = max(0, min(255, int(round((1.0 - max(0.0, min(1.0, alfa))) * 255))))
    return f"&H{a:02X}&"


def pelat_ass(w: float, h: float, r: float) -> str:
    """Persegi panjang membulat sebagai gambar vektor ASS, dari (0,0)."""
    w, h = max(1.0, w), max(1.0, h)
    r = max(0.0, min(r, w / 2, h / 2))
    k = r * 0.4477          # jarak titik kendali bezier untuk seperempat lingkaran
    f = lambda v: f"{v:.1f}".rstrip("0").rstrip(".")  # noqa: E731
    return (f"m {f(r)} 0 l {f(w - r)} 0 b {f(w - k)} 0 {f(w)} {f(k)} {f(w)} {f(r)} "
            f"l {f(w)} {f(h - r)} b {f(w)} {f(h - k)} {f(w - k)} {f(h)} {f(w - r)} {f(h)} "
            f"l {f(r)} {f(h)} b {f(k)} {f(h)} 0 {f(h - k)} 0 {f(h - r)} "
            f"l 0 {f(r)} b 0 {f(k)} {f(k)} 0 {f(r)} 0")


@dataclass
class Susunan:
    """Hasil tata letak, dalam piksel kanvas. Dipakai ASS dan diuji."""
    baris: list[str]
    ukuran: float
    pusat_x: float
    pusat_y: float
    lebar_baris: list[float]
    tinggi_blok: float
    pelat: list[tuple[float, float, float, float]]   # (x, y, w, h), pojok kiri atas
    label: Optional[tuple[float, float, float, float]] = None
    pusat_baris: list[float] = None        # pusat KAPITAL tiap baris
    geser_sel: float = 0.0                 # pusat kapital relatif ke pusat sel
    kapital: float = 0.0


# Jarak antar baris, kelipatan tinggi huruf kapital. Dihitung dari tinggi
# KAPITAL, bukan dari tinggi sel fon: sel Bungee 2,6x ukuran em-nya, dan pada
# render pertama baris-baris tema Neon terpisah jauh seperti tiga judul.
JARAK_BARIS = 1.72


def susun(tema: Tema, teks: str, *, pos_x: float, pos_y: float, box_w: float,
          ukuran: float, out_w: int, out_h: int) -> Susunan:
    """
    Tata letak judul pada kanvas `out_w` x `out_h`.

    Semua jarak diukur dari TINGGI HURUF KAPITAL, yang sudah disamakan antar
    fon oleh `faktor_ukuran`. Tiap baris lalu diletakkan sendiri: pusat
    kapitalnya jatuh tepat di tempat yang dihitung, dan pelat di belakangnya
    dihitung dari tempat yang sama. Versi pertama memakai tinggi sel dan
    menggeser pelatnya setengah baris ke atas, baris terakhir tembus keluar.
    """
    skala = out_h / 1920.0
    S = max(12.0, ukuran * skala * faktor_ukuran(tema.font) * tema.besar)
    isi = teks.strip()
    if tema.kapital:
        isi = isi.upper()
    baris = bungkus(isi, per_baris(box_w))
    lebar = [lebar_teks(b, tema.font, S) for b in baris]
    n = len(baris)
    cx = max(0.0, min(100.0, pos_x)) / 100.0 * out_w
    cy = max(0.0, min(100.0, pos_y)) / 100.0 * out_h

    m = metrik(tema.font)
    k = S * (m.per_sel if m else 1 / 1.56)
    kap = (m.kapital if m else 700.0) * k          # tinggi kapital, piksel
    langkah = kap * JARAK_BARIS
    tinggi = (n - 1) * langkah + kap               # dari puncak kapital baris
    #                                                pertama ke dasar baris akhir
    # Pusat kapital relatif ke pusat sel, yang dipakai `\an5`.
    geser = (-S / 2 + m.naik * k - kap / 2) if m else 0.0

    pusat_baris = [cy + (i - (n - 1) / 2) * langkah for i in range(n)]
    # Ruang di sekeliling teks. Render kedua menunjukkan huruf nyaris
    # menyentuh tepi pelatnya: pelat yang pas betul terlihat sesak.
    px, py = tema.pad_x * kap * 1.8, tema.pad_y * kap * 2.2
    if not tema.kapital:
        # Huruf kecil punya ekor ke bawah (g, j, y): pelatnya perlu ruang ekstra.
        py *= 1.6

    pelat: list[tuple[float, float, float, float]] = []
    if tema.latar == "sorot":
        for pb, lw in zip(pusat_baris, lebar):
            h = kap + 2 * py
            pelat.append((cx - lw / 2 - px, pb - h / 2, lw + 2 * px, h))
    elif tema.latar in ("pelat", "label"):
        lw = max(lebar) if lebar else 0.0
        h = tinggi + 2 * py
        pelat.append((cx - lw / 2 - px, cy - h / 2, lw + 2 * px, h))
    elif tema.latar == "pita":
        h = tinggi + 2 * py
        pelat.append((0.0, cy - h / 2, float(out_w), h))

    label = None
    if tema.latar == "label" and tema.cip and pelat:
        x0, y0, _, _ = pelat[0]
        Sl = S * 0.58
        kl = kap * 0.58
        lw = lebar_teks(tema.cip, tema.font, Sl)
        tl = kl * 2.1
        label = (x0, y0 - tl + kl * 0.35, lw + kl * 1.4, tl)

    return Susunan(baris=baris, ukuran=S, pusat_x=cx, pusat_y=cy, lebar_baris=lebar,
                   tinggi_blok=tinggi, pelat=pelat, label=label,
                   pusat_baris=pusat_baris, geser_sel=geser, kapital=kap)


def _gerak(tema: Tema, S: float, x: float, y: float, org: tuple[float, float]) -> str:
    """Tag gerak untuk satu bagian judul yang berpusat di (x, y)."""
    tag = GERAK.get(tema.gerak, GERAK["muncul"])
    if tema.gerak in GESER:
        gx, gy = GESER[tema.gerak]
        x0, y0 = x + gx * S, y + gy * S
        return f"\\move({x0:.0f},{y0:.0f},{x:.0f},{y:.0f},0,300)" + tag
    if tema.gerak in ("lempar", "getar"):
        # Berputar di sekitar SATU titik, jadi pelat dan huruf berputar sebagai
        # satu benda, bukan masing-masing di tempatnya.
        return f"\\org({org[0]:.0f},{org[1]:.0f})" + tag
    return tag


def ass_judul(tema_id: str, teks: str, *, mulai: float, akhir: float,
              pos_x: float, pos_y: float, box_w: float, ukuran: float,
              out_w: int, out_h: int, warna_teks: Optional[str] = None,
              warna_latar: Optional[str] = None, lapis: int = 5,
              dengan_gerak: bool = True) -> list[str]:
    """
    Baris-baris Dialogue ASS untuk satu judul bertema.

    Setiap baris membawa semua gayanya sebagai tag sebaris, jadi ia bisa
    ditempelkan ke berkas ASS mana pun tanpa menambahkan baris Style.
    """
    tema = TEMA.get(tema_id) or TEMA[BAWAAN]
    if not teks.strip():
        return []
    # Gambar pratinjau diam memakai keadaan AKHIR, bukan bingkai pertama gerak
    # masuknya, pada tema "kedip" bingkai pertama justru tembus seluruhnya.
    gerak = (lambda *a: "") if not dengan_gerak else None
    s = susun(tema, teks, pos_x=pos_x, pos_y=pos_y, box_w=box_w, ukuran=ukuran,
              out_w=out_w, out_h=out_h)
    S = s.ukuran
    skala = out_h / 1920.0
    org = (s.pusat_x, s.pusat_y)
    t0, t1 = _ts(mulai), _ts(max(mulai + 0.1, akhir))
    keluar: list[str] = []
    latar = warna_latar or tema.warna_latar

    # Pelat lebih dulu, di lapis bawah.
    for (x, y, w, h) in s.pelat:
        r = tema.radius * S if tema.latar != "pita" else 0.0
        cx, cy = x + w / 2, y + h / 2
        keluar.append(
            f"Dialogue: {lapis},{t0},{t1},Default,,0,0,0,,"
            f"{{\\an5\\pos({cx:.0f},{cy:.0f})\\bord0\\shad0\\blur0.6"
            f"\\1c{_warna(latar)}\\1a{_alfa(tema.alfa_latar)}"
            f"{(gerak or _gerak)(tema, S, cx, cy, org)}\\p1}}{pelat_ass(w, h, r)}{{\\p0}}")

    if s.label:
        x, y, w, h = s.label
        cx, cy = x + w / 2, y + h / 2
        keluar.append(
            f"Dialogue: {lapis + 1},{t0},{t1},Default,,0,0,0,,"
            f"{{\\an5\\pos({cx:.0f},{cy:.0f})\\bord0\\shad0\\blur0.6"
            f"\\1c{_warna(tema.warna_cip)}{(gerak or _gerak)(tema, S, cx, cy, org)}\\p1}}"
            f"{pelat_ass(w, h, h * 0.18)}{{\\p0}}")
        Sl = S * 0.58
        keluar.append(
            f"Dialogue: {lapis + 2},{t0},{t1},Default,,0,0,0,,"
            f"{{\\an5\\pos({cx:.0f},{cy - s.geser_sel * 0.58:.0f})\\fn{tema.font}\\fs{Sl:.0f}\\b0"
            f"\\bord0\\shad0\\1c{_warna(tema.teks_cip)}\\fsp{h * 0.05:.1f}"
            f"{(gerak or _gerak)(tema, S, cx, cy, org)}}}{_escape(tema.cip)}")

    # Huruf, satu baris ASS per baris teks: letaknya dihitung sendiri, jadi
    # pelat di bawahnya tidak bergantung pada cara libass memecah baris.
    teks_c = _warna(warna_teks or tema.teks)
    for i, b in enumerate(s.baris):
        y = s.pusat_baris[i] - s.geser_sel
        gaya = (f"\\an5\\pos({s.pusat_x:.0f},{y:.0f})\\fn{tema.font}\\fs{S:.0f}\\b0"
                f"\\1c{teks_c}\\3c{_warna(tema.warna_garis)}\\4c&H000000&"
                f"\\bord{tema.garis * skala:.1f}\\shad{tema.bayang * skala:.1f}"
                f"\\4a&H70&")
        if tema.kabur:
            gaya += f"\\blur{tema.kabur * skala:.1f}"
        keluar.append(
            f"Dialogue: {lapis + 3},{t0},{t1},Default,,0,0,0,,"
            f"{{{gaya}{(gerak or _gerak)(tema, S, s.pusat_x, y, org)}}}{_escape(b)}")
    return keluar


def _escape(teks: str) -> str:
    return (teks.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
            .replace("\n", " "))


def _ts(t: float) -> str:
    t = max(0.0, float(t))
    j = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - j * 3600 - m * 60
    return f"{j}:{m:02d}:{s:05.2f}"


def untuk_js() -> dict:
    """
    Rasio em/sel tiap fon tema, untuk pratinjau di peramban.

    CSS mengartikan ukuran sebagai tinggi em; libass sebagai tinggi sel. Supaya
    huruf di pratinjau sama besar dengan hasil render, ukuran CSS = ukuran ASS
    x rasio ini. Angkanya disalin ke temaJudul.js dan uji menjaganya tetap sama.
    """
    hasil = {}
    for t in TEMA.values():
        m = metrik(t.font)
        if m is not None:
            hasil[t.font] = {"em": round(m.upm * m.per_sel, 4),
                             "faktor": round(faktor_ukuran(t.font), 4)}
    return hasil
