"""
Pengelola kunci Gemini: nama, uji sungguhan per model, hapus satu per satu.

Diminta pemilik 16 Oktober 2026: kunci baru sudah ditambahkan tapi video tetap
dianalisis mesin lokal, dan tidak ada cara melihat kunci mana yang bekerja.
Di log ternyata kunci baru itu lolos uji saat disimpan, lalu ditolak saat
dipakai: 403 "Your project has been denied access". Uji lama hanya meminta
DAFTAR MODEL, dan Google tetap menjawab daftar itu untuk proyek yang sudah
diblokir. Uji di sini mengirim permintaan sungguhan (satu kata) ke tiap model,
jadi yang dilaporkan sama dengan yang terjadi saat analisis.

Kuncinya tetap disimpan di `ai.api_key` (satu per baris) supaya seluruh
pemakai `config.get_api_keys()` tidak berubah. Nama ada di `ai.kunci_nama`,
hasil uji terakhir di singgahan. Sidik kunci (sha256, 12 huruf) hanya dipakai
di mesin ini sebagai pengenal; kuncinya sendiri tidak pernah dikirim ke
antarmuka, hanya empat huruf terakhirnya.

Sisa kuota tidak bisa ditanyakan ke Google: Gemini API tidak punya
endpoint-nya. Yang bisa dilaporkan jujur adalah keadaan tiap model saat diuji
(bisa dipakai, jatah harian habis, jatah per menit habis) beserta batas yang
disebut Google di jawabannya bila ada.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

log = logging.getLogger("omniclip.kunci_ai")

KUNCI_NAMA = "ai.kunci_nama"
# Berapa model yang diuji per kunci. Tiap uji memakai satu permintaan dari jatah
# harian model itu, jadi tidak semua model ditanya.
MODEL_DIUJI = 5
# Kunci yang ditolak Google dilewati pemilihan klip selama ini, supaya tiap
# analisis tidak membuang belasan detik mencoba semua modelnya dulu.
LEWATI_DITOLAK_DETIK = 6 * 3600


def sidik(kunci: str) -> str:
    return hashlib.sha256((kunci or "").encode()).hexdigest()[:12]


def _settings():
    from ..repos import settings as settings_repo
    return settings_repo


def _nama_semua() -> dict:
    try:
        d = json.loads(_settings().get(KUNCI_NAMA) or "{}")
        return d if isinstance(d, dict) else {}
    except (TypeError, ValueError):
        return {}


def _simpan_nama(d: dict) -> None:
    _settings().set_value(KUNCI_NAMA, json.dumps(d, ensure_ascii=False))


def _kunci_db() -> list[str]:
    from ..config import _pecah_kunci
    return _pecah_kunci(_settings().get("ai.api_key"))


def _kunci_env() -> list[str]:
    import os
    from ..config import _pecah_kunci
    return _pecah_kunci(os.environ.get("GEMINI_API_KEY", ""))


def _hasil_uji(sid: str) -> Optional[dict]:
    from ..repos import cache as cache_repo
    d = cache_repo.ambil(f"kunci.uji:{sid}", ttl=30 * 86400)
    return d if isinstance(d, dict) else None


def daftar() -> list[dict]:
    """Semua kunci Gemini, urut seperti dicoba, tanpa isi kuncinya."""
    nama = _nama_semua()
    keluar, terlihat = [], set()
    for sumber, daftar_k in (("db", _kunci_db()), ("env", _kunci_env())):
        for k in daftar_k:
            sid = sidik(k)
            if sid in terlihat:
                continue
            terlihat.add(sid)
            keluar.append({
                "id": sid,
                "nama": nama.get(sid) or f"Gemini …{k[-4:]}",
                "nama_sendiri": bool(nama.get(sid)),
                "akhiran": k[-4:],
                "sumber": sumber,
                "uji": _hasil_uji(sid),
            })
    return keluar


def boleh_dipakai(kunci: str) -> bool:
    """False bila uji terakhir (belum lama) menyatakan Google menolak kunci ini."""
    u = _hasil_uji(sidik(kunci))
    if not u or u.get("status") != "ditolak":
        return True
    return time.time() - float(u.get("waktu") or 0) > LEWATI_DITOLAK_DETIK


# --- Uji ------------------------------------------------------------------------

def _jenis_galat(e: Exception) -> dict:
    """Satu kegagalan model -> {status, pesan, batas?, tunggu?, proyek?}."""
    kode = getattr(e, "code", None)
    teks = str(e)
    rinci = getattr(e, "details", None)
    mentah = json.dumps(rinci, ensure_ascii=False) if rinci else teks
    hasil: dict = {}
    m = re.search(r"projects/(\d{5,})", mentah)
    if m:
        hasil["proyek"] = m.group(1)
    if kode == 429 or "RESOURCE_EXHAUSTED" in teks:
        harian = re.search(r"PerDay", mentah)
        nilai = (re.search(r"limit:\s*(\d+)", mentah)
                 or re.search(r'"quotaValue":\s*"?(\d+)', mentah))
        tunggu = re.search(r'"retryDelay":\s*"(\d+)s"', mentah)
        hasil.update(status="kuota_harian" if harian else "kuota_menit")
        if nilai:
            hasil["batas"] = int(nilai.group(1))
            # "limit: 0" = tingkat gratis memang tidak memberi jatah untuk
            # model ini (model pro), bukan jatah yang sudah terpakai habis.
            if hasil["batas"] == 0:
                hasil["status"] = "tanpa_jatah"
        if tunggu:
            hasil["tunggu"] = int(tunggu.group(1))
        return hasil
    if kode == 403 or "PERMISSION_DENIED" in teks:
        hasil.update(status="ditolak",
                     pesan="denied access" if "denied access" in teks else teks[:160])
        return hasil
    if kode in (400, 401):
        if "API key" in teks or "API_KEY" in teks or kode == 401:
            hasil.update(status="tidak_sah")
            return hasil
    if kode == 404:
        hasil.update(status="tidak_ada")
        return hasil
    if kode in (500, 502, 503, 504) or "UNAVAILABLE" in teks:
        hasil.update(status="sibuk")
        return hasil
    hasil.update(status="galat", pesan=teks[:160])
    return hasil


def _coba_model(kunci: str, model: str) -> dict:
    from google import genai
    from google.genai import types
    mulai = time.time()
    client = genai.Client(api_key=kunci, http_options=types.HttpOptions(timeout=25_000))
    try:
        client.models.generate_content(
            model=model, contents="Jawab dengan satu kata saja: siap",
            config=types.GenerateContentConfig(max_output_tokens=16, temperature=0))
        return {"model": model, "status": "ok", "detik": round(time.time() - mulai, 1)}
    except Exception as e:                                # noqa: BLE001
        return {"model": model, **_jenis_galat(e)}


def _ringkas(model: list[dict], galat_daftar: Optional[dict]) -> str:
    if galat_daftar:
        return galat_daftar.get("status", "galat")
    st = [m.get("status") for m in model]
    if "ok" in st:
        return "bekerja"
    if st and all(s == "tidak_sah" for s in st):
        return "tidak_sah"
    # Satu model yang ditolak berarti proyeknya diblokir; model lain yang
    # "tanpa jatah" atau "tidak ada" tidak mengubah kesimpulan itu.
    if "ditolak" in st:
        return "ditolak"
    if any(s in ("kuota_harian", "kuota_menit") for s in st):
        return "kuota"
    if "sibuk" in st:
        return "sibuk"
    return "galat"


def uji_kunci(kunci: str, *, jumlah_model: int = MODEL_DIUJI) -> dict:
    """Menguji satu kunci dengan permintaan sungguhan; hasilnya disimpan."""
    from ..repos import cache as cache_repo
    from .peringkat_model import daftar_kunci, urutkan

    galat_daftar = None
    try:
        semua = urutkan(daftar_kunci(kunci))
    except Exception as e:                                # noqa: BLE001
        galat_daftar = _jenis_galat(e)
        semua = []
    # Model yang diuji: yang dipakai analisis (flash) lebih dulu, lalu satu
    # lite (cadangan terakhir), lalu satu pro. Tingkat gratis tidak memberi
    # jatah untuk model pro ("limit: 0"), jadi pro hanya penanda.
    flash = [m for m in semua if "flash" in m and "lite" not in m]
    lite = [m for m in semua if "lite" in m]
    pro = [m for m in semua if "pro" in m]
    pilih = flash[:max(1, jumlah_model - 2)] + lite[:1] + pro[:1]
    pilih = pilih[:jumlah_model] or semua[:jumlah_model]
    model: list[dict] = []
    if pilih:
        with ThreadPoolExecutor(max_workers=3) as ex:
            model = list(ex.map(lambda m: _coba_model(kunci, m), pilih))
    hasil = {
        "waktu": time.time(),
        "status": _ringkas(model, galat_daftar),
        "model": model,
        "model_tersedia": len(semua),
        "proyek": next((m.get("proyek") for m in model if m.get("proyek")),
                       (galat_daftar or {}).get("proyek")),
    }
    cache_repo.simpan(f"kunci.uji:{sidik(kunci)}", hasil)
    log.info("Uji kunci …%s: %s (%s)", kunci[-4:], hasil["status"],
             ", ".join(f"{m['model']}={m['status']}" for m in model))
    return hasil


def uji(sid: str) -> dict:
    for k in _kunci_db() + _kunci_env():
        if sidik(k) == sid:
            return uji_kunci(k)
    raise KeyError(sid)


# --- Ubah -----------------------------------------------------------------------

def tambah(kunci: str, nama: str = "") -> dict:
    """Menguji lalu MENAMBAHKAN kunci (bukan mengganti yang lama)."""
    from ..config import _pecah_kunci
    kunci = (_pecah_kunci(kunci) or [""])[0]
    if not kunci:
        raise ValueError("API key kosong.")
    hasil = uji_kunci(kunci, jumlah_model=3)
    if hasil["status"] == "tidak_sah":
        raise ValueError("Google tidak mengenali kunci ini. Periksa apakah seluruhnya "
                         "tersalin, tanpa spasi atau baris terpotong di ujung.")
    if hasil["status"] == "ditolak":
        raise ValueError("Google menolak kunci ini: proyeknya tidak diizinkan memakai "
                         "Gemini API (\"Your project has been denied access\"). Kunci "
                         "baru dari akun Google yang sama biasanya ikut ditolak; buat "
                         "kunci dari akun Google lain.")
    ada = _kunci_db()
    if kunci not in ada:
        ada.append(kunci)
        _settings().set_value("ai.provider", "gemini")
        _settings().set_value("ai.api_key", "\n".join(ada))
    nama = (nama or "").strip()[:60]
    if nama:
        d = _nama_semua()
        d[sidik(kunci)] = nama
        _simpan_nama(d)
    return {"id": sidik(kunci), "uji": hasil}


def ganti_nama(sid: str, nama: str) -> None:
    d = _nama_semua()
    nama = (nama or "").strip()[:60]
    if nama:
        d[sid] = nama
    else:
        d.pop(sid, None)
    _simpan_nama(d)


def hapus(sid: str) -> None:
    ada = _kunci_db()
    sisa = [k for k in ada if sidik(k) != sid]
    if len(sisa) == len(ada):
        if any(sidik(k) == sid for k in _kunci_env()):
            raise PermissionError("env")
        raise KeyError(sid)
    if sisa:
        _settings().set_value("ai.api_key", "\n".join(sisa))
    else:
        _settings().delete("ai.api_key")
    d = _nama_semua()
    d.pop(sid, None)
    _simpan_nama(d)
    from ..repos import cache as cache_repo
    try:
        cache_repo.simpan(f"kunci.uji:{sid}", None)
    except Exception:                                     # noqa: BLE001
        pass
