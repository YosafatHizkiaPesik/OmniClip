"""
Bagaimana klip yang sudah diunggah benar-benar berjalan, dan apa artinya.

Diminta pemiliknya 6 Oktober 2026: "pada fitur analytic mengapa tidak ada
tampilan apa apa padahal sudah saya masukkan api key youtube data v3, OmniClip
hanya menunjukkan kunci terpasang saja, tidak ada data apapun atau analisa
serta saran untuk meningkatkan views".

Ia benar. Yang ada sebelumnya cuma dua hal yang terpisah jauh: angka tayangan
kecil di kartu Klip jadi, dan daftar periksa `fyp.py` yang hanya muncul saat
menyiapkan satu klip untuk diunggah. Tidak ada satu tempat pun yang menjawab
"klip mana yang jalan, dan kenapa".

APA YANG BERKAS INI BOLEH KATAKAN, DAN APA YANG TIDAK.

Dengan satu-dua klip terunggah, tidak ada analisis yang jujur. Perbedaan
tayangan antara dua video bisa seluruhnya kebetulan, dan menyajikan kebetulan
itu sebagai sebab adalah cara tercepat membuat orang mengubah hal yang salah.
Jadi di bawah `AMBANG_BANDING` klip terbaca, berkas ini TIDAK membandingkan
apa pun. Yang ditampilkan daftar periksa yang digabung dari semua klip: bukan
"ini sebabnya sepi", melainkan "ini yang masih kurang di n dari m klip Anda".

Di atas ambang itu, ia baru membandingkan, dan hanya pada temuan yang benar
benar punya dua kelompok pembanding, masing-masing minimal `KELOMPOK_MIN`
klip. Yang dibandingkan median, bukan rata-rata: satu klip yang meledak
menggeser rata-rata sampai tak berarti apa-apa.

Video yang TIDAK terbaca tidak pernah dihitung nol. YouTube hanya memberi
angka untuk video publik lewat kunci API, dan klip yang masih berstatus
pribadi akan hilang dari hasil `videos.list`. Itu dikatakan apa adanya di
ringkasannya, karena "0 tayangan" pada video yang belum publik adalah angka
yang salah dan langsung dipakai orang untuk mengambil keputusan.
"""

from __future__ import annotations

import json
import logging
from statistics import median
from typing import Optional

log = logging.getLogger("omniclip.analitik")

# Berapa klip terbaca yang dibutuhkan sebelum berkas ini berani membandingkan.
AMBANG_BANDING = 8

# Dan berapa klip minimal di tiap sisi perbandingan.
KELOMPOK_MIN = 3

# Selisih median yang dianggap cukup besar untuk disebut. Di bawah ini
# bedanya tidak layak dipakai mengubah cara kerja.
SELISIH_BERARTI = 0.25

BOBOT = {"berat": 3, "sedang": 2, "ringan": 1}


def _sidecar(clip_name: str, profil_id: int) -> Optional[dict]:
    """Catatan isi klip, atau None kalau berkasnya tidak ada lagi."""
    try:
        from . import profil as profil_svc
        from .paths import safe_media_path
        jalur = safe_media_path(profil_svc.kategori_klip(profil_id), clip_name)
    except Exception:                                    # noqa: BLE001
        return None
    berkas = jalur.with_suffix(".json")
    if not berkas.is_file():
        return None
    try:
        return json.loads(berkas.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def kumpulkan(profil_id: int, *, batas: int = 200) -> dict:
    """
    Klip yang sudah diunggah ke YouTube, lengkap dengan tayangan dan temuannya.

    Tidak menyentuh jaringan selain satu panggilan `videos.list` yang sudah
    disimpan lima belas menit di `statistik.py`.
    """
    from . import fyp
    from . import statistik as stat_svc
    from ..repos import uploads as uploads_repo

    baris = uploads_repo.list_recent(batas, None, profil_id=profil_id)
    naik = [u for u in baris
            if u.get("target") == "youtube" and u.get("status") == "done"
            and (u.get("remote_id") or "").strip()]

    # Satu baris per video di kanal. Riwayat bisa memuat beberapa baris untuk
    # satu video yang sama; yang dipakai yang paling baru. Klip yang diunggah
    # dua kali tetap jadi dua baris, karena di kanalnya memang ada dua video,
    # masing-masing dengan tayangannya sendiri.
    unik: dict[str, dict] = {}
    for u in naik:
        rid = u["remote_id"].strip()
        if rid not in unik:
            unik[rid] = u

    angka = stat_svc.tayangan(list(unik.keys()))

    klip: list[dict] = []
    for rid, u in unik.items():
        meta = _sidecar(u.get("clip_name") or "", profil_id) or {}
        periksa = fyp.periksa(meta) if meta else None
        s = angka.get(rid) or {}
        klip.append({
            "remote_id": rid,
            "clip_name": u.get("clip_name") or "",
            "judul": (u.get("title") or meta.get("title") or u.get("clip_name") or "").strip(),
            "waktu": u.get("finished_at") or u.get("created_at"),
            "privasi": (u.get("privacy") or "").strip(),
            "url": u.get("remote_url") or f"https://youtu.be/{rid}",
            "durasi": float(meta.get("duration") or 0.0) or None,
            "terbaca": bool(s),
            "tayangan": s.get("tayangan"),
            "suka": s.get("suka"),
            "komentar": s.get("komentar"),
            "skor": (periksa or {}).get("skor"),
            "catatan": (periksa or {}).get("catatan") or [],
            "ada_catatan_isi": periksa is not None,
        })

    klip.sort(key=lambda k: (k["tayangan"] is None, -(k["tayangan"] or 0)))
    return {"klip": klip,
            "kunci_terpasang": bool(stat_svc.kunci_api()),
            "terunggah": len(unik),
            "terbaca": sum(1 for k in klip if k["terbaca"])}


def _ringkasan(klip: list[dict]) -> dict:
    nilai = [k["tayangan"] for k in klip if isinstance(k.get("tayangan"), int)]
    if not nilai:
        return {"total": 0, "median": None, "terbaik": None, "terendah": None}
    terbaca = [k for k in klip if isinstance(k.get("tayangan"), int)]
    terbaik = max(terbaca, key=lambda k: k["tayangan"])
    terendah = min(terbaca, key=lambda k: k["tayangan"])
    return {
        "total": sum(nilai),
        "median": int(median(nilai)),
        "terbaik": {"judul": terbaik["judul"], "tayangan": terbaik["tayangan"],
                    "clip_name": terbaik["clip_name"]},
        "terendah": {"judul": terendah["judul"], "tayangan": terendah["tayangan"],
                     "clip_name": terendah["clip_name"]},
    }


def _temuan_terkumpul(klip: list[dict]) -> list[dict]:
    """Berapa klip yang kena tiap temuan, diurutkan dari yang paling berat."""
    kena: dict[str, dict] = {}
    for k in klip:
        for c in k.get("catatan") or []:
            kode = c.get("kode") or c.get("judul") or "lain"
            pos = kena.setdefault(kode, {
                "kode": kode, "berat": c.get("berat") or "ringan",
                "judul": c.get("judul") or "", "saran": c.get("saran") or "",
                "klip": [],
            })
            pos["klip"].append(k["clip_name"])
    dari = len([k for k in klip if k.get("ada_catatan_isi")])
    hasil = []
    for pos in kena.values():
        hasil.append({**pos, "berapa": len(pos["klip"]), "dari": dari,
                      "dasar": "umum"})
    hasil.sort(key=lambda h: (-BOBOT.get(h["berat"], 1) * h["berapa"], h["judul"]))
    return hasil


def _temuan_terbukti(klip: list[dict]) -> list[dict]:
    """
    Temuan yang benar-benar berbeda tayangannya DI KANAL INI.

    Hanya dipanggil kalau klip terbacanya sudah cukup banyak. Tiap temuan
    dibandingkan median tayangan klip yang kena dengan klip yang tidak; yang
    salah satu sisinya kurang dari `KELOMPOK_MIN` klip tidak dibandingkan sama
    sekali, karena median dari dua angka bukan apa-apa.
    """
    terbaca = [k for k in klip
               if isinstance(k.get("tayangan"), int) and k.get("ada_catatan_isi")]
    semua_kode = {c.get("kode") for k in terbaca for c in (k.get("catatan") or [])}
    semua_kode.discard(None)

    hasil = []
    for kode in sorted(semua_kode):
        kena = [k for k in terbaca
                if any(c.get("kode") == kode for c in k.get("catatan") or [])]
        bersih = [k for k in terbaca if k not in kena]
        if len(kena) < KELOMPOK_MIN or len(bersih) < KELOMPOK_MIN:
            continue
        m_kena = median([k["tayangan"] for k in kena])
        m_bersih = median([k["tayangan"] for k in bersih])
        if m_bersih <= 0:
            continue
        selisih = (m_bersih - m_kena) / m_bersih
        if selisih < SELISIH_BERARTI:
            continue
        contoh = next((c for k in kena for c in (k.get("catatan") or [])
                       if c.get("kode") == kode), {})
        hasil.append({
            "kode": kode, "berat": contoh.get("berat") or "sedang",
            "judul": contoh.get("judul") or kode, "saran": contoh.get("saran") or "",
            "berapa": len(kena), "dari": len(terbaca), "dasar": "kanal",
            "median_kena": int(m_kena), "median_bersih": int(m_bersih),
            "selisih": round(selisih, 2),
        })
    hasil.sort(key=lambda h: -h["selisih"])
    return hasil


def _gabung_kanal(data: dict, profil_id: int) -> dict:
    """
    Menambahkan video kanal yang TIDAK diunggah lewat OmniClip.

    Dilaporkan pemiliknya 9 Oktober 2026: "disana tidak memuat seluruh video
    yang kita upload". Benar: `kumpulkan` membaca tabel `uploads`, yaitu
    riwayat unggahan OmniClip sendiri, dan video yang naik dari ponsel atau
    dari peramban tidak pernah lewat situ. Pada kanalnya saat itu: 4 video di
    kanal, 1 yang diunggah OmniClip. Tiga perempat datanya hilang dari halaman
    yang seharusnya menjawab "video saya harus seperti apa".

    Yang datang dari OmniClip tetap dibedakan, karena hanya untuk video itulah
    kita punya keterangan isinya: hook, durasi, tagar, hasil periksa fyp. Untuk
    video dari luar yang ada cuma angkanya, dan itu dikatakan apa adanya alih-
    alih dikarang.
    """
    from . import kanal as kanal_svc

    try:
        isi = kanal_svc.semua(profil_id)
    except Exception as e:                           # noqa: BLE001
        log.info("Daftar video kanal tidak terbaca: %s", str(e)[:160])
        return data
    if not isi.get("ada"):
        return {**data, "kanal": isi.get("kanal") or {},
                "kanal_terbaca": False,
                "kanal_alasan": isi.get("alasan") or ""}

    punya = {k["remote_id"] for k in data["klip"]}
    tambahan = []
    for v in isi["video"]:
        if v["id"] in punya:
            continue
        tambahan.append({
            "remote_id": v["id"],
            "clip_name": "",
            "judul": v["judul"],
            "waktu": v["terbit"],
            "privasi": "",
            "url": f"https://youtu.be/{v['id']}",
            "durasi": v["durasi"],
            "terbaca": v["tayangan"] is not None,
            "tayangan": v["tayangan"],
            "suka": v["suka"],
            "komentar": v["komentar"],
            "sampul": v["sampul"],
            "skor": None,
            "catatan": [],
            "ada_catatan_isi": False,
            "dari_omniclip": False,
        })

    # Angka yang paling baru menang. Video yang diunggah OmniClip juga ada di
    # daftar kanal, dan daftar kanal dibaca sekaligus dengan tanggal terbit dan
    # sampulnya, jadi keterangan itu dipinjamkan ke barisnya.
    peta = {v["id"]: v for v in isi["video"]}
    for k in data["klip"]:
        v = peta.get(k["remote_id"])
        k["dari_omniclip"] = True
        if not v:
            continue
        k["sampul"] = v["sampul"]
        k["waktu"] = v["terbit"] or k["waktu"]
        for kolom in ("tayangan", "suka", "komentar"):
            if v.get(kolom) is not None:
                k[kolom] = v[kolom]
        k["terbaca"] = True
        if not k.get("durasi"):
            k["durasi"] = v["durasi"]

    semua = data["klip"] + tambahan
    semua.sort(key=lambda k: (k["tayangan"] is None, -(k["tayangan"] or 0)))
    return {**data, "klip": semua, "kanal": isi.get("kanal") or {},
            "kanal_terbaca": True,
            "dari_omniclip": len(data["klip"]),
            "terunggah": len(semua),
            "terbaca": sum(1 for k in semua if k["terbaca"])}


def _catat_harian(klip: list[dict]) -> None:
    """
    Menyimpan angka hari ini, sekali sehari.

    Ini satu-satunya cara OmniClip bisa punya grafik: YouTube Data API hanya
    memberi angka SAAT INI, dan riwayat sungguhan ada di Analytics API yang
    menuntut izin baru plus persetujuan ulang dari tiap akun.
    """
    from ..repos import statistik_harian as sh

    try:
        if sh.sudah_dicatat():
            return
        sh.catat([{"id": k["remote_id"], "tayangan": k.get("tayangan"),
                   "suka": k.get("suka"), "komentar": k.get("komentar")}
                  for k in klip if k.get("terbaca")])
    except Exception as e:                           # noqa: BLE001
        log.info("Catatan harian gagal: %s", str(e)[:160])


def laporan(profil_id: int, *, batas: int = 200) -> dict:
    """Satu halaman penuh: angka, temuan, dan apa yang belum boleh dikatakan."""
    data = _gabung_kanal(kumpulkan(profil_id, batas=batas), profil_id)
    klip = data["klip"]
    _catat_harian(klip)
    terbaca = data["terbaca"]
    cukup = terbaca >= AMBANG_BANDING

    temuan = _temuan_terbukti(klip) if cukup else []
    if not temuan:
        # Juga saat sudah cukup data tapi tidak ada satu pun temuan yang
        # terbukti berbeda: daftar periksanya tetap berguna, asal tidak
        # mengaku sebagai sebab.
        temuan = _temuan_terkumpul(klip)

    from ..repos import statistik_harian as sh
    try:
        deret = sh.harian_kanal([k["remote_id"] for k in klip])
    except Exception:                                # noqa: BLE001
        deret = []

    return {
        **data,
        "ringkasan": _ringkasan(klip),
        "temuan": temuan,
        "cukup_data": cukup,
        "ambang": AMBANG_BANDING,
        # Grafik tayangan per hari, dicatat OmniClip sendiri. Kosong pada hari
        # pertama, dan itu dikatakan apa adanya di layar alih-alih digambar
        # sebagai garis datar yang seolah berarti "tidak ada penonton".
        "harian": deret,
        "catatan_kaki": (
            "Angka ini dibaca dengan kunci YouTube Data API, jadi hanya video "
            "PUBLIK yang terbaca; yang masih pribadi atau tidak publik tidak "
            "muncul dan tidak dihitung nol."),
    }
