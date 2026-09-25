"""
Memilih TEMA subtitle untuk sebuah klip, bukan hanya menyediakan daftarnya.

Dua puluh enam tema sudah ada, dan sampai sekarang memilihnya pekerjaan tangan:
pemiliknya membuka panel Gaya, menebak mana yang cocok, lalu mengulanginya untuk
klip berikutnya. Pada video yang menghasilkan lima belas klip, itu lima belas
tebakan untuk pertanyaan yang sebenarnya punya jawaban: tema mana yang cocok
ditentukan oleh ISI klipnya, dan isi klipnya sudah diketahui sistem.

Yang dipilih HANYA id tema. Wujud tiap tema (font, ukuran, warna, animasi)
tetap tinggal di antarmuka, satu tempat, dan tidak diduplikasi ke sini. Yang
dijaga uji adalah daftar id-nya tetap sama di kedua sisi.

Warna per penutur dipilih terpisah dan hanya bila klipnya memang berisi lebih
dari satu orang yang bergantian bicara. Pada klip satu orang, warna berbeda
per penutur bukan fitur melainkan gangguan.
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("omniclip.tema")

VERSI = 1

# id -> untuk klip seperti apa tema ini. Kalimatnya ditulis untuk DIBACA MODEL,
# jadi ia menyebut sifat klipnya, bukan sifat hurufnya: model tidak melihat
# hasilnya, ia hanya membaca keterangan ini.
TEMA: dict[str, str] = {
    "kotak_kuning": "paling umum di TikTok sekarang; cocok untuk hampir semua "
                    "podcast dan obrolan, terbaca di atas latar apa pun",
    "kotak_hijau": "seperti kotak kuning tapi lebih segar; cocok untuk konten "
                   "ringan, komedi, dan obrolan anak muda",
    "kotak_merah": "keras dan mendesak; cocok untuk berita, kemarahan, "
                   "perdebatan, dan pernyataan yang mengejutkan",
    "kotak_ungu": "kotak ungu dengan huruf miring naik; cocok untuk cerita "
                  "misteri, horor, dan hal aneh",
    "neon_biru": "kata menyala biru; cocok untuk teknologi, game, dan konten "
                 "yang latarnya gelap",
    "neon_pink": "nyala merah muda gaya klub malam; cocok untuk musik, "
                 "kehidupan malam, dan gosip selebritas",
    "satu_kata": "satu kata besar berganti cepat; cocok untuk klip pendek yang "
                 "bicaranya cepat dan bertenaga, bukan untuk penjelasan panjang",
    "pantul": "baris melompat masuk; cocok untuk konten ceria dan reaksi",
    "putar": "baris masuk sambil berputar; cocok untuk konten main-main",
    "geser": "baris meluncur dari kiri; cocok untuk cerita yang mengalir tenang",
    "getar": "hentakan kecil tiap baris; cocok untuk klip game, jumpscare, "
             "dan reaksi kaget",
    "fokus": "masuk dari buram jadi tajam; cocok untuk momen serius dan "
             "pengakuan",
    "garis_bawah": "kata diucapkan digarisbawahi; tenang, cocok untuk "
                   "penjelasan dan edukasi",
    "retro": "bayangan berwarna yang digeser; cocok untuk nostalgia dan "
             "konten bertema lama",
    "tebal": "putih tebal dengan kata aktif kuning; aman untuk apa pun bila "
             "tidak ada yang lebih cocok",
    "neon": "besar dengan sorot biru elektrik; cocok untuk konten bertenaga",
    "lembut": "huruf biasa yang memudar masuk; cocok untuk cerita sedih, "
              "haru, dan renungan",
    "naik": "baris naik dari bawah; netral dan rapi, cocok bila tidak "
        "ada yang perlu ditonjolkan",
    "papan": "blok tebal sangat mencolok; cocok untuk klip yang ditonton "
             "tanpa suara dan butuh teks paling terbaca",
    "ramping": "sempit sehingga banyak kata muat; cocok untuk bicara cepat "
               "dengan kalimat panjang",
    "ceria": "bulat gaya kartun; cocok untuk anak-anak, hewan, dan animasi",
    "bersih": "tanpa animasi di tengah bawah; cocok bila gambarnya sendiri "
              "sudah ramai",
    "apple": "pelat gelap dengan huruf biasa; tenang, cocok untuk wawancara "
             "serius dan konten profesional",
    "sinema": "pelat tipis seperti subtitle film; cocok untuk cuplikan film, "
              "anime, dan konten bersubtitle terjemahan",
    "ketik": "kata muncul satu per satu seperti diketik; cocok untuk membaca "
             "pesan, komentar, atau kutipan",
    "stiker": "pelat berwarna gaya kartun; cocok untuk konten lucu dan ringan",
}

# Tema yang dipakai bila tidak ada yang lebih cocok. Bukan diambil acak: ini
# yang paling banyak dipakai orang dan paling jarang salah.
BAWAAN = "kotak_kuning"

SISTEM = """Anda penyunting video pendek berbahasa Indonesia yang memilih GAYA
SUBTITLE untuk satu klip.

Anda diberi isi klipnya dan daftar tema yang tersedia beserta untuk klip seperti
apa masing-masing cocok. Pilih SATU tema.

Aturannya:
- Pilih dari daftar. Jangan mengarang id tema yang tidak ada di sana.
- Yang menentukan adalah ISI dan SUASANA klipnya, bukan selera. Klip horor tidak
  memakai tema ceria; wawancara serius tidak memakai tema klub malam.
- Bila klipnya biasa saja dan tidak ada yang benar-benar menonjol, pilih tema
  yang aman dan paling terbaca. Tema mencolok yang dipakai di tempat yang salah
  membuat klip terlihat murah.
- alasan maksimal 15 kata, menyebut apa dari klipnya yang membuat tema itu
  dipilih.
- warna_per_penutur hanya true bila transkripnya benar-benar menunjukkan DUA
  ORANG ATAU LEBIH bergantian bicara. Pada klip satu orang ia hanya membuat
  warnanya berkedip tanpa arti.
- Jangan pernah memakai tanda pisah panjang (em dash) di teks mana pun."""


def _schema() -> dict:
    return {
        "type": "OBJECT",
        "required": ["alasan", "tema", "warna_per_penutur"],
        "property_ordering": ["alasan", "tema", "warna_per_penutur"],
        "properties": {
            "alasan": {"type": "STRING"},
            "tema": {"type": "STRING"},
            "warna_per_penutur": {"type": "BOOLEAN"},
        },
    }


def _menu() -> str:
    return "\n".join(f"- {k}: {v}" for k, v in TEMA.items())


def _teks_klip(meta: dict, maks: int = 2500) -> str:
    baris = []
    total = 0
    for l in (meta.get("subtitles") or []):
        t = (l.get("text") or "").strip()
        if not t:
            continue
        sp = l.get("speaker")
        awalan = f"[orang {int(sp) + 1}] " if sp is not None else ""
        baris.append(awalan + t)
        total += len(t)
        if total > maks:
            break
    return "\n".join(baris)


def jumlah_penutur(meta: dict) -> int:
    sp = {int(l["speaker"]) for l in (meta.get("subtitles") or [])
          if l.get("speaker") is not None}
    return len(sp)


def pilih_lokal(meta: dict) -> dict:
    """
    Tebakan tanpa AI. Sengaja sederhana dan sengaja membosankan.

    Ia tidak berpura-pura membaca suasana; ia hanya memakai dua hal yang
    terukur: jenis klipnya dan berapa orang yang bicara. Lebih baik satu tema
    aman daripada tema mencolok yang dipilih dengan alasan karangan.
    """
    jenis = (meta.get("jenis") or "").lower()
    durasi = float(meta.get("duration") or 0)
    banyak = jumlah_penutur(meta)

    if jenis == "game":
        tema, alasan = "getar", "klip game, hentakan tiap baris"
    elif jenis in ("tanpa_wajah", "gerak"):
        tema, alasan = "papan", "tidak ada wajah, teks dibuat sejelas mungkin"
    elif 0 < durasi <= 20:
        tema, alasan = "satu_kata", "klip sangat pendek, satu kata besar"
    else:
        tema, alasan = BAWAAN, "tema yang paling jarang salah"
    return {"tema": tema, "alasan": alasan,
            "warna_per_penutur": banyak >= 2, "sumber": "lokal"}


def _bersihkan(jawab: dict, meta: dict) -> dict:
    from .teks import tanpa_pisah

    tema = str(jawab.get("tema") or "").strip().lower()
    if tema not in TEMA:
        # Model mengarang id: jatuh ke tebakan lokal, bukan ke tema acak.
        log.info("Tema '%s' tidak dikenal, memakai tebakan lokal", tema[:40])
        lokal = pilih_lokal(meta)
        lokal["alasan"] = f"model menyebut tema yang tidak ada, {lokal['alasan']}"
        return lokal
    warna = bool(jawab.get("warna_per_penutur"))
    # Warna per penutur pada klip satu orang hanya membuat warnanya berkedip.
    if jumlah_penutur(meta) < 2:
        warna = False
    return {"tema": tema,
            "alasan": tanpa_pisah(str(jawab.get("alasan") or ""))[:160],
            "warna_per_penutur": warna}


def _schema_banyak() -> dict:
    return {
        "type": "OBJECT",
        "required": ["klip"],
        "properties": {"klip": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "required": ["nomor", "alasan", "tema", "warna_per_penutur"],
            "property_ordering": ["nomor", "alasan", "tema", "warna_per_penutur"],
            "properties": {
                "nomor": {"type": "INTEGER"},
                "alasan": {"type": "STRING"},
                "tema": {"type": "STRING"},
                "warna_per_penutur": {"type": "BOOLEAN"},
            }}}},
    }


def pilih_banyak(daftar: list[dict], *, api_key: str = "", models: Optional[list] = None,
                 pakai_ai: bool = True, kabar=None, batal=None) -> list[dict]:
    """
    Tema untuk BANYAK klip sekaligus, dalam SATU panggilan model.

    Versinya yang pertama memanggil model sekali per klip, dan itu keliru dengan
    cara yang hanya terlihat setelah dihitung: jatah harian Gemini gratis 20
    permintaan per model per project, sementara satu video menghasilkan lima
    belas klip. Menyiapkan temanya saja akan menghabiskan hampir seluruh jatah
    hari itu, dan pemilihan klip video berikutnya kehabisan.

    Satu panggilan untuk lima belas klip juga lebih baik jawabannya: modelnya
    melihat seluruh video sekaligus, jadi ia bisa memberi tema yang KONSISTEN
    untuk klip yang memang berasal dari video yang sama.
    """
    if not daftar:
        return []
    if not (pakai_ai and api_key and models):
        return [pilih_lokal(m) for m in daftar]

    from .penyedia_ai import pekerjaan, tanya

    bagian = []
    for i, m in enumerate(daftar, 1):
        teks = _teks_klip(m, maks=700)
        bagian.append(
            f"--- KLIP {i} ---\n"
            f"Judul: {m.get('title') or '(tanpa judul)'}\n"
            f"Durasi {float(m.get('duration') or 0):.0f} dtk, "
            f"jenis {m.get('jenis') or 'tidak diketahui'}, "
            f"{jumlah_penutur(m) or '?'} orang bicara.\n{teks}")
    permintaan = ("Pilihkan tema untuk SETIAP klip di bawah. Jawab satu baris "
                  "per klip, dengan `nomor` sesuai nomor klipnya.\n\n"
                  + "\n\n".join(bagian)
                  + f"\n\n=== TEMA YANG TERSEDIA ===\n{_menu()}")
    try:
        with pekerjaan("tema-subtitle"):
            jawab, model, _ = tanya(
                [{"teks": permintaan}], schema=_schema_banyak(),
                sistem=SISTEM, api_key=api_key, models=models,
                suhu=0.3, maks_keluaran=min(8192, 300 + len(daftar) * 120),
                kabar=kabar, batal=batal)
    except Exception as e:
        log.info("Tema massal dipilih mesin lokal: %s", str(e)[:160])
        return [pilih_lokal(m) for m in daftar]

    per_nomor = {}
    for baris in (jawab.get("klip") or []):
        try:
            per_nomor[int(baris.get("nomor"))] = baris
        except (TypeError, ValueError):
            continue
    keluar = []
    for i, m in enumerate(daftar, 1):
        baris = per_nomor.get(i)
        if baris is None:
            keluar.append(pilih_lokal(m))
            continue
        hasil = _bersihkan(baris, m)
        hasil.setdefault("sumber", model)
        keluar.append(hasil)
    return keluar


def pilih(meta: dict, *, api_key: str = "", models: Optional[list] = None,
          pakai_ai: bool = True, kabar=None, batal=None) -> dict:
    """
    {tema, alasan, warna_per_penutur, sumber} untuk satu klip.

    `meta` adalah klip beserta subtitle-nya, ditambah `jenis` bila sudah
    diketahui (game / wajah / tanpa_wajah) dan `duration`.
    """
    teks = _teks_klip(meta)
    if not (pakai_ai and api_key and models and teks.strip()):
        return pilih_lokal(meta)

    from .penyedia_ai import pekerjaan, tanya

    permintaan = (
        f"Judul klip: {meta.get('title') or '(tanpa judul)'}\n"
        f"Durasi: {float(meta.get('duration') or 0):.0f} detik. "
        f"Jenis: {meta.get('jenis') or 'tidak diketahui'}. "
        f"Jumlah orang yang bicara: {jumlah_penutur(meta) or 'tidak diketahui'}.\n\n"
        f"=== ISI KLIP ===\n{teks}\n\n"
        f"=== TEMA YANG TERSEDIA ===\n{_menu()}"
    )
    try:
        with pekerjaan("tema-subtitle"):
            jawab, model, _ = tanya([{"teks": permintaan}], schema=_schema(),
                                    sistem=SISTEM, api_key=api_key, models=models,
                                    suhu=0.3, maks_keluaran=512,
                                    kabar=kabar, batal=batal)
    except Exception as e:
        log.info("Tema dipilih mesin lokal: %s", str(e)[:160])
        return pilih_lokal(meta)
    hasil = _bersihkan(jawab, meta)
    hasil.setdefault("sumber", model)
    return hasil
