"""
Urutan model Gemini: yang terkuat dan benar-benar bisa dipakai lebih dulu.

Dulu urutannya daftar tetap di config.py, disusun tangan. Dua hal membuat itu
salah arah:

- Model baru terus keluar. Daftar tetap tertinggal — kunci sudah bisa memakai
  gemini-3.8-flash sementara rantai bawaan masih mulai dari 3.6.
- Model terkuat tidak selalu bisa dipakai. Paket gratis memberi kuota NOL untuk
  seri Pro: jawabannya 429 "limit: 0" pada setiap permintaan, bukan "kuota
  habis, coba lagi nanti". Menanyainya di setiap pencarian cuma membuang waktu.

Jadi urutannya disusun dari daftar model yang dilaporkan kunci itu sendiri,
diperingkat menurut kelas (pro di atas flash) dan generasi (3.8 di atas 3.6),
dan model yang pernah menjawab "limit: 0" dilewati selama sehari. Bila suatu
saat kuncinya mendapat akses Pro, Pro otomatis terpakai lagi keesokan harinya.

Variabel OMNICLIP_GEMINI_MODELS tetap menang: bila diisi, urutannya dipakai
apa adanya.
"""

import logging
import os
import re
import threading
import time
from typing import Optional

log = logging.getLogger("omniclip.model")

# Hanya model teks serba guna yang cocok untuk membaca transkrip sejam dan
# menjawab dalam JSON terstruktur. Yang lain ditolak dengan sengaja:
#   - lite         : dibuat untuk tugas ringan; menilai hook butuh penalaran
#   - customtools  : varian untuk pemakaian alat, bukan untuk tugas ini
#   - gemma        : jendela konteksnya tidak muat transkrip panjang
#   - deep-research, antigravity : agen, bukan model yang menjawab satu prompt
_POLA = re.compile(r"^gemini-(\d+(?:\.\d+)?)-(pro|flash)(?:-preview(?:-[\w-]+)?)?$")
_ALIAS = {"gemini-pro-latest": ("pro", 0.0), "gemini-flash-latest": ("flash", 0.0)}

_KUNCI_DAFTAR = 6 * 3600          # daftar model disegarkan tiap enam jam
_LAMA_TANPA_KUOTA = 24 * 3600     # "limit: 0" diingat sehari

_kunci = threading.Lock()
_daftar: dict[str, tuple[float, list[str]]] = {}   # sidik kunci -> (waktu, model)
_tanpa_kuota: dict[str, float] = {}                 # model -> waktu tercatat


def peringkat(nama: str) -> Optional[tuple]:
    """Kunci urut (makin kecil makin kuat), atau None bila tidak cocok."""
    nama = nama.replace("models/", "")
    if nama in _ALIAS:
        kelas, versi = _ALIAS[nama]
        alias = 1
    else:
        m = _POLA.match(nama)
        if not m or any(x in nama for x in ("lite", "customtools", "tts", "image")):
            return None
        versi, kelas, alias = float(m.group(1)), m.group(2), 0
    # Versi bernomor tetap di atas alias berkelas sama: alias bisa berubah
    # diam-diam, jadi ia penutup, bukan pembuka.
    return (0 if kelas == "pro" else 1, alias, -versi, "preview" in nama, nama)


def cocok(nama: str) -> bool:
    return peringkat(nama) is not None


def urutkan(nama_model: list[str]) -> list[str]:
    return sorted((n for n in set(nama_model) if cocok(n)), key=peringkat)


def _sidik(api_key: str) -> str:
    import hashlib
    return hashlib.sha1(api_key.encode()).hexdigest()[:12]


def daftar_kunci(api_key: str) -> list[str]:
    """Semua model teks yang dilaporkan kunci ini (dicache enam jam)."""
    sidik = _sidik(api_key)
    with _kunci:
        ada = _daftar.get(sidik)
        if ada and time.time() - ada[0] < _KUNCI_DAFTAR:
            return list(ada[1])
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key,
                          http_options=types.HttpOptions(timeout=20_000))
    nama = []
    for m in client.models.list():
        if "generateContent" not in (getattr(m, "supported_actions", None) or []):
            continue
        nama.append(m.name.replace("models/", ""))
    with _kunci:
        _daftar[_sidik(api_key)] = (time.time(), nama)
    return nama


# Catatannya disimpan ke tabel settings, bukan hanya di memori: tanpa itu
# setiap kali aplikasi dibuka ulang, menu model kembali menyebut Pro sebagai
# "terkuat" dan pencarian pertama membuang satu putaran menanyainya lagi.
_NAMA_SIMPANAN = "ai.model_tak_terpakai"
_dimuat = False


def _muat() -> None:
    global _dimuat
    if _dimuat:
        return
    _dimuat = True
    try:
        import json
        from ..repos import settings as settings_repo
        data = json.loads(settings_repo.get(_NAMA_SIMPANAN) or "{}")
        with _kunci:
            for m, t in data.items():
                _tanpa_kuota.setdefault(m, float(t))
    except Exception:
        pass


def _simpan() -> None:
    try:
        import json
        from ..repos import settings as settings_repo
        with _kunci:
            data = {m: t for m, t in _tanpa_kuota.items()
                    if time.time() - t < _LAMA_TANPA_KUOTA}
        settings_repo.set_value(_NAMA_SIMPANAN, json.dumps(data))
    except Exception:
        pass


def tanpa_kuota(model: str) -> bool:
    _muat()
    with _kunci:
        t = _tanpa_kuota.get(model)
    return t is not None and time.time() - t < _LAMA_TANPA_KUOTA


def catat_gagal(model: str, galat: BaseException | str) -> bool:
    """
    Dipanggil setiap kali satu model gagal. Mengembalikan True bila model itu
    ternyata tidak bisa dipakai sama sekali (kuota nol atau sudah ditutup) —
    pemanggil tidak perlu mengulang.
    """
    pesan = str(galat)
    tanpa = ("429" in pesan or "RESOURCE_EXHAUSTED" in pesan) and re.search(r"limit:\s*0\b", pesan)
    # Model yang masih terdaftar tapi sudah ditutup untuk pengguna baru
    # menjawab 404 — sama tidak bergunanya dengan kuota nol.
    pensiun = "404" in pesan or "NOT_FOUND" in pesan
    if tanpa or pensiun:
        # "Baru" juga berlaku untuk catatan yang sudah kedaluwarsa, supaya
        # tanggal di simpanan ikut diperbarui.
        baru = not tanpa_kuota(model)
        with _kunci:
            _tanpa_kuota[model] = time.time()
        if baru:
            _simpan()
            log.info("%s tidak bisa dipakai kunci ini (%s); dilewati 24 jam",
                     model, "kuota nol" if tanpa else "404")
        return True
    return False


def rantai(api_key: str, pilihan: Optional[str] = None) -> list[str]:
    """
    Urutan model yang dicoba, dari yang paling kuat.

    `pilihan` (model yang dipilih pengguna) selalu di depan, sisanya cadangan.
    Model tanpa kuota dibuang, kecuali bila itu satu-satunya yang tersisa.
    """
    from ..config import GEMINI_MODELS

    if os.getenv("OMNICLIP_GEMINI_MODELS"):
        dasar = list(GEMINI_MODELS)
    else:
        try:
            dasar = urutkan(daftar_kunci(api_key)) or list(GEMINI_MODELS)
        except Exception as e:
            log.warning("Daftar model tidak terbaca, memakai urutan bawaan: %s", str(e)[:160])
            dasar = list(GEMINI_MODELS)
    urutan = ([pilihan] if pilihan else []) + [m for m in dasar if m != pilihan]
    bisa = [m for m in urutan if not tanpa_kuota(m)]
    return bisa or urutan
