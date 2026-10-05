"""
Pemeriksa klip sebelum diunggah: hal-hal yang diketahui menurunkan jangkauan.

Diminta pemiliknya 5 Oktober 2026, sesudah mengunggah banyak video dan hanya
satu-dua yang ditonton: "racikkan formula video konten saya agar tembus fyp".

APA YANG BERKAS INI TIDAK LAKUKAN, DAN KENAPA.

Ia tidak menjanjikan FYP. Tidak ada yang bisa, dan menjual jaminan itu kepada
orang yang akan memakainya untuk mencari nafkah adalah hal yang paling buruk
yang bisa dilakukan berkas ini. Peringkat ditentukan model milik platform yang
tidak diterbitkan, berubah tanpa pengumuman, dan menimbang hal-hal yang tidak
ada di dalam berkas videonya — jam tayang, riwayat kanal, siapa yang menonton
sepuluh detik pertamanya.

Yang ADA di dalam berkas videonya, dan memang menentukan, cuma satu hal:
apakah penontonnya bertahan. Semua platform pendek memberi jangkauan pada video
yang ditonton sampai habis dan menahan yang ditinggalkan. Itu bukan rahasia,
dan di situlah seluruh isi berkas ini bekerja.

Jadi yang diperiksa di sini hal-hal yang MEMBUAT ORANG PERGI, masing-masing
dengan alasan yang bisa dibaca. Bukan ramalan, melainkan daftar periksa yang
sebelumnya hanya ada di kepala editor yang berpengalaman.

Ambangnya diturunkan dari panduan terbitan platform sendiri dan dari bentuk
klip pendek yang umum, BUKAN dari pengukuran pada kanal pemiliknya — datanya
belum ada. Begitu Analytics tersambung dan klipnya cukup banyak, angka-angka di
sini harus diuji ulang terhadap kanal itu sendiri, dan yang tidak terbukti
dibuang.
"""

from __future__ import annotations

import re
from typing import Optional

# Panjang klip, dalam detik.
#
# Di bawah ini terlalu cepat untuk membangun apa pun; di atasnya penonton
# pendek mulai pergi sebelum habis, dan "ditonton sampai habis" justru ukuran
# yang paling menentukan.
DURASI_MIN = 8.0
DURASI_IDEAL = (15.0, 45.0)
DURASI_MAKS = 90.0

# Detik pertama yang menentukan. Platform pendek memutuskan nasib sebuah video
# dari sini: yang ditinggalkan di tiga detik pertama hampir tidak pernah
# mendapat gelombang kedua.
JENDELA_HOOK = 3.0

# Kalimat pembuka yang terlalu panjang berarti maknanya baru sampai sesudah
# jendela itu lewat.
HOOK_KATA_MAKS = 12

# Subtitle: berapa bagian klip yang harus bertulisan. Sebagian besar penonton
# pendek menonton tanpa suara.
TEKS_LIPUT_MIN = 0.5

# Kata pembuka yang tidak menjanjikan apa-apa. Bukan larangan — hanya penanda
# bahwa tiga detik pertamanya dipakai untuk basa-basi.
PEMBUKA_HAMPA = {
    "halo", "hai", "oke", "ok", "jadi", "nah", "eh", "em", "anu", "jadi gini",
    "selamat datang", "balik lagi", "kembali lagi", "apa kabar", "assalamualaikum",
}

_GUMAM = re.compile(r"\b(eh+|em+|anu|hmm+|aa+|ee+)\b", re.I)


def _kata(teks: str) -> list[str]:
    return [w for w in re.split(r"\s+", (teks or "").strip()) if w]


def periksa(meta: dict) -> dict:
    """
    {skor, catatan: [{berat, judul, saran}]} untuk satu klip.

    `meta` adalah sidecar klip: durasi, subtitles, hook_text, title, hashtags.
    Skor 0-100, dan ia bukan ramalan jangkauan melainkan ringkasan berapa
    banyak dari daftar ini yang lolos.
    """
    catatan: list[dict] = []
    durasi = float(meta.get("duration") or 0.0)
    baris = list(meta.get("subtitles") or [])
    teks_semua = " ".join((b.get("text") or "") for b in baris).strip()
    judul = (meta.get("title") or "").strip()
    hook = (meta.get("hook_text") or "").strip()

    # --- Panjang ---------------------------------------------------------------
    if durasi and durasi < DURASI_MIN:
        catatan.append({
            "berat": "berat", "judul": f"Terlalu pendek ({durasi:.0f} detik)",
            "saran": "Di bawah delapan detik, penonton belum sempat mengerti apa "
                     "yang terjadi sebelum videonya mengulang. Panjangkan ke "
                     "sekitar lima belas detik dengan menambah detik sebelum "
                     "momennya.",
        })
    elif durasi > DURASI_MAKS:
        catatan.append({
            "berat": "berat", "judul": f"Terlalu panjang ({durasi:.0f} detik)",
            "saran": "Yang menentukan jangkauan video pendek adalah berapa banyak "
                     "yang menontonnya sampai habis. Potong ke bagian yang paling "
                     "ramai saja; satu momen utuh lebih baik daripada tiga momen "
                     "yang ditinggalkan di tengah.",
        })
    elif durasi and not (DURASI_IDEAL[0] <= durasi <= DURASI_IDEAL[1]):
        catatan.append({
            "berat": "ringan", "judul": f"Panjangnya {durasi:.0f} detik",
            "saran": f"Yang paling sering tuntas ditonton ada di "
                     f"{DURASI_IDEAL[0]:.0f}-{DURASI_IDEAL[1]:.0f} detik. Ini bukan "
                     "aturan keras, hanya bentuk yang paling sering berhasil.",
        })

    # --- Tiga detik pertama ----------------------------------------------------
    awal = [b for b in baris if float(b.get("start") or 0) < JENDELA_HOOK]
    teks_awal = " ".join((b.get("text") or "") for b in awal).strip()
    if baris and not teks_awal:
        catatan.append({
            "berat": "berat", "judul": "Tiga detik pertama tanpa suara",
            "saran": "Tidak ada yang diucapkan di awal, jadi tidak ada alasan untuk "
                     "bertahan. Mulai klipnya tepat di kalimat yang membuat orang "
                     "ingin tahu kelanjutannya.",
        })
    elif teks_awal:
        bersih = _GUMAM.sub("", teks_awal).strip().lower()
        if any(bersih.startswith(p) for p in PEMBUKA_HAMPA):
            catatan.append({
                "berat": "sedang", "judul": "Dibuka dengan basa-basi",
                "saran": f"Kalimat pertamanya mulai dengan sapaan. Tiga detik "
                         f"pertama adalah satu-satunya kesempatan; pakai untuk "
                         f"mengatakan apa yang terjadi, bukan untuk menyapa.",
            })

    if hook and len(_kata(hook)) > HOOK_KATA_MAKS:
        catatan.append({
            "berat": "sedang",
            "judul": f"Teks hook {len(_kata(hook))} kata",
            "saran": f"Di atas {HOOK_KATA_MAKS} kata, hook-nya belum selesai dibaca "
                     "saat penonton sudah memutuskan. Potong jadi satu kalimat "
                     "pendek yang menimbulkan pertanyaan.",
        })

    # --- Subtitle --------------------------------------------------------------
    if durasi and baris:
        terliput = sum(max(0.0, float(b.get("end") or 0) - float(b.get("start") or 0))
                       for b in baris)
        porsi = terliput / durasi
        if porsi < TEKS_LIPUT_MIN:
            catatan.append({
                "berat": "sedang",
                "judul": f"Hanya {porsi * 100:.0f}% klip bertulisan",
                "saran": "Sebagian besar penonton video pendek menonton tanpa suara. "
                         "Bagian tanpa tulisan praktis bisu bagi mereka.",
            })
    elif durasi and not baris:
        catatan.append({
            "berat": "berat", "judul": "Tidak ada subtitle sama sekali",
            "saran": "Tanpa tulisan, klip ini hanya bisa dinikmati penonton yang "
                     "menyalakan suaranya — dan sebagian besar tidak.",
        })

    # --- Judul dan tagar -------------------------------------------------------
    if not judul:
        catatan.append({
            "berat": "sedang", "judul": "Belum ada judul",
            "saran": "Judul ikut dibaca mesin pencari dan ikut ditampilkan di "
                     "sebagian tempat. Klip tanpa judul kehilangan satu pintu masuk.",
        })
    tagar = [t for t in (meta.get("hashtags") or []) if str(t).strip()]
    if len(tagar) < 3:
        catatan.append({
            "berat": "ringan", "judul": f"Tagar baru {len(tagar)}",
            "saran": "Tiga sampai lima tagar yang benar-benar menggambarkan isinya. "
                     "Lebih dari itu tidak menambah apa-apa, dan tagar yang tidak "
                     "nyambung justru mendatangkan penonton yang langsung pergi.",
        })

    berat = {"berat": 25, "sedang": 12, "ringan": 5}
    skor = max(0, 100 - sum(berat.get(c["berat"], 5) for c in catatan))
    return {"skor": skor, "catatan": catatan,
            # Dikatakan di sini, bukan hanya di dokumentasi: yang membaca
            # angkanya harus tahu angka itu bukan ramalan.
            "catatan_kaki": ("Daftar periksa, bukan ramalan. Tidak ada yang bisa "
                             "menjamin FYP; yang bisa dijaga adalah hal-hal yang "
                             "diketahui membuat penonton pergi.")}
