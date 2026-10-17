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
import contextvars
import logging
from contextlib import contextmanager
import time
from typing import Callable, Optional

from .peringkat_model import (catat_gagal, catat_habis_harian, kuota_habis,
                              tanpa_kuota)

log = logging.getLogger("omniclip.penyedia")

PER_PANGGILAN_MS = 150_000
BATAS_TOTAL_DETIK = 300

_SIBUK = ("503", "UNAVAILABLE", "overloaded", "high demand", "timed out",
          "Timeout", "timeout", "504", "DEADLINE")


# Pekerjaan yang sedang berjalan, supaya catatan pemakaian tahu panggilan ini
# untuk apa dan untuk video mana. Sebuah variabel konteks, bukan argumen, karena
# jalur panggilannya melewati enam lapis yang tidak satu pun peduli soal ini.
_pekerjaan: contextvars.ContextVar = contextvars.ContextVar(
    "pekerjaan_ai", default=("ai", None))


@contextmanager
def pekerjaan(nama: str, video_id=None):
    """
    Menandai panggilan AI di dalam blok ini sebagai milik pekerjaan `nama`.

    Dipakai pemanggil paling luar, supaya catatan pemakaian bisa menjawab
    "token habis untuk apa" tanpa tiap lapis di antaranya harus meneruskan
    argumen yang tidak ada urusannya dengan pekerjaannya sendiri.
    """
    token = _pekerjaan.set((nama, video_id))
    try:
        yield
    finally:
        _pekerjaan.reset(token)


def _catat(model, pakai, *, berhasil: bool, sebab: str = "") -> None:
    from .pemakaian_ai import catat
    nama, vid = _pekerjaan.get()
    catat(model=model, pekerjaan=nama, video_id=vid, pakai=pakai,
          berhasil=berhasil, sebab=sebab)


def ada_ai(api_key: str = "", *, butuh_gambar: bool = False) -> bool:
    """Apakah ada AI yang bisa ditanya: kunci dari pemanggil, atau koneksi aktif."""
    if api_key:
        return True
    try:
        from . import koneksi_ai
        return bool(koneksi_ai.rantai(butuh_gambar=butuh_gambar))
    except Exception:                                     # noqa: BLE001
        return False


class SemuaGagal(RuntimeError):
    """Tidak satu model pun menjawab dengan benar. `.rincian` berisi alasannya."""

    def __init__(self, rincian: list[str]):
        super().__init__("Semua model gagal, " + " | ".join(rincian))
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
        # adalah siapa bereaksi kapan, yaitu wajah dan gerak besar, bukan detail.
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
        # Token BERPIKIR ikut memakan jatah keluaran, dan itu yang membuang
        # panggilan ke model terbaik.
        #
        # Terbaca di catatan pemakaian pemiliknya, 9 Oktober 2026: pemilihan
        # tema subtitle gagal berulang kali dengan "JSON tidak lengkap (281
        # karakter, finish_reason=MAX_TOKENS)" padahal jatahnya 2.700 token.
        # Dua ratus delapan puluh satu karakter itu sekitar 80 token; sisanya
        # habis sebelum satu huruf jawaban pun keluar. Yang gagal justru model
        # kuat (3.5-flash dan 3-flash-preview, 0 dari 4 berhasil), dan yang
        # akhirnya menjawab model lite. Jadi bukan modelnya yang kurang pintar,
        # melainkan jatahnya yang habis dipakai berpikir.
        #
        # Tugas-tugas di sini memilih dari menu dan mengisi JSON berstruktur;
        # tidak satu pun menuntut penalaran panjang. Dimatikan, seluruh jatah
        # jadi milik jawabannya. Model yang tidak mengenal setelan ini
        # mengabaikannya, dan itu sebabnya ia dipasang tanpa syarat.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
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
                _catat(model, pakai, berhasil=True)
                return data, model, pakai
            except Exception as e:
                pesan = str(e)
                _catat(model, None, berhasil=False, sebab=pesan)
                gagal.append(f"{model}: {pesan[:140]}")
                log.warning("%s gagal (percobaan %d): %s", model, percobaan + 1, pesan[:200])
                if catat_gagal(model, e):
                    if kabar is not None and berikut:
                        kabar(f"{model} tidak tersedia untuk kunci ini, mencoba {berikut}…")
                    break
                if any(x in pesan for x in _SIBUK):
                    if kabar is not None:
                        kabar(f"{model} sedang sibuk" + (f", mencoba {berikut}…" if berikut else "."))
                    break
                if kuota_habis(e):
                    # Jatah harian dihitung per MODEL: yang berikutnya masih
                    # punya jatahnya sendiri. Yang percuma cuma mengulang model
                    # yang sama.
                    catat_habis_harian(model, e)
                    if kabar is not None and berikut:
                        kabar(f"Jatah harian {model} habis, mencoba {berikut}…")
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


def tanya(bahan: list[dict], *, schema, sistem: str, api_key: str,
          models: list[str], suhu: float = 0.3, maks_keluaran: int = 8192,
          kabar: Optional[Callable[[str], None]] = None,
          batal: Optional[Callable[[], None]] = None,
          batas_detik: float = BATAS_TOTAL_DETIK,
          cadangan: Optional[Callable[[], list[dict]]] = None) -> tuple[dict, str, dict]:
    """
    Koneksi AI dicoba sesuai urutan di Pengaturan (services/koneksi_ai.py).
    (data, model, pakai).

    Gemini menerima video utuh dengan suaranya; OpenRouter memakai rantai
    model gratisnya sendiri; koneksi lain (Claude, server bergaya OpenAI, AI
    lokal) menerima teks, dan gambar kunci dari `cadangan()` bila mereka bisa
    melihat. Koneksi yang tidak bisa melihat dilewati untuk bahan bergambar.

    `api_key`/`models` dari pemanggil tetap dihormati untuk Gemini: kunci itu
    dicoba dengan daftar model yang diberikan.
    """
    from . import koneksi_ai, openrouter
    from .peringkat_model import rantai as rantai_gemini

    rincian: list[str] = []
    daftar = koneksi_ai.rantai()
    if api_key and not any(k.get("kunci") == api_key for k in daftar):
        daftar = [{"id": "-", "nama": "Gemini", "penyedia": "gemini", "kunci": api_key,
                   "model": ""}] + daftar
    butuh_lihat = any(("video" in b) or ("gambar" in b) for b in bahan)
    _cad: Optional[list[dict]] = None

    for k in daftar:
        if batal is not None:
            batal()
        try:
            if k["penyedia"] == "gemini":
                m = models if (k["kunci"] == api_key and models) else rantai_gemini(k["kunci"])
                return tanya_gemini(bahan, schema=schema, sistem=sistem, api_key=k["kunci"],
                                    models=m, suhu=suhu, maks_keluaran=maks_keluaran,
                                    kabar=kabar, batal=batal, batas_detik=batas_detik)
            if k["penyedia"] == "openrouter":
                if kabar is not None:
                    kabar("Mencoba OpenRouter…")
                return openrouter.tanya(
                    bahan, skema=schema, sistem=sistem, api_key=k["kunci"],
                    models=openrouter.rantai(k.get("model") or None),
                    suhu=suhu, maks_keluaran=maks_keluaran, kabar=kabar, batal=batal,
                    batas_detik=batas_detik, cadangan=cadangan)
            bisa_lihat = koneksi_ai.PENYEDIA.get(k["penyedia"], {}).get("gambar")
            isi = bahan
            if any("video" in b for b in bahan):
                if not (bisa_lihat and cadangan is not None):
                    rincian.append(f"{k['nama']}: tidak bisa menonton video")
                    continue
                if _cad is None:
                    if kabar is not None:
                        kabar("Menyiapkan gambar kunci…")
                    _cad = cadangan()
                isi = [b for b in _cad if "suara" not in b]
            elif butuh_lihat and not bisa_lihat:
                rincian.append(f"{k['nama']}: tidak bisa melihat gambar")
                continue
            if kabar is not None:
                kabar(f"Memakai {k['nama']}…")
            data, nama_model, pakai = koneksi_ai.tanya_satu(
                k, isi, skema=schema, sistem=sistem, suhu=suhu,
                maks_keluaran=min(maks_keluaran, 4096) if k["penyedia"] == "lokal" else maks_keluaran)
            _catat(nama_model, pakai, berhasil=True)
            return data, nama_model, pakai
        except SemuaGagal as e:
            rincian.extend(e.rincian)
        except Exception as e:                            # noqa: BLE001
            if type(e).__name__ == "JobCancelled":
                raise
            rincian.append(f"{k['nama']}: {str(e)[:300]}")
            log.warning("%s gagal: %s", k["nama"], str(e)[:200])
    if not daftar:
        rincian.append("belum ada koneksi AI yang aktif")
    raise SemuaGagal(rincian)
