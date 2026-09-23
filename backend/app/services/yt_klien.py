"""
Pemilihan player client YouTube — otomatis, dan menyembuhkan diri sendiri.

Masalah yang diselesaikan: "Sign in to confirm you're not a bot" yang muncul
berulang dan tidak hilang meski ditunggu lama. Menunggu bukan jawabannya, dan
menyuruh pengguna memasang cookies jelas bukan jawaban untuk aplikasi yang
harus bisa dipakai siapa saja di komputer mana saja.

YouTube punya belasan "player client" (aplikasi TV, iOS, Android, web, headset
visionOS) dan memperlakukan tiap-tiapnya berbeda. Yang menolak permintaan bukan
YouTube secara keseluruhan, melainkan client tertentu pada saat tertentu.
Diukur 16 September 2026, yt-dlp 2026.08.19, tanpa cookies, dua video:

    tv_simply 0 fmt   ios 0 fmt   web_safari 0 fmt   mweb 0 fmt   tv 0 fmt
    web 0 fmt   web_embedded 0 fmt   android 1 fmt   android_vr 1 fmt
    visionos  34 fmt / 1440p   dan   32 fmt / 1080p

Satu client bekerja sempurna sementara sembilan lainnya nol. Tapi pengukuran
kedua, dua puluh menit kemudian, menunjukkan hal yang jauh lebih penting:
`visionos` yang sama berbalik jadi NOL, sementara gabungan beberapa client
tetap memberi 35 format. Jadi tidak ada satu client yang benar — yang ada hanya
client yang sedang bekerja, dan itu berubah dalam hitungan menit.

Karena itu dua keputusan di sini:

  * Yang dicoba adalah KUMPULAN client dalam SATU permintaan, bukan satu client
    per permintaan. yt-dlp menanyai tiap client lalu menggabungkan formatnya,
    dan itu jauh lebih murah daripada memutar sepuluh permintaan terpisah:
    terukur 2,4 detik untuk empat client sekaligus, melawan 30 detik untuk
    perputaran satu per satu.
  * Kumpulan yang terakhir berhasil DIINGAT dan dicoba lebih dulu. Kalau suatu
    hari kumpulan teratas mati, aplikasi berpindah sendiri — tanpa pembaruan,
    tanpa ada yang perlu disentuh pengguna.
"""

from __future__ import annotations

import threading

# Diurutkan dari yang paling murah ke yang paling luas. Yang pertama menjawab,
# dialah yang dipakai — dan sisanya tidak pernah dijalankan.
STRATEGI: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Empat client yang terbukti masih memberi format saat yang lain nol.
    # Terukur 2,4 detik, 35 format.
    ("cepat", ("visionos", "ios", "tv_simply", "android_vr")),
    # Semua yang dikenal. Lebih lambat (terukur 5,3 detik) tapi memberi YouTube
    # sepuluh pintu untuk dibuka alih-alih empat.
    ("luas", ("visionos", "ios", "tv_simply", "android_vr", "web_safari",
              "mweb", "tv", "web", "web_embedded", "android")),
    # Kosong = biarkan yt-dlp memilih sendiri. Ditaruh terakhir sebagai jaring
    # pengaman: kalau daftar di atas jadi usang karena YouTube menambah client
    # baru, yt-dlp yang diperbarui akan tahu, sementara daftar ini tidak.
    ("bawaan", ()),
)

# Jeda sebelum mencoba kumpulan berikutnya. Sebagian penolakan YouTube memang
# sesaat, dan berpindah strategi dalam milidetik menghabiskan seluruh daftar
# sebelum penolakan sesaat itu sempat reda.
JEDA_ANTAR_STRATEGI = 1.5

KUNCI = "youtube.strategi_terakhir"

_kunci = threading.Lock()
_terakhir: str | None = None
_sudah_dibaca = False
_nama_sah = {n for n, _ in STRATEGI}


def _baca_simpanan() -> None:
    global _terakhir, _sudah_dibaca
    if _sudah_dibaca:
        return
    _sudah_dibaca = True
    try:
        from ..repos import settings as settings_repo
        nilai = settings_repo.get(KUNCI, "").strip()
        if nilai in _nama_sah:
            _terakhir = nilai
    except Exception:
        # Basis data yang belum siap bukan alasan menolak melayani permintaan.
        pass


def urutan_coba() -> list[tuple[str, tuple[str, ...]]]:
    """Kumpulan client yang dicoba, yang terakhir berhasil paling depan."""
    with _kunci:
        _baca_simpanan()
        pilihan = _terakhir
    urut = list(STRATEGI)
    if pilihan:
        urut.sort(key=lambda s: s[0] != pilihan)
    try:
        from . import cookies as cookies_svc
        if cookies_svc.aktif():
            # visionos/ios/android tidak menerima cookies sama sekali; dengan
            # sesi login, pilihan bawaan yt-dlp (client web) yang bekerja.
            urut.sort(key=lambda s: s[0] != "bawaan")
    except Exception:
        pass
    return urut


def catat_berhasil(nama: str) -> None:
    """Mengingat kumpulan yang barusan bekerja, supaya dicoba pertama nanti."""
    global _terakhir
    with _kunci:
        _baca_simpanan()
        if _terakhir == nama:
            return
        _terakhir = nama
    try:
        from ..repos import settings as settings_repo
        settings_repo.set_value(KUNCI, nama)
    except Exception:
        # Gagal menyimpan hanya berarti pencariannya diulang lain kali.
        pass


def terakhir_berhasil() -> tuple[str, tuple[str, ...]] | None:
    with _kunci:
        _baca_simpanan()
        nama = _terakhir
    if not nama:
        return None
    return next((s for s in STRATEGI if s[0] == nama), None)


def pasang(opts: dict, klien: tuple[str, ...]) -> dict:
    """Menyetel kumpulan player client pada SALINAN opsi yt-dlp."""
    o = dict(opts)
    if not klien:
        # Biarkan yt-dlp memilih: jangan tinggalkan setelan dari percobaan lalu.
        ekstra = dict(o.get("extractor_args") or {})
        yt = dict(ekstra.get("youtube") or {})
        yt.pop("player_client", None)
        if yt:
            ekstra["youtube"] = yt
        else:
            ekstra.pop("youtube", None)
        if ekstra:
            o["extractor_args"] = ekstra
        else:
            o.pop("extractor_args", None)
        return o
    ekstra = dict(o.get("extractor_args") or {})
    yt = dict(ekstra.get("youtube") or {})
    yt["player_client"] = list(klien)
    ekstra["youtube"] = yt
    o["extractor_args"] = ekstra
    return o
