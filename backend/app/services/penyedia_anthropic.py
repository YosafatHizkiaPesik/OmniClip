"""
Claude (Anthropic) sebagai salah satu koneksi AI (koneksi_ai.py).

Memakai SDK resmi `anthropic`. Jawaban diikat skema lewat structured outputs
(`output_config.format` json_schema), jadi hasilnya selalu JSON yang sah.
Model bawaan claude-opus-5-5; model lain bisa dipilih per koneksi dari daftar
yang dilaporkan kuncinya sendiri (Models API).
"""

from __future__ import annotations

import base64
import json
from typing import Optional

PER_PANGGILAN_DETIK = 240.0


def _klien(kunci: str):
    import anthropic
    return anthropic.Anthropic(api_key=kunci, timeout=PER_PANGGILAN_DETIK, max_retries=1)


def _gagal(e: Exception):
    """Galat SDK -> koneksi_ai.Gagal dengan status yang dipahami antarmuka."""
    import anthropic

    from .koneksi_ai import Gagal
    if isinstance(e, anthropic.AuthenticationError):
        return Gagal("Kunci Anthropic tidak sah.", "tidak_sah")
    if isinstance(e, anthropic.PermissionDeniedError):
        return Gagal("Kunci Anthropic tidak diizinkan memakai model ini.", "ditolak")
    if isinstance(e, anthropic.NotFoundError):
        return Gagal("Model tidak ditemukan untuk kunci ini.", "tidak_ada")
    if isinstance(e, anthropic.RateLimitError):
        return Gagal("Batas permintaan Anthropic tercapai, coba lagi sebentar lagi.", "kuota")
    if isinstance(e, anthropic.BadRequestError):
        pesan = getattr(e, "message", str(e))
        if "credit balance" in pesan.lower():
            return Gagal("Saldo kredit Anthropic habis.", "saldo")
        return Gagal(pesan[:300], "galat")
    if isinstance(e, anthropic.APIStatusError):
        return Gagal(f"Anthropic menjawab {e.status_code}.", "sibuk" if e.status_code >= 500 else "galat")
    if isinstance(e, anthropic.APIConnectionError):
        return Gagal("Tidak bisa menghubungi Anthropic.", "sibuk")
    return Gagal(str(e)[:300], "galat")


def daftar_model(kunci: str) -> list[str]:
    try:
        return [m.id for m in _klien(kunci).models.list()]
    except Exception as e:                                # noqa: BLE001
        raise _gagal(e) from e


def tanya(kunci: str, model: str, bahan: list[dict], *, skema: dict, sistem: str,
          maks_keluaran: int = 16000) -> tuple[dict, str, dict]:
    """(data_json, "anthropic:<model>", pemakaian)."""
    from .koneksi_ai import Gagal
    from .openrouter import _json_schema

    isi: list[dict] = []
    for b in bahan:
        if "gambar" in b:
            isi.append({"type": "image", "source": {
                "type": "base64", "media_type": b.get("mime", "image/jpeg"),
                "data": base64.standard_b64encode(b["gambar"]).decode("utf-8")}})
        elif "teks" in b:
            isi.append({"type": "text", "text": b["teks"]})
    if not isi:
        raise Gagal("tidak ada bahan yang bisa dibaca Claude", "galat")
    try:
        resp = _klien(kunci).messages.create(
            model=model, max_tokens=max(1024, maks_keluaran), system=sistem,
            messages=[{"role": "user", "content": isi}],
            output_config={"format": {"type": "json_schema", "schema": _json_schema(skema)}},
        )
    except Exception as e:                                # noqa: BLE001
        raise _gagal(e) from e
    if resp.stop_reason == "refusal":
        raise Gagal("Claude menolak permintaan ini.", "galat")
    if resp.stop_reason == "max_tokens":
        raise Gagal("Jawaban Claude terpotong (batas token).", "galat")
    teks: Optional[str] = next((b.text for b in resp.content if b.type == "text"), None)
    if not teks:
        raise Gagal("Claude tidak mengembalikan teks.", "galat")
    try:
        data = json.loads(teks)
    except json.JSONDecodeError as e:
        raise Gagal(f"JSON dari Claude tidak terbaca: {e}", "galat") from e
    u = resp.usage
    return data, f"anthropic:{model}", {"masuk": u.input_tokens, "keluar": u.output_tokens}
