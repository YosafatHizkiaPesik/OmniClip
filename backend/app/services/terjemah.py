"""
Menerjemahkan baris subtitle, dengan WAKTU yang tetap sama.

Subtitle terjemahan tidak dibuat dari transkrip ulang: baris-baris klip yang
sudah ada diterjemahkan satu lawan satu, jadi tiap baris terjemahan muncul dan
hilang tepat bersama baris aslinya. Itu satu-satunya cara dua subtitle —
Inggris di atas, Indonesia di bawah — bisa berjalan serempak.

Konsekuensinya jujur: sorotan per KATA tidak berlaku untuk terjemahan. Urutan
kata berubah antar bahasa, jadi tidak ada cara menandai kapan "rumah"
diucapkan dalam kalimat yang aslinya berbunyi "house". Baris terjemahan tampil
utuh selama baris aslinya diucapkan.

Mesinnya Gemini. Hasil tiap baris disimpan (tabel `terjemahan`, dikunci sidik
teks + bahasa), jadi menerjemahkan klip yang sama dua kali — atau dua klip yang
berbagi kalimat — tidak memakai kuota lagi.
"""

import hashlib
import json
import logging
from typing import Optional

from ..db import get_conn, now, tx
from .peringkat_model import catat_gagal, tanpa_kuota

log = logging.getLogger("omniclip.terjemah")

# Nama bahasa untuk perintah ke model. Kode yang tidak ada di sini tetap bisa
# dipakai — model mengerti kode ISO — tapi nama lengkap lebih tidak ambigu.
NAMA_BAHASA = {
    "id": "Bahasa Indonesia (santai, seperti subtitle YouTube, bukan bahasa buku)",
    "en": "English", "ms": "Bahasa Melayu", "ja": "Japanese", "ko": "Korean",
    "zh": "Simplified Chinese", "ar": "Arabic", "es": "Spanish", "pt": "Portuguese",
    "fr": "French", "de": "German", "hi": "Hindi", "th": "Thai", "vi": "Vietnamese",
    "tr": "Turkish", "ru": "Russian", "jv": "Basa Jawa", "su": "Basa Sunda",
}

PER_PANGGILAN = 80
GEMINI_BATAS_DETIK = 45


def _sidik(teks: str) -> str:
    return hashlib.sha1(teks.strip().encode("utf-8")).hexdigest()


def _dari_simpanan(teks: list[str], bahasa: str) -> dict[str, str]:
    sidik = list({_sidik(t) for t in teks if t.strip()})
    if not sidik:
        return {}
    keluar: dict[str, str] = {}
    conn = get_conn()
    for i in range(0, len(sidik), 400):
        bagian = sidik[i:i + 400]
        tanda = ",".join("?" * len(bagian))
        for r in conn.execute(
                f"SELECT sidik, teks FROM terjemahan WHERE bahasa=? AND sidik IN ({tanda})",
                [bahasa, *bagian]):
            keluar[r["sidik"]] = r["teks"]
    return keluar


def _simpan(pasangan: dict[str, str], bahasa: str) -> None:
    if not pasangan:
        return
    with tx() as c:
        c.executemany(
            "INSERT OR REPLACE INTO terjemahan(sidik, bahasa, teks, created_at) VALUES (?,?,?,?)",
            [(s, bahasa, t, now()) for s, t in pasangan.items()])


def _panggil(baris: list[str], bahasa: str, *, api_key: str, models: list[str],
             model_override: Optional[str], konteks: str) -> tuple[list[str], str]:
    from google import genai
    from google.genai import types

    schema = types.Schema(
        type=types.Type.OBJECT, required=["baris"],
        properties={"baris": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT, required=["i", "t"],
                properties={"i": types.Schema(type=types.Type.INTEGER),
                            "t": types.Schema(type=types.Type.STRING)}))})
    tujuan = NAMA_BAHASA.get(bahasa, bahasa)
    prompt = (
        f"Terjemahkan setiap baris subtitle di bawah ke {tujuan}.\n\n"
        "Aturan:\n"
        "- SATU baris masuk, SATU baris keluar, dengan nomor yang sama. Jangan "
        "menggabungkan atau memecah baris: tiap baris tampil di layar pada "
        "waktunya sendiri.\n"
        "- Terjemahan harus sependek aslinya, karena dibaca sambil menonton. "
        "Pilih kata yang wajar diucapkan, bukan terjemahan kata demi kata.\n"
        "- Baris yang sepotong-sepotong tetap diterjemahkan sepotong: kalimatnya "
        "bersambung ke baris berikutnya.\n"
        "- Nama orang, merek, dan istilah game tidak diterjemahkan.\n"
        "- Jangan menambahkan tanda kutip, catatan, atau penjelasan.\n"
        + (f"\nKonteks video: {konteks}\n" if konteks else "")
        + "\n=== BARIS ===\n"
        + "\n".join(f"[{i}] {t}" for i, t in enumerate(baris))
    )
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=schema,
        temperature=0.2, max_output_tokens=max(2048, 90 * len(baris)))
    # Batas waktu total, bukan hanya per panggilan. Saat Gemini sibuk (503)
    # atau kuotanya habis, mencoba enam model satu per satu terukur lebih
    # dari dua menit — padahal ada cadangan tanpa kunci yang menjawab dalam
    # hitungan detik (`_panggil_gratis`).
    import time as _time
    tenggat = _time.monotonic() + GEMINI_BATAS_DETIK
    client = genai.Client(api_key=api_key,
                          http_options=types.HttpOptions(timeout=GEMINI_BATAS_DETIK * 1000))
    urutan = ([model_override] if model_override else []) + \
        [m for m in models if m != model_override]
    terakhir: Optional[Exception] = None
    for model in urutan:
        if _time.monotonic() > tenggat:
            terakhir = terakhir or TimeoutError("Gemini tidak menjawab dalam batas waktu.")
            break
        if tanpa_kuota(model) and model != urutan[-1]:
            continue
        try:
            resp = client.models.generate_content(model=model, contents=prompt, config=config)
            data = json.loads(resp.text)
        except Exception as e:
            terakhir = e
            catat_gagal(model, e)
            log.warning("Terjemahan gagal di %s: %s", model, str(e)[:200])
            continue
        hasil = [""] * len(baris)
        for row in data.get("baris") or []:
            try:
                i = int(row["i"])
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= i < len(baris):
                hasil[i] = str(row.get("t") or "").strip().strip('"')
        if sum(1 for h in hasil if h) >= max(1, int(0.8 * len(baris))):
            return hasil, model
        terakhir = RuntimeError(f"{model} hanya menerjemahkan sebagian baris")
    raise terakhir or RuntimeError("Gemini tidak mengembalikan terjemahan.")


GRATIS_NAMA = "Google Terjemahan (tanpa kunci)"
GRATIS_BATAS_HURUF = 1800     # per permintaan; URL panjang ditolak


def _panggil_gratis(baris: list[str], bahasa: str) -> list[str]:
    """
    Terjemahan tanpa kunci lewat titik akses web Google Terjemahan.

    Cadangan, bukan jalur utama: tidak resmi (bisa berubah atau dibatasi), dan
    hasilnya harfiah — Gemini memahami konteks video, yang ini tidak. Tapi ia
    membuat subtitle kedua bisa dipakai siapa pun, termasuk yang belum punya
    kunci Gemini atau kuota hariannya habis. Baris dikirim berkelompok,
    dipisah baris baru, dan dipasangkan kembali per baris.
    """
    import urllib.parse
    import urllib.request

    kode = bahasa.split("-")[0].lower() if bahasa not in ("zh-TW", "zh-CN") else bahasa
    keluar: list[str] = []
    kelompok: list[str] = []

    def kirim(isi: list[str]) -> list[str]:
        # Baris baru di dalam satu baris subtitle akan mengacaukan pemasangan.
        bersih = [" ".join(x.split()) for x in isi]
        url = ("https://translate.googleapis.com/translate_a/single?"
               + urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": kode,
                                         "dt": "t", "q": "\n".join(bersih)}))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        teks = "".join(seg[0] for seg in (data[0] or []) if seg and seg[0])
        hasil = [x.strip() for x in teks.split("\n")]
        if len(hasil) != len(bersih):
            # Pemasangan tidak bisa dipercaya: satu per satu.
            if len(bersih) == 1:
                return [" ".join(hasil)]
            return [kirim([x])[0] for x in bersih]
        return hasil

    panjang = 0
    for b in baris:
        if kelompok and panjang + len(b) + 1 > GRATIS_BATAS_HURUF:
            keluar += kirim(kelompok)
            kelompok, panjang = [], 0
        kelompok.append(b)
        panjang += len(b) + 1
    if kelompok:
        keluar += kirim(kelompok)
    return keluar


def terjemahkan(teks: list[str], bahasa: str, *, api_key: str, models: list[str],
                model_override: Optional[str] = None, konteks: str = "") -> dict:
    """
    {teks: [...], dari_simpanan: n, model: str|None}. Panjang keluaran = masukan;
    baris yang gagal diterjemahkan berisi teks aslinya, bukan kosong.

    Tanpa kunci Gemini, atau bila Gemini gagal (kuota habis, sibuk), jatuh ke
    `_panggil_gratis`.
    """
    simpanan = _dari_simpanan(teks, bahasa)
    kurang = [t for t in dict.fromkeys(teks) if t.strip() and _sidik(t) not in simpanan]
    model = None
    for i in range(0, len(kurang), PER_PANGGILAN):
        bagian = kurang[i:i + PER_PANGGILAN]
        hasil = None
        if api_key and models:
            try:
                hasil, model = _panggil(bagian, bahasa, api_key=api_key, models=models,
                                        model_override=model_override, konteks=konteks)
            except Exception as e:
                log.warning("Terjemahan Gemini gagal, memakai cadangan tanpa kunci: %s", str(e)[:160])
        if hasil is None:
            hasil, model = _panggil_gratis(bagian, bahasa), GRATIS_NAMA
        baru = {_sidik(a): b for a, b in zip(bagian, hasil) if b}
        _simpan(baru, bahasa)
        simpanan.update(baru)
    keluar = [simpanan.get(_sidik(t), t) if t.strip() else t for t in teks]
    return {"teks": keluar, "dari_simpanan": len(teks) - len(kurang), "model": model}


# --- Subtitle kedua otomatis untuk video berbahasa asing --------------------------
#
# Anime berbahasa Jepang, video berbahasa Inggris: pemiliknya ingin subtitle
# ASLINYA tetap tampil (terkesan lebih menarik) DENGAN terjemahan di bawahnya.
# Dibuat saat analisis, bukan menunggu tombol per klip.
BAWAAN_OTOMATIS = "id"

# Terjemahan DI ATAS subtitle asli: asli tetap di 300 dari bawah (tumbuh ke
# atas sampai ±2 baris), terjemahan kuning di 560. Bukan di bawahnya: anime
# dari situs fansub hampir selalu membawa subtitle tertanam di 15% bawah
# gambar, dan terjemahan di sana tertimpa (terlihat pada uji anime OP 1179).
GAYA_KEDUA_OTOMATIS = {
    "font": "Poppins", "size": 70, "primary": "#FFE500", "uppercase": False,
    "position": "bottom", "margin_v": 560, "outline_px": 6, "animation": "fade",
    "bg": False,
}


def bahasa_otomatis() -> str:
    """Bahasa tujuan terjemahan otomatis, atau "" bila dimatikan."""
    try:
        from ..repos import settings as settings_repo
        v = settings_repo.get("terjemah.otomatis", BAWAAN_OTOMATIS).strip()
    except Exception:
        v = BAWAAN_OTOMATIS
    return "" if v in ("", "mati") else v


def sidik_utama(lines: list[dict]) -> str:
    """Sama dengan `sidikUtama` di TerjemahPanel.jsx: penanda terjemahan usang."""
    return "\n".join(f"{float(l['start']):.2f}|{float(l['end']):.2f}|{l.get('text') or ''}"
                      for l in lines or [])


def kedua_untuk_klip(clips: list[dict], bahasa_video: Optional[str], *,
                     api_key: str, models: list[str], konteks: str = "") -> int:
    """
    Menambahkan `subtitle_kedua` (terjemahan) ke klip-klip yang belum punya.
    Mengembalikan jumlah klip yang diberi terjemahan; 0 bila tidak perlu.
    """
    tujuan = bahasa_otomatis()
    asal = (bahasa_video or "").split("-")[0].lower()
    if not tujuan or not asal or asal == tujuan.split("-")[0].lower():
        return 0
    semua = [l.get("text") or "" for c in clips if not c.get("subtitle_kedua")
             for l in c.get("subtitles") or []]
    if not any(t.strip() for t in semua):
        return 0
    hasil = terjemahkan(semua, tujuan, api_key=api_key, models=models, konteks=konteks)["teks"]
    i = n = 0
    for c in clips:
        if c.get("subtitle_kedua"):
            continue
        lines = c.get("subtitles") or []
        c["subtitle_kedua"] = {
            "aktif": True, "bahasa": tujuan,
            "lines": [{"start": l["start"], "end": l["end"], "text": hasil[i + k] or l.get("text", "")}
                      for k, l in enumerate(lines)],
            "style": dict(GAYA_KEDUA_OTOMATIS),
            "sumber_sidik": sidik_utama(lines),
        }
        i += len(lines)
        n += 1
    return n
