"""
OpenRouter: cadangan saat Gemini kehabisan kuota harian.

Kuota gratis Gemini habis pada sore hari kalau dipakai serius, dan sesudah itu
seluruh jalur sutradara mati — bukan melambat, mati. OpenRouter menyalurkan
model dari banyak penyedia lewat satu API bergaya OpenAI, dan beberapa di
antaranya menerima video, gambar, dan suara tanpa biaya.

Yang perlu diketahui tentang model gratis di sana, dan yang membentuk berkas
ini:

- Jumlahnya sedikit dan berubah-ubah. Daftarnya karena itu diambil dari
  `/api/v1/models` (terbuka, tanpa kunci) dan disaring pada harga nol serta
  modalitas yang dibutuhkan — bukan ditulis tangan di sini, karena daftar
  tangan akan basi dalam hitungan minggu.
- Tidak semuanya menerima `response_format`. Yang tidak menerimanya tetap bisa
  dipakai: skema yang sama dikirim sebagai teks perintah, lalu jawabannya
  dipetik dari tulisannya. Model yang menerimanya dipakai lebih dulu.
- Sebagian menerima suara, sebagian hanya gambar. Tawa dan sorak paling jelas
  terdengar, bukan terlihat, jadi model yang menerima suara diperingkat di
  atas.
- Jatah hariannya kecil (puluhan permintaan). Ia cadangan, bukan mesin utama.

Berbayar TIDAK pernah dipilih sendiri. Model berbayar hanya dipakai bila
pemiliknya menyebut namanya sendiri di Pengaturan — tagihan yang muncul tanpa
diminta adalah hal terakhir yang boleh dilakukan program di komputer orang.
"""

import base64
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

log = logging.getLogger("omniclip.openrouter")

ALAMAT = "https://openrouter.ai/api/v1"
NAMA_KUNCI = "ai.openrouter_key"
NAMA_MODEL = "ai.openrouter_model"

PER_PANGGILAN_DETIK = 180
_DAFTAR_LAMA = 6 * 3600        # daftar model disegarkan tiap enam jam

# Video dikirim sebagai data URL di dalam badan JSON, dan base64 menambah
# sepertiga. Di atas batas ini yang dikirim gambar kunci + suara: permintaan
# 60 MB ditolak gerbangnya sebelum model mana pun melihatnya.
BATAS_VIDEO_MB = 12

_kunci_daftar = threading.Lock()
_daftar: tuple[float, list[dict]] = (0.0, [])


# --- Kunci dan pilihan pengguna ------------------------------------------------
def kunci() -> str:
    """Kunci OpenRouter yang berlaku: basis data dulu, lalu lingkungan."""
    try:
        from ..repos import settings as settings_repo
        nilai = (settings_repo.get(NAMA_KUNCI) or "").strip()
        if nilai:
            return nilai
    except Exception:          # basis data belum siap
        pass
    return os.environ.get("OPENROUTER_API_KEY", "").strip()


def model_pilihan() -> str:
    try:
        from ..repos import settings as settings_repo
        return (settings_repo.get(NAMA_MODEL) or "").strip()
    except Exception:
        return ""


def aktif() -> bool:
    return bool(kunci())


# --- Daftar model --------------------------------------------------------------
def _ambil_daftar() -> list[dict]:
    permintaan = urllib.request.Request(
        f"{ALAMAT}/models", headers={"Accept": "application/json"})
    with urllib.request.urlopen(permintaan, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    keluar = []
    for m in data.get("data") or []:
        arsitektur = m.get("architecture") or {}
        masuk = set(arsitektur.get("input_modalities") or [])
        harga = m.get("pricing") or {}
        def angka(x) -> float:
            try:
                return float(harga.get(x) or 0)
            except (TypeError, ValueError):
                return 0.0
        keluar.append({
            "id": m.get("id") or "",
            "nama": m.get("name") or m.get("id") or "",
            "video": "video" in masuk,
            "suara": "audio" in masuk,
            "gambar": "image" in masuk,
            "json": "response_format" in (m.get("supported_parameters") or [])
                    or "structured_outputs" in (m.get("supported_parameters") or []),
            "gratis": angka("prompt") == 0 and angka("completion") == 0,
            "konteks": int(m.get("context_length") or 0),
        })
    return [m for m in keluar if m["id"]]


def daftar(segarkan: bool = False) -> list[dict]:
    """Semua model OpenRouter beserta modalitasnya (dicache enam jam)."""
    global _daftar
    with _kunci_daftar:
        waktu, isi = _daftar
        if isi and not segarkan and time.time() - waktu < _DAFTAR_LAMA:
            return list(isi)
    isi = _ambil_daftar()
    with _kunci_daftar:
        _daftar = (time.time(), isi)
    return list(isi)


def _peringkat(m: dict) -> tuple:
    """Makin kecil makin didahulukan."""
    return (0 if m["video"] else 1,        # menonton lebih baik daripada menebak
            0 if m["suara"] else 1,        # tawa terdengar sebelum terlihat
            0 if m["json"] else 1,         # jawaban terstruktur lebih jarang gagal
            -m["konteks"], m["id"])


def urutkan(semua: list[dict]) -> list[dict]:
    """Model gratis yang bisa menonton, dari yang paling cocok."""
    return sorted((m for m in semua if m["gratis"] and (m["video"] or m["gambar"])),
                  key=_peringkat)


def rantai(pilihan: Optional[str] = None, *, maks: int = 4) -> list[dict]:
    """
    Urutan model yang dicoba: pilihan pengguna di depan, lalu model gratis yang
    bisa menonton. Daftar yang tidak bisa diambil (jaringan mati) bukan alasan
    untuk gagal diam-diam — ia mengembalikan daftar kosong, dan pemanggil yang
    menjelaskan.
    """
    try:
        semua = daftar()
    except Exception as e:
        log.warning("Daftar model OpenRouter tidak terbaca: %s", str(e)[:160])
        semua = []
    urut = urutkan(semua)[:maks]
    if pilihan:
        dipilih = next((m for m in semua if m["id"] == pilihan), None)
        if dipilih is None:
            # Model yang diketik pemiliknya tapi tidak ada di daftar tetap
            # dicoba: daftarnya bisa saja baru, dan jawaban "tidak ada" dari
            # OpenRouter lebih jelas daripada penolakan diam-diam di sini.
            dipilih = {"id": pilihan, "nama": pilihan, "video": True, "suara": True,
                       "gambar": True, "json": True, "gratis": False, "konteks": 0}
        urut = [dipilih] + [m for m in urut if m["id"] != dipilih["id"]]
    return urut


# --- Skema dan jawaban ---------------------------------------------------------
def _json_schema(skema: dict) -> dict:
    """Skema netral (`sutradara_ai._schema`) → JSON Schema biasa."""
    keluar: dict = {}
    for k, v in skema.items():
        if k == "property_ordering":
            continue
        if k == "type":
            keluar["type"] = str(v).lower()
        elif k == "properties":
            keluar["properties"] = {n: _json_schema(s) for n, s in v.items()}
        elif k == "items":
            keluar["items"] = _json_schema(v)
        else:
            keluar[k] = v
    if keluar.get("type") == "object":
        # Wajib untuk mode ketat OpenAI, dan tidak merugikan yang lain: tanpa
        # ini model boleh menambah kolom karangan yang lalu kita abaikan.
        keluar["additionalProperties"] = False
        keluar.setdefault("required", list((keluar.get("properties") or {}).keys()))
    return keluar


def _bentuk(skema: dict, dalam: int = 0) -> str:
    """Skema sebagai contoh bentuk yang bisa dibaca model, untuk yang tidak
    menerima `response_format`. Nilainya berupa keterangan, bukan contoh
    jawaban — contoh jawaban gampang ditiru mentah-mentah."""
    sela = "  " * (dalam + 1)
    jenis = str(skema.get("type", "")).upper()
    if jenis == "OBJECT":
        urut = skema.get("property_ordering") or list((skema.get("properties") or {}).keys())
        baris = [f'{sela}"{n}": {_bentuk(skema["properties"][n], dalam + 1)}'
                 for n in urut if n in (skema.get("properties") or {})]
        return "{\n" + ",\n".join(baris) + "\n" + "  " * dalam + "}"
    if jenis == "ARRAY":
        return "[" + _bentuk(skema.get("items") or {}, dalam) + ", …]"
    if skema.get("enum"):
        return " | ".join(f'"{v}"' for v in skema["enum"])
    return {"STRING": "<teks>", "INTEGER": "<bilangan bulat>",
            "NUMBER": "<angka>", "BOOLEAN": "true|false"}.get(jenis, "<nilai>")


def _uraikan(teks: str) -> dict:
    """
    JSON dari jawaban model yang tidak terikat skema.

    Model tanpa `response_format` membungkus jawabannya: pagar ```json, kalimat
    pembuka, atau penalaran di depan. Yang dicari karena itu bukan "seluruh
    teks ini JSON", melainkan objek JSON terbesar di dalamnya.
    """
    teks = (teks or "").strip()
    if not teks:
        raise ValueError("jawaban kosong")
    try:
        return json.loads(teks)
    except json.JSONDecodeError:
        pass
    pagar = re.search(r"```(?:json)?\s*(.+?)```", teks, re.S)
    if pagar:
        try:
            return json.loads(pagar.group(1).strip())
        except json.JSONDecodeError:
            pass
    awal = teks.find("{")
    while awal != -1:
        dalam, i = 0, awal
        while i < len(teks):
            if teks[i] == "{":
                dalam += 1
            elif teks[i] == "}":
                dalam -= 1
                if dalam == 0:
                    try:
                        return json.loads(teks[awal:i + 1])
                    except json.JSONDecodeError:
                        break
            i += 1
        awal = teks.find("{", awal + 1)
    raise ValueError(f"tidak ada JSON dalam jawaban ({len(teks)} karakter)")


# --- Bahan ---------------------------------------------------------------------
def _bagian(bahan: list[dict], model: dict) -> list[dict]:
    """Bahan netral → bagian pesan OpenRouter, disesuaikan kemampuan model."""
    isi = []
    for b in bahan:
        if "video" in b and model["video"]:
            data = base64.b64encode(b["video"]).decode("ascii")
            isi.append({"type": "video_url",
                        "video_url": {"url": f"data:{b.get('mime', 'video/mp4')};base64,{data}"}})
        elif "gambar" in b and model["gambar"]:
            data = base64.b64encode(b["gambar"]).decode("ascii")
            isi.append({"type": "image_url",
                        "image_url": {"url": f"data:{b.get('mime', 'image/jpeg')};base64,{data}"}})
        elif "suara" in b and model["suara"]:
            isi.append({"type": "input_audio",
                        "input_audio": {"data": base64.b64encode(b["suara"]).decode("ascii"),
                                        "format": b.get("format", "mp3")}})
        elif "teks" in b:
            isi.append({"type": "text", "text": b["teks"]})
    return isi


def _muat(bahan: list[dict]) -> float:
    """Megabita bahan biner di dalam daftar."""
    n = sum(len(b[k]) for b in bahan for k in ("video", "gambar", "suara") if k in b)
    return n / 1_000_000


def _bisa(bahan: list[dict], model: dict) -> bool:
    """Apakah model ini sanggup melihat bahan utamanya sama sekali?"""
    if any("video" in b for b in bahan) and model["video"]:
        return True
    if any("gambar" in b for b in bahan) and model["gambar"]:
        return True
    return not any(k in b for b in bahan for k in ("video", "gambar", "suara"))


# --- Panggilan -----------------------------------------------------------------
class Ditolak(RuntimeError):
    """Satu panggilan gagal. `.kode` berisi status HTTP bila ada."""

    def __init__(self, pesan: str, kode: Optional[int] = None):
        super().__init__(pesan)
        self.kode = kode


def _panggil(model: dict, isi: list[dict], *, sistem: str, api_key: str,
             skema: dict, suhu: float, maks_keluaran: int) -> tuple[dict, dict]:
    perintah = sistem
    if not model["json"]:
        # Model yang tidak bisa diikat skema tetap harus menjawab dalam bentuk
        # yang sama, jadi bentuknya diminta di perintah.
        perintah += ("\n\nJawab HANYA dengan satu objek JSON berbentuk persis "
                     "seperti ini, tanpa kalimat pembuka dan tanpa pagar kode:\n"
                     + _bentuk(skema))
    badan = {
        "model": model["id"],
        "messages": [{"role": "system", "content": perintah},
                     {"role": "user", "content": isi}],
        "temperature": suhu,
        "max_tokens": maks_keluaran,
    }
    if model["json"]:
        badan["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "sutradara", "strict": True,
                            "schema": _json_schema(skema)}}
    data = json.dumps(badan).encode("utf-8")
    permintaan = urllib.request.Request(
        f"{ALAMAT}/chat/completions", data=data, method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Dipakai OpenRouter untuk papan peringkat aplikasi. Hanya nama
            # program dan alamat proyeknya — tidak ada apa pun milik pengguna.
            "HTTP-Referer": "https://github.com/YosafatHizkiaPesik/OmniClip",
            "X-Title": "OmniClip",
        })
    try:
        with urllib.request.urlopen(permintaan, timeout=PER_PANGGILAN_DETIK) as r:
            jawab = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        badan_galat = ""
        try:
            badan_galat = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise Ditolak(f"HTTP {e.code}: {badan_galat or e.reason}", e.code) from e
    except urllib.error.URLError as e:
        raise Ditolak(f"jaringan: {e.reason}") from e

    # Galat tingkat aplikasi datang dengan status 200 di sini.
    if jawab.get("error"):
        g = jawab["error"]
        raise Ditolak(str(g.get("message") or g)[:300], g.get("code"))
    pilihan = (jawab.get("choices") or [None])[0]
    if not pilihan:
        raise Ditolak("jawaban tanpa pilihan")
    pesan = pilihan.get("message") or {}
    teks = pesan.get("content")
    if isinstance(teks, list):        # sebagian penyedia memecah isinya
        teks = "".join(p.get("text") or "" for p in teks if isinstance(p, dict))
    data_json = _uraikan(teks or "")
    u = jawab.get("usage") or {}
    pakai = {"masuk": u.get("prompt_tokens"), "keluar": u.get("completion_tokens"),
             "berpikir": (u.get("completion_tokens_details") or {}).get("reasoning_tokens")}
    return data_json, pakai


_SIBUK_KODE = (408, 429, 500, 502, 503, 504)


def tanya(bahan: list[dict], *, skema: dict, sistem: str, api_key: str,
          models: list[dict], suhu: float = 0.3, maks_keluaran: int = 8192,
          kabar: Optional[Callable[[str], None]] = None,
          batal: Optional[Callable[[], None]] = None,
          batas_detik: float = 300.0,
          cadangan: Optional[Callable[[], list[dict]]] = None) -> tuple[dict, str, dict]:
    """
    (data_json, "openrouter:<model>", pemakaian). Melempar `Ditolak` bila tidak
    satu model pun menjawab.

    `cadangan()` menghasilkan bahan pengganti — gambar kunci dan suara — untuk
    model yang tidak menerima video, atau saat videonya terlalu besar untuk
    dikirim utuh. Ia dipanggil paling banyak sekali.
    """
    if not models:
        raise Ditolak("tidak ada model OpenRouter yang bisa dipakai")
    tenggat = time.monotonic() + batas_detik
    gagal: list[str] = []
    _cadangan: Optional[list[dict]] = None
    berat = _muat(bahan) > BATAS_VIDEO_MB

    def bahan_untuk(m: dict) -> Optional[list[dict]]:
        nonlocal _cadangan
        pakai_video = m["video"] and not berat
        if not pakai_video and cadangan is not None:
            if _cadangan is None:
                if kabar is not None:
                    kabar("Menyiapkan gambar kunci untuk model cadangan…")
                _cadangan = cadangan()
            calon = _cadangan
        else:
            calon = bahan
        return calon if _bisa(calon, m) else None

    for urutan, m in enumerate(models):
        if batal is not None:
            batal()
        if tenggat - time.monotonic() <= 5:
            gagal.append(f"batas waktu {batas_detik:.0f} dtk habis")
            break
        isi_bahan = bahan_untuk(m)
        if isi_bahan is None:
            gagal.append(f"{m['id']}: tidak bisa melihat bahannya")
            continue
        if kabar is not None:
            kabar(f"Menonton klip lewat OpenRouter ({m['id']})…")
        try:
            data, pakai = _panggil(m, _bagian(isi_bahan, m), sistem=sistem,
                                   api_key=api_key, skema=skema, suhu=suhu,
                                   maks_keluaran=maks_keluaran)
            log.info("OpenRouter %s menjawab: %s token masuk, %s keluar",
                     m["id"], pakai["masuk"], pakai["keluar"])
            return data, f"openrouter:{m['id']}", pakai
        except Exception as e:
            kode = getattr(e, "kode", None)
            gagal.append(f"{m['id']}: {str(e)[:140]}")
            log.warning("OpenRouter %s gagal: %s", m["id"], str(e)[:200])
            if kode == 402:
                # Saldo habis berlaku untuk seluruh kunci, bukan satu model.
                gagal.append("saldo/jatah OpenRouter habis")
                break
            if kode in (401, 403):
                gagal.append("kunci OpenRouter ditolak")
                break
            if kode in _SIBUK_KODE and kabar is not None and urutan + 1 < len(models):
                kabar(f"{m['id']} sedang sibuk — mencoba model berikutnya…")
    raise Ditolak("OpenRouter gagal — " + " | ".join(gagal))
