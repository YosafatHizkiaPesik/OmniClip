"""Analisis auto-clip dan render klip."""

import re
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from ..errors import InvalidInput, NotFound
from ..repos import analyses as analyses_repo
from ..repos import media as media_repo
from ..services.jobs import queue
from ..services.paths import (
    extract_id_from_filename,
    extract_youtube_id,
    safe_media_path,
)
from ..services.render import list_local_clips

router = APIRouter(prefix="/api", tags=["clips"])


class AutoClipRequest(BaseModel):
    video_id: str = Field(..., description="ID atau URL YouTube")
    # "Terbaik", bukan "720p".
    #
    # Bawaan lama adalah plafon kualitas SELURUH hasil, diam-diam. Frontend
    # tidak pernah mengirim field ini, jadi nilai inilah yang selalu dipakai —
    # dan pipeline yang di bawahnya sudah menulis "auto-clip SELALU mengambil
    # yang terbaik kecuali diminta lain" hanya melihat "720p" dan menurutinya.
    # Keluarannya 1080x1920, sedangkan jendela 9:16 dari sumber 720p cuma
    # 405x720: diregangkan 2,67x, dan tidak ada filter yang bisa mengembalikan
    # detail yang tidak pernah terekam.
    quality: str = "Terbaik"
    whisper_model: str = "base"
    # 0 = biarkan sistem menghitungnya dari durasi video. Angka tetap 8 dulu
    # memperlakukan podcast dua jam sama dengan video sepuluh menit.
    max_clips: int = 0
    # Perkiraan penutur dari warna suara. Menambah ~15 detik pada video panjang.
    diarize: bool = True
    speakers: Optional[int] = None      # None = tebak sendiri
    use_gemini: bool = True
    # Nama model Gemini pilihan pengguna; kosong = pakai urutan bawaan.
    gemini_model: Optional[str] = None
    force: bool = False  # abaikan hasil analisis yang sudah tersimpan
    # Jalur audio (sulih suara) yang diunduh, mis. "en". Kosong = suara asli.
    audio_lang: Optional[str] = Field(None, max_length=16, pattern=r"^[A-Za-z0-9-]*$")


class SegmentModel(BaseModel):
    start: float
    end: float


_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _warna(v: Optional[str]) -> Optional[str]:
    """
    Warna harus heksadesimal, dan penolakannya harus terdengar.

    Dulu nilai apa pun diterima lalu diubah diam-diam jadi putih jauh di
    dalam penyusun ASS. Satu preset di antarmuka mengirim `var(--danger)`,
    dan akibatnya seluruh subtitle keluar putih di video sementara pratinjau
    menampilkannya merah — tanpa galat, jadi yang terlihat cuma "warnanya
    beda". Ditolak di sini, kekeliruan yang sama tidak bisa lagi lolos diam-diam.
    """
    if v is None:
        return None
    v = v.strip()
    if not _HEX.match(v):
        raise ValueError(f"warna harus berbentuk #RRGGBB, bukan {v!r}")
    return v.upper()


class CaptionStyleModel(BaseModel):
    """Gaya teks dari UI. Semua nilai di sini benar-benar sampai ke ffmpeg."""
    size: Optional[int] = None
    primary: Optional[str] = None
    highlight: Optional[str] = None
    position: Optional[str] = None
    uppercase: Optional[bool] = None
    animation: Optional[str] = None
    font: Optional[str] = None
    # False = subtitle tidak digambar sama sekali. Barisnya tetap tersimpan.
    aktif: Optional[bool] = None
    # False = tidak ada kata yang disorot; baris tampil satu warna.
    highlight_words: Optional[bool] = None
    # Pelat tembus pandang di belakang teks, pengganti garis luar tebal.
    bg: Optional[bool] = None
    bg_color: Optional[str] = None
    bg_opacity: Optional[float] = Field(None, ge=0.0, le=1.0)
    bg_pad: Optional[int] = Field(None, ge=0, le=60)
    # Jarak teks dari tepi yang dijadikan jangkar, dalam piksel pada kanvas
    # setinggi 1920. Diisi saat pengguna menyeret subtitle di pratinjau.
    margin_v: Optional[int] = None
    outline_px: Optional[int] = None
    # Penempatan mendatar dalam persen lebar kanvas: pos_x titik tengah kotak
    # teks, box_w lebarnya. Bersama margin_v, keduanya membuat subtitle bisa
    # ditaruh di pojok mana pun, bukan hanya di tengah.
    pos_x: Optional[float] = None
    box_w: Optional[float] = None
    # Warna per penutur, diindeks langsung: [0] orang pertama, [1] kedua, dst.
    speaker_colors: Optional[List[str]] = None
    # False = satu warna untuk seluruh klip, apa pun tebakan penuturnya.
    per_speaker_colors: Optional[bool] = None
    # Subtitle kedua saja: True = warnanya mengikuti orang yang bicara, dengan
    # palet subtitle utama.
    ikut_warna_orang: Optional[bool] = None
    # --- Tanda air: gayanya sendiri, bukan pinjaman dari subtitle ------------
    wm_font: Optional[str] = None
    wm_size: Optional[int] = Field(None, ge=8, le=400)
    wm_color: Optional[str] = None
    wm_opacity: Optional[float] = Field(None, ge=0.0, le=1.0)
    wm_x: Optional[float] = Field(None, ge=0.0, le=100.0)
    wm_y: Optional[float] = Field(None, ge=0.0, le=100.0)
    wm_outline: Optional[int] = Field(None, ge=0, le=16)

    @field_validator("primary", "highlight", "wm_color", "bg_color")
    @classmethod
    def _cek_warna(cls, v):
        return _warna(v)

    @field_validator("speaker_colors")
    @classmethod
    def _cek_palet(cls, v):
        return None if v is None else [_warna(x) for x in v]


class FrameRectModel(BaseModel):
    """Persegi dalam persen. Dijepit di sini, bukan dipercaya dari klien."""
    x: float = Field(0, ge=0, le=100)
    y: float = Field(0, ge=0, le=100)
    w: float = Field(100, ge=1, le=100)
    h: float = Field(100, ge=1, le=100)


class FrameModel(BaseModel):
    label: str = ""
    src: FrameRectModel = FrameRectModel()
    dst: FrameRectModel = FrameRectModel()
    fit: str = "cover"
    # Bila benar, posisi mendatar jendela ini digerakkan jejak wajah; lebar,
    # tinggi, dan posisi tegaknya tetap dari kotak yang digambar pengguna.
    follow: bool = False
    # Orang yang dibuntuti, bila ditentukan (nomor orang dari rencana wajah).
    # Tanpa ini orangnya ditebak dari letak kotak — cukup untuk kotak yang
    # digambar pengguna, tapi ambigu di podcast yang berganti kamera: "orang
    # terdekat dari tengah kotak" rata-rata sepanjang klip bisa orang lain.
    person: Optional[int] = Field(None, ge=0, le=7)


class ReaksiModel(BaseModel):
    """Main game: letak kotak wajah mulai detik klip `t`."""
    t: float = Field(0.0, ge=0)
    src: FrameRectModel = FrameRectModel()


class FrameLayoutModel(BaseModel):
    background: str = "blur"
    # Main game: kotak wajah yang berpindah mengikuti facecam sepanjang klip,
    # dan setelan susunannya. Diabaikan oleh susunan biasa.
    reaksi: List[ReaksiModel] = Field(default_factory=list, max_length=64)
    gaming: Optional[Dict[str, Any]] = None
    # Delapan bingkai sudah jauh melewati apa pun yang masih terbaca di layar
    # ponsel, dan tiap bingkai menambah satu cabang skala di filtergraph.
    frames: List[FrameModel] = Field(default_factory=list, max_length=8)


class FrameKeyModel(BaseModel):
    """Satu titik pergantian cara membingkai, dalam waktu KLIP."""

    t: float = Field(0.0, ge=0)
    # smart = ikuti wajah, box = kotak tetap yang digambar pengguna,
    # gaming = wajah di atas + permainan di bawah, center = crop tengah,
    # blur = bilah kabur, layout = susunan buatan pengguna.
    mode: str = "smart"
    # Dibaca hanya oleh mode "box": bagian mana dari bingkai sumber yang
    # diambil, dalam persen.
    rect: Optional[FrameRectModel] = None
    # Dibaca hanya oleh mode "smart": orang keberapa yang dibuntuti.
    person: Optional[int] = Field(None, ge=0, le=7)
    # Dibaca hanya oleh mode "layout".
    layout: Optional[FrameLayoutModel] = None
    # "otomatis" bila diusulkan sutradara, beserta alasannya. Ikut disimpan
    # supaya lajur Bingkai bisa menjelaskan kenapa bingkainya berganti di situ.
    asal: Optional[str] = Field(None, max_length=16)
    alasan: Optional[str] = Field(None, max_length=200)


class MediaLayerModel(BaseModel):
    """Satu sisipan: berkas dari luar video sumber, ditempel pada waktunya."""

    # id aset dari /api/aset — BUKAN jalur berkas.
    aset: str = Field(..., max_length=64)
    # Nama tampilan dan jenisnya, disimpan di sisipan supaya linimasa bisa
    # menggambarnya tanpa memuat pustaka aset lebih dulu.
    nama: Optional[str] = Field(None, max_length=120)
    jenis: Optional[str] = Field(None, max_length=16)
    t: float = Field(0.0, ge=0)
    # Kosong = sepanjang asetnya (dipotong di akhir klip).
    dur: Optional[float] = Field(None, gt=0, le=3600)
    mulai_sumber: float = Field(0.0, ge=0)
    posisi: Literal["penuh", "atas", "bawah", "tengah", "sudut"] = "penuh"
    volume: float = Field(1.0, ge=0.0, le=2.0)
    # Musik latar mengecil sendiri saat orang bicara.
    redam: bool = False
    # Dari mana sisipan ini datang: "pengguna" atau "otomatis" (sutradara).
    asal: Optional[str] = Field(None, max_length=16)
    alasan: Optional[str] = Field(None, max_length=200)


class SubtitleKeduaModel(BaseModel):
    aktif: bool = True
    bahasa: str = Field("id", max_length=12)
    lines: List[Dict[str, Any]] = Field(default_factory=list, max_length=4000)
    style: Optional[CaptionStyleModel] = None


class PersonKeyModel(BaseModel):
    """
    Satu tanda di linimasa klip: mulai detik `t`, bingkai menunjuk `person`.

    `person` kosong berarti "kembali ke otomatis mulai di sini", jadi satu
    bagian yang meleset bisa dibetulkan tanpa mengambil alih sisa klipnya.
    """
    t: float = Field(0.0, ge=0)
    person: Optional[int] = Field(None, ge=0, le=7)


class TitleCardModel(BaseModel):
    """
    Kartu judul di awal klip.

    `mode`: overlay = judul menutupi klip yang berjalan; freeze = bingkai
    pertama dibekukan sebagai latar; zoom = sama seperti freeze, gambarnya
    merayap membesar. Dua yang terakhir menambah panjang klip.
    """
    enabled: bool = False
    text: str = ""
    mode: str = "freeze"
    seconds: float = Field(3.0, ge=1.2, le=12.0)
    voice: bool = True
    voice_id: str = "piper-news"
    rate: float = Field(1.05, ge=0.6, le=1.6)
    size: int = Field(104, ge=28, le=240)
    color: str = "#FFFFFF"
    shadow: str = "#000000"
    # Letak dan lebar kotak judul, dalam persen kanvas. Diseret langsung di atas
    # pratinjau; disimpan dalam persen supaya satu setelan berlaku sama untuk
    # kanvas 9:16 maupun 16:9.
    pos_x: float = Field(50.0, ge=0.0, le=100.0)
    pos_y: float = Field(50.0, ge=0.0, le=100.0)
    box_w: float = Field(84.0, ge=20.0, le=100.0)
    variant: str = "garis"
    font: str = ""
    # Panjang kartu yang SEBENARNYA, dari lama bacaannya. Disimpan klien setelah
    # suaranya dibuat supaya linimasa dan pratinjau memakai angka yang sama
    # dengan yang nanti dipakai ffmpeg.
    card_seconds: float = Field(0.0, ge=0.0, le=12.0)


class RenderClipRequest(BaseModel):
    # Referensi video, bukan path filesystem: klien tidak menentukan file mana
    # yang dibuka server.
    source_path: str
    # Klip bisa terdiri dari beberapa potongan yang disambung — misalnya menit 10
    # digabung dengan menit 50. Bila kosong, start/end dipakai sebagai satu segmen.
    segments: Optional[List[SegmentModel]] = None
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    subtitles: Optional[List[Dict[str, Any]]] = None
    aspect_ratio: str = "9:16"
    font_color: str = "yellow"
    font_size: int = 24
    position: str = "bottom"
    hook_text: str = ""
    # Judul di atas video mati secara bawaan: hasilnya lebih bersih, dan hook
    # yang dihasilkan otomatis sering kalah bagus dari klipnya sendiri.
    show_hook: bool = False
    watermark: str = ""
    video_filter: str = "normal"
    # smart = ikuti wajah pembicara, blur = bilah kabur, center = crop tengah,
    # original = tanpa dipotong, layout = susunan bingkai buatan pengguna.
    frame_mode: str = "smart"
    # Gaya perpindahan bingkai: mulus (kamera mengikuti) atau potong (diam,
    # lalu berpindah seketika).
    frame_motion: Literal["smooth", "cut"] = "smooth"
    # Susunan bingkai. Tiap bingkai punya persegi SUMBER (bagian mana dari video
    # yang diambil) dan persegi TUJUAN (di mana ia ditaruh pada kanvas hasil),
    # keduanya dalam persen. Hanya dibaca bila frame_mode == "layout".
    frame_layout: Optional[FrameLayoutModel] = None
    # Linimasa pembingkaian: tiap kunci berlaku dari `t` sampai kunci
    # berikutnya. Dua kunci atau lebih MENANG atas `frame_mode` — di situlah
    # satu klip bisa memakai beberapa cara membingkai sekaligus.
    frame_keys: List[FrameKeyModel] = Field(default_factory=list)
    # Sisipan: cuplikan, gambar, musik, efek suara dari luar video sumber.
    media_layers: List[MediaLayerModel] = Field(default_factory=list, max_length=60)
    # Subtitle kedua — biasanya terjemahan. Gayanya sendiri; divalidasi dengan
    # model yang sama dengan gaya subtitle utama, jadi warna tetap wajib hex.
    subtitle_kedua: Optional[SubtitleKeduaModel] = None
    # Mode ikut-wajah: orang yang ditunjuk pengguna. None = otomatis.
    lock_person: Optional[int] = Field(None, ge=0, le=7)
    person_keys: List[PersonKeyModel] = Field(default_factory=list)
    title_card: Optional[TitleCardModel] = None
    # Nomor klip, dipakai untuk menamai berkas hasilnya.
    clip_index: Optional[int] = None
    # Judul dan tagar klip. Judulnya jadi nama berkas hasil; tanpanya semua
    # klip dari satu video bernama sama kecuali nomornya.
    title: str = ""
    hashtags: List[str] = Field(default_factory=list)
    caption_style: Optional[CaptionStyleModel] = None
    # Unggah sesudah render, untuk render ini saja: {"youtube", "drive",
    # "privasi"}. None = ikut setelan unggah otomatis profil.
    unggah: Optional[Dict[str, Any]] = None


def _resolve_video_id(reference: str) -> str:
    vid = extract_youtube_id(reference) or extract_id_from_filename(reference)
    if not vid:
        raise NotFound("Video sumber tidak dikenali.")
    return vid


@router.post("/auto-clip", status_code=202)
async def start_auto_clip(req: AutoClipRequest):
    """
    Mengantrekan pipeline auto-clip lengkap dan mengembalikan job_id.

    Frontend mengikuti progres lewat SSE di /api/jobs/{id}/events. Seluruh teks
    tahapan datang dari server — tidak ada progres yang disimulasikan di klien.
    """
    video_id = _resolve_video_id(req.video_id)
    # Kartu Partitur-nya milik profil yang meminta — termasuk bila hasil
    # analisis video ini sudah ada dari profil lain dan langsung dipakai ulang.
    from ..repos import profil as profil_repo
    from ..services import profil
    profil_repo.tandai_video(profil.kini(), video_id)

    # Jalur audio yang diminta tidak sama dengan yang ada di disk: videonya
    # harus diunduh ulang, jadi hasil tersimpan tidak boleh langsung dipakai.
    beda_audio = False
    if req.audio_lang:
        from ..services.paths import find_local_video
        from ..services.ytdlp import audio_cocok, bahasa_audio
        lokal = find_local_video(video_id)
        beda_audio = lokal is not None and not audio_cocok(bahasa_audio(lokal), req.audio_lang)

    if not req.force and not beda_audio:
        cached = analyses_repo.latest_for_video(video_id)
        if cached:
            if cached["result"].get("has_transcript") is False:
                return {"job_id": None, "cached": True, "result": cached["result"]}
            # Hasil tersimpan hanya dipakai bila jumlah klipnya memang mencukupi
            # permintaan; kalau tidak, analisis diulang. Tanpa syarat ini,
            # meminta 8 klip akan diam-diam mengembalikan 3 klip dari analisis
            # sebelumnya. Untuk permintaan otomatis, targetnya dihitung dari
            # durasi yang tercatat di analisis itu sendiri — sehingga analisis
            # lama yang dipatok 8 klip ikut diperbarui pada video panjang.
            from ..services.heuristics import auto_clip_count
            want = req.max_clips or auto_clip_count(
                float(cached["result"].get("duration") or 0))
            if len(cached["result"].get("clips") or []) >= want:
                return {"job_id": None, "cached": True, "result": cached["result"]}

    job_id, created = queue.enqueue(
        "auto_clip",
        {
            "video_id": video_id,
            "quality": req.quality,
            "whisper_model": req.whisper_model,
            "max_clips": req.max_clips,
            "diarize": req.diarize,
            "speakers": req.speakers,
            "use_gemini": req.use_gemini,
            "gemini_model": req.gemini_model,
            "audio_lang": req.audio_lang,
        },
        video_id=video_id,
        dedupe_key=f"auto_clip:{video_id}:{req.gemini_model or 'auto'}:{req.audio_lang or 'asli'}",
    )
    return {"job_id": job_id, "created": created, "cached": False, "video_id": video_id}


@router.post("/projects/{video_id}/lanjutkan")
async def lanjutkan_proses(video_id: str):
    """
    Menjalankan ulang pekerjaan klip yang gagal atau terputus, dengan setelan
    yang SAMA PERSIS, dan melaporkan langkah mana yang akan dilewati.

    Pipeline-nya sendiri sudah tidak mengulang pekerjaan yang pernah selesai:
    video yang sudah ada di disk tidak diunduh lagi, transkrip yang tersimpan
    tidak disalin ulang, dan unduhan yang terputus dilanjutkan dari berkas
    `.part`-nya. Yang tidak ada selama ini hanyalah CARA memicunya — pengguna
    harus menghapus proyeknya lalu memulai dari halaman tonton, tanpa tahu
    bahwa hampir seluruh pekerjaannya masih tersimpan.
    """
    import json as _json

    from ..db import get_conn
    from ..repos import transcripts as tx_repo
    from ..services.paths import find_local_video

    vid = _resolve_video_id(video_id)
    row = get_conn().execute(
        """SELECT payload_json, status FROM jobs WHERE type='auto_clip' AND video_id=?
           ORDER BY created_at DESC LIMIT 1""", (vid,)).fetchone()
    if row is None:
        raise NotFound("Belum pernah ada proses klip untuk video ini.")
    if row["status"] in ("queued", "running"):
        raise InvalidInput("Proses untuk video ini masih berjalan.")
    try:
        payload = _json.loads(row["payload_json"] or "{}")
    except ValueError:
        payload = {}
    payload["video_id"] = vid

    dilewati: list[str] = []
    if find_local_video(vid) is not None:
        dilewati.append("unduhan (video sudah ada)")
    if tx_repo.get_best(vid):
        dilewati.append("transkrip (sudah tersimpan)")

    job_id, created = queue.enqueue(
        "auto_clip", payload, video_id=vid,
        dedupe_key=f"auto_clip:{vid}:{payload.get('gemini_model') or 'auto'}",
    )
    return {"job_id": job_id, "created": created, "video_id": vid, "dilewati": dilewati}


class CariUlangRequest(BaseModel):
    # "gemini" = peringkat disusun ulang oleh model; "heuristik" = mesin lokal.
    mesin: Literal["gemini", "heuristik"] = "gemini"
    gemini_model: Optional[str] = Field(None, max_length=80)
    # 0 = dihitung dari durasi video.
    max_clips: int = Field(0, ge=0, le=60)


@router.post("/projects/{video_id}/cari-ulang", status_code=202)
async def cari_ulang(video_id: str, req: CariUlangRequest):
    """
    Mencari ulang rekomendasi klip, hook, dan judul — tanpa mengunduh atau
    mentranskrip ulang.

    Dulu satu-satunya jalan beralih dari mesin lokal ke Gemini (atau mencoba
    model lain) adalah menghapus proyek lalu mengunduh videonya lagi. Yang
    diulang di sini hanya pemilihan momen; transkrip dan penanda narasumber
    yang tersimpan dipakai apa adanya. Hasil sebelumnya tetap tersimpan dan
    bisa dikembalikan lewat /pulihkan.
    """
    from ..config import get_api_key
    from ..errors import AppError
    from ..repos import transcripts as tx_repo
    from ..services.paths import find_local_video

    vid = _resolve_video_id(video_id)
    if find_local_video(vid) is None:
        raise AppError("Video sumber belum ada di penyimpanan. Unduh ulang dulu.",
                       code="SOURCE_NOT_DOWNLOADED", status=409)
    if not tx_repo.get_best(vid):
        raise AppError("Video ini belum punya transkrip — jalankan klip otomatis dulu.",
                       code="NO_TRANSCRIPT", status=409)
    if req.mesin == "gemini" and not get_api_key():
        raise AppError("Gemini butuh kunci API. Isi di Pengaturan → Model AI, "
                       "atau pilih mesin lokal.", code="AI_KEY_MISSING", status=409)

    job_id, created = queue.enqueue(
        "auto_clip",
        {
            "video_id": vid,
            "ulang": True,
            "use_gemini": req.mesin == "gemini",
            "gemini_model": req.gemini_model if req.mesin == "gemini" else None,
            "max_clips": req.max_clips,
        },
        video_id=vid,
        dedupe_key=f"auto_clip:{vid}:ulang",
    )
    return {"job_id": job_id, "created": created, "video_id": vid}


@router.post("/projects/{video_id}/pulihkan")
async def pulihkan_analisis(video_id: str):
    """Mengembalikan rekomendasi klip sebelum "Cari ulang klip" terakhir."""
    vid = _resolve_video_id(video_id)
    kini = analyses_repo.latest_for_video(vid)
    asal = ((kini or {}).get("result") or {}).get("sebelumnya") or {}
    lama = analyses_repo.get(int(asal["id"])) if asal.get("id") else None
    if not lama or lama.get("video_id") != vid:
        raise NotFound("Tidak ada hasil sebelumnya untuk dikembalikan.")
    # Yang dipulihkan menunjuk balik ke hasil yang baru saja diganti, jadi
    # tombol yang sama bisa membalikkannya lagi.
    hasil = {**lama["result"], "sebelumnya": {
        "id": kini["id"], "engine": kini["result"].get("engine"),
        "model": kini["result"].get("model"),
        "clip_count": len(kini["result"].get("clips") or [])}}
    analyses_repo.save(
        video_id=vid, transcript_id=lama.get("transcript_id"),
        engine=lama.get("engine") or "heuristic", model=lama.get("model"),
        params={**(lama.get("params") or {}), "dipulihkan_dari": lama["id"]},
        result=hasil,
    )
    return {"success": True, "clip_count": len(lama["result"].get("clips") or [])}


@router.get("/analysis/{video_id}")
async def get_analysis(video_id: str):
    cached = analyses_repo.latest_for_video(_resolve_video_id(video_id))
    if not cached:
        raise NotFound("Belum ada analisis untuk video ini.")

    # Judul dan tagar diisikan saat DIBACA, bukan hanya saat dianalisis.
    #
    # Analisis yang tersimpan sebelum keduanya ada akan membuka editor dengan
    # tab Judul kosong, dan satu-satunya jalan keluarnya adalah menganalisis
    # ulang video sepanjang satu jam. Mengisinya di sini membuat project lama
    # ikut mendapatkannya tanpa memproses apa pun lagi.
    from ..services.clipmodel import (
        normalize_hashtags, suggest_hashtags, suggest_title,
    )

    result = cached["result"]
    vtitle = result.get("title") or ""
    channel = (media_repo.get_video(_resolve_video_id(video_id)) or {}).get("channel") or ""
    for clip in result.get("clips") or []:
        text = clip.get("transcript_text") or ""
        if not (clip.get("title") or "").strip():
            clip["title"] = suggest_title(text, vtitle)
        clip["hashtags"] = normalize_hashtags(
            clip.get("hashtags")
            or suggest_hashtags(text, vtitle, channel,
                                duration=float(clip.get("duration") or 0)))
    return result


class ClipPreviewRequest(BaseModel):
    video_id: str
    segments: List[SegmentModel]


class ReframePlanRequest(BaseModel):
    video_id: str
    segments: List[SegmentModel]
    aspect_ratio: str = "9:16"
    # Baris subtitle berlabel penutur. Dipakai untuk mencocokkan wajah dengan
    # penutur, supaya pratinjau memakai rencana yang sama dengan render.
    subtitles: Optional[List[Dict[str, Any]]] = None
    # Orang yang ditunjuk pengguna (indeks, kiri ke kanan). None = otomatis.
    lock_person: Optional[int] = Field(None, ge=0, le=7)
    # Tanda linimasa: berlaku per rentang, bukan sekali untuk seluruh klip.
    person_keys: List[PersonKeyModel] = Field(default_factory=list)
    # Dikirim juga ke pratinjau, supaya jejak yang digambar di editor memakai
    # gaya perpindahan yang sama dengan yang nanti dirender.
    frame_motion: Literal["smooth", "cut"] = "smooth"
    # Yang dijejak: wajah manusia, atau pusat gerakan (kartun, hewan, gameplay).
    # Dulu pratinjau mode "Ikuti gerakan" tidak meminta apa pun ke sini — ia
    # hanya menggambar kotak diam di tengah, jadi tidak ada cara melihat apakah
    # bingkainya benar-benar mengikuti tokoh sebelum merender.
    subjek: Literal["wajah", "gerak"] = "wajah"


# Perencanaan reframe memakan beberapa detik per klip, sementara editor
# memintanya setiap kali pengguna berpindah klip. Hasilnya disimpan sebentar
# di memori, dikunci oleh susunan segmen yang persis.
_REFRAME_CACHE: dict[tuple, dict] = {}
_REFRAME_CACHE_MAX = 48


@router.post("/clip-reframe")
async def clip_reframe(req: ReframePlanRequest):
    """
    Rencana crop yang mengikuti wajah, untuk digambar di pratinjau editor.

    Tanpa ini pratinjau menampilkan frame 16:9 apa adanya, sehingga pengguna
    tidak punya cara melihat bagaimana hasil 9:16-nya nanti membingkai
    pembicara — satu-satunya cara mengetahuinya adalah dengan merender.
    """
    import asyncio

    video_id = _resolve_video_id(req.video_id)
    segments = [{"start": round(s.start, 3), "end": round(s.end, 3)}
                for s in req.segments if s.end - s.start > 0.2]
    if not segments:
        raise NotFound("Rentang klip tidak valid.")

    turns = [
        (float(l["start"]), float(l["end"]), int(l["speaker"]))
        for l in (req.subtitles or [])
        if l.get("speaker") is not None and l.get("end") is not None
    ]
    key = (video_id, req.aspect_ratio,
           tuple((s["start"], s["end"]) for s in segments),
           tuple(turns), req.lock_person,
           tuple((round(k.t, 3), k.person) for k in req.person_keys),
           req.frame_motion, req.subjek)
    if key in _REFRAME_CACHE:
        return _REFRAME_CACHE[key]

    from ..services.paths import find_local_video
    from ..services.reframe import SAMPLE_FPS, plan_reframe

    source = find_local_video(video_id)
    if source is None:
        raise NotFound("Video sumber belum diunduh.")

    # track_only: jejaknya juga dipakai bingkai buatan pengguna, yang lebar
    # jendelanya tidak diturunkan dari rasio kanvas. Tanpa itu, video yang
    # sumbernya sudah tegak dijawab "tidak tersedia" padahal bingkai sempit di
    # dalamnya masih punya ruang untuk bergeser.
    plan = await asyncio.to_thread(plan_reframe, str(source), segments,
                                   aspect_ratio=req.aspect_ratio, track_only=True,
                                   speaker_turns=turns, lock_person=req.lock_person,
                                   person_keys=[k.model_dump() for k in req.person_keys],
                                   frame_motion=req.frame_motion,
                                   subjek=req.subjek)
    if plan is None:
        payload = {"available": False,
                   "reason": "no_motion" if req.subjek == "gerak" else "unsupported"}
    else:
        payload = {
            "available": plan.usable,
            "reason": None if plan.usable else "low_face_coverage",
            "crop_w": plan.crop_w, "crop_h": plan.crop_h,
            "source_w": plan.source_w, "source_h": plan.source_h,
            "face_coverage": plan.face_coverage,
            "keyframes": plan.keyframes,
            # Titik tengah wajah sepanjang waktu. Pratinjau menurunkan posisi
            # tiap bingkai pengikut dari sini memakai rumus yang sama dengan
            # render, jadi yang terlihat di layar adalah yang akan dirender.
            "centers": plan.centers,
            # Satu jejak per ORANG di layar, urut kiri ke kanan, dalam persen
            # lebar. Bingkai yang diminta membuntuti seseorang memakai jejak
            # ini, bukan jejak wajah utama.
            "people": [
                [None if v is None else round(v / plan.source_w * 100, 2)
                 for v in track]
                for track in plan.people
            ],
            # Kapan tiap orang BENAR-BENAR terlihat. Jejak di atas menahan
            # posisi terakhirnya saat wajahnya hilang — perlu, supaya crop tidak
            # melompat tiap kali kepala menoleh — tapi karena itu ia tidak bisa
            # dipakai untuk menjawab "apakah dia ada di layar sekarang". Editor
            # menaruh penanda orang di atas video sumber dari daftar ini, jadi
            # penandanya menghilang saat orangnya keluar dari bidikan alih-alih
            # berdiri di atas kursi kosong.
            "people_seen": plan.people_seen,
            "people_fps": SAMPLE_FPS,
            # Penutur mana milik wajah mana. Linimasa memakainya untuk menaruh
            # baris subtitle pada lajur orangnya — tanpa peta ini, nomor
            # penutur (dari suara) dan nomor wajah (dari gambar) adalah dua
            # penomoran berbeda yang kebetulan sama-sama angka.
            "speaker_faces": {str(k): v for k, v in plan.speaker_faces.items()},
        }

    if len(_REFRAME_CACHE) >= _REFRAME_CACHE_MAX:
        _REFRAME_CACHE.clear()
    _REFRAME_CACHE[key] = payload
    return payload


class SutradaraRequest(BaseModel):
    video_id: str
    segments: List[SegmentModel]
    aspect_ratio: str = "9:16"


@router.post("/clip-sutradara")
async def clip_sutradara(req: SutradaraRequest):
    """
    Usulan susunan otomatis untuk satu klip: kunci bingkai + sisipan suara.

    Tidak MENERAPKAN apa pun. Hasilnya dikembalikan ke Studio, yang menaruhnya
    di lajur Bingkai dan daftar Sisipan sebagai usulan bertanda "otomatis" —
    kelihatan, beralasan, dan bisa dihapus satu per satu.
    """
    import asyncio

    from ..services import sutradara
    from ..services.paths import find_local_video
    from ..services.render import PLAY_RES

    video_id = _resolve_video_id(req.video_id)
    segments = [{"start": round(s.start, 3), "end": round(s.end, 3)}
                for s in req.segments if s.end - s.start > 0.2]
    if not segments:
        raise NotFound("Rentang klip tidak valid.")
    source = find_local_video(video_id)
    if source is None:
        raise NotFound("Video sumber belum diunduh.")
    out_w, out_h = PLAY_RES.get(req.aspect_ratio, (1080, 1920))
    hasil = await asyncio.to_thread(sutradara.susun, source, segments,
                                    out_w=out_w, out_h=out_h)
    hasil.pop("facecam", None)
    return hasil


class SutradaraAIRequest(BaseModel):
    video_id: str
    segments: List[SegmentModel] = Field(..., min_length=1, max_length=20)
    subtitles: Optional[List[Dict[str, Any]]] = None
    aspect_ratio: str = "9:16"
    mesin: Literal["ai", "lokal"] = "ai"
    gemini_model: Optional[str] = None


@router.post("/clip-sutradara-ai")
async def clip_sutradara_ai(req: SutradaraAIRequest):
    """
    Sutradara yang menonton klipnya: momen reaksi → bingkai reaksi.

    Pekerjaan panjang (memindai wajah, mendengar tawa, menunggu model), jadi
    dijalankan sebagai job. Hasilnya USULAN kunci bingkai di `result.keys`;
    Studio yang menerapkannya supaya bisa dibatalkan seperti suntingan lain.
    """
    import hashlib
    import json as _json

    from ..services.paths import find_local_video

    vid = _resolve_video_id(req.video_id)
    if find_local_video(vid) is None:
        raise NotFound("Video sumber belum diunduh.")
    segments = [{"start": round(s.start, 3), "end": round(s.end, 3)}
                for s in req.segments if s.end - s.start > 0.2]
    if not segments:
        raise NotFound("Rentang klip tidak valid.")
    sidik = hashlib.sha1(_json.dumps([segments, req.mesin]).encode()).hexdigest()[:12]
    job_id, created = queue.enqueue(
        "sutradara",
        {"video_id": vid, "segments": segments, "subtitles": req.subtitles or [],
         "aspect_ratio": req.aspect_ratio, "mesin": req.mesin,
         "gemini_model": req.gemini_model},
        video_id=vid, dedupe_key=f"sutradara:{vid}:{sidik}",
    )
    return {"job_id": job_id, "created": created}


class TerjemahRequest(BaseModel):
    video_id: str
    bahasa: str = Field(..., min_length=2, max_length=12)
    teks: List[str] = Field(..., max_length=2000)


@router.post("/clip-terjemah")
async def clip_terjemah(req: TerjemahRequest):
    """
    Menerjemahkan baris subtitle satu lawan satu. Waktunya tidak disentuh:
    klien memasangkan hasilnya ke baris yang sama.
    """
    import asyncio

    from ..config import get_api_key, get_model_override
    from ..errors import AppError
    from ..services.peringkat_model import rantai
    from ..services.terjemah import terjemahkan

    # Tanpa kunci Gemini tetap bisa: terjemah.py jatuh ke Google Terjemahan.
    api_key = get_api_key() or ""
    vid = _resolve_video_id(req.video_id)
    video = media_repo.get_video(vid) or {}
    try:
        return await asyncio.to_thread(
            terjemahkan, req.teks, req.bahasa.strip(), api_key=api_key,
            models=rantai(api_key, get_model_override() or None) if api_key else [],
            konteks=(video.get("title") or "")[:200])
    except Exception as e:
        raise AppError(f"Terjemahan gagal: {str(e)[:200]}",
                       code="TERJEMAH_GAGAL", status=502) from e


class TitleVoiceRequest(BaseModel):
    text: str
    rate: float = Field(1.05, ge=0.6, le=1.6)
    voice_id: str = "piper-news"


@router.post("/title-voice")
async def title_voice(req: TitleVoiceRequest):
    """
    Membacakan judul dan mengembalikan berkas suaranya.

    Dipisahkan dari render supaya judul bisa DIDENGAR sebelum diputuskan: nada
    dan tempo pembacaan menentukan berapa lama kartunya menahan layar, dan
    menunggu satu render penuh untuk mengetahuinya membuat penyetelan mustahil.

    Hasilnya disimpan menurut isi teks dan tempo, jadi menekan tombolnya
    berkali-kali hanya menjalankan model sekali.
    """
    import asyncio
    import hashlib

    from ..config import VOICE_DIR
    from ..services import tts

    text = (req.text or "").strip()
    if not text:
        raise InvalidInput("Judulnya masih kosong.")
    spec = tts.voice_by_id(req.voice_id)
    if spec["engine"] == "piper" and not tts.available():
        raise NotFound("Suara pembaca judul belum terpasang.")
    if spec["engine"] == "edge" and not tts.edge_available():
        raise NotFound("Suara Microsoft tidak tersedia di pemasangan ini.")

    stamp = hashlib.sha1(f"{text}|{req.rate:.2f}|{spec['id']}".encode()).hexdigest()[:16]
    name = f"judul_{stamp}.wav"
    path = VOICE_DIR / name
    if not path.is_file():
        seconds = await asyncio.to_thread(tts.synthesize, text, path,
                                          rate=req.rate, voice=spec["id"])
    else:
        import wave

        with wave.open(str(path)) as w:
            seconds = w.getnframes() / float(w.getframerate() or 1)

    return {"url": f"/api/media/title_voice/{name}",
            "seconds": round(seconds, 3),
            "card_seconds": round(seconds + 0.55, 3)}


@router.get("/title-voice/status")
async def title_voice_status():
    """Apakah suara pembaca sudah siap, dan berapa besar bila belum."""
    from ..services import tts

    return {"available": tts.available() or tts.edge_available(),
            "local_ready": tts.available(),
            "voice": tts.VOICE_NAME, "size_mb": 63,
            "installed": tts.VOICE_PATH.is_file(),
            "voices": tts.catalogue()}


@router.post("/title-voice/install", status_code=202)
async def title_voice_install():
    """Mengunduh berkas suara. Tidak pernah terjadi diam-diam di tengah render."""
    job_id, created = queue.enqueue("tts_voice", {}, dedupe_key="tts_voice")
    return {"job_id": job_id, "created": created}


class RetitleRequest(BaseModel):
    video_id: str
    # Bawaannya hanya klip yang judulnya masih heuristik. Menulis ulang semuanya
    # berarti membuang judul Gemini yang sudah bagus dan sudah disunting tangan.
    only_weak: bool = True


@router.post("/clip-titles", status_code=202)
async def rewrite_clip_titles(req: RetitleRequest):
    """Menulis ulang judul dan tagar klip dengan Gemini, tanpa analisis ulang."""
    video_id = _resolve_video_id(req.video_id)
    job_id, created = queue.enqueue(
        "retitle", {"video_id": video_id, "only_weak": req.only_weak},
        video_id=video_id, dedupe_key=f"retitle:{video_id}",
    )
    return {"job_id": job_id, "created": created}


@router.post("/clip-preview")
async def clip_preview(req: ClipPreviewRequest):
    """
    Menghitung ulang subtitle setelah pengguna menggeser batas klip atau
    menggabungkan potongan dari menit lain.

    Perhitungannya hanya ada di satu tempat (backend) supaya subtitle yang
    dilihat di preview persis sama dengan yang nanti dibakar ke video.
    """
    from ..repos import transcripts as tx_repo
    from ..services.clipmodel import rebuild_subtitles_for_segments

    video_id = _resolve_video_id(req.video_id)
    stored = tx_repo.get_best(video_id)
    if not stored:
        raise NotFound("Video ini belum punya transkrip.")

    segments = [{"start": s.start, "end": s.end} for s in req.segments
                if s.end - s.start > 0.2]
    if not segments:
        raise NotFound("Rentang klip tidak valid.")

    subtitles, words = rebuild_subtitles_for_segments(segments, stored["words"])
    return {
        "segments": segments,
        "duration": round(sum(s["end"] - s["start"] for s in segments), 3),
        "subtitles": subtitles,
        "words": words,
    }


class RapatRequest(BaseModel):
    video_id: str
    segments: List[SegmentModel]
    gumaman: bool = True


@router.post("/clip-rapatkan")
async def clip_rapatkan(req: RapatRequest):
    """
    Membuang jeda dan gumaman dari sebuah klip, lalu mengembalikan segmen dan
    subtitle barunya.

    Hasilnya usulan, bukan perubahan: Studio yang menerapkannya, sehingga bisa
    dibatalkan seperti suntingan lain. Itu penting karena penilaian "jeda ini
    layak dibuang" tidak pernah bisa benar seratus persen — yang bisa dilakukan
    program adalah menunjukkan hasilnya dan membiarkan orangnya memutuskan.
    """
    import asyncio

    from ..repos import transcripts as tx_repo
    from ..services.clipmodel import rebuild_subtitles_for_segments
    from ..services.paths import find_local_video
    from ..services.rapat import rapatkan, ringkas

    video_id = _resolve_video_id(req.video_id)
    stored = tx_repo.get_best(video_id)
    if not stored:
        raise NotFound("Video ini belum punya transkrip, jadi jedanya tidak bisa diukur.")
    segments = [{"start": s.start, "end": s.end} for s in req.segments if s.end - s.start > 0.2]
    if not segments:
        raise NotFound("Rentang klip tidak valid.")
    durasi_lama = sum(s["end"] - s["start"] for s in segments)

    src = find_local_video(video_id)
    from ..services import suara
    sumber = (suara.tersimpan(src) or src) if src else None

    hasil = await asyncio.to_thread(rapatkan, segments, stored["words"],
                                    sumber=sumber, gumaman=req.gumaman)
    subtitles, words = rebuild_subtitles_for_segments(hasil["segments"], stored["words"])
    return {
        "segments": hasil["segments"],
        "subtitles": subtitles,
        "words": words,
        "duration": round(sum(s["end"] - s["start"] for s in hasil["segments"]), 3),
        "dibuang": hasil["dibuang"],
        "potongan": hasil["potongan"],
        "ditahan": hasil.get("ditahan", 0),
        "pesan": ringkas(hasil, durasi_lama),
    }


@router.post("/render-clip", status_code=202)
async def render_clip(req: RenderClipRequest):
    """Mengantrekan render dan mengembalikan job_id untuk dipantau lewat SSE."""
    video_id = _resolve_video_id(req.source_path)

    segments = (
        [{"start": s.start, "end": s.end} for s in req.segments]
        if req.segments
        else [{"start": req.start_seconds, "end": req.end_seconds}]
    )
    segments = [s for s in segments if s["end"] - s["start"] > 0.2]
    if not segments:
        raise NotFound("Rentang klip tidak valid.")

    job_id, created = queue.enqueue(
        "render",
        {
            "video_id": video_id,
            "segments": segments,
            "subtitles": req.subtitles,
            "aspect_ratio": req.aspect_ratio,
            "font_color": req.font_color,
            "font_size": req.font_size,
            "position": req.position,
            "hook_text": req.hook_text if req.show_hook else "",
            "watermark": req.watermark,
            "video_filter": req.video_filter,
            "title": req.title,
            "hashtags": req.hashtags,
            "frame_mode": req.frame_mode,
            "frame_motion": req.frame_motion,
            "lock_person": req.lock_person,
            "person_keys": [k.model_dump() for k in req.person_keys],
            "title_card": (req.title_card.model_dump() if req.title_card else None),
            "frame_layout": (req.frame_layout.model_dump()
                             if req.frame_layout else None),
            "frame_keys": [k.model_dump(exclude_none=True) for k in req.frame_keys],
            "media_layers": [l.model_dump(exclude_none=True) for l in req.media_layers],
            "subtitle_kedua": (req.subtitle_kedua.model_dump(exclude_none=True)
                               if req.subtitle_kedua else None),
            "clip_index": req.clip_index,
            "caption_style": (req.caption_style.model_dump(exclude_none=True)
                              if req.caption_style else None),
            # Pilihan unggah untuk render ini saja; None = setelan profil.
            "unggah": req.unggah,
        },
        video_id=video_id,
    )
    return {"job_id": job_id, "created": created, "video_id": video_id}


@router.get("/clips")
async def get_clips():
    from ..services import profil
    pid = profil.kini()
    kategori = profil.kategori_klip(pid)
    clips = list_local_clips(profil.folder_klip(pid))
    for c in clips:
        c["kategori"] = kategori
        c["web_url"] = f"/api/media/{kategori}/{c['file_name']}"
        # Subtitle dan sisipan tiap klip tidak ditampilkan di halaman ini, tapi
        # ikut terkirim: 357 KB untuk 51 klip, dan halaman ini dibuka tiap kali
        # pengguna kembali ke daftar. Keduanya ada di dalam `metadata`, dan
        # `metadata` itu milik cache daftar klip — jadi yang dikirim salinan
        # baru, bukan yang aslinya dikurangi. Berkas sidecar-nya tetap utuh.
        meta = c.get("metadata")
        if isinstance(meta, dict):
            c["metadata"] = {k: v for k, v in meta.items()
                             if k not in ("subtitles", "media_layers", "frame_layout")}
    return {"local_clips": clips}


@router.delete("/clips/{filename}")
async def delete_clip(filename: str):
    from ..services import profil
    path = safe_media_path(profil.kategori_klip(profil.kini()), filename)
    path.unlink()
    sidecar = path.with_suffix(".json")
    if sidecar.exists():
        sidecar.unlink()
    return {"success": True, "file_name": path.name}


class DiarizeRequest(BaseModel):
    video_id: str
    # None = biarkan sistem menebak sendiri; angka = pengguna sudah tahu
    # jumlahnya dan ingin sistem berhenti menebak.
    speakers: Optional[int] = Field(None, ge=1, le=8)


@router.post("/clip-speakers", status_code=202)
async def rediarize(req: DiarizeRequest):
    """
    Menandai ulang penutur pada analisis yang sudah ada.

    Dipisahkan dari pipeline utama supaya membetulkan jumlah narasumber tidak
    berarti mengunduh dan mentranskrip ulang video satu jam.
    """
    video_id = _resolve_video_id(req.video_id)
    job_id, created = queue.enqueue(
        "diarize",
        {"video_id": video_id, "speakers": req.speakers},
        video_id=video_id,
        dedupe_key=f"diarize:{video_id}:{req.speakers or 'auto'}",
    )
    return {"job_id": job_id, "created": created, "video_id": video_id}


class SaveClipsRequest(BaseModel):
    clips: List[Dict[str, Any]]


@router.put("/projects/{video_id}/clips")
async def save_clips(video_id: str, req: SaveClipsRequest):
    """
    Menyimpan susunan klip hasil suntingan pengguna.

    Dibutuhkan karena mesin otomatis pasti melewatkan momen: pengguna menonton
    videonya sendiri dan melihat bagian bagus yang tidak terpilih. Tanpa ini,
    klip yang ia potong sendiri hilang begitu halaman ditutup.
    """
    from ..repos import transcripts as tx_repo

    vid = _resolve_video_id(video_id)
    cached = analyses_repo.latest_for_video(vid)
    if not cached:
        raise NotFound("Belum ada analisis untuk video ini.")

    result = dict(cached["result"])
    # Nomor urut disusun ulang di server: klien boleh menambah dan menghapus di
    # tengah daftar, dan penomoran yang bolong akan ikut ke nama berkas.
    result["clips"] = [{**c, "index": i} for i, c in enumerate(req.clips, 1)]

    stored = tx_repo.get_best(vid)
    analyses_repo.save(
        video_id=vid, transcript_id=stored["id"] if stored else None,
        engine=result.get("engine", "heuristic"), model=result.get("model"),
        params={"user_edited": True, "clip_count": len(result["clips"])},
        result=result,
    )
    return {"success": True, "clip_count": len(result["clips"])}


class FacecamRequest(BaseModel):
    video_id: str
    segments: List[SegmentModel]


# Isi klip tidak berubah selama segmennya sama; Studio menanyakannya setiap
# kali klip dibuka.
_JENIS_CACHE: dict[tuple, dict] = {}


@router.post("/clip-jenis")
async def clip_jenis(req: FacecamRequest):
    """Bingkai bawaan untuk klip ini: game, ikuti gerakan, atau ikuti wajah."""
    import asyncio

    from ..services.paths import find_local_video
    from ..services.sutradara_ai import jenis_klip_tersimpan

    video_id = _resolve_video_id(req.video_id)
    segments = [{"start": round(s.start, 3), "end": round(s.end, 3)}
                for s in req.segments if s.end - s.start > 0.2]
    if not segments:
        raise NotFound("Rentang klip tidak valid.")
    key = (video_id, tuple((s["start"], s["end"]) for s in segments))
    if key in _JENIS_CACHE:
        return _JENIS_CACHE[key]
    src = find_local_video(video_id)
    if not src:
        raise NotFound("Video sumber belum diunduh.")
    hasil = await asyncio.to_thread(jenis_klip_tersimpan, video_id, src, segments)
    if len(_JENIS_CACHE) >= 200:
        _JENIS_CACHE.clear()
    _JENIS_CACHE[key] = hasil
    return hasil


@router.post("/clip-facecam")
async def clip_facecam(req: FacecamRequest):
    """
    Susunan dua bidang untuk klip gameplay, diturunkan dari videonya sendiri.

    Ada supaya "Main game" tidak menuntut penyetelan tangan sama sekali.
    Susunannya memang sederhana — reaksi pemain di atas, permainannya utuh di
    bawah — dan kedua letaknya tidak berpindah sepanjang video, jadi keduanya
    bisa ditemukan sekali lalu dipakai apa adanya.

    Dikembalikan dalam bentuk `frame_layout` supaya editor bisa langsung
    menaruhnya di panel Susun sendiri: pengguna melihatnya sebelum merender,
    dan bisa menggeser kotaknya kalau tebakannya meleset sedikit.
    """
    import asyncio

    from ..services.media import probe
    from ..services.paths import find_local_video
    from ..services.reframe import deteksi_facecam_waktu
    from ..services.render import rasio_bidang_wajah, susun_layout_gaming

    src = find_local_video(req.video_id)
    if not src:
        raise NotFound("Video sumber belum diunduh.")
    segs = [s.model_dump() for s in req.segments] or [{"start": 0.0, "end": 30.0}]

    def kerja():
        info = probe(str(src))
        w = int(info.get("width") or 1920)
        h = int(info.get("height") or 1080)
        posisi = deteksi_facecam_waktu(str(src), segs, w, h,
                                       rasio_potongan=rasio_bidang_wajah(1080, 1920))
        if not posisi:
            return {"ditemukan": False, "layout": None}
        return {"ditemukan": True, "facecam": posisi[0]["facecam"],
                "src_w": w, "src_h": h,
                "layout": susun_layout_gaming(posisi, src_w=w, src_h=h)}

    return await asyncio.to_thread(kerja)
