"""
Unggah klip ke Google Drive dan YouTube.

Satu per satu, tidak pernah berombongan: antreannya berjalan di lane `upload`
yang lebarnya satu, dan untuk YouTube ada jeda tambahan antar unggahan yang
berhasil. Mengirim selusin klip ke satu kanal beruntun adalah persis pola yang
membuat kanal ditandai, dan itu bukan risiko yang boleh diambil aplikasi ini
atas nama penggunanya.
"""

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..config import UPLOAD_GAP_SECONDS
from ..errors import AppError
from ..repos import uploads as uploads_repo
from ..repos import profil as profil_repo
from ..services import google_upload as google
from ..services.jobs import queue
from ..services.paths import safe_media_path

log = logging.getLogger("omniclip.uploads")
router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.get("/google/status")
async def google_status():
    st = google.status()
    st["gap_seconds"] = UPLOAD_GAP_SECONDS
    return st


@router.post("/google/client")
async def set_client(payload: str = Body(..., media_type="text/plain")):
    """Menerima isi berkas OAuth client apa adanya, bukan jalur berkasnya."""
    return google.save_client_secret(payload)


class SambungRequest(BaseModel):
    # Satu layanan per permintaan: Google menolak izin YouTube dan Drive yang
    # diminta bersamaan (lihat SCOPES_LAYANAN di services/google_upload.py).
    layanan: str = Field("youtube", pattern="^(youtube|drive)$")


@router.post("/google/connect")
async def connect(req: SambungRequest | None = None):
    layanan = (req.layanan if req else "youtube")
    return {"authorization_url": google.begin_authorization(layanan),
            "layanan": layanan}


@router.get("/google/callback", response_class=HTMLResponse)
async def callback(request: Request, state: str = "", error: str = ""):
    """
    Google mengembalikan pengguna ke sini setelah halaman izin.

    Yang dikirim balik adalah halaman kecil, bukan JSON: yang membacanya adalah
    orang di dalam tab browser, bukan program.
    """
    # Akun wadahnya dibuang di SETIAP jalur gagal, bukan ditinggalkan untuk
    # penyapu berumur 15 menit. Lihat `profil.buang_wadah_gagal`.
    def _bersihkan() -> bool:
        from ..services import profil as profil_svc
        pid = google.profil_menunggu(state)
        google.lupakan_sesi(state)
        try:
            return profil_svc.buang_wadah_gagal(pid)
        except Exception:                            # noqa: BLE001
            log.exception("Akun wadah gagal dibuang")
            return False

    if error:
        dibuang = await asyncio.to_thread(_bersihkan)
        return _page("Izin ditolak",
                     f"Google menjawab: {error}."
                     + (" Akun yang disiapkan untuk login ini sudah dibuang,"
                        " jadi tidak ada akun kosong yang tertinggal."
                        if dibuang else ""),
                     ok=False)
    try:
        email, pid = google.finish_authorization(str(request.url), state)
        from ..services import profil as profil_svc
        # Akunnya sudah punya Google; ia bukan lagi akun yang menunggu izin.
        profil_repo.sahkan(pid)
        nama = profil_svc.namai_dari_akun(pid, email)
        if nama:
            log.info("Akun %s dinamai dari surelnya: %s", pid, nama)
        # Foldernya juga. Dijalankan tiap kali izin selesai, bukan hanya saat
        # penamaan pertama: akun yang dulu terlanjur mendapat folder bernomor
        # ikut dirapikan saat masuk lagi.
        profil_svc.folder_untuk_akun(pid, email)
        # Foto akun untuk lencana profil. Gagalnya tidak menggagalkan apa pun:
        # lencana huruf tetap ada sebagai jalan mundurnya.
        google.simpan_foto(pid)
    except AppError as e:
        await asyncio.to_thread(_bersihkan)
        return _page("Gagal menyambungkan", e.message, ok=False)
    except Exception as e:  # noqa: BLE001, halaman ini tidak boleh 500
        log.exception("Callback OAuth gagal")
        await asyncio.to_thread(_bersihkan)
        return _page("Gagal menyambungkan", google.explain_error(e), ok=False)
    return _page("Akun tersambung",
                 f"{email or 'Akun Google'} siap dipakai. Tab ini menutup "
                 "sendiri sebentar lagi.", ok=True)


def _page(title: str, body: str, *, ok: bool) -> HTMLResponse:
    """
    Halaman kecil yang dibaca ORANG, bukan program, plus satu pekerjaan kecil.

    Saat berhasil, halaman ini memberi tahu tab OmniClip yang membukanya lalu
    menutup dirinya sendiri. Tanpa itu pemiliknya harus kembali sendiri ke tab
    sebelah dan menekan tombol "Saya sudah selesai" — sebuah tombol yang ada
    semata-mata karena tab ini dulu tidak bisa bicara dengan tab yang
    membukanya, dan pertanyaan "kenapa harus saya tekan?" tidak punya jawaban
    yang memuaskan.

    `postMessage` dipagari ke asal yang sama, dan penutupan dirinya dibiarkan
    gagal diam-diam: peramban hanya mengizinkan sebuah tab menutup dirinya bila
    ia memang dibuka oleh skrip, dan itu tidak selalu benar.
    """
    colour = "#07683B" if ok else "#B3182C"
    # Tab OmniClip dikabari BAIK saat berhasil maupun saat gagal.
    #
    # Sebelumnya hanya keberhasilan yang dikabarkan, jadi login yang gagal
    # meninggalkan halaman "Menunggu izin dari Google" menyala sampai lima
    # menit, dengan akun wadah sebagai akun aktif. Yang gagal tidak menutup
    # tabnya sendiri: pesan dari Google layak dibaca, bukan dikedipkan.
    pesan = "omniclip:google-tersambung" if ok else "omniclip:google-gagal"
    tutup = ("setTimeout(function(){try{window.close();}catch(e){}},1200);"
             if ok else "")
    skrip = ("<script>try{if(window.opener&&!window.opener.closed){"
             f"window.opener.postMessage('{pesan}',"
             "window.location.origin);}"
             f"{tutup}"
             "}catch(e){}</script>")
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'>"
        "<title>OmniClip</title>"
        "<body style=\"margin:0;display:grid;place-items:center;min-height:100vh;"
        "font:16px/1.6 system-ui,sans-serif;background:#EDF1F6;color:#0E1420\">"
        f"<div style='max-width:420px;padding:28px;text-align:center'>"
        f"<h1 style='margin:0 0 8px;font-size:1.3rem;color:{colour}'>{title}</h1>"
        f"<p style='margin:0;color:#46536A'>{body}</p></div>{skrip}</body>",
        status_code=200 if ok else 400,
    )


@router.post("/google/disconnect")
async def disconnect(req: SambungRequest | None = None):
    """Memutus satu layanan; tanpa isi, memutus keduanya."""
    google.disconnect(layanan=req.layanan if req else None)
    return {"status": "ok"}


class UploadRequest(BaseModel):
    clip_name: str
    target: str = Field("drive", pattern="^(drive|youtube)$")
    title: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    privacy: str = Field("private", pattern="^(private|unlisted|public)$")
    folder_id: str = ""


@router.post("", status_code=202)
async def start_upload(req: UploadRequest):
    """
    Mengantrekan satu unggahan.

    Satu klip per permintaan. Tidak ada bentuk jamaknya, dan itu disengaja:
    antarmuka yang menerima daftar akan membuat "unggah semua" terasa seperti
    satu tombol yang wajar, padahal itu justru yang harus dihindari.
    """
    if not google.status()["connected"]:
        raise AppError("Akun Google belum tersambung. Sambungkan dulu di Pengaturan.",
                       code="GOOGLE_NOT_CONNECTED", status=409)

    # Memastikan klipnya ada SEBELUM barisnya dicatat, supaya riwayat tidak
    # terisi baris gagal untuk nama berkas yang salah ketik.
    from ..services import profil
    safe_media_path(profil.kategori_klip(profil.kini()), req.clip_name)

    from ..services.unggah import antrekan
    job_id, created = antrekan(
        clip_name=req.clip_name, target=req.target, title=req.title,
        description=req.description, tags=req.tags, privacy=req.privacy,
        folder_id=req.folder_id)
    return {"job_id": job_id, "created": created}


@router.get("/saran-deskripsi")
async def saran_deskripsi(clip_name: str, judul: str = ""):
    """
    Deskripsi unggahan dari templat profil, lengkap dengan kredit sumbernya.

    Dipakai formulir unggah manual supaya isinya SAMA dengan unggahan otomatis.
    Sebelum JOB-2 F0-2 formulir itu membangun deskripsinya sendiri di peramban
    dari tagar saja, jadi unggahan manual tidak pernah membawa kredit dan tidak
    pernah memakai templat profil.
    """
    import asyncio

    from ..services import profil
    from ..services.analitik import _sidecar
    from ..services.unggah import deskripsi, kredit, sumber_klip

    def kerja():
        pid = profil.kini()
        setel = profil.unggah(pid)
        meta = _sidecar(clip_name, pid) or {}
        tagar = list(dict.fromkeys([*(setel.get("hashtag") or []),
                                    *(meta.get("hashtags") or [])]))
        sumber = sumber_klip(clip_name, pid)
        pakai = setel.get("kredit", True) is not False
        return {
            "deskripsi": deskripsi(setel.get("deskripsi", ""),
                                   judul=judul or meta.get("title") or "",
                                   hashtag=tagar, sumber=sumber, pakai_kredit=pakai),
            "kredit": kredit(sumber) if pakai else "",
            "sumber": sumber,
        }

    return await asyncio.to_thread(kerja)


@router.get("")
async def list_uploads(clip_name: Optional[str] = None, limit: int = 60,
                       statistik: bool = False):
    """
    Riwayat unggahan profil ini. `statistik=true` ikut membawa tayangannya.

    Tayangan diminta HANYA bila ditanya, dan selalu di utas lain: ia menembak
    YouTube, dan halaman yang menampilkan riwayat tidak boleh ikut menunggu
    jaringan yang lambat untuk angka yang sifatnya tambahan.
    """
    import asyncio

    from ..services import profil
    daftar = uploads_repo.list_recent(min(limit, 200), clip_name,
                                      profil_id=profil.kini())
    if not statistik:
        return {"uploads": daftar}

    from ..services import statistik as stat_svc
    ids = [u["remote_id"] for u in daftar
           if u.get("target") == "youtube" and u.get("status") == "done"
           and u.get("remote_id")]
    angka = await asyncio.to_thread(stat_svc.tayangan, ids)
    for u in daftar:
        s = angka.get(u.get("remote_id") or "")
        if s:
            u["statistik"] = s
    return {"uploads": daftar,
            # Supaya antarmuka bisa membedakan "belum disetel" dari "disetel
            # tapi videonya privat", dan mengatakan yang benar untuk keduanya.
            "statistik_siap": bool(stat_svc.kunci_api()),
            "statistik_terbaca": len(angka)}


@router.get("/analitik")
async def analitik_kanal(limit: int = 200):
    """
    Performa klip yang sudah diunggah, dan apa yang bisa dibaca darinya.

    Semuanya dikerjakan di utas lain: ia membaca sidecar tiap klip dari cakram
    dan menembak YouTube sekali. Jawabannya selalu mengatakan berapa klip yang
    terbaca dan berapa yang tidak, supaya halaman di depannya tidak perlu
    menebak kenapa angkanya sedikit.
    """
    import asyncio

    from ..services import analitik as analitik_svc
    from ..services import profil

    return await asyncio.to_thread(analitik_svc.laporan, profil.kini(),
                                   batas=min(limit, 500))
