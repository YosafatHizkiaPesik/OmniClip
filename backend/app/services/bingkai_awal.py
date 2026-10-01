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

# Batas jumlah klip yang dipanaskan.
#
# Dulu 20, dengan alasan "lebih dari ini jarang dibuka orang dalam satu sesi".
# Alasan itu sudah tidak berlaku sejak biayanya turun: klip gameplay 9,1 detik
# dan klip podcast memakai jejak wajah yang toh dibutuhkan penambatan suara.
# Yang tersisa dari alasan lama hanyalah kerugiannya — klip ke-21 dan
# seterusnya membuat orangnya menunggu lagi, satu per satu, persis keadaan
# yang fitur ini ada untuk menghilangkannya.
#
# 60 dipilih karena di atas itu videonya bukan lagi satu sesi penyuntingan, dan
# pekerjaan ini berjalan dengan prioritas paling rendah: ia mengalah pada apa
# pun yang ditunggu orang di depan layar, jadi batas yang longgar tidak
# memperlambat apa pun yang dilihat.
MAKS_KLIP = 60


def run_bingkai_awal(ctx) -> dict:
    """payload: {video_id, klip: [{segments, subtitles}], aspect_ratio}"""
    from . import reframe
    with reframe.di_latar():
        return _jalankan(ctx)


def _jalankan(ctx) -> dict:
    """
    Isi sebenarnya, dipisah supaya seluruhnya berjalan sebagai pekerjaan latar.

    Tidak ada yang menunggu pekerjaan ini di depan layar, jadi di dalam
    `di_latar()` ia memakai separuh utas analisis dan prioritas proses
    terendah. Itu yang membedakan "berjalan di latar" dari "menguasai mesin".
    """
    from ..routers.clips import hitung_reframe
    from .pipeline import pemanasan_bingkai

    video_id = ctx.payload["video_id"]
    daftar = (ctx.payload.get("klip") or [])[:MAKS_KLIP]
    rasio = ctx.payload.get("aspect_ratio") or "9:16"
    # Diminta langsung lewat tombol "Siapkan bingkai video ini sekarang".
    #
    # Sejak sakelarnya bawaannya MATI, pekerjaan ini tidak boleh lagi membaca
    # sakelar itu sebagai izin: yang menekan tombolnya sudah menyatakan maunya
    # untuk video ini, dan tanpa `paksa` pekerjaannya berhenti di klip pertama
    # lalu melaporkan dirinya "dihentikan" tanpa mengerjakan apa pun.
    paksa = bool(ctx.payload.get("paksa"))
    if not daftar:
        ctx.progress(1.0, stage="done", message="Tidak ada klip yang perlu dihitung.")
        return {"siap": 0}

    # Gameplay atau bukan, ditanyakan sekali dari klip pertama — dan hanya
    # untuk memutuskan apakah suara perlu ditambatkan ke wajah.
    #
    # Sampai 26 September 2026 jawaban ini juga dipakai untuk MELEWATI jejak
    # wajah pada seluruh video gameplay, dengan alasan klip gameplay tidak
    # memakainya. Alasan itu salah, dan ini koreksinya: `jenis_klip` — yang
    # Studio panggil untuk SETIAP klip yang dibuka — dihitung dari jejak wajah
    # itu juga. Melewatinya tidak menghemat apa pun, ia hanya memindahkan
    # tunggunya ke depan layar. Terukur sesudah "pemanasan selesai" pada video
    # Minecraft pemiliknya: keempat klip yang dibuka menunggu 9 sampai 27 detik
    # untuk penggolongan yang sama.
    #
    # Sekarang tiap klip digolongkan di sini, dan yang disiapkan adalah persis
    # jejak yang akan diminta klip itu: facecam untuk gaming, jejak gerakan
    # untuk klip tanpa wajah, jejak wajah untuk sisanya.
    gameplay = _jenis_video(video_id, daftar)
    log.info("Video %s %s.", video_id,
             "gameplay" if gameplay else "bukan gameplay")

    # Menambatkan suara ke wajah DIKERJAKAN LEBIH DULU, bukan di akhir.
    #
    # Langkah ini menulis ulang label penutur tiap kalimat, dan label itu masuk
    # ke KUNCI simpanan rencana bingkai. Dikerjakan belakangan, seluruh rencana
    # yang baru saja dihitung memakai label lama, lalu Studio memintanya dengan
    # label baru dan menghitung semuanya lagi. Terukur pada podcast pemiliknya:
    # 3 dari 14 klip kehilangan seluruh hasil pemanasannya, 12-15 detik
    # menunggu untuk masing-masing.
    #
    # Pindah ke depan tidak menambah kerja: pemindaian wajah yang dipakainya
    # tersimpan dan dipakai ulang oleh perhitungan bingkai di bawah.
    tambat = None
    if not gameplay and (paksa or pemanasan_bingkai()):
        try:
            ctx.check_cancelled()
            ctx.progress(0.02, stage="prepare", message="Menambatkan suara ke wajah…")
            from .pipeline import tambatkan_ke_wajah
            # 0,20..0,42 adalah rentang yang dipakai langkah itu sendiri.
            tambat = tambatkan_ke_wajah(video_id, _Ekor(ctx, 0.02, 0.30, 0.20, 0.42))
        except JobCancelled:
            raise
        except Exception as e:
            log.warning("Penambatan suara ke wajah dilewati: %s", str(e)[:160])
        if tambat:
            # Labelnya berubah, jadi daftar klip dibaca ulang. Tanpa ini,
            # giliran penutur yang dipakai di bawah adalah yang lama lagi.
            daftar = _daftar_terbaru(video_id, daftar)

    siap = gagal = tersusun = 0
    berhenti = False
    for i, klip in enumerate(daftar):
        ctx.check_cancelled()
        # Minggir dulu bila ada yang menunggu gerbang CPU.
        #
        # "Prioritas paling rendah" pada antrean hanya memutuskan siapa yang
        # MASUK lebih dulu. Begitu pekerjaan ini masuk, ia memegang gerbang CPU
        # sampai seluruh 60 klipnya selesai, dan analisis video lain menunggu
        # di belakangnya belasan menit. Terlapor pemiliknya 27 September 2026:
        # empat video diklip bersamaan, dua di antaranya berhenti di "menunggu
        # giliran analisis" sementara satu video memanaskan bingkainya.
        #
        # Di sela dua klip tidak ada yang tergantung di memori, jadi ini titik
        # paling murah untuk minggir.
        ctx.mengalah_cpu(lambda: ctx.progress(
            0.32 + 0.62 * (i / len(daftar)), stage="prepare", paksa=True,
            message="Memberi jalan dulu, ada video lain yang sedang dianalisis…"))
        # Sakelarnya dibaca tiap klip, bukan sekali di awal.
        #
        # Pembatalan dari luar sudah menutup jalur biasanya, tapi pekerjaan ini
        # bisa juga sedang ANTRE saat sakelarnya dimatikan lalu baru berjalan
        # sesudahnya. Membaca sakelarnya di sini berarti ia tidak pernah
        # mengerjakan apa pun yang sudah tidak diinginkan, dari jalur mana pun
        # ia sampai ke sini.
        if not (paksa or pemanasan_bingkai()):
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
        ctx.progress(0.32 + 0.62 * (i / len(daftar)), stage="prepare",
                     message=f"Bingkai klip {i + 1} dari {len(daftar)}{sisa}")
        try:
            # Jenis klip ini, dan jejak yang memang akan diminta Studio.
            #
            # Penggolongan didahulukan karena Studio MEMINTANYA untuk setiap
            # klip yang dibuka, dan karena ia sendiri menghitung jejak wajah
            # klip itu — jadi memanggilnya di sini bukan kerja tambahan.
            mode = _mode_klip(video_id, segmen)
            if mode == "gaming":
                _panaskan_facecam(video_id, segmen)
                if _tulis_bingkai(video_id, klip.get("clip_id"), segmen, rasio):
                    tersusun += 1
            elif mode == "motion":
                # Klip tanpa wajah dibingkai dengan MENGIKUTI GERAKAN, dan
                # Studio memintanya sebagai jejak yang berbeda. Sampai
                # 26 September 2026 pemanasan tidak pernah menghitungnya, jadi
                # klip seperti itu tetap membuat orangnya menunggu 5 detik
                # walaupun pemanasan melaporkan dirinya selesai.
                hitung_reframe(video_id=video_id, segments=segmen,
                               aspect_ratio=rasio, turns=turns, subjek="gerak")
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

    if berhenti:
        # Berhenti atas permintaan bukan kegagalan, dan bukan pula "selesai".
        # Yang sudah terhitung tetap tersimpan, jadi menyalakannya lagi
        # melanjutkan dari sini, bukan mengulang dari nol.
        pesan = (f"Dihentikan. Bingkai {siap} dari {len(daftar)} klip sudah siap; "
                 "nyalakan lagi untuk melanjutkan.")
        ctx.progress(1.0, stage="done", message=pesan)
        log.info("Bingkai awal video %s dihentikan: %d siap", video_id, siap)
        return {"siap": siap, "gagal": gagal, "dihentikan": True}

    tema_siap = _tema_untuk_semua(ctx, daftar, video_id)

    pesan = (f"Susunan Main game {siap} klip siap dipakai" if gameplay
             else f"Bingkai {siap} klip siap dipakai")
    if tersusun:
        pesan += f", {tersusun} di antaranya sudah tersusun di lajur Bingkai"
    if tambat:
        pesan += f", {tambat['speaker_count']} penutur ditandai dari wajahnya"
    if gagal:
        pesan += f", {gagal} dihitung nanti saat dibuka"
    if tema_siap:
        pesan += f". Tema subtitle dipilihkan untuk {tema_siap} klip"
    ctx.progress(1.0, stage="done", message=pesan + ".")
    log.info("Bingkai awal video %s: %d siap, %d gagal, %d tema",
             video_id, siap, gagal, tema_siap)
    return {"siap": siap, "gagal": gagal, "tema": tema_siap, "tersusun": tersusun,
            # Sidik daftar klipnya, dibaca `_sudah_dipanaskan` supaya membuka
            # proyek yang sama lagi tidak mengantrekan pekerjaan yang sama.
            "sidik": ctx.payload.get("sidik") or ""}




def _tulis_bingkai(video_id: str, clip_id, segmen: list[dict], rasio: str) -> bool:
    """
    Potongan hasil pemindaian -> kunci bingkai di klip tersimpan.

    Dilaporkan pemiliknya 1 Oktober 2026: "proses sudah selesai namun bingkai
    belum tersusun". Benar, dan sampai sekarang memang begitu: pekerjaan ini
    hanya MENGHANGATKAN simpanan. Yang menyusun lajur Bingkai adalah Studio,
    dan ia baru mengerjakannya saat sebuah klip DIBUKA, satu per satu. Jadi
    pesan "Susunan Main game 12 klip siap dipakai" benar secara teknis dan
    menyesatkan secara arti: dua belas klip itu dipindai, tapi tidak satu pun
    punya bingkai tersusun sampai dibuka.

    Sekarang pekerjaan ini menuliskannya sendiri. Perhitungannya sama persis
    dengan yang dipakai `/clip-facecam`, bukan jalur kedua: letak facecam dari
    simpanan, `susun_layout_gaming` untuk seluruh klip, lalu `_layout_bidikan`
    per bidikan.

    Kunci buatan pengguna tidak pernah ditimpa. Klip yang sudah punya kunci —
    apa pun asalnya — dilewati, aturan yang sama dengan yang dipakai Studio.
    """
    if not clip_id:
        return False
    try:
        from ..repos import analyses as analyses_repo
        from ..routers.clips import _facecam_tersimpan, _layout_bidikan
        from .render import PLAY_RES, susun_layout_gaming

        tersimpan = _facecam_tersimpan(video_id, segmen) or {}
        posisi = tersimpan.get("posisi") or []
        potongan = tersimpan.get("potongan") or []
        # Satu potongan berarti tidak ada yang berganti sepanjang klip; lajur
        # Bingkai yang berisi satu kunci tidak mengatakan apa pun.
        if not posisi or len(potongan) < 2:
            return False

        cached = analyses_repo.latest_for_video(video_id)
        if not cached:
            return False
        hasil = dict(cached["result"])
        klip = list(hasil.get("clips") or [])
        sasaran = next((i for i, c in enumerate(klip)
                        if str(c.get("clip_id")) == str(clip_id)), None)
        if sasaran is None:
            return False
        if [k for k in (klip[sasaran].get("frame_keys") or []) if isinstance(k, dict)]:
            return False

        w = int(tersimpan.get("src_w") or 1920)
        h = int(tersimpan.get("src_h") or 1080)
        out_w, out_h = PLAY_RES.get(rasio, (1080, 1920))
        tata = susun_layout_gaming(posisi, src_w=w, src_h=h, out_w=out_w, out_h=out_h)

        kunci = []
        for n, bagian in enumerate(potongan):
            k = {"id": f"auto-{n}", "t": round(float(bagian.get("t") or 0), 3),
                 "mode": bagian.get("mode") or "gaming", "asal": "otomatis",
                 "alasan": bagian.get("alasan") or ""}
            r = ((bagian.get("layout") or {}).get("reaksi") or [None])[0]
            if k["mode"] == "gaming" and r:
                k["layout"] = _layout_bidikan(tata, r, src_w=w, src_h=h,
                                              out_w=out_w, out_h=out_h)
            kunci.append(k)
        if len(kunci) < 2:
            return False

        klip[sasaran] = {**klip[sasaran], "frame_keys": kunci}
        hasil["clips"] = klip
        analyses_repo.replace_result(cached["id"], hasil)
        return True
    except Exception as e:                                # noqa: BLE001
        # Bingkai yang gagal ditulis bukan alasan menggagalkan pemanasannya;
        # Studio tetap menyusunnya sendiri saat klipnya dibuka.
        log.warning("Bingkai klip %s tidak tersusun: %s", clip_id, str(e)[:160])
        return False

def _jenis_video(video_id: str, daftar: list[dict]) -> bool:
    """Gameplay atau bukan, dari klip pertama yang punya potongan sah."""
    for klip in daftar:
        segmen = [{"start": round(float(x["start"]), 3), "end": round(float(x["end"]), 3)}
                  for x in (klip.get("segments") or [])
                  if float(x["end"]) - float(x["start"]) > 0.2]
        if segmen:
            return _jenis_gameplay(video_id, segmen)
    return False


def _daftar_terbaru(video_id: str, lama: list[dict]) -> list[dict]:
    """
    Daftar klip dengan label penutur yang SUDAH diperbarui penambatan.

    Dicocokkan lewat potongan waktunya, bukan urutannya: penambatan tidak
    menambah atau membuang klip, tapi mengandalkan urutan berarti satu
    perubahan di tempat lain diam-diam menukar subtitle antar klip.
    """
    try:
        from ..repos import analyses as analyses_repo
        cached = analyses_repo.latest_for_video(video_id)
        baru = ((cached or {}).get("result") or {}).get("clips") or []
        if not baru:
            return lama
        def kunci(c):
            return tuple((round(float(s["start"]), 2), round(float(s["end"]), 2))
                         for s in (c.get("segments") or []))
        peta = {kunci(c): c for c in baru}
        hasil = []
        for c in lama:
            cocok = peta.get(kunci(c))
            hasil.append({**c, "subtitles": cocok.get("subtitles") or []} if cocok else c)
        return hasil
    except Exception as e:                           # noqa: BLE001
        log.info("Daftar klip terbaru tidak terbaca: %s", str(e)[:140])
        return lama


def _mode_klip(video_id: str, segmen: list[dict]) -> str:
    """
    Bingkai bawaan klip ini menurut penggolong yang sama dengan yang dipakai
    Studio: "gaming", "motion", atau "smart".

    Hasilnya tersimpan, dan menghitungnya juga memanaskan jejak wajah klip ini
    — jadi memanggilnya di sini bukan kerja tambahan, melainkan kerja yang
    sama yang dikerjakan lebih awal.
    """
    try:
        from .paths import find_local_video
        from .sutradara_ai import jenis_klip_tersimpan

        src = find_local_video(video_id)
        if not src:
            return "smart"
        return (jenis_klip_tersimpan(video_id, src, segmen) or {}).get("mode") or "smart"
    except Exception as e:                           # noqa: BLE001
        log.info("Penggolongan klip dilewati: %s", str(e)[:140])
        return "smart"


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

    Rentang ASALNYA harus disebut, bukan dianggap 0..1. Versi pertama tidak
    menyebutnya: `tambatkan_ke_wajah` melapor 0,20 sampai 0,42 karena di dalam
    auto-klip ia memang berada di situ, dan angka itu diperlakukan seolah 0
    sampai 1. Akibatnya bilah kemajuan hanya merayap dari 7,6% ke 13,8% selama
    SELURUH langkah — dan pada video pemiliknya langkah itu berjalan 22 menit.
    Yang terlihat di layar: "Memindai wajah klip 5 dari 5… 13%", diam di angka
    yang sama menit demi menit. Terlapor: "loading tidak jalan jalan".
    """

    def __init__(self, ctx, mulai: float, akhir: float,
                 dari: float = 0.0, sampai: float = 1.0):
        self._ctx = ctx
        self._a = mulai
        self._b = akhir
        self._dari = dari
        self._lebar = max(1e-6, sampai - dari)

    def check_cancelled(self):
        self._ctx.check_cancelled()

    def progress(self, p, **kw):
        # Dari rentang asalnya ke 0..1 dulu, baru ke rentang tujuan.
        bagian = (float(p or 0.0) - self._dari) / self._lebar
        bagian = max(0.0, min(1.0, bagian))
        self._ctx.progress(self._a + (self._b - self._a) * bagian, **kw)

    def __getattr__(self, nama):
        return getattr(self._ctx, nama)


def _panaskan_facecam(video_id: str, segmen: list[dict]) -> bool:
    """
    Memindai letak facecam satu klip lebih dulu, menyimpannya, dan menjawab
    apakah klip ini punya facecam sama sekali.

    Memakai simpanan yang SAMA dengan yang dibaca `/clip-facecam`, jadi saat
    klipnya dibuka Studio menemukannya sudah jadi. Yang disimpan letak panelnya
    DAN pemecahan klipnya; susunannya sendiri dihitung ulang saat dibaca,
    supaya aturan susunan yang berubah berlaku juga untuk klip yang sudah
    pernah dipanaskan.

    Pemecahan klip (`potongan`) dulu TIDAK ikut disimpan di sini, dan itu
    menyisakan setengah pekerjaan untuk nanti: Studio menemukan simpanan tanpa
    `potongan` lalu menghitungnya sendiri saat klip dibuka, satu per satu.
    Akibatnya pemanasan melaporkan dirinya selesai sementara lajur Bingkai
    masih kosong — dilaporkan pemiliknya 1 Oktober 2026, "proses sudah selesai
    namun bingkai belum tersusun". Pemecahannya memakai pemindaian yang sudah
    ada di tangan, jadi menghitungnya di sini hampir tidak menambah ongkos.

    Kegagalannya ditelan: pemanasan yang gagal bukan alasan menggagalkan
    sisanya, dan klip itu akan memindai sendiri saat dibuka, persis seperti
    sebelumnya.
    """
    try:
        from ..routers.clips import _facecam_tersimpan, _kunci_facecam, _potongan_game
        from ..repos import cache as cache_repo
        from .media import probe
        from .paths import find_local_video
        from .reframe import deteksi_facecam_waktu
        from .render import rasio_bidang_wajah

        src = find_local_video(video_id)
        tersimpan = _facecam_tersimpan(video_id, segmen)
        if tersimpan is not None and "posisi" in tersimpan:
            # Simpanan lama yang belum punya pemecahan klip DILENGKAPI, bukan
            # dipakai apa adanya: kalau tidak, video yang sempat dipanaskan
            # oleh versi sebelumnya selamanya menyisakan pekerjaan itu ke
            # Studio.
            if "potongan" not in tersimpan and src:
                lengkap = dict(tersimpan)
                lengkap["potongan"] = _potongan_game(
                    str(src), segmen, tersimpan.get("posisi") or [])
                cache_repo.simpan(_kunci_facecam(video_id, segmen), lengkap)
            return bool(tersimpan["posisi"])
        if not src:
            return False
        info = probe(str(src))
        w = int(info.get("width") or 1920)
        h = int(info.get("height") or 1080)
        posisi = deteksi_facecam_waktu(str(src), segmen, w, h,
                                       rasio_potongan=rasio_bidang_wajah(1080, 1920))
        cache_repo.simpan(_kunci_facecam(video_id, segmen),
                          {"posisi": posisi or [], "src_w": w, "src_h": h,
                           "potongan": _potongan_game(str(src), segmen, posisi)})
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
