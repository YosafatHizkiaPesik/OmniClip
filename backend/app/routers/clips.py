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
    # short / medium / long — menentukan rentang durasi klip yang dicari.
    clip_length: str = "medium"
    # Perkiraan penutur dari warna suara. Menambah ~15 detik pada video panjang.
    diarize: bool = True
    speakers: Optional[int] = None      # None = tebak sendiri
    use_gemini: bool = True
    # Nama model Gemini pilihan pengguna; kosong = pakai urutan bawaan.
    gemini_model: Optional[str] = None
    force: bool = False  # abaikan hasil analisis yang sudah tersimpan


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
    # --- Tanda air: gayanya sendiri, bukan pinjaman dari subtitle ------------
    wm_font: Optional[str] = None
    wm_size: Optional[int] = Field(None, ge=8, le=400)
    wm_color: Optional[str] = None
    wm_opacity: Optional[float] = Field(None, ge=0.0, le=1.0)
    wm_x: Optional[float] = Field(None, ge=0.0, le=100.0)
    wm_y: Optional[float] = Field(None, ge=0.0, le=100.0)
    wm_outline: Optional[int] = Field(None, ge=0, le=16)

    @field_validator("primary", "highlight", "wm_color")
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


class FrameLayoutModel(BaseModel):
    background: str = "blur"
    # Delapan bingkai sudah jauh melewati apa pun yang masih terbaca di layar
    # ponsel, dan tiap bingkai menambah satu cabang skala di filtergraph.
    frames: List[FrameModel] = Field(default_factory=list, max_length=8)


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

    if not req.force:
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
            "clip_length": req.clip_length,
            "diarize": req.diarize,
            "speakers": req.speakers,
            "use_gemini": req.use_gemini,
            "gemini_model": req.gemini_model,
        },
        video_id=video_id,
        # Panjang klip ikut ke dalam kunci: meminta klip panjang untuk video
        # yang analisis pendeknya sedang berjalan adalah permintaan berbeda.
        dedupe_key=f"auto_clip:{video_id}:{req.clip_length}:{req.gemini_model or 'auto'}",
    )
    return {"job_id": job_id, "created": created, "cached": False, "video_id": video_id}


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
           req.frame_motion)
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
                                   frame_motion=req.frame_motion)
    if plan is None:
        payload = {"available": False, "reason": "unsupported"}
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
            "clip_index": req.clip_index,
            "caption_style": (req.caption_style.model_dump(exclude_none=True)
                              if req.caption_style else None),
        },
        video_id=video_id,
    )
    return {"job_id": job_id, "created": created, "video_id": video_id}


@router.get("/clips")
async def get_clips():
    clips = list_local_clips()
    for c in clips:
        c["web_url"] = f"/api/media/edited_clips/{c['file_name']}"
    return {"local_clips": clips}


@router.delete("/clips/{filename}")
async def delete_clip(filename: str):
    path = safe_media_path("edited_clips", filename)
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
