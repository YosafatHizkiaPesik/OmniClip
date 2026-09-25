"""
Merapatkan klip: membuang jeda dan gumaman, seperti editor memotong.

Ini yang paling membedakan klip amatir dari klip yang dikerjakan editor. Orang
berbicara dengan jeda — mengambil napas, berpikir, menunggu giliran — dan jeda
itu wajar saat ditonton dalam video sejam. Dalam klip enam puluh detik yang
harus menahan orang di tiga detik pertama, jeda satu detik terasa seperti
kesalahan pemutaran.

Yang dipotong hanya yang TERUKUR diam dari transkrip: waktu antar kata, bukan
tebakan. Dan potongannya menyisakan bantalan di kedua sisi, karena memotong
tepat di batas kata memakan huruf pertama dan terakhirnya — cacat yang
terdengar sebagai "video rusak", bukan sebagai potongan.

Hasilnya berupa segmen baru untuk klip yang sama. Renderer sudah bisa
menyambung banyak segmen, dan subtitle dihitung ulang dari segmen itu, jadi
seluruh rantai sesudahnya tidak perlu tahu apa-apa tentang berkas ini.
"""

import logging
import re
from typing import Optional

log = logging.getLogger("omniclip.rapat")

JEDA_MIN = 0.50          # jeda sependek ini dibiarkan; memotongnya terasa cegukan
BANTALAN = 0.14          # sisa napas di kedua sisi potongan
UJUNG_MIN = 1.00         # diam di awal/akhir klip yang layak dipangkas
UJUNG_SISA = 0.30
POTONG_MIN = 0.16        # potongan lebih pendek dari ini tidak sepadan
SISA_MIN = 0.40          # kepingan tersisa yang lebih pendek malah jadi kedipan
MAKS_POTONG = 24         # satu klip, satu batas; tiap potongan menambah input ffmpeg

# Gumaman yang dibuang bila ia berdiri sendiri di antara dua jeda.
#
# Daftarnya sengaja pendek dan hanya berisi bunyi yang BUKAN kata. "Ya", "apa",
# dan "kan" tidak masuk walau sering jadi pengisi: ketiganya juga kata
# sungguhan, dan membuang kata sungguhan mengubah arti kalimat.
GUMAMAN = {"eh", "ee", "eee", "eeh", "ehm", "em", "emm", "emmm", "mm", "mmm",
           "hmm", "hm", "hmmm", "ah", "aa", "aaa", "uh", "uhm", "anu", "eu", "euh"}
GUMAMAN_MAKS = 0.9       # gumaman yang lebih panjang dari ini mungkin kata sungguhan

_BUKAN_HURUF = re.compile(r"[^\w]+", re.UNICODE)


def _bersih(w: str) -> str:
    return _BUKAN_HURUF.sub("", (w or "").strip().lower())


# Jeda hanya dipotong bila di sana memang tidak terjadi apa-apa.
#
# Pada podcast, diam berarti diam. Pada gameplay tidak: bagian tanpa kata bisa
# berisi musik yang menegang, langkah kaki, atau jeritan — dan membuangnya
# berarti membuang justru bagian yang membuat klipnya bagus. Karena itu tiap
# calon potongan diperiksa kekerasannya, dan yang masih bersuara dibiarkan.
ENERGI_LANGKAH = 0.1           # detik per nilai
ENERGI_SELISIH = 14.0          # dB di bawah suara bicara = dianggap sunyi
_RMS = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?\d+(?:\.\d+)?)")


def jejak_energi(sumber, a: float, b: float,
                 langkah: float = ENERGI_LANGKAH) -> Optional[list[float]]:
    """RMS dB per `langkah` detik untuk rentang [a, b], atau None bila gagal."""
    from .proses import jalankan
    contoh = max(1, int(round(8000 * langkah)))
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
           "-ss", f"{max(0.0, a):.3f}", "-t", f"{max(0.1, b - a):.3f}",
           "-i", str(sumber), "-vn",
           "-af", f"aresample=8000,asetnsamples={contoh},astats=metadata=1:reset=1,"
                  "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
           "-f", "null", "-"]
    try:
        r = jalankan(cmd, timeout=180, rendah=True)
    except Exception as e:
        log.warning("Energi tidak terbaca: %s", str(e)[:160])
        return None
    nilai = []
    for m in _RMS.finditer(r.stdout or ""):
        try:
            nilai.append(float(m.group(1)))
        except ValueError:
            nilai.append(-90.0)
    return nilai or None


def _iris_sunyi(jejak: Optional[list[float]], asal: float, x: float, y: float,
                ambang: float) -> Optional[tuple]:
    """
    Bagian dari [x, y] yang benar-benar tanpa suara, atau None.

    Bukan pertanyaan ya/tidak, karena jawabannya jarang ya/tidak. Terukur pada
    wawancara: jeda 3,3 detik di antara dua kata ternyata memuat tawa selama
    satu detik. Membuang seluruh jeda berarti membuang tawanya — justru bagian
    yang membuat klipnya bagus. Membiarkan seluruhnya berarti menyimpan dua
    detik diam. Yang benar adalah membuang yang diamnya saja, jadi yang dicari
    di sini deretan sunyi TERPANJANG di dalamnya.
    """
    if not jejak:
        return (x, y)
    i = max(0, int((x - asal) / ENERGI_LANGKAH))
    j = min(len(jejak), int((y - asal) / ENERGI_LANGKAH) + 1)
    if j <= i:
        return None
    terbaik = (0, 0)
    mulai = None
    for k in range(i, j + 1):
        sunyi = k < j and jejak[k] <= ambang
        if sunyi and mulai is None:
            mulai = k
        elif not sunyi and mulai is not None:
            if k - mulai > terbaik[1] - terbaik[0]:
                terbaik = (mulai, k)
            mulai = None
    if terbaik[1] <= terbaik[0]:
        return None
    a2 = max(x, asal + terbaik[0] * ENERGI_LANGKAH)
    b2 = min(y, asal + terbaik[1] * ENERGI_LANGKAH)
    return (a2, b2) if b2 - a2 >= POTONG_MIN else None


def _ambang(jejak: Optional[list[float]], asal: float, kata: list[dict]) -> float:
    """Batas 'sunyi': sekian dB di bawah kekerasan khas saat orang bicara."""
    if not jejak or not kata:
        return 0.0
    saat_bicara = []
    for k in kata:
        i = max(0, int((k["s"] - asal) / ENERGI_LANGKAH))
        j = min(len(jejak), int((k["e"] - asal) / ENERGI_LANGKAH) + 1)
        saat_bicara += jejak[i:j]
    if not saat_bicara:
        return 0.0
    saat_bicara.sort()
    tengah = saat_bicara[len(saat_bicara) // 2]
    return tengah - ENERGI_SELISIH


def _ambang_tanpa_kata(jejak: list[float]) -> float:
    """
    Batas 'sunyi' untuk klip yang tidak punya transkrip.

    Tanpa kata, tidak ada yang bisa dipakai menjawab "sekeras apa saat ada
    isinya". Yang tersedia cuma sebaran kekerasannya sendiri, jadi patokannya
    diambil dari sana: persentil 70 sebagai wakil "sedang ada isinya", lalu
    turun sejauh yang sama dengan jalur bertranskrip. Diambil 70, bukan tengah,
    karena pada klip musik atau gameplay bagian yang berisi justru lebih banyak
    daripada bagian sunyinya, dan nilai tengah akan ikut terseret naik.
    """
    urut = sorted(jejak)
    if not urut:
        return 0.0
    return urut[int(len(urut) * 0.7)] - ENERGI_SELISIH


def _potongan_dari_energi(jejak: list[float], asal: float, a: float, b: float,
                          ambang: float, *, jeda_min: float) -> list[tuple]:
    """
    Bagian sunyi yang layak dipotong, dibaca dari SUARA saja.

    Ada karena klip tanpa transkrip dulu tidak bisa dirapatkan sama sekali:
    musik, gameplay tanpa bicara, dan video berbahasa asing yang subtitle-nya
    gagal diambil. Padahal jeda di sana justru sering paling panjang.

    Bentuknya sama dengan jalur bertranskrip supaya sisa pipeline tidak perlu
    tahu bedanya: daftar (mulai, selesai, jenis).
    """
    keluar: list[tuple] = []
    i0 = max(0, int((a - asal) / ENERGI_LANGKAH))
    i1 = min(len(jejak), int((b - asal) / ENERGI_LANGKAH) + 1)
    mulai = None
    for i in range(i0, i1):
        sunyi = jejak[i] <= ambang
        if sunyi and mulai is None:
            mulai = i
        elif not sunyi and mulai is not None:
            keluar.append((mulai, i))
            mulai = None
    if mulai is not None:
        keluar.append((mulai, i1))

    potong = []
    for i, j in keluar:
        x = asal + i * ENERGI_LANGKAH + BANTALAN
        y = asal + j * ENERGI_LANGKAH - BANTALAN
        if y - x >= max(jeda_min, POTONG_MIN):
            potong.append((x, y, "sunyi"))
    return potong


def _kata_dalam(words: list[dict], a: float, b: float) -> list[dict]:
    keluar = []
    for w in words or []:
        try:
            s, e = float(w["s"]), float(w["e"])
        except (KeyError, TypeError, ValueError):
            continue
        if e > a and s < b:
            keluar.append({"w": w.get("w", ""), "s": max(s, a), "e": min(e, b)})
    keluar.sort(key=lambda x: x["s"])
    return keluar


def _potongan_segmen(a: float, b: float, kata: list[dict], *,
                     jeda_min: float, gumaman: bool) -> list[tuple]:
    """Rentang yang DIBUANG di dalam satu segmen, urut dari awal."""
    if not kata:
        return []
    buang: list[tuple] = []

    # Diam di ujung. Dipangkas lebih longgar daripada jeda di tengah: yang di
    # tengah memutus kalimat, yang di ujung hanya menunda mulainya.
    if kata[0]["s"] - a >= UJUNG_MIN:
        buang.append((a, kata[0]["s"] - UJUNG_SISA, "awal"))
    if b - kata[-1]["e"] >= UJUNG_MIN:
        buang.append((kata[-1]["e"] + UJUNG_SISA, b, "akhir"))

    for i in range(len(kata) - 1):
        kiri, kanan = kata[i], kata[i + 1]
        senjang = kanan["s"] - kiri["e"]
        if senjang >= jeda_min:
            buang.append((kiri["e"] + BANTALAN, kanan["s"] - BANTALAN, "jeda"))

    if gumaman:
        for i, k in enumerate(kata):
            if _bersih(k["w"]) not in GUMAMAN or k["e"] - k["s"] > GUMAMAN_MAKS:
                continue
            # Hanya yang berdiri sendiri: gumaman yang menempel pada kata
            # sebelumnya atau sesudahnya ikut membawa suku kata tetangganya.
            sebelum = k["s"] - (kata[i - 1]["e"] if i else a)
            sesudah = (kata[i + 1]["s"] if i + 1 < len(kata) else b) - k["e"]
            if sebelum >= 0.12 and sesudah >= 0.12:
                buang.append((k["s"] - 0.05, k["e"] + 0.05, "gumaman"))

    buang = [(max(a, x), min(b, y), jenis) for x, y, jenis in buang if y - x >= POTONG_MIN]
    buang.sort()
    # Potongan yang bersinggungan disatukan, supaya dua aturan yang mengenai
    # tempat yang sama tidak menghasilkan kepingan sepersekian detik.
    satu: list[list] = []
    for x, y, jenis in buang:
        if satu and x <= satu[-1][1] + 0.01:
            satu[-1][1] = max(satu[-1][1], y)
        else:
            satu.append([x, y, jenis])
    return [tuple(s) for s in satu]


def rapatkan(segments: list[dict], words: list[dict], *,
             sumber=None, jeda_min: float = JEDA_MIN, gumaman: bool = True,
             maks_potong: int = MAKS_POTONG) -> dict:
    """
    {segments, dibuang, potongan, rincian} — segmen baru tanpa jeda panjang.

    `dibuang` dalam detik. Bila tidak ada yang layak dipotong, segmennya
    dikembalikan apa adanya: lebih baik tidak berubah daripada berubah
    sedikit-sedikit tanpa terasa bedanya.
    """
    asal = [{"start": float(s["start"]), "end": float(s["end"])} for s in segments or []
            if float(s["end"]) - float(s["start"]) > 0.2]
    if not asal:
        return {"segments": asal, "dibuang": 0.0, "potongan": 0, "rincian": {}}
    # Tanpa transkrip DAN tanpa berkas sumber, tidak ada satu pun bahan untuk
    # menilai di mana jedanya. Dengan salah satunya, masih bisa.
    if not words and sumber is None:
        return {"segments": asal, "dibuang": 0.0, "potongan": 0, "rincian": {}}

    calon: list[tuple] = []
    ditahan = 0
    for s in asal:
        kata = _kata_dalam(words, s["start"], s["end"])
        if not kata:
            # Klip tanpa transkrip: jedanya dibaca dari suaranya sendiri.
            jejak = jejak_energi(sumber, s["start"], s["end"])
            if jejak:
                calon += _potongan_dari_energi(
                    jejak, s["start"], s["start"], s["end"],
                    _ambang_tanpa_kata(jejak), jeda_min=jeda_min)
            continue
        milik = _potongan_segmen(s["start"], s["end"], kata,
                                 jeda_min=jeda_min, gumaman=gumaman)
        if milik and sumber is not None:
            jejak = jejak_energi(sumber, s["start"], s["end"])
            ambang = _ambang(jejak, s["start"], kata)
            if jejak and ambang:
                dipangkas = []
                for x, y, jenis in milik:
                    iris = _iris_sunyi(jejak, s["start"], x, y, ambang)
                    if iris is None:
                        ditahan += 1
                        continue
                    dipangkas.append((iris[0], iris[1], jenis))
                milik = dipangkas
        calon += milik
    if ditahan:
        log.info("%d potongan dibatalkan: di sana masih ada suara", ditahan)

    # Yang terpanjang lebih dulu bila jumlahnya harus dibatasi: satu jeda tiga
    # detik lebih terasa daripada enam jeda setengah detik.
    if len(calon) > maks_potong:
        calon = sorted(sorted(calon, key=lambda c: c[1] - c[0], reverse=True)[:maks_potong])

    keluar: list[dict] = []
    rincian: dict[str, int] = {}
    dibuang = 0.0
    for s in asal:
        kursor = s["start"]
        milik = [c for c in calon if c[0] >= s["start"] - 1e-6 and c[1] <= s["end"] + 1e-6]
        for x, y, jenis in milik:
            if x - kursor >= SISA_MIN:
                keluar.append({"start": round(kursor, 3), "end": round(x, 3)})
                dibuang += y - x
                rincian[jenis] = rincian.get(jenis, 0) + 1
                kursor = y
            elif x <= kursor + 1e-6:
                # Potongan yang menempel pada potongan sebelumnya: lanjutkan
                # saja, tanpa menyisakan kepingan.
                dibuang += max(0.0, y - max(x, kursor))
                rincian[jenis] = rincian.get(jenis, 0) + 1
                kursor = max(kursor, y)
        if s["end"] - kursor >= SISA_MIN:
            keluar.append({"start": round(kursor, 3), "end": round(s["end"], 3)})
        elif keluar:
            keluar[-1]["end"] = round(s["end"], 3)

    if not keluar or dibuang < 0.35:
        return {"segments": asal, "dibuang": 0.0, "potongan": 0, "rincian": {}}
    log.info("Klip dirapatkan: %d potongan, %.1f detik dibuang (%s)",
             sum(rincian.values()), dibuang,
             ", ".join(f"{k}×{v}" for k, v in rincian.items()))
    return {"segments": keluar, "dibuang": round(dibuang, 2),
            "potongan": sum(rincian.values()), "rincian": rincian,
            "ditahan": ditahan}


def ringkas(hasil: dict, durasi_lama: float) -> str:
    """Kalimat jujur untuk ditampilkan: apa yang dibuang dan jadi berapa."""
    if not hasil.get("potongan"):
        return "Tidak ada jeda yang cukup panjang untuk dibuang."
    baru = durasi_lama - hasil["dibuang"]
    bagian = []
    for nama, label in (("jeda", "jeda"), ("gumaman", "gumaman"),
                        ("awal", "diam di awal"), ("akhir", "diam di akhir")):
        if hasil["rincian"].get(nama):
            bagian.append(f"{hasil['rincian'][nama]} {label}")
    return (f"{', '.join(bagian)} dibuang, {hasil['dibuang']:.1f} detik. "
            f"Klip jadi {baru:.0f} detik dari {durasi_lama:.0f}.")
