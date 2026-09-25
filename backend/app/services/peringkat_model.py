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
#   - customtools  : varian untuk pemakaian alat, bukan untuk tugas ini
#   - gemma        : jendela konteksnya tidak muat transkrip panjang
#   - deep-research, antigravity : agen, bukan model yang menjawab satu prompt
_POLA = re.compile(r"^gemini-(\d+(?:\.\d+)?)-(pro|flash)(?:-preview(?:-[\w-]+)?)?$")

# Model "lite": dipakai TERAKHIR, sesudah semua model penuh kehabisan jatah.
#
# Dulu ditolak seluruhnya, dengan alasan yang masih benar: ia dibuat untuk tugas
# ringan, dan menilai mana momen yang lucu butuh penalaran. Tapi alasan itu
# membandingkannya dengan model penuh, padahal pada saat ia dibutuhkan
# pembandingnya adalah MESIN LOKAL yang tidak menilai apa pun.
#
# Yang membuatnya berharga: jatah harian dihitung PER MODEL. Terukur 24
# September 2026, saat enam model penuh sudah habis semua, jatah lite masih
# utuh: dua puluh permintaan per model per project per hari, dan lite punya
# dua puluhnya sendiri.
_POLA_LITE = re.compile(r"^gemini-(\d+(?:\.\d+)?)-flash-lite(?:-preview(?:-[\w-]+)?)?$")
_ALIAS = {"gemini-pro-latest": ("pro", 0.0), "gemini-flash-latest": ("flash", 0.0)}

_KUNCI_DAFTAR = 6 * 3600          # daftar model disegarkan tiap enam jam
_LAMA_TANPA_KUOTA = 24 * 3600     # "limit: 0" diingat sehari

_kunci = threading.Lock()
_daftar: dict[str, tuple[float, list[str]]] = {}   # sidik kunci -> (waktu, model)
_tanpa_kuota: dict[str, float] = {}                 # model -> waktu tercatat
# model -> kapan jatah hariannya berputar (detik epoch)
_habis_harian: dict[str, float] = {}


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


def lite(nama: str) -> bool:
    nama = nama.replace("models/", "")
    return bool(_POLA_LITE.match(nama)) and not any(
        x in nama for x in ("customtools", "tts", "image"))


def _peringkat_lite(nama: str) -> tuple:
    m = _POLA_LITE.match(nama.replace("models/", ""))
    return (-float(m.group(1)) if m else 0.0, nama)


def urutkan(nama_model: list[str]) -> list[str]:
    """
    Model penuh dulu, model lite di paling belakang.

    Urutannya bukan selera: lite hanya masuk akal sesudah semua yang lebih baik
    kehabisan jatah, dan pada saat itu ia satu-satunya yang masih bisa menilai
    isi klip sama sekali.
    """
    unik = set(nama_model)
    return (sorted((n for n in unik if cocok(n)), key=peringkat)
            + sorted((n for n in unik if lite(n)), key=_peringkat_lite))


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
# Model yang TERAKHIR benar-benar menjawab, dan kapan.
#
# Ada karena urutan "terkuat dulu" saja tidak cukup pada hari yang buruk.
# Terukur 23 September 2026: empat dari enam model flash menjawab 503 serentak
# selama berjam-jam, sementara satu model yang lebih tua menjawab normal dalam
# dua detik. Rantai tetap mencoba yang terkuat lebih dulu setiap kali, gagal di
# empat model berturut-turut, kehabisan anggaran waktu, lalu jatuh ke mesin
# lokal. Tiga kali berturut-turut, dan hasilnya klip yang tidak menarik.
#
# Sekarang model yang baru saja berhasil dicoba lebih dulu, tapi hanya selama
# beberapa jam: kalau ia mulai gagal, urutan biasa mengambil alih lagi, dan
# esok harinya yang terkuat kembali dicoba pertama.
_NAMA_BERHASIL = "ai.model_terakhir_berhasil"
_LAMA_BERHASIL = 6 * 3600
_berhasil: tuple[str, float] | None = None
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
            for m, t in (data.get("nol") or data).items():
                _tanpa_kuota.setdefault(m, float(t))
            for m, t in (data.get("harian") or {}).items():
                _habis_harian.setdefault(m, float(t))
    except Exception:
        pass
    try:
        import json
        from ..repos import settings as settings_repo
        global _berhasil
        simpan = json.loads(settings_repo.get(_NAMA_BERHASIL) or "null")
        if simpan and _berhasil is None:
            _berhasil = (str(simpan[0]), float(simpan[1]))
    except Exception:
        pass


def _simpan() -> None:
    try:
        import json
        from ..repos import settings as settings_repo
        sekarang = time.time()
        with _kunci:
            data = {
                "nol": {m: t for m, t in _tanpa_kuota.items()
                        if sekarang - t < _LAMA_TANPA_KUOTA},
                "harian": {m: t for m, t in _habis_harian.items() if t > sekarang},
            }
        settings_repo.set_value(_NAMA_SIMPANAN, json.dumps(data))
    except Exception:
        pass


def catat_berhasil(model: str) -> None:
    """Dipanggil saat sebuah model benar-benar menjawab dengan hasil yang dipakai."""
    global _berhasil
    _muat()
    lama = _berhasil
    _berhasil = (model, time.time())
    if lama is None or lama[0] != model:
        try:
            import json
            from ..repos import settings as settings_repo
            settings_repo.set_value(_NAMA_BERHASIL, json.dumps(list(_berhasil)))
        except Exception:
            pass


def terakhir_berhasil() -> Optional[str]:
    """
    Model yang terakhir menjawab, bila catatannya masih baru DAN masih relevan.

    Dua batas, dan keduanya pernah salah tanpa yang lain:

    - Enam jam. Petunjuk "yang ini tadi menjawab" hanya berguna selama gelombang
      503 yang sedang berlangsung.
    - Putaran jatah harian. Catatan yang dibuat sebelum jatah berputar menunjuk
      keadaan kemarin: terukur 24 September 2026, seluruh model penuh kehabisan
      jatah sore hari sehingga yang terakhir menjawab adalah model lite, dan
      pukul lima pagi berikutnya, dengan jatah yang sudah pulih, menu model
      MASIH menyebut lite sebagai yang akan dicoba pertama.
    """
    _muat()
    if not _berhasil:
        return None
    umur = time.time() - _berhasil[1]
    if umur >= _LAMA_BERHASIL:
        return None
    # Kapan jatah terakhir berputar: sekarang dikurangi berapa lama hari kuota
    # ini sudah berjalan.
    putaran = time.time() - (86400 - detik_ke_putaran())
    if _berhasil[1] < putaran:
        return None
    return _berhasil[0]


def tanpa_kuota(model: str) -> bool:
    _muat()
    with _kunci:
        t = _tanpa_kuota.get(model)
    return t is not None and time.time() - t < _LAMA_TANPA_KUOTA


# Kunci yang jatah HARIANNYA habis, dan kapan tercatat.
#
# Kuota Gemini dihitung per project, bukan per model (kalimat dokumentasi
# Google). Jadi begitu satu model menjawab "you exceeded your current quota",
# model lain dengan kunci yang sama akan menjawab hal yang sama. Terukur 24
# September 2026: satu permintaan menghasilkan DUA BELAS panggilan 429 berturut
# turut sebelum sistem menyerah, dan tak satu pun punya peluang berhasil.
#
# Catatannya berumur pendek. Jatah harian Google berputar, dan menguncinya
# sampai besok akan salah pada jam yang salah.
_LAMA_KUNCI_HABIS = 20 * 60
_kunci_habis: dict[str, float] = {}


def catat_kunci_habis(api_key: str) -> None:
    with _kunci:
        _kunci_habis[_sidik(api_key)] = time.time()
    log.info("Jatah kunci ini habis; dilewati %d menit", _LAMA_KUNCI_HABIS // 60)


def kunci_habis(api_key: str) -> bool:
    with _kunci:
        t = _kunci_habis.get(_sidik(api_key))
    return t is not None and time.time() - t < _LAMA_KUNCI_HABIS


def kuota_habis(galat: BaseException | str) -> bool:
    """
    Apakah galat ini berarti jatah HARIAN model ini habis.

    Dibaca dari id kuotanya, bukan dari tebakan. Google menyebutnya
    `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, dan kata "PerModel" di
    situ yang menentukan: model LAIN dengan kunci yang sama masih punya jatahnya
    sendiri. Terukur 24 September 2026, saat enam model penuh sudah habis
    semua, empat model lite masih utuh.
    """
    pesan = str(galat)
    if "429" not in pesan and "RESOURCE_EXHAUSTED" not in pesan:
        return False
    # "limit: 0" artinya model itu memang tidak pernah boleh dipakai kunci ini;
    # itu urusan `catat_gagal`, bukan urusan jatah harian.
    if re.search(r"limit:\s*0\b", pesan):
        return False
    return True


# Jatah harian gratis Google berputar tengah malam waktu Pasifik.
_ZONA_PUTARAN = -8 * 3600           # PST; satu jam meleset saat musim panas


def detik_ke_putaran(sekarang: Optional[float] = None) -> float:
    """
    Berapa detik lagi jatah harian berputar.

    Dihitung, bukan dipatok dua puluh empat jam: jatah yang habis pukul delapan
    malam waktu Pasifik pulih empat jam kemudian, dan menungguinya sehari penuh
    berarti membuang satu hari jatah yang sudah tersedia.
    """
    sekarang = time.time() if sekarang is None else sekarang
    lewat = (sekarang + _ZONA_PUTARAN) % 86400
    return 86400 - lewat


def habis_harian(model: str) -> bool:
    """Apakah model ini sudah memakai jatah hariannya dan belum berputar."""
    _muat()
    with _kunci:
        t = _habis_harian.get(model)
    return t is not None and time.time() < t


def jatah_dari_galat(galat: BaseException | str) -> Optional[int]:
    """
    Batas harian yang DISEBUTKAN Google di dalam galat 429-nya.

    Google tidak pernah mengirim sisa kuota — tidak ada satu pun header kuota di
    jawabannya, diperiksa 24 September 2026. Tapi saat jatahnya habis, ia
    menyebutkan BATASNYA di `QuotaFailure.violations[].quotaValue`. Angka itu
    yang dipakai, bukan tebakan yang ditulis di kode: batas tiap model bisa
    berbeda, dan bisa berubah kapan saja tanpa memberi tahu siapa pun.
    """
    import re as _re

    m = _re.search(r"'quotaValue':\s*'?(\d+)", str(galat))
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def catat_habis_harian(model: str, galat: BaseException | str = "") -> None:
    """Model ini memakai jatah hariannya. Dilewati sampai jatahnya berputar."""
    kapan = time.time() + detik_ke_putaran()
    with _kunci:
        _habis_harian[model] = kapan
    _simpan()
    # Saat inilah satu-satunya waktu sisa jatahnya diketahui PASTI, yaitu nol.
    # Pencatat pemakaian memakainya untuk menyetel ulang hitungannya, supaya
    # angka yang ditampilkan berhenti jadi perkiraan.
    try:
        from .pemakaian_ai import tandai_habis
        tandai_habis(model, jatah_dari_galat(galat))
    except Exception:
        pass
    log.info("%s kehabisan jatah harian; dilewati %.1f jam lagi",
             model, detik_ke_putaran() / 3600)


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


# Berapa panggilan per model yang DISISAKAN untuk pemilihan klip.
#
# Jatah gratis dua puluh per model per hari harus dibagi antara dua pekerjaan
# yang tidak setara. Memilih klip menentukan seluruh isi video: salah di situ
# dan yang tersisa cuma daftar potongan yang tidak menarik, dan mesin lokal
# tidak bisa menggantikannya karena ia tidak menilai apakah sesuatu lucu.
# Menyusun bingkai punya mesin lokal yang hasilnya masih masuk akal.
#
# Terukur 24 September 2026: 171 panggilan dalam sehari, tujuh model penuh
# habis semua sebelum tengah malam, dan video berikutnya dipilih mesin lokal.
# Yang menghabiskannya bukan pemilihan klip melainkan sutradara bingkai, satu
# panggilan per klip, belasan klip per video.
CADANGAN_KLIP = 6


def sisa_model(model: str) -> int:
    """Sisa jatah harian model ini menurut catatan pemakaian sendiri."""
    try:
        from .pemakaian_ai import sisa_model as _sisa
        return _sisa(model)
    except Exception:
        return 99


def rantai(api_key: str, pilihan: Optional[str] = None, *,
           sisakan: int = 0) -> list[str]:
    """
    Urutan model yang dicoba, dari yang paling kuat.

    `pilihan` (model yang dipilih pengguna) selalu di depan, sisanya cadangan.
    Model tanpa kuota dibuang, kecuali bila itu satu-satunya yang tersisa.

    `sisakan` membuat pemanggil MENGALAH: model yang jatah hariannya tinggal
    sekian atau kurang tidak ikut, dan daftar yang kosong adalah jawaban yang
    sah, bukan kegagalan. Dipakai pekerjaan yang punya cadangan lokal layak,
    supaya jatah terakhir tetap ada saat video berikutnya perlu dipilih.
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
    # Pilihan pengguna selalu di depan. Sesudahnya model yang baru saja
    # berhasil, karena pada gelombang 503 itulah satu-satunya petunjuk yang
    # benar-benar datang dari keadaan sekarang, bukan dari peringkat.
    #
    # Kecuali model lite. Ia menjawab justru KARENA yang lain sedang habis, jadi
    # "terakhir berhasil" untuknya berarti "yang lain sedang tidak bisa", bukan
    # "yang ini paling baik". Membiarkannya memimpin membuat seluruh pemilihan
    # klip dikerjakan model paling lemah selama enam jam sesudah jatah harian
    # pulih, dan hasilnya persis keluhan "klipnya tidak berbobot". Tempatnya
    # tetap paling belakang, tempat ia memang berguna.
    baru = terakhir_berhasil()
    depan = [m for m in (pilihan, None if (baru and lite(baru)) else baru) if m]
    urutan = depan + [m for m in dasar if m not in depan]
    bisa = [m for m in urutan if not tanpa_kuota(m) and not habis_harian(m)]
    if sisakan > 0:
        # Kosong berarti "mengalah", bukan "tidak ada model". Jadi TIDAK ada
        # jaring `or urutan` di sini: menjatuhkannya kembali ke daftar penuh
        # akan menghapus seluruh gunanya menyisakan jatah.
        return [m for m in bisa if sisa_model(m) > sisakan]
    return bisa or urutan
