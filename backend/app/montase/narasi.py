"""
Narasi dan rekaman suara Montase (JOB-4 M3.3).

Narasi: teks + suara dari katalog `services/tts.py` (Piper lokal atau suara
Microsoft lewat edge-tts) -> berkas WAV -> bahan berasal `tts`. Kuncinya
sidik (teks, suara, kecepatan): meminta narasi yang persis sama mengembalikan
bahan yang sudah ada, jadi mengetik ulang kalimat yang sama tidak membuat
berkas baru. Mengubah teksnya membuat bahan baru, dan editor mengganti bahan
item narasinya (item tetap di tempatnya).

Rekaman mikrofon: peramban merekam WebM/Opus (MediaRecorder); di sini diubah
ke M4A/AAC supaya pratinjau, mesin render, dan pemutar mana pun membacanya
sama, lalu dicatat sebagai bahan berasal `rekam`.

Berkas keduanya milik Montase (`<data>/montase/suara/`), jadi ikut terhapus
bersama bahannya; berkas bahan dari Unduhan atau Aset tidak pernah dihapus.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import uuid
from pathlib import Path

from ..config import STORAGE_DIR
from ..repos import media as media_repo
from ..repos import montase as repo
from ..services.media import probe
from . import bahan as bahan_svc

log = logging.getLogger("omniclip.montase.narasi")

TEKS_MAKS = 2000
KECEPATAN = (0.6, 1.6)


class GagalNarasi(Exception):
    pass


def folder() -> Path:
    return STORAGE_DIR / "montase" / "suara"


def daftar_suara() -> list[dict]:
    from ..services import tts
    return [{"id": v["id"], "label": v["label"], "bahasa": v.get("bahasa", "id"),
             "mesin": v["engine"], "siap": bool(v["ready"])} for v in tts.catalogue()]


def _catat(pid: int, asal: str, rujukan: str, jalur: Path, nama: str) -> dict:
    info = probe(jalur)
    data = {
        "asal": asal, "rujukan": rujukan, "nama": nama[:200],
        "rel_path": media_repo.rel_to_storage(jalur), "jenis": "audio",
        "durasi": info.get("duration"), "lebar": None, "tinggi": None, "fps": None,
        "ada_suara": True,
    }
    baris = repo.catat_bahan(pid, data)
    bahan_svc._jadwalkan_persiapan(baris["id"], pid)
    return baris


def buat_narasi(pid: int, teks: str, suara: str, kecepatan: float = 1.0) -> dict:
    from ..services import tts
    teks = " ".join((teks or "").split())
    if not teks:
        raise GagalNarasi("Teks narasinya masih kosong.")
    if len(teks) > TEKS_MAKS:
        raise GagalNarasi(f"Teks narasi paling panjang {TEKS_MAKS} huruf.")
    kecepatan = min(KECEPATAN[1], max(KECEPATAN[0], float(kecepatan or 1)))
    spec = tts.voice_by_id(suara)
    if spec["engine"] == "piper" and not tts.available():
        raise GagalNarasi("Suara pembaca judul belum terpasang. Pasang dulu di Studio Klip "
                          "(Judul > suara pembaca), atau pilih suara Microsoft.")
    if spec["engine"] == "edge" and not tts.edge_available():
        raise GagalNarasi("Suara Microsoft tidak tersedia di pemasangan ini.")
    kunci = hashlib.sha1(f"{spec['id']}|{kecepatan:.2f}|{teks}".encode()).hexdigest()[:16]
    ada = repo.cari_bahan(pid, "tts", kunci)
    if ada is not None and bahan_svc.jalur_asli(pid, ada["id"]) is not None:
        return ada
    jalur = folder() / f"narasi_{kunci}.wav"
    try:
        tts.synthesize(teks, jalur, rate=kecepatan, voice=spec["id"])
    except Exception as e:      # noqa: BLE001 - jaringan, model, atau teks yang ditolak mesin
        log.warning("Narasi gagal: %s", e)
        jalur.unlink(missing_ok=True)
        raise GagalNarasi("Suara tidak bisa dibuat. Periksa sambungan internet untuk suara "
                          "Microsoft, atau coba suara lain.") from e
    if ada is not None:         # berkasnya hilang: catatan lama dipakai ulang
        return ada
    return _catat(pid, "tts", kunci, jalur, teks)


def simpan_rekaman(pid: int, sumber: Path, nama: str) -> dict:
    """Rekaman mikrofon (WebM/Opus atau apa pun yang dibaca ffmpeg) -> M4A."""
    kunci = uuid.uuid4().hex[:16]
    tujuan = folder() / f"rekam_{kunci}.m4a"
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(sumber),
                        "-vn", "-ac", "1", "-ar", "48000", "-c:a", "aac", "-b:a", "128k",
                        str(tujuan)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not tujuan.is_file() or tujuan.stat().st_size == 0:
        tujuan.unlink(missing_ok=True)
        raise GagalNarasi("Rekaman tidak bisa dibaca. Coba rekam ulang.")
    return _catat(pid, "rekam", kunci, tujuan, nama)


def hapus_berkas_milik(b: dict) -> None:
    """Berkas tts/rekam dihapus bersama bahannya; asal lain tidak disentuh."""
    if b.get("asal") not in ("tts", "rekam") or not b.get("rel_path"):
        return
    jalur = media_repo.abs_from_storage(b["rel_path"])
    try:
        if jalur.is_relative_to(folder()):
            jalur.unlink(missing_ok=True)
    except OSError:
        pass
