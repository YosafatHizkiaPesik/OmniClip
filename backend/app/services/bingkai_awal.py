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
    from .pipeline import pemanasan_bingkai

    video_id = ctx.payload["video_id"]
    daftar = (ctx.payload.get("klip") or [])[:MAKS_KLIP]
    rasio = ctx.payload.get("aspect_ratio") or "9:16"
    if not daftar:
        ctx.progress(1.0, stage="done", message="Tidak ada klip yang perlu dihitung.")
        return {"siap": 0}

    # Video gameplay atau bukan, ditanyakan SEKALI.
    #
    # Klip gameplay tidak memakai jejak wajah sama sekali: susunannya datang
    # dari letak panel facecam. Sampai 26 September 2026 pemanasan tetap
    # menghitung jejak wajah untuk tiap klip video seperti itu. Terukur pada
    # video horor 2560x1440 milik pemiliknya: 18,3 detik jejak wajah yang
    # tidak dipakai, ditambah 11,7 detik pindai facecam yang dipakai — 30
    # detik per klip, 10 menit untuk 20 klip, 6 menit di antaranya sia-sia.
    #
    # Letak panel facecam tidak berpindah sepanjang video, jadi satu klip
    # sudah cukup untuk menjawab pertanyaannya.
    # Gameplay atau bukan, dijawab oleh KLIP PERTAMA — bukan oleh pemeriksaan
    # tersendiri, dan tidak oleh pemindai panel facecam sendirian.
    #
    # Pemindai panel itu terlalu mudah setuju: pada satu klip podcast pemiliknya
    # ia mengembalikan "panel" 32% x 49% di tengah bingkai dengan kehadiran
    # 100% — wajah orang yang sedang bicara, bukan kamera pojok. Memakai itu
    # sebagai jawaban berarti podcast diperlakukan sebagai video game.
    #
    # `jenis_klip` adalah penggolong yang memang dibuat untuk pertanyaan ini,
    # dan Studio memakainya juga untuk memilih bingkai bawaan tiap klip. Memakai
    # sumber yang sama berarti pemanasan menyiapkan persis apa yang nanti
    # diminta Studio, bukan tebakannya sendiri.
    gameplay = None

    siap = gagal = 0
    berhenti = False
    for i, klip in enumerate(daftar):
        ctx.check_cancelled()
        # Sakelarnya dibaca tiap klip, bukan sekali di awal.
        #
        # Pembatalan dari luar sudah menutup jalur biasanya, tapi pekerjaan ini
        # bisa juga sedang ANTRE saat sakelarnya dimatikan lalu baru berjalan
        # sesudahnya. Membaca sakelarnya di sini berarti ia tidak pernah
        # mengerjakan apa pun yang sudah tidak diinginkan, dari jalur mana pun
        # ia sampai ke sini.
        if not pemanasan_bingkai():
            berhenti = True
            log.info("Penyiapan bingkai %s dihentikan: sakelarnya dimatikan.", video_id)
            break
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
        # Nomor, jumlah, dan judulnya. "Sedang memproses" tanpa nomor tidak
        # bisa dibedakan dari macet, dan justru pekerjaan inilah yang paling
        # lama tanpa ada yang menunggunya di layar mana pun.
        judul = (klip.get("title") or "").strip()
        sisa = f" · {judul[:44]}" if judul else ""
        ctx.progress(0.02 + 0.92 * (i / len(daftar)), stage="prepare",
                     message=f"Bingkai klip {i + 1} dari {len(daftar)}{sisa}")
        try:
            if gameplay is None:
                # Klip pertama menjawabnya. `jenis_klip` sendiri menghitung
                # jejak wajah dan menyimpannya, jadi untuk video biasa
                # pertanyaan ini tidak menambah kerja apa pun: jejak yang
                # dipakainya itulah yang memang dibutuhkan klip pertama.
                gameplay = _jenis_gameplay(video_id, segmen)
                if gameplay:
                    _panaskan_facecam(video_id, segmen)
                else:
                    hitung_reframe(video_id=video_id, segments=segmen,
                                   aspect_ratio=rasio, turns=turns)
                log.info("Video %s %s.", video_id,
                         "gameplay: jejak wajah dilewati" if gameplay
                         else "bukan gameplay: jejak wajah dipakai")
            elif gameplay:
                # Yang dipakai klip gameplay hanya ini.
                _panaskan_facecam(video_id, segmen)
            else:
                hitung_reframe(video_id=video_id, segments=segmen,
                               aspect_ratio=rasio, turns=turns)
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
    if berhenti:
        # Berhenti atas permintaan bukan kegagalan, dan bukan pula "selesai".
        # Yang sudah terhitung tetap tersimpan, jadi menyalakannya lagi
        # melanjutkan dari sini, bukan mengulang dari nol.
        pesan = (f"Dihentikan. Bingkai {siap} dari {len(daftar)} klip sudah siap; "
                 "nyalakan lagi untuk melanjutkan.")
        ctx.progress(1.0, stage="done", message=pesan)
        log.info("Bingkai awal video %s dihentikan: %d siap", video_id, siap)
        return {"siap": siap, "gagal": gagal, "dihentikan": True}

    # Menambatkan suara ke wajah menuntut jejak wajah yang pada video gameplay
    # sengaja tidak dihitung, dan di sana penuturnya memang satu orang.
    tambat = None
    try:
        ctx.check_cancelled()
        if not gameplay:
            # Angka yang SAMA dengan awal rentang pemetanya di bawah. Beda
            # sedikit pun membuat bilahnya mundur satu persen, dan bilah yang
            # mundur adalah hal yang sedang kita hilangkan.
            ctx.progress(0.94, stage="prepare", message="Menambatkan suara ke wajah…")
        if not gameplay:
            from .pipeline import tambatkan_ke_wajah
            # Lewat pemeta: langkah ini melapor 0,20-0,42 karena di dalam
            # auto-klip ia memang berada di situ. Diteruskan apa adanya, bilah
            # kemajuan MELOMPAT MUNDUR dari 96% ke 20% di akhir pekerjaan —
            # terukur pada satu video podcast — dan bilah yang mundur terbaca
            # persis seperti macet, yang justru sedang kita hilangkan.
            tambat = tambatkan_ke_wajah(video_id, _Ekor(ctx, 0.94, 0.99))
    except JobCancelled:
        raise
    except Exception as e:
        log.warning("Penambatan suara ke wajah dilewati: %s", str(e)[:160])

    tema_siap = _tema_untuk_semua(ctx, daftar, video_id)

    pesan = (f"Susunan Main game {siap} klip siap dipakai" if gameplay
             else f"Bingkai {siap} klip siap dipakai")
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


def _jenis_gameplay(video_id: str, segmen: list[dict]) -> bool:
    """
    Apakah klip ini digolongkan "Main game" oleh penggolong yang sama dengan
    yang dipakai Studio.

    Gagal berarti "bukan" — jalur lama, yang bekerja untuk video apa pun.
    """
    try:
        from .paths import find_local_video
        from .sutradara_ai import jenis_klip_tersimpan

        src = find_local_video(video_id)
        if not src:
            return False
        return (jenis_klip_tersimpan(video_id, src, segmen) or {}).get("mode") == "gaming"
    except Exception as e:                           # noqa: BLE001
        log.info("Penggolongan jenis klip dilewati: %s", str(e)[:140])
        return False


class _Ekor:
    """
    Meneruskan kemajuan sebuah langkah ke SEPOTONG rentang milik pekerjaan ini.

    Langkah yang dipakai bersama beberapa pekerjaan melaporkan kemajuan dalam
    rentangnya sendiri. Yang benar bukan mengubah langkah itu — ia juga dipakai
    di tempat lain dengan rentang yang berbeda — melainkan memetakan angkanya
    di tempat ia dipinjam.
    """

    def __init__(self, ctx, mulai: float, akhir: float):
        self._ctx = ctx
        self._a = mulai
        self._b = akhir

    def check_cancelled(self):
        self._ctx.check_cancelled()

    def progress(self, p, **kw):
        p = max(0.0, min(1.0, float(p or 0.0)))
        self._ctx.progress(self._a + (self._b - self._a) * p, **kw)

    def __getattr__(self, nama):
        return getattr(self._ctx, nama)


def _panaskan_facecam(video_id: str, segmen: list[dict]) -> bool:
    """
    Memindai letak facecam satu klip lebih dulu, menyimpannya, dan menjawab
    apakah klip ini punya facecam sama sekali.

    Memakai simpanan yang SAMA dengan yang dibaca `/clip-facecam`, jadi saat
    klipnya dibuka Studio menemukannya sudah jadi. Yang disimpan hanya letak
    panelnya; susunannya dihitung ulang saat dibaca, supaya aturan susunan yang
    berubah berlaku juga untuk klip yang sudah pernah dipanaskan.

    Kegagalannya ditelan: pemanasan yang gagal bukan alasan menggagalkan
    sisanya, dan klip itu akan memindai sendiri saat dibuka, persis seperti
    sebelumnya.
    """
    try:
        from ..routers.clips import _facecam_tersimpan, _kunci_facecam
        from ..repos import cache as cache_repo
        from .media import probe
        from .paths import find_local_video
        from .reframe import deteksi_facecam_waktu
        from .render import rasio_bidang_wajah

        tersimpan = _facecam_tersimpan(video_id, segmen)
        if tersimpan is not None and "posisi" in tersimpan:
            return bool(tersimpan["posisi"])
        src = find_local_video(video_id)
        if not src:
            return False
        info = probe(str(src))
        w = int(info.get("width") or 1920)
        h = int(info.get("height") or 1080)
        posisi = deteksi_facecam_waktu(str(src), segmen, w, h,
                                       rasio_potongan=rasio_bidang_wajah(1080, 1920))
        cache_repo.simpan(_kunci_facecam(video_id, segmen),
                          {"posisi": posisi or [], "src_w": w, "src_h": h})
        return bool(posisi)
    except Exception as e:                           # noqa: BLE001
        log.info("Pemanasan facecam dilewati: %s", str(e)[:140])
        return False


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
