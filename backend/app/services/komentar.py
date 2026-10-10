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

import hashlib
import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ..config import STORAGE_DIR
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


# =============================================================================
# Suara komentar (F1-4)
# =============================================================================
#
# Dua jalan, dan rekaman orangnya sendiri yang didahulukan: suara manusia yang
# sama di setiap klip adalah identitas kanal, sedangkan TTS terdengar sama di
# ribuan kanal lain. TTS tetap ada untuk yang tidak bisa merekam, dan berkas
# TTS ditandai `sintetis` DI SINI, di server, supaya label konten sintetis
# YouTube (F0-7) tidak bergantung pada kejujuran peramban.
#
# Keduanya disimpan sebagai m4a 48 kHz stereo yang kekerasannya sudah
# diratakan ke -16 LUFS, sama dengan suara klip sesudah `loudnorm`. Rekaman
# mikrofon laptop biasanya 10-20 dB lebih pelan daripada podcast yang diklip;
# tanpa diratakan, komentarnya tenggelam begitu klip berlanjut.

SUARA_DIR = STORAGE_DIR / "komentar_suara"
_POLA_ID = re.compile(r"[a-f0-9]{16}")
BATAS_REKAMAN_DETIK = 60.0


def _ratakan_ke_m4a(sumber: Path, tujuan: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(sumber),
         "-vn", "-t", f"{BATAS_REKAMAN_DETIK:.0f}",
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000",
         "-ac", "2", "-c:a", "aac", "-b:a", "160k", str(tujuan)],
        check=True, timeout=180, capture_output=True)


def _durasi_berkas(path: Path) -> float:
    from .media import probe
    try:
        return round(float((probe(path) or {}).get("duration") or 0.0), 3)
    except Exception:                            # noqa: BLE001
        return 0.0


def _catatan_suara(sidik: str) -> Path:
    return SUARA_DIR / f"{sidik}.json"


def _simpan(sementara: Path, *, sintetis: bool, teks: str = "",
            suara: str = "") -> dict:
    """Memindahkan m4a jadi ke tempatnya, bernama sidik isinya."""
    h = hashlib.sha1(sementara.read_bytes()).hexdigest()[:16]
    tujuan = SUARA_DIR / f"{h}.m4a"
    if tujuan.is_file():
        sementara.unlink(missing_ok=True)
    else:
        sementara.replace(tujuan)
    durasi = _durasi_berkas(tujuan)
    if durasi <= 0.2:
        tujuan.unlink(missing_ok=True)
        raise ValueError("Rekamannya kosong atau terlalu pendek.")
    data = {"id": h, "durasi": durasi, "sintetis": bool(sintetis),
            "teks": (teks or "")[:400], "suara": suara}
    _catatan_suara(h).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def simpan_rekaman(sumber: Path) -> dict:
    """Rekaman mikrofon dari Studio (webm/ogg/apa pun) -> suara komentar."""
    SUARA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkstemp(prefix="komentar_", suffix=".m4a", dir=SUARA_DIR)[1])
    try:
        _ratakan_ke_m4a(sumber, tmp)
    except subprocess.CalledProcessError as e:
        tmp.unlink(missing_ok=True)
        raise ValueError("Rekaman ini tidak bisa dibaca sebagai suara.") from e
    return _simpan(tmp, sintetis=False)


def buat_tts(teks: str, suara: str = "") -> dict:
    """Membacakan `teks` dengan TTS -> suara komentar bertanda sintetis."""
    from . import tts

    teks = re.sub(r"\s+", " ", tanpa_pisah(teks or "")).strip()
    if not teks:
        raise ValueError("Tulis dulu komentarnya, baru bisa dibacakan.")
    suara = suara or tts.DEFAULT_VOICE
    tts.voice_by_id(suara)              # menolak nama suara yang tidak dikenal
    SUARA_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SUARA_DIR) as d:
        wav = Path(d) / "baca.wav"
        tts.synthesize(teks, wav, rate=1.0, voice=suara)
        tmp = Path(d) / "jadi.m4a"
        _ratakan_ke_m4a(wav, tmp)
        keluar = Path(tempfile.mkstemp(prefix="komentar_", suffix=".m4a", dir=SUARA_DIR)[1])
        tmp.replace(keluar)
    return _simpan(keluar, sintetis=True, teks=teks, suara=suara)


def jalur_suara(sidik: str) -> Optional[Path]:
    sidik = (sidik or "").strip()
    if not _POLA_ID.fullmatch(sidik):
        return None
    p = SUARA_DIR / f"{sidik}.m4a"
    return p if p.is_file() else None


def info_suara(sidik: str) -> Optional[dict]:
    if jalur_suara(sidik) is None:
        return None
    try:
        return json.loads(_catatan_suara(sidik).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# =============================================================================
# Render komentar (F1-5, F1-6)
# =============================================================================
#
# Komentar disisipkan dengan MEMBEKUKAN gambar, bukan ditumpuk di atas klip.
# Komentar yang ditimpa ke atas orang yang sedang bicara membuat keduanya tidak
# terdengar; dibekukan, penonton mendengar komentarnya utuh lalu klip lanjut
# dari titik yang sama. Pembuka membekukan bingkai pertama, penutup bingkai
# terakhir, sela bingkai di jeda yang dipilih.
#
# Mode "timpa" tetap ada untuk komentar pendek yang memang ingin terdengar
# bersamaan ("nah ini"), dan di situ suara klip diredam selama komentarnya
# berbunyi dengan rumus yang sama dengan redaman musik latar.
#
# Kartu opini (F1-6) adalah teks komentarnya sendiri di tengah layar, bisa
# dengan atau tanpa suara. Tanpa suara, lamanya mengikuti waktu baca.

POSISI = ("pembuka", "sela", "penutup")
MODE = ("bekukan", "timpa")
MAKS_DETIK_KOMENTAR = 20.0
JEDA_EKOR = 0.3              # napas sesudah komentar sebelum klip lanjut
KARTU_UKURAN = 3.6           # persen tinggi kanvas
MAKS_KOMENTAR = 6


def detik_baca(teks: str) -> float:
    """Berapa lama kartu teks tanpa suara perlu tampil supaya terbaca."""
    return round(max(2.5, min(8.0, len(teks or "") / 14.0 + 1.0)), 2)


def siapkan_render(items, durasi: float) -> list[dict]:
    """Membersihkan daftar komentar dari Studio. Yang tak bisa dipakai dibuang."""
    keluar: list[dict] = []
    for k in (items or [])[:MAKS_KOMENTAR]:
        if not isinstance(k, dict):
            continue
        posisi = str(k.get("posisi") or "")
        if posisi not in POSISI:
            continue
        teks = _bersih(k.get("teks"), 240)
        path = jalur_suara(str(k.get("suara") or ""))
        info = info_suara(str(k.get("suara") or "")) if path else None
        if not teks and path is None:
            continue
        tampil = bool(k.get("tampil_teks", path is None)) and bool(teks)
        if path is None and not tampil:
            continue
        if path is not None:
            d = float((info or {}).get("durasi") or _durasi_berkas(path)) + JEDA_EKOR
        else:
            d = detik_baca(teks)
        d = round(min(MAKS_DETIK_KOMENTAR, max(0.5, d)), 3)
        mode = str(k.get("mode") or "bekukan")
        mode = mode if mode in MODE else "bekukan"
        if posisi == "pembuka":
            t = 0.0
        elif posisi == "penutup":
            t = float(durasi)
        else:
            try:
                t = float(k.get("t"))
            except (TypeError, ValueError):
                continue
            t = min(max(0.1, t), max(0.1, durasi - 0.1))
        if mode == "timpa":
            if posisi == "penutup":
                t = max(0.0, durasi - d)
            # Komentar yang lebih panjang daripada sisa klipnya tidak dipotong
            # di tengah kalimat: ia dibekukan saja.
            if d > durasi - t + 1e-6:
                mode = "bekukan"
                t = float(durasi) if posisi == "penutup" else t
        d = round(d, 3)
        keluar.append({
            "posisi": posisi, "t": round(t, 3), "d": d, "mode": mode,
            "teks": teks, "tampil": tampil, "path": path,
            "sintetis": bool((info or {}).get("sintetis")) if path else False,
        })
    urut = {"pembuka": 0, "sela": 1, "penutup": 2}
    keluar.sort(key=lambda k: (k["t"], urut[k["posisi"]]))
    return keluar


def _bungkus(teks: str, per_baris: int) -> str:
    baris, kini = [], ""
    for kata in teks.split():
        if kini and len(kini) + 1 + len(kata) > per_baris:
            baris.append(kini)
            kini = kata
        else:
            kini = f"{kini} {kata}".strip()
    if kini:
        baris.append(kini)
    return "\n".join(baris[:7])


def _kartu(bagian: list[str], label: str, teks: str, t0: float, d: float,
           nomor: int, out_w: int, out_h: int) -> str:
    """
    drawtext kartu opini, satu per baris. Mengembalikan label videonya.

    Satu `drawtext` per baris, bukan satu dengan pemisah baris: `drawtext`
    tidak membungkus sendiri, dan "\\n" di dalam teksnya tercetak sebagai
    huruf n. Terlihat pada render uji 10 Oktober 2026.
    """
    from .render import TEKS_KELUARGA_BAWAAN, _graf_teks

    tinggi = out_h * KARTU_UKURAN / 100.0
    per_baris = max(10, int(out_w * 0.78 / (tinggi * 0.62)))
    baris = _bungkus(teks, per_baris).split("\n")
    tinggi_baris = KARTU_UKURAN * 1.55                  # persen kanvas
    atas = 50.0 - tinggi_baris * len(baris) / 2
    for j, isi in enumerate(baris):
        lapis = {
            "teks": isi, "t": t0, "dur": d,
            "rect": {"x": 4.0, "y": atas + j * tinggi_baris, "w": 92.0, "h": tinggi_baris},
            "ukuran": KARTU_UKURAN, "keluarga": TEKS_KELUARGA_BAWAAN,
            "warna": "#FFFFFF", "garis": "#000000", "tebal_garis": 0.0,
            "latar": "#000000", "opasitas": 1.0,
            "fade_masuk": min(0.2, d / 4), "fade_keluar": min(0.2, d / 4),
        }
        label = _graf_teks(bagian, lapis, label, 900 + nomor * 10 + j, out_w, out_h)
    return label


def graf_render(items: list[dict], vin: str, ain: str, *, input_awal: int,
                fps: int, out_w: int, out_h: int, durasi: float
                ) -> tuple[list[str], str, str, str, float]:
    """
    (input tambahan, graf, label video, label audio, detik tambahan).

    `vin`/`ain` adalah aliran klip yang SUDAH jadi (bersubtitle, suaranya sudah
    diratakan), jadi bingkai yang dibekukan adalah yang memang dilihat penonton.
    """
    from .render import rumus_redam

    if not items:
        return [], "", vin, ain, 0.0
    inputs: list[str] = []
    bagian: list[str] = []
    idx = input_awal
    masukan: dict[int, int] = {}
    for n, k in enumerate(items):
        if k["path"] is not None:
            inputs += ["-i", str(k["path"])]
            masukan[n] = idx
            idx += 1

    def suara_komentar(n: int, d: float, label: str) -> None:
        bagian.append(f"[{masukan[n]}:a]aresample=48000,aformat=channel_layouts=stereo,"
                      f"asetpts=PTS-STARTPTS,apad,atrim=duration={d:.3f}{label}")

    bagian.append(f"{ain}aresample=48000,aformat=channel_layouts=stereo[kmA0]")
    video, audio = vin, "[kmA0]"

    # --- Timpa: di atas aliran yang masih utuh, waktunya waktu klip asli. ---
    timpa = [(n, k) for n, k in enumerate(items) if k["mode"] == "timpa"]
    if timpa:
        suara_t = [(n, k) for n, k in timpa if n in masukan]
        if suara_t:
            rumus = rumus_redam([(k["t"], k["t"] + k["d"]) for _, k in suara_t])
            bagian.append(f"{audio}volume=volume='{rumus}':eval=frame[kmA1]")
            campur = ["[kmA1]"]
            for n, k in suara_t:
                ms = int(round(k["t"] * 1000))
                suara_komentar(n, k["d"], f"[kmT{n}]")
                bagian.append(f"[kmT{n}]adelay={ms}|{ms}[kmTd{n}]")
                campur.append(f"[kmTd{n}]")
            bagian.append("".join(campur) + f"amix=inputs={len(campur)}:duration=first:"
                          "normalize=0,alimiter=limit=0.97[kmA2]")
            audio = "[kmA2]"
        for n, k in timpa:
            if k["tampil"]:
                video = _kartu(bagian, video, k["teks"], k["t"], k["d"], n, out_w, out_h)

    # --- Bekukan: aliran dipotong di titik komentar, bingkainya ditahan. ---
    beku = [(n, k) for n, k in enumerate(items) if k["mode"] == "bekukan"]
    tambah = 0.0
    if beku:
        urutan: list[tuple] = []
        kini = 0.0
        for n, k in beku:
            t = min(k["t"], durasi)
            if t - kini > 1e-3:
                urutan.append(("klip", kini, t))
            urutan.append(("beku", n, k))
            kini = max(kini, t)
        if durasi - kini > 1e-3:
            urutan.append(("klip", kini, durasi))

        jumlah = len(urutan)
        bagian.append(f"{video}split={jumlah}" + "".join(f"[kmv{i}]" for i in range(jumlah)))
        n_klip = sum(1 for u in urutan if u[0] == "klip")
        if n_klip:
            bagian.append(f"{audio}asplit={n_klip}" + "".join(f"[kma{i}]" for i in range(n_klip)))
        else:
            bagian.append(f"{audio}anullsink")
        satu = 1.0 / max(1, fps)
        potong: list[str] = []
        ia = 0
        for i, u in enumerate(urutan):
            if u[0] == "klip":
                _, a, b = u
                bagian.append(f"[kmv{i}]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[kpv{i}]")
                bagian.append(f"[kma{ia}]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[kpa{i}]")
                ia += 1
            else:
                _, n, k = u
                d = k["d"]
                # Satu bingkai sedikit sebelum titiknya: tepat di ujung klip
                # tidak ada bingkai lagi untuk ditahan.
                ft = max(0.0, min(k["t"], durasi - 3 * satu))
                label_v = f"[kbv{i}]"
                bagian.append(f"[kmv{i}]trim=start={ft:.3f}:duration={3 * satu:.4f},"
                              f"setpts=PTS-STARTPTS,trim=end_frame=1,"
                              f"tpad=stop_mode=clone:stop_duration={d:.3f},"
                              f"trim=duration={d:.3f},setpts=PTS-STARTPTS{label_v}")
                if k["tampil"]:
                    label_v = _kartu(bagian, label_v, k["teks"], 0.0, d, n, out_w, out_h)
                bagian.append(f"{label_v}null[kpv{i}]")
                if n in masukan:
                    suara_komentar(n, d, f"[kpa{i}]")
                else:
                    bagian.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={d:.3f}[kpa{i}]")
                tambah += d
            potong.append(f"[kpv{i}][kpa{i}]")
        bagian.append("".join(potong) + f"concat=n={jumlah}:v=1:a=1[kmV][kmA]")
        video, audio = "[kmV]", "[kmA]"

    return inputs, ";".join(bagian), video, audio, round(tambah, 3)


def geser_subtitle(subtitles, items: list[dict]) -> list[dict]:
    """Waktu subtitle sesudah bingkai dibekukan, untuk sidecar klipnya."""
    beku = [(k["t"], k["d"]) for k in items if k["mode"] == "bekukan"]
    if not beku:
        return list(subtitles or [])
    out = []
    for b in subtitles or []:
        if not isinstance(b, dict):
            continue
        try:
            s = float(b.get("start", 0.0))
        except (TypeError, ValueError):
            out.append(b)
            continue
        geser = sum(d for t, d in beku if t <= s + 1e-6)
        if geser:
            b = {**b, "start": round(s + geser, 3),
                 "end": round(float(b.get("end", s)) + geser, 3)}
            if isinstance(b.get("words"), list):
                b["words"] = [{**w, "s": round(float(w.get("s", 0)) + geser, 3),
                               "e": round(float(w.get("e", 0)) + geser, 3)}
                              for w in b["words"] if isinstance(w, dict)]
        out.append(b)
    return out


def ringkas_sidecar(items: list[dict]) -> list[dict]:
    """Yang dicatat di sidecar: tanpa jalur berkas, dengan detiknya."""
    return [{"posisi": k["posisi"], "t": k["t"], "d": k["d"], "mode": k["mode"],
             "teks": k["teks"], "bersuara": k["path"] is not None,
             "sintetis": k["sintetis"], "kartu": k["tampil"]} for k in items]
