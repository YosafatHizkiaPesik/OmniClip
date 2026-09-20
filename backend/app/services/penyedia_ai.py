"""
Panggilan model yang MENONTON: video, gambar, dan teks dalam satu permintaan.

Bahan dikirim sebagai daftar netral —
    [{"video": bytes, "fps": 2}, {"gambar": bytes}, {"teks": str}]
— supaya penyedia lain (OpenRouter) bisa memakai bahan yang sama tanpa
pemanggil tahu siapa yang menjawab.

Pola rantai modelnya sama dengan `gemini.refine_candidates`: urutan dari yang
terkuat (`peringkat_model.rantai`), model sibuk/timeout langsung dilewati,
model berkuota nol atau sudah ditutup dicatat dan tidak ditanya lagi, dan ada
batas waktu per panggilan serta untuk seluruh rangkaian — tanpa itu satu
permintaan yang tidak pernah dijawab menahan pekerjaan selamanya.
"""

import json
import logging
import time
from typing import Callable, Optional

from .peringkat_model import catat_gagal, tanpa_kuota

log = logging.getLogger("omniclip.penyedia")

PER_PANGGILAN_MS = 150_000
BATAS_TOTAL_DETIK = 300

_SIBUK = ("503", "UNAVAILABLE", "overloaded", "high demand", "timed out",
          "Timeout", "timeout", "504", "DEADLINE")


class SemuaGagal(RuntimeError):
    """Tidak satu model pun menjawab dengan benar. `.rincian` berisi alasannya."""

    def __init__(self, rincian: list[str]):
        super().__init__("Semua model gagal — " + " | ".join(rincian))
        self.rincian = rincian


def _bagian_gemini(bahan: list[dict]):
    from google.genai import types
    parts = []
    for b in bahan:
        if "video" in b:
            parts.append(types.Part(
                inline_data=types.Blob(data=b["video"], mime_type=b.get("mime", "video/mp4")),
                video_metadata=types.VideoMetadata(fps=b.get("fps", 2))))
        elif "gambar" in b:
            parts.append(types.Part(inline_data=types.Blob(
                data=b["gambar"], mime_type=b.get("mime", "image/jpeg"))))
        elif "teks" in b:
            parts.append(types.Part(text=b["teks"]))
    return [types.Content(role="user", parts=parts)]


def tanya_gemini(bahan: list[dict], *, schema, sistem: str, api_key: str,
                 models: list[str], suhu: float = 0.3, maks_keluaran: int = 8192,
                 kabar: Optional[Callable[[str], None]] = None,
                 batal: Optional[Callable[[], None]] = None,
                 batas_detik: float = BATAS_TOTAL_DETIK) -> tuple[dict, str, dict]:
    """
    (data_json, nama_model, pemakaian_token). Melempar `SemuaGagal` bila tidak
    ada model yang menjawab; `batal()` boleh melempar untuk menghentikannya.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key,
                          http_options=types.HttpOptions(timeout=PER_PANGGILAN_MS))
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=schema,
        temperature=suhu, max_output_tokens=maks_keluaran,
        system_instruction=sistem,
        # Resolusi rendah: ±100 token per detik video, bukan ±300. Yang dinilai
        # adalah siapa bereaksi kapan — wajah dan gerak besar, bukan detail.
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
    )
    isi = _bagian_gemini(bahan)
    tenggat = time.monotonic() + batas_detik
    gagal: list[str] = []

    for urutan, model in enumerate(models):
        if tanpa_kuota(model) and urutan + 1 < len(models):
            continue
        berikut = models[urutan + 1] if urutan + 1 < len(models) else None
        for percobaan in range(2):
            if batal is not None:
                batal()
            if tenggat - time.monotonic() <= 5:
                gagal.append(f"batas waktu {batas_detik:.0f} dtk habis")
                raise SemuaGagal(gagal)
            if kabar is not None:
                kabar(f"Menonton klip ({model})"
                      + (f", percobaan {percobaan + 1}" if percobaan else "") + "…")
            try:
                resp = client.models.generate_content(model=model, contents=isi,
                                                      config=config)
                teks = resp.text or ""
                try:
                    data = json.loads(teks)
                except json.JSONDecodeError as e:
                    alasan = getattr((resp.candidates or [None])[0], "finish_reason", None)
                    raise ValueError(f"JSON tidak lengkap ({len(teks)} karakter, "
                                     f"finish_reason={alasan}): {e}") from e
                u = resp.usage_metadata
                pakai = {"masuk": getattr(u, "prompt_token_count", None),
                         "keluar": getattr(u, "candidates_token_count", None),
                         "berpikir": getattr(u, "thoughts_token_count", None)}
                log.info("%s menjawab: %s token masuk, %s keluar", model,
                         pakai["masuk"], pakai["keluar"])
                return data, model, pakai
            except Exception as e:
                pesan = str(e)
                gagal.append(f"{model}: {pesan[:140]}")
                log.warning("%s gagal (percobaan %d): %s", model, percobaan + 1, pesan[:200])
                if catat_gagal(model, e):
                    if kabar is not None and berikut:
                        kabar(f"{model} tidak tersedia untuk kunci ini — mencoba {berikut}…")
                    break
                if any(x in pesan for x in _SIBUK):
                    if kabar is not None:
                        kabar(f"{model} sedang sibuk" + (f" — mencoba {berikut}…" if berikut else "."))
                    break
                if "429" in pesan or "RESOURCE_EXHAUSTED" in pesan:
                    if percobaan == 0:
                        time.sleep(3)
                        continue
                    break
                if percobaan == 0 and isinstance(e, ValueError):
                    config.temperature = 0.1
                    continue
                break
    raise SemuaGagal(gagal or ["tidak ada model yang bisa dicoba"])
