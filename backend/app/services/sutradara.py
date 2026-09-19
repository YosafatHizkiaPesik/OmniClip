"""
Sutradara otomatis: memutuskan CARA MEMBINGKAI dan EFEK SUARA per momen.

Selama ini satu klip memakai satu cara membingkai dari awal sampai akhir,
kecuali pengguna membelah lajur Bingkai sendiri. Modul ini membelahnya: ia
membaca videonya, menemukan momen yang menuntut bidikan lain, lalu MENGUSULKAN
kunci bingkai dan sisipan suara.

Kata kuncinya "mengusulkan". Semua keputusannya keluar sebagai kunci bingkai
dan sisipan BIASA — kelihatan di lajur Bingkai dan di daftar Sisipan, bertanda
"otomatis" beserta alasannya, dan bisa dihapus satu per satu seperti buatan
tangan. Keputusan otomatis yang meleset lebih mahal daripada ketiadaannya bila
ia tersembunyi di dalam renderer, karena pengguna harus lebih dulu menemukannya
sebelum bisa membetulkannya.

Pola pertama yang dikenali: GAMEPLAY BERFACECAM.
  - dasar: wajah pemain di atas, permainan di bawah (mode `gaming`);
  - JUMPSCARE: lonjakan suara mendadak sesudah suasana tenang. Di situ bingkai
    pindah ke reaksi penuh — wajahnya sendiri, 9:16, memenuhi layar — selama
    beberapa detik, lalu kembali. Plus satu dentum di titik kejutnya.

Pola berikutnya (belum): reaksi beberapa orang sekaligus di podcast, dan
perpindahan adegan pada kartun. Keduanya dicatat di SISA-PEKERJAAN.md.
"""

import logging
from .proses import jalankan
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger("omniclip.sutradara")

# Resolusi jejak energi. 50 ms cukup untuk menangkap awal teriakan; lebih kasar
# dari itu, titik perpindahannya terlambat terasa.
LANGKAH = 0.05
# Seberapa lama "suasana tenang" yang dijadikan pembanding, dan seberapa lebar
# jendela lonjakannya.
LATAR_DETIK = 3.0
LONJAK_DETIK = 0.25
# Lonjakan yang dihitung kejutan: sekian dB di atas latarnya, DAN cukup keras
# dengan sendirinya. Syarat kedua membuang lonjakan dari hening total ke suara
# biasa — napas sesudah jeda panjang bukan jumpscare.
NAIK_MIN_DB = 14.0
KERAS_MIN_DB = -26.0
# Reaksi penuh ditahan sekian detik, dan dua kejutan tidak boleh lebih rapat
# dari ini: bingkai yang berpindah terus-menerus lebih buruk daripada yang diam.
# Syarat kedua dan ketiga, ditambahkan sesudah diuji pada rekaman horor
# sungguhan (Windah Basudara, 40 menit). Dengan dua syarat pertama saja, "kejutan"
# muncul tiap 6-15 detik — setiap kali pemainnya mulai bicara lagi sesudah jeda.
# Dilihat bingkai demi bingkai, TIDAK SATU PUN dari kandidat terkuatnya adalah
# jumpscare: yang tertangkap adalah pemain tertawa di layar kredit dan kamera
# yang berbalik. Streamer horor memang bersuara keras hampir terus-menerus.
#
# Suara permainan dan suara mikrofon ada di SATU trek, jadi keduanya tidak bisa
# dipisahkan. Yang bisa dikenali dengan jujur adalah REAKSI TERKERAS: jauh di
# atas kebiasaan orang itu sendiri (persentil 90 klipnya), dan datang mendadak.
DI_ATAS_KEBIASAAN_DB = 3.0
SERANGAN_MIN_DB = 12.0     # lompatan terbesar antar dua langkah 50 ms
TAHAN_REAKSI = 2.6
JARAK_MIN = 6.0
# Bingkai sedikit mendahului lonjakan, supaya wajahnya sudah penuh saat
# teriakannya terdengar — bukan menyusul sesudahnya.
MENDAHULUI = 0.12


def _energi_klip(src: Path, segments: list[dict]) -> list[float]:
    """Kekerasan suara per LANGKAH dalam dBFS, dalam waktu KLIP."""
    import numpy as np

    sr = 16000
    per = int(sr * LANGKAH)
    hasil: list[float] = []
    for seg in segments:
        mulai = float(seg["start"])
        panjang = max(0.0, float(seg["end"]) - mulai)
        cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
               "-ss", f"{mulai:.3f}", "-t", f"{panjang:.3f}", "-i", str(src),
               "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
        mentah = jalankan(cmd, text=False).stdout
        x = np.frombuffer(mentah, np.int16).astype(np.float64) / 32768.0
        n = len(x) // per
        if n == 0:
            continue
        rms = np.sqrt(np.mean(x[: n * per].reshape(n, per) ** 2, axis=1))
        hasil.extend((20 * np.log10(rms + 1e-6)).tolist())
    return hasil


def cari_kejutan(energi: list[float]) -> list[dict]:
    """
    Titik jumpscare: [{t, naik_db, keras_db}], urut waktu.

    Pembandingnya MEDIAN tiga detik sebelumnya, bukan rata-rata: satu langkah
    kaki keras di tengah keheningan menaikkan rata-rata tapi tidak menaikkan
    median, jadi keheningannya tetap terbaca sebagai hening.
    """
    import numpy as np

    e = np.asarray(energi, dtype=np.float64)
    bersuara = e[e > -60]
    if len(bersuara) < 10:
        return []
    kebiasaan = float(np.percentile(bersuara, 90))
    n_latar = int(LATAR_DETIK / LANGKAH)
    n_lonjak = max(1, int(LONJAK_DETIK / LANGKAH))
    kandidat: list[dict] = []
    for i in range(n_latar, len(e) - n_lonjak):
        latar = float(np.median(e[i - n_latar:i - 2]))
        # Kekerasan jendela lonjakan dihitung dari DAYA, bukan rata-rata dB:
        # rata-rata desibel meremehkan puncak pendek, dan teriakan memang pendek.
        daya = np.mean(10 ** (e[i:i + n_lonjak] / 10))
        keras = float(10 * np.log10(daya + 1e-12))
        naik = keras - latar
        if naik < NAIK_MIN_DB or keras < KERAS_MIN_DB:
            continue
        if keras - kebiasaan < DI_ATAS_KEBIASAAN_DB:
            continue
        serangan = float(np.max(np.diff(e[max(0, i - 2):i + 3])))
        if serangan < SERANGAN_MIN_DB:
            continue
        kandidat.append({"t": i * LANGKAH, "naik_db": naik, "keras_db": keras,
                         "di_atas_db": keras - kebiasaan})

    # Satu wakil per ledakan (yang naiknya terbesar), dan jarak minimum antar
    # wakil — yang lebih kuat menang.
    kandidat.sort(key=lambda k: k["naik_db"], reverse=True)
    terpilih: list[dict] = []
    for k in kandidat:
        if all(abs(k["t"] - p["t"]) >= JARAK_MIN for p in terpilih):
            terpilih.append(k)
    terpilih.sort(key=lambda k: k["t"])
    return [{**k, "t": round(k["t"], 2), "naik_db": round(k["naik_db"], 1),
             "keras_db": round(k["keras_db"], 1),
             "di_atas_db": round(k["di_atas_db"], 1)} for k in terpilih]


def kotak_reaksi(fc: dict, src_w: int, src_h: int) -> dict:
    """
    Potongan 9:16 dari DALAM facecam, berpusat pada wajahnya, dalam persen.

    Memotong facecam 16:9 asal di tengah akan memenggal wajah pada streamer yang
    duduk di pinggir panelnya. Pusatnya diambil dari awan deteksi wajah, lalu
    potongannya dijepit supaya tidak keluar dari panel.
    """
    x, y, w, h = fc["x"], fc["y"], fc["w"], fc["h"]
    tinggi_px = h / 100 * src_h
    lebar_px = min(tinggi_px * 9 / 16, w / 100 * src_w)
    lebar = lebar_px / src_w * 100
    awan = fc.get("awan_kotak") or [x, y, x + w, y + h]
    pusat = (awan[0] + awan[2]) / 2
    kiri = min(max(pusat - lebar / 2, x), x + w - lebar)
    return {"x": round(kiri, 3), "y": round(y, 3), "w": round(lebar, 3), "h": round(h, 3)}


def susun(src: Path, segments: list[dict], *, out_w: int = 1080,
          out_h: int = 1920) -> dict:
    """
    Usulan kunci bingkai dan sisipan untuk satu klip.

    {jenis, keys, layers, catatan, kejutan}. `keys` kosong berarti sutradara
    tidak menemukan pola yang ia kenali — itu jawaban, bukan kegagalan.
    """
    from .media import probe
    from .reframe import deteksi_facecam
    from .render import rasio_bidang_wajah

    src = Path(src)
    info = probe(src)
    sw, sh = int(info.get("width") or 1920), int(info.get("height") or 1080)
    durasi = sum(float(s["end"]) - float(s["start"]) for s in segments)
    mulai = float(segments[0]["start"]) if segments else 0.0

    fc = deteksi_facecam(src, mulai, min(durasi, 30.0), sw, sh,
                         rasio_potongan=rasio_bidang_wajah(out_w, out_h))
    if not fc:
        return {"jenis": "tidak_dikenali", "keys": [], "layers": [], "kejutan": [],
                "catatan": ["Tidak ada facecam yang diam di satu tempat — klip ini "
                            "bukan rekaman gameplay berkamera pemain. Susunan "
                            "otomatis untuk jenis video lain belum ada."]}

    kejutan = [k for k in cari_kejutan(_energi_klip(src, segments))
               if k["t"] + TAHAN_REAKSI <= durasi + 0.5]
    reaksi = kotak_reaksi(fc, sw, sh)

    keys: list[dict] = [{
        "t": 0.0, "mode": "gaming", "asal": "otomatis",
        "alasan": "Facecam ditemukan — wajah di atas, permainan di bawah",
    }]
    layers: list[dict] = []
    for k in kejutan:
        t0 = max(0.0, k["t"] - MENDAHULUI)
        keys.append({
            "t": round(t0, 2), "mode": "box", "rect": reaksi, "asal": "otomatis",
            "alasan": (f"Reaksi kaget — suara {k['di_atas_db']:.0f} dB di atas "
                       f"kebiasaannya, mendadak. Wajah dibuat penuh."),
        })
        keys.append({
            "t": round(min(durasi, t0 + TAHAN_REAKSI), 2), "mode": "gaming",
            "asal": "otomatis", "alasan": "Kembali ke permainan",
        })
        layers.append({
            "aset": "efek:dentum", "jenis": "audio", "nama": "Dentum",
            "t": round(t0, 2), "dur": 1.6, "volume": 0.7,
            "asal": "otomatis",
            "alasan": "Dentum menegaskan momen kagetnya",
        })
    keys = [k for k in keys if k["t"] < durasi - 0.05]

    catatan = [f"Facecam di x={fc['x']:.0f}% y={fc['y']:.0f}%, "
               f"hadir {fc.get('kehadiran', 0) * 100:.0f}% waktu."]
    catatan.append(f"{len(kejutan)} reaksi kaget ditemukan." if kejutan else
                   "Tidak ada reaksi yang cukup menonjol dibanding kebiasaan "
                   "pemainnya — bingkai tetap wajah di atas, permainan di bawah.")
    log.info("Sutradara: gameplay, %d kejutan di %s", len(kejutan),
             [k["t"] for k in kejutan])
    return {"jenis": "gameplay", "keys": keys, "layers": layers,
            "kejutan": kejutan, "catatan": catatan, "facecam": fc}


# --- Berapa orang di rekaman gameplay ------------------------------------------
#
# Jumlah penutur ditebak dari SUARA, dan pada gameplay itu keliru dengan cara
# yang khas: suara pemain yang berbisik lalu berteriak, suara tokoh permainan,
# dan efek suaranya terbaca sebagai orang-orang berbeda. Terukur pada rekaman
# horor Windah seorang diri: tujuh "penutur" dengan porsi 41/27/14/6/5/4/3%, dan
# ditandai YAKIN.
#
# Porsi bicara sendiri tidak bisa membedakannya — podcast lima orang sungguhan
# juga punya satu penutur yang hanya 4,2%. Yang membedakan ada di GAMBAR: facecam
# kecil yang diam di satu pojok, berisi satu wajah.
#
#   gameplay Windah (2 video) : facecam 17-19% x 29-39%, sebaran wajah 0,08
#   podcast lima orang        : tidak ada
#   wawancara Elon, Andry     : "facecam" 53-79% lebar — itu close-up, bukan
#                               facecam, dan ditolak oleh batas ukuran di bawah
FACECAM_LEBAR_MAKS_PERSEN = 30.0
FACECAM_TINGGI_MAKS_PERSEN = 50.0
# Sebaran wajah di dalam facecam, sebagai pecahan lebar layar. Satu orang
# ± 0,08; dua orang berbagi satu kamera melebar jauh di atasnya.
SATU_WAJAH_SEBARAN_MAKS = 0.12


def perkiraan_pemain(src, durasi: float) -> Optional[int]:
    """
    Jumlah orang di facecam bila ini rekaman gameplay; None bila bukan.

    Dua titik contoh (25% dan 60% video), masing-masing 12 detik — sekitar 5-18
    detik total. Cukup satu titik yang menemukan facecam KECIL, asal tidak ada
    titik yang menemukan wajah close-up besar (yang berarti ini rekaman orang,
    bukan permainan).
    """
    from .media import probe
    from .reframe import deteksi_facecam

    try:
        info = probe(src)
        w, h = int(info.get("width") or 0), int(info.get("height") or 0)
    except Exception:
        return None
    if not w or not h or durasi <= 30:
        return None

    kecil: list[dict] = []
    for bagian in (0.25, 0.60):
        fc = deteksi_facecam(src, durasi * bagian, 12.0, w, h)
        if not fc:
            continue
        if fc["w"] > FACECAM_LEBAR_MAKS_PERSEN or fc["h"] > FACECAM_TINGGI_MAKS_PERSEN:
            return None                    # close-up orang: bukan gameplay
        kecil.append(fc)
    if not kecil:
        return None
    sebaran = max(float((fc.get("awan") or [0])[0]) for fc in kecil)
    jumlah = 1 if sebaran <= SATU_WAJAH_SEBARAN_MAKS else 2
    log.info("Rekaman gameplay: facecam di x=%.0f%% y=%.0f%%, sebaran wajah %.3f -> %d orang",
             kecil[0]["x"], kecil[0]["y"], sebaran, jumlah)
    return jumlah
