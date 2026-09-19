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
    client = genai.Client(api_key=api_key,
                          http_options=types.HttpOptions(timeout=120_000))
    urutan = ([model_override] if model_override else []) + \
        [m for m in models if m != model_override]
    terakhir: Optional[Exception] = None
    for model in urutan:
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


def terjemahkan(teks: list[str], bahasa: str, *, api_key: str, models: list[str],
                model_override: Optional[str] = None, konteks: str = "") -> dict:
    """
    {teks: [...], dari_simpanan: n, model: str|None}. Panjang keluaran = masukan;
    baris yang gagal diterjemahkan berisi teks aslinya, bukan kosong.
    """
    simpanan = _dari_simpanan(teks, bahasa)
    kurang = [t for t in dict.fromkeys(teks) if t.strip() and _sidik(t) not in simpanan]
    model = None
    for i in range(0, len(kurang), PER_PANGGILAN):
        bagian = kurang[i:i + PER_PANGGILAN]
        hasil, model = _panggil(bagian, bahasa, api_key=api_key, models=models,
                                model_override=model_override, konteks=konteks)
        baru = {_sidik(a): b for a, b in zip(bagian, hasil) if b}
        _simpan(baru, bahasa)
        simpanan.update(baru)
    keluar = [simpanan.get(_sidik(t), t) if t.strip() else t for t in teks]
    return {"teks": keluar, "dari_simpanan": len(teks) - len(kurang), "model": model}
