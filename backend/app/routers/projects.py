"""
Project klip: daftar video yang sedang atau sudah diproses, plus data timeline.

Halaman Studio menampilkan ini sebagai kartu. Pengguna bisa menekan "Clip" pada
beberapa video berturut-turut lalu kembali menonton; pekerjaannya berjalan di
antrean, dan kartunya menunjukkan kemajuan masing-masing.
"""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Query

from ..errors import AppError, NotFound
from ..repos import analyses as analyses_repo
from ..repos import jobs as jobs_repo
from ..repos import projects as projects_repo
from ..services.jobs import queue
from ..services.paths import extract_youtube_id, find_local_video, url_sumber

log = logging.getLogger("omniclip.projects")

router = APIRouter(prefix="/api", tags=["projects"])


def _resolve(video_id: str) -> str:
    vid = extract_youtube_id(video_id) or (video_id if len(video_id) == 11 else "")
    if not vid:
        raise NotFound("Video tidak dikenali.")
    return vid


def _pratinjau(local, vid: str = "") -> dict:
    if local is None:
        return {"preview_url": None, "pratinjau_disiapkan": False}
    from ..services import proksi
    try:
        if not proksi.butuh_salinan(local):
            return {"preview_url": url_sumber(vid, local), "pratinjau_disiapkan": False}
        salinan = proksi.untuk_pratinjau(local)
    except Exception:
        salinan = None
    if salinan is not None:
        return {"preview_url": f"/api/media/proksi/{salinan.name}", "pratinjau_disiapkan": False}
    # Kemajuannya ikut, supaya yang menunggu tahu ia bergerak. Pada video dua
    # jam salinan ini memakan puluhan menit sampai berjam-jam, dan lingkaran
    # berputar tanpa angka tidak bisa dibedakan dari macet.
    return {"preview_url": url_sumber(vid, local), "pratinjau_disiapkan": True,
            "pratinjau_kemajuan": proksi.kemajuan(local)}


@router.get("/projects")
async def list_projects(limit: int = Query(60, le=200)):
    from ..services import profil
    return await asyncio.to_thread(projects_repo.list_projects, limit, profil.kini())


@router.get("/projects/{video_id}")
async def get_project(video_id: str):
    """Semua yang dibutuhkan halaman editor dalam satu permintaan."""
    vid = _resolve(video_id)
    cached = await asyncio.to_thread(analyses_repo.latest_for_video, vid)
    if not cached:
        raise NotFound("Belum ada analisis untuk video ini.")

    result = cached["result"]

    # Penanda non-ucapan ("[Musik]", "[Tertawa]") dibersihkan saat dibaca, bukan
    # hanya saat analisis baru dibuat, supaya project yang sudah tersimpan ikut
    # membaik tanpa perlu dianalisis ulang.
    from ..repos import transcripts as tx_repo
    from ..services.clipmodel import (rebuild_subtitles_for_segments,
                                      repair_caption_timing,
                                      sanitize_caption_lines, suggest_title)

    # Transkrip dipakai untuk membangun ulang baris yang memang rusak sejak
    # dibuat. Dibaca sekali, bukan per klip.
    tersimpan = tx_repo.get_best(vid)
    kata_video = tersimpan["words"] if tersimpan else []

    def _kalimat_utuh(lines: list[dict]) -> bool:
        """
        Apakah baris ini lahir dari cue takarir, bukan dari kata?

        Tandanya satu dan tidak ambigu: sebuah "kata" yang berisi spasi. Itu
        hanya mungkin terjadi pada takarir resmi kanal, yang berwaktu per-cue —
        dan baris yang lahir darinya memuat kalimat enam puluh karakter dalam
        satu setengah detik, yang tidak bisa dibaca siapa pun.
        """
        return any(" " in (w.get("w") or "")
                   for l in lines for w in (l.get("words") or []))

    def _lengkapi(c: dict) -> dict:
        lines = sanitize_caption_lines(c.get("subtitles") or [])
        # Dibangun ulang HANYA bila barisnya memang cue, bukan kata.
        #
        # Ini membuang suntingan tangan pada klip itu, jadi syaratnya sengaja
        # sempit: yang dibangun ulang cuma yang sejak awal tidak pernah bisa
        # dibaca. Transkripnya sendiri sudah dipecah jadi kata di lapisan
        # penyimpanan, jadi hasil bangunan ulangnya memakai waktu per kata.
        if kata_video and c.get("segments") and _kalimat_utuh(lines):
            try:
                baru, _ = rebuild_subtitles_for_segments(c["segments"], kata_video)
                if baru:
                    lines = sanitize_caption_lines(baru)
            except Exception:      # membangun ulang tidak boleh menjatuhkan proyek
                pass
        # Waktu tampil dibetulkan JUGA untuk klip yang sudah tersimpan.
        #
        # Tanpa ini, perbaikan hanya berlaku untuk analisis baru: proyek yang
        # sudah ada tetap memakai baris berkedip 0,3 detik selamanya, dan
        # satu-satunya cara memperbaikinya adalah menganalisis ulang seluruh
        # video. Keduanya hanya MEMANJANGKAN ke dalam jeda yang memang kosong
        # dan tidak pernah melewati baris berikutnya, jadi menjalankannya
        # berulang kali pada data yang sama tidak menggeser apa pun lagi.
        lines = repair_caption_timing(lines)
        out = {**c, "subtitles": lines}
        # Judul diisikan bila belum ada.
        #
        # Analisis yang tersimpan sebelum fitur judul ada tidak punya judul sama
        # sekali, dan Gemini pun kadang mengembalikan klip tanpa judul. Dulu itu
        # hanya berarti nama berkas yang kurang enak; sejak ada kartu judul di
        # awal klip, judul kosong berarti kartu kosong. Yang diisikan bukan
        # karangan — ia kalimat dari klip itu sendiri, sama seperti yang dipakai
        # analisis baru.
        if not (out.get("title") or "").strip():
            teks = " ".join((l.get("text") or "") for l in lines)
            judul = suggest_title(teks)
            if judul:
                out["title"] = judul
        return out

    result = {**result, "clips": [_lengkapi(c) for c in (result.get("clips") or [])]}

    local = find_local_video(vid)
    return {
        "video_id": vid,
        "analysis_id": cached["id"],
        "created_at": cached["created_at"],
        **result,
        # local_url dihitung ulang di sini, bukan dibaca dari hasil tersimpan:
        # berkasnya bisa saja sudah dihapus sejak analisis dibuat. Dan ia
        # ditaruh SESUDAH `**result` — sebelumnya di depannya, sehingga
        # `local_url` lama dari hasil tersimpan menimpanya, dan Studio
        # memutar berkas yang tidak ada: layar hitam tanpa keterangan apa pun.
        "local_url": url_sumber(vid, local) if local else None,
        "downloaded": local is not None,
        # Yang diputar Studio: salinan ringan untuk sumber besar (4K VP9
        # macet di Firefox), sumbernya sendiri untuk yang kecil. Render selalu
        # memakai sumber asli.
        **_pratinjau(local, vid),
    }


@router.delete("/projects/{video_id}")
async def delete_project(video_id: str, hapus_video: bool = False):
    """
    Hapus satu kartu Partitur sampai benar-benar hilang.

    `hapus_video` ikut membuang berkas video mentahnya. Bawaannya TIDAK:
    unduhan itu 900 MB rata-rata dan sampai 4 GB, dan mengunduhnya lagi
    memakan menit-menit — membuangnya diam-diam bersama kartu adalah kerugian
    yang tidak diminta. Tapi membiarkannya selamanya juga salah: terukur pada
    penyimpanan pemiliknya, 42 video sumber menumpuk sampai 37,9 GB. Karena
    itu pilihannya diberikan, bukan diputuskan.

    Kartunya disusun dari dua sumber — `analyses` dan `jobs` — jadi membuang
    analisisnya saja tidak cukup: baris job yang tertinggal membangun kembali
    kartu yang sama pada pemuatan berikutnya, berlabel "Gagal". Itu juga alasan
    kartu yang MEMANG gagal dulu tidak bisa dihapus sama sekali; kartu seperti
    itu tidak punya analisis, hanya job.

    Job yang masih berjalan dibatalkan lebih dulu, supaya pekerjaannya berhenti
    alih-alih terus memakai CPU untuk sesuatu yang barisnya sudah tidak ada.
    """
    vid = _resolve(video_id)

    # Kartu yang juga dipakai profil lain hanya dilepas dari profil ini:
    # analisisnya milik bersama, dan menghapusnya akan mengosongkan Partitur
    # profil yang tidak pernah meminta penghapusan itu.
    from ..repos import profil as profil_repo
    from ..services import profil
    await asyncio.to_thread(profil_repo.lepas_video, profil.kini(), vid)
    pemilik_lain = await asyncio.to_thread(
        lambda: [p["id"] for p in profil_repo.semua() if vid in profil_repo.video_milik(p["id"])])
    if pemilik_lain:
        return {"success": True, "video_id": vid, "jobs_dihapus": 0, "hanya_dilepas": True}

    for job_id in await asyncio.to_thread(jobs_repo.ids_for_video, vid, only_active=True):
        queue.cancel(job_id)

    await asyncio.to_thread(analyses_repo.delete_for_video, vid)
    jobs_dihapus = await asyncio.to_thread(jobs_repo.delete_for_video, vid)
    # Salinan video impor ikut dibuang — tanpa kartunya ia tidak terlihat di
    # mana pun dan hanya memakan ruang. Berkas asli pengguna tidak disentuh.
    from ..services.paths import buang_salinan_impor
    await asyncio.to_thread(buang_salinan_impor, vid)

    video_dibuang, bita = 0, 0
    if hapus_video:
        video_dibuang, bita = await asyncio.to_thread(_buang_berkas_sumber, vid)
    return {"success": True, "video_id": vid, "jobs_dihapus": jobs_dihapus,
            "video_dihapus": video_dibuang, "bita_dibebaskan": bita}


def _buang_berkas_sumber(vid: str) -> tuple[int, int]:
    """
    Membuang video mentah dan salinan analisisnya. (jumlah berkas, bita).

    Berkas di LUAR folder OmniClip tidak disentuh: video impor menunjuk ke
    berkas milik pengguna sendiri, dan menghapus kartu di aplikasi ini tidak
    boleh berarti menghapus berkas di folder mereka.
    """
    from ..config import DOWNLOAD_DIR
    from ..services.paths import find_local_video
    from ..services.proksi import _nama as nama_proksi

    n = bita = 0
    src = find_local_video(vid)
    if src is None:
        return 0, 0
    calon = [src]
    try:
        calon.append(nama_proksi(src))
    except OSError:
        pass
    for f in calon:
        try:
            if not f.is_file():
                continue
            # Hanya yang memang milik OmniClip.
            f.resolve().relative_to(Path(DOWNLOAD_DIR).resolve().parent)
        except (OSError, ValueError):
            continue
        try:
            ukuran = f.stat().st_size
            f.unlink()
            n += 1
            bita += ukuran
        except OSError as e:
            log.warning("Berkas %s tidak bisa dihapus: %s", f.name, e)
    if n:
        log.info("Video sumber %s dibuang: %d berkas, %.0f MB", vid, n, bita / 1e6)
    return n, bita


# Hitungan gelombang yang sedang berjalan, per (video, bins). Permintaan kedua
# untuk kunci yang sama MENUNGGU hitungan pertama alih-alih memulai sendiri:
# terukur, membuka Studio sekali memicu dua pembacaan berkas 3 GB bersamaan di
# cakram eksternal, dan keduanya jadi dua kali lebih lambat.
_GELOMBANG_JALAN: dict = {}


@router.get("/videos/{video_id}/waveform")
async def waveform(video_id: str, bins: int = Query(1200, ge=100, le=4000)):
    """
    Puncak amplitudo untuk digambar di timeline.

    Dihitung sekali lalu di-cache: satu pass ffmpeg atas podcast 75 menit
    memakan beberapa detik, dan timeline memintanya setiap kali editor dibuka.
    """
    vid = _resolve(video_id)
    cached = await asyncio.to_thread(projects_repo.get_waveform, vid, bins)
    if cached:
        return {"video_id": vid, "bins": len(cached), "peaks": cached, "cached": True}

    source = find_local_video(vid)
    if source is None:
        raise AppError("Video belum diunduh, gelombang suara belum bisa dibuat.",
                       code="SOURCE_NOT_DOWNLOADED", status=409)

    from ..services.media import probe, waveform_peaks

    kunci = (vid, bins)
    jalan = _GELOMBANG_JALAN.get(kunci)
    if jalan is not None:
        return await asyncio.shield(jalan)

    async def hitung() -> dict:
        info = await asyncio.to_thread(probe, source)
        duration = float(info.get("duration") or 0)
        # Audio yang sudah disimpan pipeline jauh lebih kecil daripada videonya.
        from ..services import suara
        asal = suara.tersimpan(source) or source
        peaks = await asyncio.to_thread(waveform_peaks, asal, bins=bins, duration=duration)
        if peaks:
            await asyncio.to_thread(projects_repo.save_waveform, vid, bins, peaks, duration)
        return {"video_id": vid, "bins": len(peaks), "peaks": peaks,
                "duration": duration, "cached": False}

    tugas = asyncio.ensure_future(hitung())
    _GELOMBANG_JALAN[kunci] = tugas
    try:
        return await asyncio.shield(tugas)
    finally:
        if tugas.done():
            _GELOMBANG_JALAN.pop(kunci, None)
        else:
            tugas.add_done_callback(lambda _t: _GELOMBANG_JALAN.pop(kunci, None))
