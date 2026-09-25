"""
Menghitung jejak wajah untuk SEMUA klip sebuah video, sebelum ada yang membuka.

Ada karena keluhan yang tepat: "ada beberapa yang langsung mengikuti wajah dan
ada beberapa yang perlu menunggu lagi padahal pemrosesan sudah selesai."

Sebabnya bukan analisis yang belum selesai. Jejak wajah tidak pernah ikut
dihitung di sana; ia dihitung saat sebuah klip DIBUKA, beberapa detik per klip,
dan hasilnya dulu hanya tinggal di memori. Jadi klip yang kebetulan sudah
pernah dibuka terasa langsung jadi, dan sisanya menunggu lagi dari nol, setiap
kali aplikasinya dijalankan ulang.

Pekerjaan ini menghitungnya lebih awal, berurutan, di lajur cpu dengan
prioritas paling rendah: tidak ada yang sedang menunggunya, jadi ia mengalah
pada apa pun yang ditunggu orang di depan layar. Hasilnya masuk ke simpanan
yang sama dengan yang dibaca editor, jadi tidak ada jalur kedua yang bisa
berbeda diam-diam.
"""

from __future__ import annotations

import logging

from ..errors import JobCancelled

log = logging.getLogger("omniclip.bingkai")

# Lebih banyak dari ini jarang dibuka orang dalam satu sesi, dan tiap klip
# memakan beberapa detik cpu yang tidak ditunggu siapa pun.
MAKS_KLIP = 20


def run_bingkai_awal(ctx) -> dict:
    """payload: {video_id, klip: [{segments, subtitles}], aspect_ratio}"""
    from ..routers.clips import hitung_reframe

    video_id = ctx.payload["video_id"]
    daftar = (ctx.payload.get("klip") or [])[:MAKS_KLIP]
    rasio = ctx.payload.get("aspect_ratio") or "9:16"
    if not daftar:
        ctx.progress(1.0, stage="done", message="Tidak ada klip yang perlu dihitung.")
        return {"siap": 0}

    siap = gagal = 0
    for i, klip in enumerate(daftar):
        ctx.check_cancelled()
        segmen = [{"start": round(float(s["start"]), 3), "end": round(float(s["end"]), 3)}
                  for s in (klip.get("segments") or [])
                  if float(s["end"]) - float(s["start"]) > 0.2]
        if not segmen:
            continue
        turns = tuple(
            (float(l["start"]), float(l["end"]), int(l["speaker"]))
            for l in (klip.get("subtitles") or [])
            if l.get("speaker") is not None and l.get("end") is not None
        )
        ctx.progress(i / len(daftar), stage="prepare",
                     message=f"Menyiapkan bingkai klip {i + 1} dari {len(daftar)}…")
        try:
            hitung_reframe(video_id=video_id, segments=segmen,
                           aspect_ratio=rasio, turns=turns)
            # Video gameplay TIDAK memakai jejak wajah di atas: Studio
            # memintanya lewat `/clip-facecam`, dan sampai 25 September 2026
            # pemanasan tidak menyentuhnya sama sekali. Jadi pada video game
            # pemanasan menghitung hal yang tidak pernah dipakai, sementara
            # yang benar-benar dibutuhkan tetap dihitung satu per satu saat
            # klipnya dibuka. Terlapor: "sudah menunggu beberapa menit, satu
            # klip pun bingkainya belum tersusun".
            _panaskan_facecam(video_id, segmen)
            siap += 1
        except JobCancelled:
            raise
        except Exception as e:
            # Satu klip yang gagal bukan alasan membatalkan sisanya; editor
            # akan menghitungnya sendiri saat klip itu dibuka.
            gagal += 1
            log.warning("Bingkai awal klip %d gagal: %s", i + 1, str(e)[:160])

    # Warna penutur, dari WAJAH. Dikerjakan di sini karena pelacakan wajahnya
    # memang sudah selesai di atas; di dalam auto-klip ia akan menambah
    # menit-menit pada pekerjaan yang ditunggu orang di depan layar.
    tambat = None
    try:
        ctx.check_cancelled()
        ctx.progress(0.96, stage="prepare", message="Menambatkan suara ke wajah…")
        from .pipeline import tambatkan_ke_wajah
        tambat = tambatkan_ke_wajah(video_id, ctx)
    except JobCancelled:
        raise
    except Exception as e:
        log.warning("Penambatan suara ke wajah dilewati: %s", str(e)[:160])

    tema_siap = _tema_untuk_semua(ctx, daftar, video_id)

    pesan = f"Bingkai {siap} klip siap dipakai"
    if tambat:
        pesan += f", {tambat['speaker_count']} penutur ditandai dari wajahnya"
    if gagal:
        pesan += f", {gagal} dihitung nanti saat dibuka"
    if tema_siap:
        pesan += f". Tema subtitle dipilihkan untuk {tema_siap} klip"
    ctx.progress(1.0, stage="done", message=pesan + ".")
    log.info("Bingkai awal video %s: %d siap, %d gagal, %d tema",
             video_id, siap, gagal, tema_siap)
    return {"siap": siap, "gagal": gagal, "tema": tema_siap}


def _panaskan_facecam(video_id: str, segmen: list[dict]) -> None:
    """
    Menghitung susunan Main game untuk satu klip, lalu menyimpannya.

    Memakai simpanan yang SAMA dengan yang dibaca `/clip-facecam`, jadi saat
    klipnya dibuka Studio menemukannya sudah jadi. Kegagalannya ditelan:
    pemanasan yang gagal bukan alasan menggagalkan sisanya, dan klip itu akan
    menghitung sendiri saat dibuka, persis seperti sebelumnya.
    """
    try:
        from ..routers.clips import _facecam_tersimpan, _kunci_facecam
        from ..repos import cache as cache_repo
        from .media import probe
        from .paths import find_local_video
        from .reframe import deteksi_facecam_waktu
        from .render import rasio_bidang_wajah, susun_layout_gaming

        if _facecam_tersimpan(video_id, segmen) is not None:
            return
        src = find_local_video(video_id)
        if not src:
            return
        info = probe(str(src))
        w = int(info.get("width") or 1920)
        h = int(info.get("height") or 1080)
        posisi = deteksi_facecam_waktu(str(src), segmen, w, h,
                                       rasio_potongan=rasio_bidang_wajah(1080, 1920))
        hasil = ({"ditemukan": False, "layout": None} if not posisi else
                 {"ditemukan": True, "facecam": posisi[0]["facecam"],
                  "src_w": w, "src_h": h,
                  "layout": susun_layout_gaming(posisi, src_w=w, src_h=h)})
        cache_repo.simpan(_kunci_facecam(video_id, segmen), hasil)
    except Exception as e:                           # noqa: BLE001
        log.info("Pemanasan facecam dilewati: %s", str(e)[:140])


def _tema_untuk_semua(ctx, daftar: list[dict], video_id: str) -> int:
    """
    Memilihkan tema subtitle untuk semua klip, dalam SATU panggilan model.

    Tidak menerapkan apa pun. Hasilnya masuk ke simpanan yang sama dengan yang
    dibaca tombol "Pilihkan tema untuk klip ini", jadi saat pemiliknya menekan
    tombol itu jawabannya sudah ada dan datang seketika. Menerapkannya sendiri
    akan mengganti gaya yang mungkin sudah disetel tangan, dan tema adalah
    keputusan rasa: yang pantas dikerjakan diam-diam adalah menyiapkan
    jawabannya, bukan memaksakannya.

    Satu panggilan, bukan satu per klip. Jatah harian Gemini gratis 20
    permintaan per model per project, dan satu video menghasilkan belasan klip:
    versi pertama pekerjaan ini akan menghabiskan hampir seluruh jatah hari itu
    hanya untuk menyiapkan tema.
    """
    from ..config import get_api_key, get_model_override
    from ..repos import cache as cache_repo
    from ..routers.clips import kunci_tema
    from .peringkat_model import rantai
    from . import tema as tema_svc

    kunci_ai = get_api_key() or ""
    models = rantai(kunci_ai, get_model_override() or None) if kunci_ai else []

    perlu, kunci_per_klip, siap = [], [], 0
    for klip in daftar:
        meta = {"title": klip.get("title") or "", "jenis": klip.get("jenis") or "",
                "duration": klip.get("duration") or 0.0,
                "subtitles": klip.get("subtitles") or []}
        if not meta["subtitles"]:
            continue
        kunci = kunci_tema(video_id, meta)
        try:
            if cache_repo.ambil(kunci, ttl=float("inf")) is not None:
                siap += 1
                continue
        except Exception:
            pass
        perlu.append(meta)
        kunci_per_klip.append(kunci)

    if not perlu:
        return siap

    ctx.check_cancelled()
    ctx.progress(0.98, stage="prepare",
                 message=f"Memilihkan tema subtitle untuk {len(perlu)} klip…")
    try:
        hasil = tema_svc.pilih_banyak(perlu, api_key=kunci_ai, models=models,
                                      batal=ctx.check_cancelled)
    except JobCancelled:
        raise
    except Exception as e:
        log.warning("Tema tidak bisa disiapkan: %s", str(e)[:160])
        return siap

    for kunci, h in zip(kunci_per_klip, hasil):
        try:
            cache_repo.simpan(kunci, h)
            siap += 1
        except Exception:
            pass
    return siap
