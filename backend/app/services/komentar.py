"""
Draf komentar pemilik kanal untuk satu klip (JOB-2 F1-2).

Klip OmniClip sampai Oktober 2026 hanya potongan, bingkai, dan subtitle. Itu
persis "klip tanpa narasi tambahan" yang ditolak kebijakan konten yang
digunakan ulang YouTube. Yang menambah nilai adalah suara ORANGNYA: pendapat,
reaksi, konteks yang tidak ada di klip.

Berkas ini hanya menulis DRAF untuk itu, bukan komentar jadi. Alasannya bukan
kerendahan hati: komentar mesin yang sama polanya di setiap klip ("Lihat apa
yang terjadi ketika...") justru tanda produksi massal yang sedang dihindari.
Draf yang baik di sini adalah yang memberi orangnya bahan untuk disunting,
bukan yang bisa dipakai tanpa dibaca.

Bentuknya tiga bagian, mengikuti tempat komentar bisa diletakkan di Studio
(F1-3):

    pembuka   satu kalimat sebelum klip mulai, menyiapkan penonton
    sela      opsional, satu pendapat di jeda alami antara dua baris subtitle
    penutup   pendapat atau pertanyaan sesudah klip selesai

Tempat `sela` dipilih model sebagai NOMOR baris subtitle, lalu kodenya yang
menghitung detiknya dari akhir baris itu. Model tidak pandai menyebut detik;
ia cukup pandai memilih sesudah kalimat mana orang biasanya menyela.

Tanpa AI, drafnya kosong dengan penjelasan. Tidak ada komentar karangan lokal:
kalimat generik yang disusun dari templat adalah persis yang tidak boleh ada.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from .teks import tanpa_pisah

log = logging.getLogger("omniclip.komentar")

VERSI = 2

# Batas panjang tiap bagian, dalam karakter. Komentar yang diucapkan sekitar
# 15 karakter per detik; pembuka 120 karakter sudah delapan detik, dan itu
# delapan detik sebelum isi klipnya mulai.
MAKS_PEMBUKA = 120
MAKS_SELA = 140
MAKS_PENUTUP = 160

# Jeda di bawah ini terlalu sempit untuk disela tanpa memotong orang bicara.
JEDA_MIN_SELA = 0.25
GESER_SELA = 2

# Frasa pembuka yang dipakai jutaan klip otomatis. Draf yang memuatnya dibuang
# bagian itu, bukan diperbaiki: memperbaikinya tetap menyisakan kalimat yang
# tidak berisi apa-apa.
FRASA_TEMPLAT = (
    "lihat apa yang terjadi",
    "tonton sampai habis",
    "tonton sampai akhir",
    "kalian tidak akan percaya",
    "kamu tidak akan percaya",
    "jangan lupa like",
    "jangan lupa subscribe",
    "jangan skip",
    "video ini akan",
    "simak video berikut",
    "inilah yang terjadi",
    "bikin geleng kepala",
    "wajib nonton",
)

SISTEM = """Anda membantu pemilik kanal YouTube berbahasa Indonesia menulis
KOMENTAR PRIBADINYA untuk sebuah klip dari video orang lain.

Klip itu potongan obrolan atau siaran orang lain. Yang membuatnya layak
diunggah ulang adalah pendapat pemilik kanal tentang isinya: reaksi, sudut
pandang, atau konteks yang tidak ada di klipnya. Anda menulis DRAF yang akan
dibaca, disunting, lalu diucapkan atau ditampilkan oleh pemilik kanal.

Tulis tiga bagian:

1. PEMBUKA, satu kalimat, maksimal 120 karakter. Diucapkan sebelum klip
   mulai. Menyiapkan penonton dengan menyebut hal KONKRET dari klipnya (nama,
   angka, pernyataan, kejadian), bukan menjanjikan sesuatu.

2. SELA, opsional. Satu pendapat singkat (maksimal 140 karakter) yang
   diucapkan di jeda antara dua kalimat di klip, saat penonton paling mungkin
   ikut berpikir. Pilih `sela_baris`: NOMOR baris transkrip yang SESUDAHNYA
   sela diucapkan, HANYA dari baris yang ditandai "(jeda ... dtk)", karena di
   tempat lain orangnya masih bicara. Isi -1 dan kosongkan `sela` bila tidak
   ada baris bertanda, atau bila klipnya tidak butuh disela (misalnya karena
   punchline-nya harus mengalir tanpa putus).

3. PENUTUP, satu atau dua kalimat, maksimal 160 karakter. Pendapat pemilik
   kanal tentang yang baru ditonton, atau pertanyaan yang benar-benar ingin ia
   dengar jawabannya dari penonton.

Aturan yang tidak boleh dilanggar:
  - Setiap bagian harus terikat pada isi klip INI. Kalimat yang bisa ditempel
    ke klip mana pun dianggap gagal.
  - Dilarang frasa templat: "lihat apa yang terjadi", "tonton sampai habis",
    "kalian tidak akan percaya", "jangan lupa like dan subscribe", "momen
    ini", "wajib nonton", dan sejenisnya.
  - Jangan mengarang fakta yang tidak ada di transkrip, judul, atau konteks.
    Pendapat boleh; fakta karangan tidak.
  - Jangan pernah memakai tanda pisah panjang (em dash). Pakai koma atau titik.
  - Bahasa sehari-hari, orang pertama ("gue", "aku", atau "saya", ikuti gaya
    kanal bila disebut), seperti orang bicara ke kamera. Tanpa huruf kapital
    semua, tanpa tanda seru bertumpuk, tanpa emoji."""


def _schema() -> dict:
    return {
        "type": "OBJECT",
        "required": ["pembuka", "sela_baris", "sela", "penutup"],
        "property_ordering": ["pembuka", "sela_baris", "sela", "penutup"],
        "properties": {
            "pembuka": {"type": "STRING"},
            "sela_baris": {"type": "INTEGER"},
            "sela": {"type": "STRING"},
            "penutup": {"type": "STRING"},
        },
    }


def _bersih(teks, batas: int) -> str:
    t = re.sub(r"\s+", " ", tanpa_pisah(str(teks or ""))).strip()
    if len(t) <= batas:
        return t
    # Dipotong di akhir kalimat atau kata, bukan di tengah kata.
    potong = t[:batas]
    titik = max(potong.rfind(". "), potong.rfind("? "), potong.rfind("! "))
    if titik >= batas // 2:
        return potong[:titik + 1].strip()
    return potong.rsplit(" ", 1)[0].rstrip(",;: ") + "..."


def templat_di(teks: str) -> str:
    """Frasa templat pertama yang ada di `teks`, atau teks kosong."""
    kecil = (teks or "").lower()
    for f in FRASA_TEMPLAT:
        if f in kecil:
            return f
    return ""


def _baris(subtitles) -> list[dict]:
    """Baris subtitle yang berisi teks, diurutkan menurut waktu."""
    out = []
    for b in subtitles or []:
        if not isinstance(b, dict):
            continue
        teks = str(b.get("text") or "").strip()
        try:
            mulai, akhir = float(b.get("start")), float(b.get("end"))
        except (TypeError, ValueError):
            continue
        if teks and akhir > mulai:
            out.append({"start": mulai, "end": akhir, "text": teks})
    out.sort(key=lambda b: b["start"])
    return out


def _jeda_sesudah(baris: list[dict], i: int) -> float:
    if i < 0 or i >= len(baris) - 1:
        return 0.0
    return baris[i + 1]["start"] - baris[i]["end"]


def tempat_sela(baris: list[dict], nomor) -> Optional[dict]:
    """
    {detik, jeda, baris} untuk sela sesudah baris `nomor`, atau None.

    Sela sesudah baris TERAKHIR bukan sela, itu penutup. Jeda yang terlalu
    sempit tidak dipakai: komentar di situ memotong orang bicara. Bila baris
    pilihan model tidak berjeda, dipakai jeda terdekat paling jauh
    `GESER_SELA` baris darinya; diukur 10 Oktober 2026 pada klip nyata, hanya
    4 dari 47 batas baris yang berjeda cukup, jadi pilihan yang meleset satu
    baris itu biasa dan tidak berarti selanya salah tempat.
    """
    try:
        i = int(nomor)
    except (TypeError, ValueError):
        return None
    if i < 0 or i >= len(baris) - 1:
        return None
    for geser in sorted(range(-GESER_SELA, GESER_SELA + 1), key=abs):
        j = i + geser
        jeda = _jeda_sesudah(baris, j)
        if jeda >= JEDA_MIN_SELA:
            return {"detik": round(baris[j]["end"], 2), "jeda": round(jeda, 2), "baris": j}
    return None


def _bahan(klip: dict, baris: list[dict], gaya: str) -> str:
    # Jeda yang cukup untuk disela ditandai, supaya model memilih di antaranya.
    transkrip = "\n".join(
        f"[{i}] {b['text']}" + (f"   (jeda {_jeda_sesudah(baris, i):.1f} dtk)"
                               if _jeda_sesudah(baris, i) >= JEDA_MIN_SELA else "")
        for i, b in enumerate(baris))[:6000]
    konteks = (klip.get("konteks") or "").strip()
    return (
        f"Judul video sumber: {klip.get('video_title') or '(tidak diketahui)'}\n"
        f"Kanal sumber: {klip.get('channel') or '(tidak diketahui)'}\n"
        f"Judul klip: {klip.get('title') or '(belum ada)'}\n"
        f"Durasi klip: {float(klip.get('duration') or 0):.0f} detik\n"
        f"Konteks: {konteks or '(tidak ada; simpulkan dari transkrip saja)'}\n"
        f"Gaya kanal pemilik: {gaya.strip() or '(tidak disebut; santai dan jujur)'}\n\n"
        f"=== TRANSKRIP KLIP, bernomor per baris ===\n{transkrip}\n\n"
        "Tulis pembuka, sela (dengan nomor barisnya, atau -1), dan penutup.")


def kosong(catatan: str) -> dict:
    return {"pembuka": "", "sela": None, "penutup": "", "sumber": "",
            "catatan": [catatan], "versi": VERSI}


def draf(klip: dict, *, api_key: str = "", models: Optional[list] = None,
         gaya: str = "") -> dict:
    """
    {pembuka, sela: {teks, detik, jeda, baris} | None, penutup, sumber, catatan}.

    `klip` memuat `subtitles` ({start, end, text}, waktu klip), dan bila ada
    `konteks`, `title`, `video_title`, `channel`, `duration`. `konteks` boleh
    kosong (klip lama dan klip dari mesin lokal tidak punya).
    """
    from .penyedia_ai import SemuaGagal, pekerjaan, tanya

    baris = _baris(klip.get("subtitles"))
    if sum(len(b["text"]) for b in baris) < 40:
        return kosong("Klip ini hampir tidak berisi ucapan, jadi tidak ada "
                      "yang bisa dikomentari dari transkripnya.")
    if not api_key or not models:
        return kosong("Draf komentar butuh AI, dan kunci API belum diisi. "
                      "Tulis komentarnya sendiri, atau isi kunci di Pengaturan.")
    try:
        with pekerjaan("komentar"):
            hasil, model, _pakai = tanya(
                [{"teks": _bahan(klip, baris, gaya)}], schema=_schema(),
                sistem=SISTEM, api_key=api_key, models=models,
                suhu=0.8, maks_keluaran=1024, batas_detik=90)
    except SemuaGagal as e:
        log.info("Draf komentar AI tidak tersedia: %s", str(e)[:200])
        return kosong("Semua model AI sedang tidak bisa dipakai (kuota habis "
                      "atau gangguan). Coba lagi nanti, atau tulis sendiri.")
    except Exception as e:                       # noqa: BLE001
        log.warning("Draf komentar AI gagal: %s", str(e)[:200])
        return kosong("Draf komentar gagal disusun. Coba lagi, atau tulis sendiri.")

    catatan: list[str] = []
    bagian = {
        "pembuka": _bersih(hasil.get("pembuka"), MAKS_PEMBUKA),
        "sela": _bersih(hasil.get("sela"), MAKS_SELA),
        "penutup": _bersih(hasil.get("penutup"), MAKS_PENUTUP),
    }
    for nama, teks in bagian.items():
        frasa = templat_di(teks)
        if frasa:
            log.info("Draf %s dibuang karena frasa templat '%s'", nama, frasa)
            catatan.append(f"Draf {nama} dibuang karena memakai frasa templat "
                           f"\"{frasa}\". Tulis sendiri bagian itu.")
            bagian[nama] = ""

    sela = None
    if bagian["sela"]:
        tempat = tempat_sela(baris, hasil.get("sela_baris"))
        if tempat:
            sela = {"teks": bagian["sela"], **tempat}
        else:
            catatan.append("Tempat sela yang dipilih AI tidak berada di jeda "
                           "antara dua kalimat, jadi selanya tidak dipakai.")

    return {"pembuka": bagian["pembuka"], "sela": sela,
            "penutup": bagian["penutup"], "sumber": model,
            "catatan": catatan, "versi": VERSI}
