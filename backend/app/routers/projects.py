"""
Project klip: daftar video yang sedang atau sudah diproses, plus data timeline.

Halaman Studio menampilkan ini sebagai kartu. Pengguna bisa menekan "Clip" pada
beberapa video berturut-turut lalu kembali menonton; pekerjaannya berjalan di
antrean, dan kartunya menunjukkan kemajuan masing-masing.
"""

import asyncio

from fastapi import APIRouter, Query

from ..errors import AppError, NotFound
from ..repos import analyses as analyses_repo
from ..repos import jobs as jobs_repo
from ..repos import projects as projects_repo
from ..services.jobs import queue
from ..services.paths import extract_youtube_id, find_local_video

router = APIRouter(prefix="/api", tags=["projects"])


def _resolve(video_id: str) -> str:
    vid = extract_youtube_id(video_id) or (video_id if len(video_id) == 11 else "")
    if not vid:
        raise NotFound("Video tidak dikenali.")
    return vid


@router.get("/projects")
async def list_projects(limit: int = Query(60, le=200)):
    return await asyncio.to_thread(projects_repo.list_projects, limit)


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
        # local_url ikut dihitung ulang di sini, bukan hanya dibaca dari hasil
        # tersimpan: file bisa saja sudah dihapus sejak analisis dibuat.
        "local_url": f"/api/media/local_downloads/{local.name}" if local else None,
        "downloaded": local is not None,
        **result,
    }


@router.delete("/projects/{video_id}")
async def delete_project(video_id: str):
    """
    Hapus satu kartu Partitur sampai benar-benar hilang.

    Kartunya disusun dari dua sumber — `analyses` dan `jobs` — jadi membuang
    analisisnya saja tidak cukup: baris job yang tertinggal membangun kembali
    kartu yang sama pada pemuatan berikutnya, berlabel "Gagal". Itu juga alasan
    kartu yang MEMANG gagal dulu tidak bisa dihapus sama sekali; kartu seperti
    itu tidak punya analisis, hanya job.

    Job yang masih berjalan dibatalkan lebih dulu, supaya pekerjaannya berhenti
    alih-alih terus memakai CPU untuk sesuatu yang barisnya sudah tidak ada.
    """
    vid = _resolve(video_id)

    for job_id in await asyncio.to_thread(jobs_repo.ids_for_video, vid, only_active=True):
        queue.cancel(job_id)

    await asyncio.to_thread(analyses_repo.delete_for_video, vid)
    jobs_dihapus = await asyncio.to_thread(jobs_repo.delete_for_video, vid)
    return {"success": True, "video_id": vid, "jobs_dihapus": jobs_dihapus}


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

    info = await asyncio.to_thread(probe, source)
    duration = float(info.get("duration") or 0)
    peaks = await asyncio.to_thread(waveform_peaks, source, bins=bins, duration=duration)
    if peaks:
        await asyncio.to_thread(projects_repo.save_waveform, vid, bins, peaks, duration)
    return {"video_id": vid, "bins": len(peaks), "peaks": peaks,
            "duration": duration, "cached": False}
