"""
Koneksi AI universal: satu daftar untuk SEMUA penyedia, urut sesuai pilihan.

Diminta pemilik 17 Oktober 2026: Gemini dan OpenRouter jangan dua kartu
terpisah, dan jangan hanya dua penyedia itu ("mungkin ke depannya saya ingin
memasukkan API Claude atau lainnya"); di Pengaturan bisa dipilih mana yang
dipakai, dan AI lokal bisa dijadikan utama.

Tiap koneksi:
    {id, nama, penyedia, kunci, model, alamat, aktif, sumber}
Urutan daftar = urutan dicoba; yang pertama dan aktif adalah UTAMA. Yang
gagal (kuota, ditolak, sibuk) membuat koneksi berikutnya dicoba.

Jenis penyedia:
    gemini      SDK google-genai (bisa video); ujinya per model (kunci_ai)
    openrouter  API bergaya OpenAI, rantai model gratis (openrouter.py)
    anthropic   Claude, SDK resmi `anthropic` (penyedia_anthropic.py)
    openai, groq, mistral, deepseek, cerebras, kustom
                API bergaya OpenAI (/chat/completions); `kustom` untuk Ollama,
                LM Studio, atau server lain dengan alamat sendiri
    lokal       AI lokal OmniClip (ai_lokal.py, llama.cpp)

Kunci dari variabel lingkungan (`GEMINI_API_KEY`, `OPENROUTER_API_KEY`) ikut
tampil sebagai koneksi bersumber `env`: urutan dan aktifnya bisa diatur, tapi
kuncinya tidak disimpan di basis data dan tidak bisa dihapus dari sini.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

log = logging.getLogger("omniclip.koneksi_ai")

SIMPAN = "ai.koneksi"

# json: "skema" = response_format json_schema; "objek" = json_object + bentuk
# di perintah; "tidak" = bentuk di perintah saja.
PENYEDIA = {
    "gemini": {"nama": "Google Gemini", "kunci_url": "https://aistudio.google.com/app/apikey",
               "butuh_kunci": True, "gambar": True, "video": True},
    "openrouter": {"nama": "OpenRouter", "alamat": "https://openrouter.ai/api/v1",
                   "kunci_url": "https://openrouter.ai/keys", "butuh_kunci": True,
                   "gambar": True, "video": True},
    "anthropic": {"nama": "Anthropic Claude", "kunci_url": "https://console.anthropic.com/settings/keys",
                  "butuh_kunci": True, "gambar": True, "model": "claude-opus-5-5"},
    "openai": {"nama": "OpenAI", "alamat": "https://api.openai.com/v1",
               "kunci_url": "https://platform.openai.com/api-keys", "butuh_kunci": True,
               "gambar": True, "json": "skema"},
    "groq": {"nama": "Groq", "alamat": "https://api.groq.com/openai/v1",
             "kunci_url": "https://console.groq.com/keys", "butuh_kunci": True,
             "model": "llama-3.3-70b-versatile", "json": "objek"},
    "mistral": {"nama": "Mistral", "alamat": "https://api.mistral.ai/v1",
                "kunci_url": "https://console.mistral.ai/api-keys", "butuh_kunci": True,
                "model": "mistral-small-latest", "json": "objek"},
    "deepseek": {"nama": "DeepSeek", "alamat": "https://api.deepseek.com/v1",
                 "kunci_url": "https://platform.deepseek.com/api_keys", "butuh_kunci": True,
                 "model": "deepseek-chat", "json": "objek"},
    "cerebras": {"nama": "Cerebras", "alamat": "https://api.cerebras.ai/v1",
                 "kunci_url": "https://cloud.cerebras.ai", "butuh_kunci": True, "json": "objek"},
    "kustom": {"nama": "Server bergaya OpenAI (Ollama, LM Studio, ...)", "butuh_kunci": False,
               "alamat": "http://127.0.0.1:11434/v1", "json": "objek"},
    "lokal": {"nama": "AI lokal OmniClip", "butuh_kunci": False, "json": "skema"},
}

# Koneksi yang uji terakhirnya menyatakan ditolak / kunci tidak sah dilewati
# selama ini, supaya tiap analisis tidak membuang waktu mencobanya.
LEWATI_DETIK = 6 * 3600
PER_PANGGILAN_DETIK = 240


class Gagal(RuntimeError):
    """Satu koneksi gagal. `.status`: kuota|ditolak|tidak_sah|saldo|tidak_ada|sibuk|galat."""

    def __init__(self, pesan: str, status: str = "galat"):
        super().__init__(pesan)
        self.status = status


# --- Penyimpanan ----------------------------------------------------------------

def _settings():
    from ..repos import settings as settings_repo
    return settings_repo


def _baca() -> Optional[list[dict]]:
    try:
        isi = json.loads(_settings().get(SIMPAN) or "null")
    except (TypeError, ValueError):
        return None
    return isi if isinstance(isi, list) else None


def _tulis(daftar: list[dict]) -> None:
    _settings().set_value(SIMPAN, json.dumps(daftar, ensure_ascii=False))


def _id_baru() -> str:
    return secrets.token_hex(6)


def _env_kunci() -> dict[str, tuple[str, str]]:
    """{id: (penyedia, kunci)} untuk kunci dari variabel lingkungan."""
    from ..config import _pecah_kunci
    from .kunci_ai import sidik
    keluar = {}
    for k in _pecah_kunci(os.environ.get("GEMINI_API_KEY", "")):
        keluar[sidik(k)] = ("gemini", k)
    k = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if k:
        keluar[sidik(k)] = ("openrouter", k)
    return keluar


def _migrasi() -> list[dict]:
    """Daftar pertama, dari kunci Gemini dan OpenRouter yang sudah tersimpan."""
    from ..config import _pecah_kunci
    from .kunci_ai import _nama_semua, sidik
    s = _settings()
    nama = _nama_semua()
    daftar: list[dict] = []
    for k in _pecah_kunci(s.get("ai.api_key")):
        daftar.append({"id": sidik(k), "nama": nama.get(sidik(k)) or f"Gemini …{k[-4:]}",
                       "penyedia": "gemini", "kunci": k, "model": "", "alamat": "",
                       "aktif": True, "sumber": "db"})
    k = (s.get("ai.openrouter_key") or "").strip()
    if k:
        daftar.append({"id": sidik(k), "nama": f"OpenRouter …{k[-4:]}", "penyedia": "openrouter",
                       "kunci": k, "model": (s.get("ai.openrouter_model") or "").strip(),
                       "alamat": "", "aktif": True, "sumber": "db"})
    return daftar


def semua() -> list[dict]:
    """Seluruh koneksi, urut, termasuk yang dari lingkungan. Berisi kunci asli."""
    daftar = _baca()
    if daftar is None:
        daftar = _migrasi()
        _tulis(daftar)
    env = _env_kunci()
    ada = {k["id"] for k in daftar}
    keluar = []
    for k in daftar:
        if k.get("sumber") == "env":
            if k["id"] not in env:
                continue              # variabelnya sudah dihapus
            k = {**k, "kunci": env[k["id"]][1]}
        keluar.append(k)
    for sid, (penyedia, kunci) in env.items():
        if sid not in ada:
            keluar.append({"id": sid, "nama": f"{PENYEDIA[penyedia]['nama']} (.env) …{kunci[-4:]}",
                           "penyedia": penyedia, "kunci": kunci, "model": "", "alamat": "",
                           "aktif": True, "sumber": "env"})
    return keluar


def _simpan_semua(daftar: list[dict]) -> None:
    """Menyimpan urutan dan isian; kunci dari .env tidak ikut ditulis."""
    _tulis([{**k, "kunci": ""} if k.get("sumber") == "env" else k for k in daftar])
    # Cermin untuk pembaca lama (config.get_api_keys, openrouter.kunci).
    s = _settings()
    gem = [k["kunci"] for k in daftar if k["penyedia"] == "gemini" and k.get("sumber") != "env"]
    if gem:
        s.set_value("ai.api_key", "\n".join(gem))
    else:
        s.delete("ai.api_key")


def _hasil_uji(kid: str) -> Optional[dict]:
    from ..repos import cache as cache_repo
    d = cache_repo.ambil(f"kunci.uji:{kid}", ttl=30 * 86400)
    return d if isinstance(d, dict) else None


def _simpan_uji(kid: str, hasil: dict) -> None:
    from ..repos import cache as cache_repo
    cache_repo.simpan(f"kunci.uji:{kid}", hasil)


def daftar_publik() -> list[dict]:
    """Untuk antarmuka: tanpa kunci, hanya empat huruf terakhirnya."""
    keluar = []
    utama_ada = False
    for k in semua():
        p = PENYEDIA.get(k["penyedia"], {})
        utama = bool(k.get("aktif")) and not utama_ada
        utama_ada = utama_ada or utama
        keluar.append({
            "id": k["id"], "nama": k["nama"], "penyedia": k["penyedia"],
            "penyedia_nama": p.get("nama", k["penyedia"]),
            "akhiran": (k.get("kunci") or "")[-4:], "model": k.get("model") or "",
            "model_bawaan": p.get("model", ""), "alamat": k.get("alamat") or "",
            "aktif": bool(k.get("aktif")), "sumber": k.get("sumber", "db"),
            "utama": utama, "uji": _hasil_uji(k["id"]),
        })
    return keluar


def penyedia_publik() -> list[dict]:
    return [{"id": i, **{k: v for k, v in p.items()}} for i, p in PENYEDIA.items()]


# --- Ubah -----------------------------------------------------------------------

def tambah(penyedia: str, kunci: str = "", nama: str = "", model: str = "",
           alamat: str = "") -> dict:
    if penyedia not in PENYEDIA:
        raise ValueError("Penyedia AI tidak dikenal.")
    p = PENYEDIA[penyedia]
    kunci = (kunci or "").strip()
    if p.get("butuh_kunci") and not kunci:
        raise ValueError("API key kosong.")
    daftar = semua()
    if kunci and any(k.get("kunci") == kunci for k in daftar):
        raise ValueError("Kunci ini sudah ada di daftar.")
    if penyedia == "lokal":
        # AI lokal dengan model yang sama cukup satu; dipakai ulang.
        sama = next((k for k in daftar if k["penyedia"] == "lokal"
                     and (k.get("model") or "") == (model or "").strip()), None)
        if sama is not None:
            return {"id": sama["id"], "uji": uji_koneksi(sama)}
    if penyedia == "gemini":
        from .kunci_ai import sidik
        kid = sidik(kunci)
    else:
        kid = _id_baru()
    nama = (nama or "").strip()[:60] or (
        f"{p['nama']} …{kunci[-4:]}" if kunci else p["nama"])
    k = {"id": kid, "nama": nama, "penyedia": penyedia, "kunci": kunci,
         "model": (model or "").strip()[:120], "alamat": (alamat or "").strip()[:300],
         "aktif": True, "sumber": "db"}
    hasil = uji_koneksi(k)
    if hasil["status"] in ("tidak_sah", "ditolak"):
        raise ValueError(_pesan_tolak(hasil, p["nama"]))
    daftar.append(k)
    _simpan_semua(daftar)
    return {"id": kid, "uji": hasil}


def _pesan_tolak(hasil: dict, nama: str) -> str:
    if hasil["status"] == "tidak_sah":
        return (f"{nama} tidak mengenali kunci ini. Periksa apakah seluruhnya tersalin, "
                "tanpa spasi di ujung.")
    if hasil.get("pesan") == "denied access":
        return ("Google menolak kunci ini: proyeknya tidak diizinkan memakai Gemini API "
                "(\"Your project has been denied access\"). Kunci baru dari akun Google yang "
                "sama biasanya ikut ditolak; buat kunci dari akun Google lain.")
    return f"{nama} menolak kunci ini." + (f" {hasil['pesan']}" if hasil.get("pesan") else "")


def ubah(kid: str, **isian) -> None:
    daftar = semua()
    for k in daftar:
        if k["id"] == kid:
            for f in ("nama", "model", "alamat"):
                if f in isian and isian[f] is not None:
                    k[f] = str(isian[f]).strip()[:300]
            if isian.get("aktif") is not None:
                k["aktif"] = bool(isian["aktif"])
            _simpan_semua(daftar)
            return
    raise KeyError(kid)


def urutkan(ids: list[str]) -> None:
    daftar = semua()
    per = {k["id"]: k for k in daftar}
    baru = [per[i] for i in ids if i in per]
    baru += [k for k in daftar if k["id"] not in ids]
    _simpan_semua(baru)


def jadikan_utama(kid: str) -> None:
    daftar = semua()
    k = next((x for x in daftar if x["id"] == kid), None)
    if k is None:
        raise KeyError(kid)
    k["aktif"] = True
    _simpan_semua([k] + [x for x in daftar if x["id"] != kid])


def hapus(kid: str) -> None:
    daftar = semua()
    k = next((x for x in daftar if x["id"] == kid), None)
    if k is None:
        raise KeyError(kid)
    if k.get("sumber") == "env":
        raise PermissionError("env")
    _simpan_semua([x for x in daftar if x["id"] != kid])


# --- Rantai ---------------------------------------------------------------------

def _boleh(k: dict) -> bool:
    u = _hasil_uji(k["id"])
    if not u or u.get("status") not in ("ditolak", "tidak_sah"):
        return True
    return time.time() - float(u.get("waktu") or 0) > LEWATI_DETIK


def rantai(*, butuh_gambar: bool = False) -> list[dict]:
    """Koneksi aktif, urut, yang tidak baru saja ditolak. Berisi kunci asli."""
    aktif = [k for k in semua() if k.get("aktif")]
    if butuh_gambar:
        aktif = [k for k in aktif if PENYEDIA.get(k["penyedia"], {}).get("gambar")]
    boleh = [k for k in aktif if _boleh(k)]
    return boleh or aktif


def ada_aktif() -> bool:
    return bool(rantai())


def kunci_gemini() -> list[str]:
    return [k["kunci"] for k in rantai() if k["penyedia"] == "gemini" and k.get("kunci")]


def openrouter_aktif() -> Optional[dict]:
    return next((k for k in rantai() if k["penyedia"] == "openrouter" and k.get("kunci")), None)


# --- Panggilan bergaya OpenAI ---------------------------------------------------

def _alamat(k: dict) -> str:
    if k["penyedia"] == "lokal":
        from . import ai_lokal
        return ai_lokal.alamat(k.get("model") or ai_lokal.MODEL_BAWAAN)
    return (k.get("alamat") or PENYEDIA[k["penyedia"]].get("alamat") or "").rstrip("/")


def _model(k: dict) -> str:
    if k["penyedia"] == "lokal":
        return k.get("model") or "lokal"
    return k.get("model") or PENYEDIA[k["penyedia"]].get("model", "")


def _http(url: str, kunci: str, badan: Optional[dict], waktu: float) -> dict:
    kepala = {"Content-Type": "application/json", "User-Agent": "OmniClip"}
    if kunci:
        kepala["Authorization"] = f"Bearer {kunci}"
    data = json.dumps(badan).encode("utf-8") if badan is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET", headers=kepala)
    try:
        with urllib.request.urlopen(req, timeout=waktu) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        isi = ""
        try:
            isi = e.read().decode("utf-8", "replace")[:300]
        except Exception:                                 # noqa: BLE001
            pass
        status = {401: "tidak_sah", 403: "ditolak", 402: "saldo", 404: "tidak_ada",
                  429: "kuota"}.get(e.code, "sibuk" if e.code >= 500 else "galat")
        raise Gagal(f"HTTP {e.code}: {isi or e.reason}", status) from e
    except urllib.error.URLError as e:
        raise Gagal(f"jaringan: {e.reason}", "sibuk") from e
    except (OSError, ValueError) as e:      # sambungan putus, jawaban bukan JSON
        raise Gagal(f"sambungan: {str(e)[:160]}", "sibuk") from e


def tanya_openai(k: dict, bahan: list[dict], *, skema: dict, sistem: str,
                 suhu: float = 0.3, maks_keluaran: int = 4096) -> tuple[dict, str, dict]:
    """Satu panggilan /chat/completions. (data_json, nama_model, pemakaian)."""
    from .openrouter import _bentuk, _json_schema, _uraikan
    p = PENYEDIA[k["penyedia"]]
    mode = p.get("json", "objek")
    isi = []
    for b in bahan:
        if "teks" in b:
            isi.append({"type": "text", "text": b["teks"]})
        elif "gambar" in b and p.get("gambar"):
            data = base64.b64encode(b["gambar"]).decode("ascii")
            isi.append({"type": "image_url",
                        "image_url": {"url": f"data:{b.get('mime', 'image/jpeg')};base64,{data}"}})
    if not isi:
        raise Gagal("tidak ada bahan yang bisa dibaca model ini", "galat")
    perintah = sistem
    if mode != "skema":
        perintah += ("\n\nJawab HANYA dengan satu objek JSON berbentuk persis seperti ini, "
                     "tanpa kalimat pembuka dan tanpa pagar kode:\n" + _bentuk(skema))
    model = _model(k)
    if not model:
        raise Gagal("model belum dipilih untuk koneksi ini", "galat")
    badan = {"model": model, "temperature": suhu, "max_tokens": maks_keluaran,
             "messages": [{"role": "system", "content": perintah},
                          {"role": "user", "content": isi if len(isi) > 1 else isi[0]["text"]
                           if isi[0]["type"] == "text" else isi}]}
    if mode == "skema":
        badan["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "jawaban", "strict": True, "schema": _json_schema(skema)}}
    elif mode == "objek":
        badan["response_format"] = {"type": "json_object"}
    url = _alamat(k) + "/chat/completions"
    lokal = k["penyedia"] == "lokal"
    if lokal:
        from . import ai_lokal
        ai_lokal.mulai_pakai()
    try:
        # Model di CPU butuh menit, bukan detik, untuk jawaban panjang.
        jawab = _http(url, k.get("kunci", ""), badan, 900 if lokal else PER_PANGGILAN_DETIK)
    finally:
        if lokal:
            ai_lokal.selesai_pakai()
    if jawab.get("error"):
        g = jawab["error"]
        raise Gagal(str(g.get("message") or g)[:300])
    pilihan = (jawab.get("choices") or [None])[0]
    if not pilihan:
        raise Gagal("jawaban tanpa pilihan")
    teks = (pilihan.get("message") or {}).get("content")
    if isinstance(teks, list):
        teks = "".join(x.get("text") or "" for x in teks if isinstance(x, dict))
    try:
        data = _uraikan(teks or "")
    except ValueError as e:
        raise Gagal(str(e)) from e
    u = jawab.get("usage") or {}
    return data, f"{k['penyedia']}:{model}", {"masuk": u.get("prompt_tokens"),
                                               "keluar": u.get("completion_tokens")}


def tanya_satu(k: dict, bahan: list[dict], *, skema: dict, sistem: str,
               suhu: float = 0.3, maks_keluaran: int = 4096) -> tuple[dict, str, dict]:
    """Satu koneksi selain Gemini/OpenRouter (yang punya jalurnya sendiri)."""
    if k["penyedia"] == "anthropic":
        from . import penyedia_anthropic
        return penyedia_anthropic.tanya(k["kunci"], _model(k), bahan, skema=skema,
                                        sistem=sistem, maks_keluaran=maks_keluaran)
    return tanya_openai(k, bahan, skema=skema, sistem=sistem, suhu=suhu,
                        maks_keluaran=maks_keluaran)


# --- Uji ------------------------------------------------------------------------

_SKEMA_UJI = {"type": "OBJECT", "properties": {"siap": {"type": "BOOLEAN"}},
              "required": ["siap"]}


def daftar_model(k: dict) -> list[str]:
    """Model yang dilaporkan penyedia (bila ia punya /models)."""
    if k["penyedia"] == "gemini":
        from .peringkat_model import daftar_kunci, urutkan
        return urutkan(daftar_kunci(k["kunci"]))
    if k["penyedia"] == "anthropic":
        from . import penyedia_anthropic
        return penyedia_anthropic.daftar_model(k["kunci"])
    if k["penyedia"] == "lokal":
        from . import ai_lokal
        return [m["id"] for m in ai_lokal.status()["model"] if m["terpasang"]]
    data = _http(_alamat(k) + "/models", k.get("kunci", ""), None, 20)
    return sorted(m.get("id") for m in (data.get("data") or []) if m.get("id"))


def uji_koneksi(k: dict) -> dict:
    """Menguji satu koneksi dengan permintaan sungguhan. Hasilnya disimpan."""
    if k["penyedia"] == "gemini":
        from .kunci_ai import uji_kunci
        hasil = uji_kunci(k["kunci"])
        _simpan_uji(k["id"], hasil)
        return hasil
    mulai = time.time()
    hasil: dict = {"waktu": time.time(), "model": [], "model_tersedia": 0}
    try:
        try:
            nama = daftar_model(k)
            hasil["model_tersedia"] = len(nama)
            hasil["daftar_model"] = nama[:200]
        except Gagal as e:
            if e.status in ("tidak_sah", "ditolak"):
                raise
            nama = []
        if k["penyedia"] == "lokal" and not nama:
            raise Gagal("AI lokal belum dipasang.", "tidak_ada")
        if not _model(k) and k["penyedia"] not in ("lokal",):
            hasil.update(status="pilih_model")
            _simpan_uji(k["id"], hasil)
            return hasil
        if k["penyedia"] == "openrouter":
            from . import openrouter
            m = openrouter.rantai_teks(k.get("model") or None, maks=1)
            if not m:
                raise Gagal("tidak ada model OpenRouter gratis yang cocok", "tidak_ada")
            data, model, _ = openrouter.tanya(
                [{"teks": "Balas dengan siap=true."}], skema=_SKEMA_UJI,
                sistem="Jawab dalam JSON.", api_key=k["kunci"], models=m, maks_keluaran=64)
        else:
            data, model, _ = tanya_satu(k, [{"teks": "Balas dengan siap=true."}],
                                        skema=_SKEMA_UJI, sistem="Jawab dalam JSON.",
                                        maks_keluaran=64)
        hasil.update(status="bekerja",
                     model=[{"model": model.split(":", 1)[-1], "status": "ok",
                             "detik": round(time.time() - mulai, 1)}])
    except Gagal as e:
        hasil.update(status=e.status if e.status != "galat" else "galat", pesan=str(e)[:200],
                     model=[{"model": _model(k) or "-", "status": e.status, "pesan": str(e)[:160]}])
    except Exception as e:                                # noqa: BLE001
        status = getattr(e, "status", None)
        hasil.update(status=status if status in ("kuota", "ditolak", "tidak_sah", "saldo",
                                                 "tidak_ada", "sibuk") else "galat",
                     pesan=str(e)[:200],
                     model=[{"model": _model(k) or "-", "status": "galat", "pesan": str(e)[:160]}])
    _simpan_uji(k["id"], hasil)
    log.info("Uji koneksi %s (%s): %s", k["nama"], k["penyedia"], hasil["status"])
    return hasil


def uji(kid: str) -> dict:
    for k in semua():
        if k["id"] == kid:
            return uji_koneksi(k)
    raise KeyError(kid)
