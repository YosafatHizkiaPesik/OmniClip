"""
Mengantrekan unggahan — dari tombol Unggah, atau sendiri sesudah render.

Unggah otomatis dijalankan SERVER begitu job render selesai, bukan oleh
halaman Studio: render bisa memakan menit, dan pemiliknya boleh menutup
browser atau pindah halaman sementara itu. Tujuan, privasi, dan templat
deskripsinya milik profil (services/profil.py), karena tiap profil adalah
kanal dengan kebiasaannya sendiri.
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("omniclip.unggah")


def antrekan(*, clip_name: str, target: str, title: str = "", description: str = "",
             tags: Optional[list[str]] = None, privacy: str = "private",
             folder_id: str = "", profil_id: Optional[int] = None,
             mulai_setelah: float = 0.0) -> tuple[str, bool]:
    from ..repos import uploads as uploads_repo
    from . import profil
    from .jobs import queue

    pid = profil_id or profil.kini()
    # Baris riwayat dibuat LEBIH DULU supaya id-nya sudah ada di dalam muatan
    # saat pekerja mengambilnya.
    upload_id = uploads_repo.create(clip_name=clip_name, target=target, title=title,
                                    privacy=privacy, job_id="", profil_id=pid)
    job_id, created = queue.enqueue(
        "upload",
        {"clip_name": clip_name, "target": target, "title": title,
         "description": description, "tags": tags or [], "privacy": privacy,
         "folder_id": folder_id, "upload_id": upload_id, "profil_id": pid},
        # Satu klip tidak boleh naik dua kali ke tujuan yang sama.
        dedupe_key=f"upload:{pid}:{target}:{clip_name}",
        mulai_setelah=mulai_setelah,
    )
    if created:
        uploads_repo.attach_job(upload_id, job_id)
    else:
        uploads_repo.drop(upload_id)
    return job_id, created


def deskripsi(templat: str, *, judul: str, hashtag: list[str]) -> str:
    tagar = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtag if h.strip())
    teks = (templat or "{judul}\n\n{hashtag}").replace("{judul}", judul).replace("{hashtag}", tagar)
    return teks.strip()[:5000]


def setelah_render(*, clip_name: str, judul: str, hashtag: list[str],
                   minta: Optional[dict] = None) -> list[dict]:
    """
    Unggahan yang diantrekan sesudah render selesai, sesuai setelan profil.

    `minta` (dari Studio) boleh menimpa setelan profil untuk render ini saja:
    {"youtube": bool, "drive": bool, "privasi": str}. Tanpa `minta`, yang
    berlaku hanya bila profilnya menyalakan unggah otomatis.
    """
    from . import google_upload, profil

    pid = profil.kini()
    setel = profil.unggah(pid)
    if minta is None and not setel.get("otomatis"):
        return []
    pilihan = {**setel, **(minta or {})}
    tagar = list(dict.fromkeys([*(setel.get("hashtag") or []), *(hashtag or [])]))
    hasil = []
    google_siap = google_upload.status(pid)["connected"]
    for target in ("youtube", "drive"):
        if not pilihan.get(target):
            continue
        if not google_siap:
            hasil.append({"target": target,
                          "galat": "Akun Google profil ini belum tersambung."})
            continue
        jam = _jam_tayang(target, pid, float(pilihan.get("jadwal_jam") or 0))
        tagar_kirim = (_pastikan_shorts(tagar, clip_name)
                       if target == "youtube" else tagar)
        job_id, _ = antrekan(
            clip_name=clip_name, target=target, title=judul,
            description=deskripsi(setel.get("deskripsi", ""), judul=judul,
                                  hashtag=tagar_kirim),
            tags=[h.lstrip("#") for h in tagar_kirim][:15],
            privacy=pilihan.get("privasi") or "private", profil_id=pid,
            mulai_setelah=jam)
        hasil.append({"target": target, "job_id": job_id, "mulai_setelah": jam})
    return hasil


# Ambang Shorts milik YouTube: tegak, dan paling lama tiga menit.
SHORTS_DETIK_MAKS = 180.0


def _pastikan_shorts(tagar: list[str], clip_name: str) -> list[str]:
    """
    Menambahkan #Shorts bila klipnya memang memenuhi syarat Shorts.

    YouTube menentukan sendiri sebuah unggahan masuk rak Shorts atau tidak,
    dari bentuk dan panjangnya, dan tagar ini adalah penanda yang membantunya
    memutuskan lebih cepat dan lebih pasti. Terlapor 25 September 2026: klip
    tegak 51 detik naik sebagai video biasa, bukan Shorts.

    Syaratnya diperiksa dari catatan render klipnya sendiri, bukan ditebak:
    klip 4:5 atau 16:9, dan klip yang lebih panjang dari tiga menit, memang
    BUKAN Shorts, dan menempelkan tagarnya di sana cuma bohong pada
    penontonnya.
    """
    if any(t.lower().lstrip("#") == "shorts" for t in tagar):
        return tagar
    try:
        import json
        from . import profil as profil_svc
        from .paths import safe_media_path

        jalur = safe_media_path(profil_svc.kategori_klip(profil_svc.kini()), clip_name)
        meta = json.loads(jalur.with_suffix(".json").read_text(encoding="utf-8"))
        rasio = str(meta.get("aspect_ratio") or "9:16")
        durasi = float(meta.get("duration") or 0)
        lebar, tinggi = (rasio.split(":") + ["1"])[:2]
        tegak = float(lebar) < float(tinggi)
        if tegak and 0 < durasi <= SHORTS_DETIK_MAKS:
            return [*tagar, "#Shorts"]
    except Exception as e:                           # noqa: BLE001
        log.info("Syarat Shorts tidak terbaca untuk %s: %s", clip_name, str(e)[:120])
    return tagar


def _jam_tayang(target: str, pid: int, jarak_jam: float) -> float:
    """
    Kapan unggahan ini boleh mulai.

    Nol berarti sekarang. Dengan jarak yang disetel profil, tiap klip berikutnya
    dijadwalkan sekian jam sesudah yang terakhir diantrekan — bukan sesudah
    yang terakhir SELESAI, karena yang terakhir mungkin belum jalan sama
    sekali. Sepuluh klip yang selesai dirender bersamaan karena itu naik
    berjarak, bukan berombongan: kanal baru yang menerbitkan sepuluh video
    dalam sepuluh menit adalah kanal yang minta ditandai.
    """
    if jarak_jam <= 0:
        return 0.0
    import time

    from ..repos import jobs as jobs_repo
    sebelumnya = jobs_repo.jadwal_terakhir("upload", pid)
    dasar = max(sebelumnya, time.time())
    return round(dasar + jarak_jam * 3600, 3)
