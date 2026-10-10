"""Analisis auto-clip dan render klip."""

import asyncio
import contextlib
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import os
import logging
from pathlib import Path
import threading
import re
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from ..errors import AppError, InvalidInput, NotFound
from ..repos import analyses as analyses_repo
from ..repos import media as media_repo
from ..services.jobs import queue
from ..services.paths import (
    extract_id_from_filename,
    extract_youtube_id,
    safe_media_path,
)
from ..services.render import REAKSI_MAKS, list_local_clips

from ..services.ytdlp import RESOLUSI_BAWAAN

log = logging.getLogger("omniclip.clips")

router = APIRouter(prefix="/api", tags=["clips"])


class AutoClipRequest(BaseModel):
    video_id: str = Field(..., description="ID atau URL YouTube")
    # Bawaannya `RESOLUSI_BAWAAN` (1080p) — lihat alasannya di services/ytdlp.
    # Frontend tidak pernah mengirim field ini, jadi nilai inilah yang selalu
    # dipakai. Dulu "720p" (terlalu kecil: jendela 9:16-nya 405x720), lalu
    # "Terbaik" (terlalu besar: sampai 4 GB per video).
    quality: str = RESOLUSI_BAWAAN
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
    # Cara kata yang sedang diucapkan ditandai: warna saja, memantul, kotak
    # berwarna di belakangnya, nyala neon, atau garis bawah. Kosong berarti
    # diturunkan dari `animation` demi klip lama.
    sorot: Optional[str] = None
    kotak_warna: Optional[str] = None
    kotak_teks: Optional[str] = None
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
    # Jarak antar kata dalam satuan em. Batasnya sama dengan JARAK_KATA_MIN dan
    # JARAK_KATA_MAKS di services/subtitles.py.
    jarak_kata: Optional[float] = Field(None, ge=0.12, le=0.90)
    # Bayangan teks. Dipakai tema "Retro" (bayangan berwarna yang digeser), dan
    # sampai 25 September 2026 kedua bidangnya tidak ada di sini, jadi tema itu
    # dirender tanpa bayangan sama sekali. Pratinjaunya menampilkannya.
    shadow_px: Optional[int] = Field(None, ge=0, le=40)
    bayang_warna: Optional[str] = None
    # Batas pemenggalan baris. Belum ada di antarmuka, tapi diterima supaya
    # gaya yang datang dari luar tidak kehilangan nilainya diam-diam.
    max_words_per_line: Optional[int] = Field(None, ge=1, le=20)
    max_chars_per_line: Optional[int] = Field(None, ge=6, le=80)
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

    @field_validator("primary", "highlight", "wm_color", "bg_color", "bayang_warna")
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
    # Potongan PERMAINAN yang berlaku bersama letak wajah ini. Ada sejak
    # 7 Oktober 2026; klip lama tanpa medan ini memakai potongan tetap seperti
    # sebelumnya.
    main: Optional[FrameRectModel] = None
    # Panel facecam dan petak wajah di dalamnya, apa adanya dari pemindaian.
    # Editor memakainya untuk menghitung ulang potongan saat tinggi bidang
    # wajah digeser; tanpa dibawa di sini, keduanya hilang pada perjalanan
    # pulang-pergi lewat API dan editor kehilangan dasar hitungannya.
    kotak: Optional[FrameRectModel] = None
    muka: Optional[List[float]] = Field(None, max_length=4)


class FrameLayoutModel(BaseModel):
    background: str = "blur"
    # Main game: kotak wajah yang berpindah mengikuti facecam sepanjang klip,
    # dan setelan susunannya. Diabaikan oleh susunan biasa.
    reaksi: List[ReaksiModel] = Field(default_factory=list, max_length=REAKSI_MAKS)
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


class RectSisipanModel(BaseModel):
    """Petak sisipan dalam persen kanvas: (x, y) pojok kiri atas, lalu ukurannya."""

    x: float = Field(0.0, ge=0.0, le=100.0)
    y: float = Field(0.0, ge=0.0, le=100.0)
    # Minimal 2%: petak yang lebih kecil dari itu membulat jadi nol piksel pada
    # kanvas mana pun, dan filter dengan lebar nol menggagalkan seluruh render.
    w: float = Field(100.0, ge=2.0, le=100.0)
    h: float = Field(100.0, ge=2.0, le=100.0)


class MediaLayerModel(BaseModel):
    """Satu sisipan: berkas dari luar video sumber, ditempel pada waktunya."""

    # id aset dari /api/aset — BUKAN jalur berkas. Kosong untuk sisipan TEKS.
    #
    # Sampai 10 Oktober 2026 medan ini wajib dan medan teks di bawah tidak
    # ada, jadi setiap klip yang memakai sisipan "Tulisan" ditolak dengan 422
    # saat dirender, dan tulisannya sendiri dibuang pydantic sebelum sampai
    # ke `render._siapkan_teks`.
    aset: str = Field("", max_length=64)
    # Nama tampilan dan jenisnya, disimpan di sisipan supaya linimasa bisa
    # menggambarnya tanpa memuat pustaka aset lebih dulu.
    nama: Optional[str] = Field(None, max_length=120)
    jenis: Optional[str] = Field(None, max_length=16)
    t: float = Field(0.0, ge=0)
    # Kosong = sepanjang asetnya (dipotong di akhir klip).
    dur: Optional[float] = Field(None, gt=0, le=3600)
    mulai_sumber: float = Field(0.0, ge=0)
    # Preset lama. Tetap diterima, dan tetap dipakai oleh klip yang sudah
    # tersimpan sebelum `rect` ada; `rect` menang bila keduanya ada.
    posisi: Literal["penuh", "atas", "bawah", "tengah", "sudut"] = "penuh"
    # Petak bebas yang digambar pengguna di pratinjau, dalam PERSEN kanvas.
    # Persen, bukan piksel: klip yang sama bisa dirender 9:16 dan 4:5, dan
    # petak berpiksel akan pindah tempat di antara keduanya.
    rect: Optional[RectSisipanModel] = None
    # Cara isi petaknya: "penuh" memotong sisi yang kelebihan, "muat" memuat
    # utuh dengan ruang kosong di sisanya.
    isi: Optional[Literal["penuh", "muat"]] = None
    # Ketembusan 0..1. Berguna untuk tanda air dan lapisan tekstur.
    opasitas: float = Field(1.0, ge=0.0, le=1.0)
    # Lembut masuk dan keluar, dalam detik. Berlaku untuk gambar, video, dan
    # suara sekaligus; pada visual ia bekerja di saluran alfa, jadi yang
    # memudar adalah sisipannya, bukan gambar di bawahnya.
    fade_masuk: float = Field(0.0, ge=0.0, le=30.0)
    fade_keluar: float = Field(0.0, ge=0.0, le=30.0)
    # Berkas yang lebih pendek daripada petaknya diputar berulang.
    ulang: bool = False
    volume: float = Field(1.0, ge=0.0, le=2.0)
    # Musik latar mengecil sendiri saat orang bicara.
    redam: bool = False
    # Dari mana sisipan ini datang: "pengguna" atau "otomatis" (sutradara).
    asal: Optional[str] = Field(None, max_length=16)
    alasan: Optional[str] = Field(None, max_length=200)
    # Sisipan TEKS (jenis "teks"): tulisannya dan gayanya. Lihat
    # render._siapkan_teks untuk bawaan masing-masing.
    teks: Optional[str] = Field(None, max_length=400)
    ukuran: Optional[float] = Field(None, ge=1.0, le=40.0)
    keluarga: Optional[str] = Field(None, max_length=80)
    warna: Optional[str] = Field(None, max_length=32)
    garis: Optional[str] = Field(None, max_length=32)
    tebal_garis: Optional[float] = Field(None, ge=0.0, le=12.0)
    latar: Optional[str] = Field(None, max_length=32)

    @field_validator("teks")
    @classmethod
    def _teks_bersih(cls, v):
        return v.strip() if isinstance(v, str) else v

    def model_post_init(self, __context) -> None:
        if not self.aset and not (self.jenis == "teks" and self.teks):
            raise ValueError("Sisipan butuh aset, atau tulisan untuk sisipan teks.")


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


class JudulVideoModel(BaseModel):
    """
    Judul yang menempel DI DALAM video, sepanjang klip atau sebagian awalnya.

    Berbeda dari kartu judul: kartu berdiri di depan klip lalu hilang, judul
    ini berjalan bersama klipnya. Diminta pemiliknya: "jika saya ingin membuat
    judul selalu muncul di klip dimana opsinya". Sebelumnya yang ada hanya
    "hook", berwarna tetap, di letak tetap, dan hilang sesudah 3,5 detik.
    """
    aktif: bool = False
    teks: str = Field("", max_length=240)
    tema: str = Field("kartu-putih", max_length=40)
    pos_x: float = Field(50.0, ge=0.0, le=100.0)
    pos_y: float = Field(14.0, ge=0.0, le=100.0)
    box_w: float = Field(84.0, ge=10.0, le=100.0)
    ukuran: float = Field(72.0, ge=20.0, le=260.0)
    mulai: float = Field(0.0, ge=0.0)
    # Kosong = sampai akhir klip.
    durasi: Optional[float] = Field(None, gt=0.0, le=3600.0)


class KomentarKlipModel(BaseModel):
    """Satu komentar pemilik kanal (JOB-2 F1-3). Lihat services/komentar.py."""
    posisi: Literal["pembuka", "sela", "penutup"]
    # Waktu KLIP, hanya dibaca untuk `sela`.
    t: Optional[float] = Field(None, ge=0.0, le=7200.0)
    teks: str = Field("", max_length=600)
    # Id suara komentar (rekaman atau TTS), kosong = tanpa suara.
    suara: str = Field("", max_length=32)
    tampil_teks: Optional[bool] = None
    mode: Literal["bekukan", "timpa"] = "bekukan"


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
    # Perbesaran bingkai wajah dan geseran tegaknya. 1.0 dan 0 = seperti
    # sebelum setelan ini ada. Geser -100 menempel atas, 100 menempel bawah,
    # dan ruang untuk menggeser baru ada begitu bingkainya diperbesar.
    frame_zoom: float = Field(1.0, ge=1.0, le=2.0)
    frame_geser_y: float = Field(0.0, ge=-100.0, le=100.0)
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
    # Komentar pemilik kanal: pembuka, sela, penutup (JOB-2 F1-3).
    komentar: List[KomentarKlipModel] = Field(default_factory=list, max_length=6)
    # Sambungan antar potongan klip multi-segmen (JOB-2 F2-4).
    transisi: Literal["potong", "celup", "kilat"] = "potong"
    # Intro/outro kanal dari setelan akun (JOB-2 F2-5). False = klip ini tanpa.
    pakai_merek: bool = True
    # Subtitle kedua — biasanya terjemahan. Gayanya sendiri; divalidasi dengan
    # model yang sama dengan gaya subtitle utama, jadi warna tetap wajib hex.
    subtitle_kedua: Optional[SubtitleKeduaModel] = None
    # Mode ikut-wajah: orang yang ditunjuk pengguna. None = otomatis.
    lock_person: Optional[int] = Field(None, ge=0, le=7)
    person_keys: List[PersonKeyModel] = Field(default_factory=list)
    title_card: Optional[TitleCardModel] = None
    judul_video: Optional[JudulVideoModel] = None
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
    pid = profil.kini()
    profil_repo.tandai_video(pid, video_id)

    # Preferensi pengklipan MILIK AKUN ini dipakai untuk yang tidak dikirim.
    #
    # Sebelumnya ketiganya hanya ada di localStorage peramban, satu nilai untuk
    # semua akun. Dilaporkan 9 Oktober 2026: "tiap akun tidak memiliki
    # settingnya masing masing". Dibaca di SERVER, bukan hanya dikirim dari
    # satu halaman, supaya jalur mana pun yang memanggil auto-clip memakai
    # setelan akun yang sama: halaman unduhan, halaman tonton, dan pekerjaan
    # berjadwal.
    setelan_klip = profil_repo.setelan(pid, "klip")
    if not req.max_clips:
        req.max_clips = int(setelan_klip.get("max_clips") or 0)
    if req.whisper_model == "base" and setelan_klip.get("whisper_model"):
        req.whisper_model = str(setelan_klip["whisper_model"])
    if not req.gemini_model and setelan_klip.get("gemini_model"):
        req.gemini_model = str(setelan_klip["gemini_model"])

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
    if (await asyncio.to_thread(tx_repo.get_best, vid)):
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
    if not (await asyncio.to_thread(tx_repo.get_best, vid)):
        raise AppError("Video ini belum punya transkrip, jalankan klip otomatis dulu.",
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
    # Perbesaran bingkai wajah dan geseran tegaknya. 1.0 dan 0 = seperti
    # sebelum setelan ini ada. Geser -100 menempel atas, 100 menempel bawah,
    # dan ruang untuk menggeser baru ada begitu bingkainya diperbesar.
    frame_zoom: float = Field(1.0, ge=1.0, le=2.0)
    frame_geser_y: float = Field(0.0, ge=-100.0, le=100.0)
    # Yang dijejak: wajah manusia, atau pusat gerakan (kartun, hewan, gameplay).
    # Dulu pratinjau mode "Ikuti gerakan" tidak meminta apa pun ke sini — ia
    # hanya menggambar kotak diam di tengah, jadi tidak ada cara melihat apakah
    # bingkainya benar-benar mengikuti tokoh sebelum merender.
    subjek: Literal["wajah", "gerak"] = "wajah"


# Perencanaan reframe memakan beberapa detik per klip, sementara editor
# memintanya setiap kali pengguna berpindah klip. Hasilnya disimpan dua kali:
# di memori untuk perpindahan klip dalam satu sesi, dan di basis data supaya
# menutup aplikasi tidak berarti menunggu semuanya lagi dari nol.
#
# Simpanan di memori saja tidak cukup, dan itu yang dilaporkan: "ada beberapa
# yang langsung mengikuti wajah dan ada beberapa yang perlu menunggu lagi
# padahal pemrosesan sudah selesai". Yang cepat adalah klip yang kebetulan
# sudah pernah dibuka; sisanya dihitung ulang dari awal, dan hitungan itu
# hilang lagi setiap kali OmniClip dijalankan ulang.
_REFRAME_CACHE: dict[tuple, dict] = {}
_REFRAME_CACHE_MAX = 48

# Berapa pemindaian bingkai boleh berjalan BERSAMAAN, di seluruh aplikasi.
#
# Sampai 27 September 2026 tidak ada batasnya sama sekali untuk pemindaian yang
# diminta Studio: gerbang CPU hanya menjaga ANTREAN PEKERJAAN, dan permintaan
# HTTP tidak lewat sana. Terlihat pada laptop pemiliknya (Core i5-8250U 15 watt,
# RAM 7,6 GB): sembilan ffmpeg memindai bersamaan dari tiga video berbeda,
# masing-masing ~20% CPU, sebagian sudah hidup 171 detik. Suhu 93°C, beban 21,6
# dari 8 utas, swap 95% penuh — dan dari luar itu terasa sebagai "kipasnya
# kencang, lemot, sering tidak terhubung ke server".
#
# Satu, bukan dua: tiap pemindaian sendiri sudah memakai beberapa utas
# (`reframe.INTI_ANALISIS`), jadi menjalankan dua sekaligus tidak menyelesaikan
# apa pun lebih cepat pada mesin empat inti, ia hanya membuat keduanya lambat.
# Berapa lama pemindaian Studio bersedia menunggu pekerjaan latar minggir.
#
# Pemindaian yang diminta Studio tidak lewat antrean pekerjaan, jadi gerbang
# CPU tidak tahu ia ada — dan pemanasan bingkai yang sedang berjalan di latar
# TIDAK PERNAH minggir untuknya. Akibatnya dua pemindaian berat jalan
# bersamaan: ffmpeg enam utas dua kali, deteksi wajah dua kali. Terukur pada
# mesin ini (i5-8250U, 4 inti/8 utas, sama dengan laptop pemiliknya): beban
# rata-rata 9 dari 8 utas, ffmpeg 394% CPU. Dilaporkan sebagai "setelah saya
# membuka partitur, kipasnya menjadi kencang dan sistem mulai terputus".
#
# Sekarang pemindaian Studio ikut antre di gerbang yang sama — bukan untuk
# menunggu lama, melainkan supaya pemanasan TAHU ada yang menunggu lalu minggir
# di sela dua klip. Kalau dalam dua menit gilirannya belum datang, ia jalan
# saja: pengguna yang sedang menunggu klipnya terbuka tidak boleh disandera
# pekerjaan latar.
GILIRAN_CPU_BATAS = 120.0


@contextlib.contextmanager
def _giliran_cpu(batas: float = GILIRAN_CPU_BATAS):
    """Ikut antre di gerbang CPU supaya pekerjaan latar sempat minggir."""
    from ..services.jobs import gerbang_cpu

    dapat = False
    try:
        dapat = gerbang_cpu.acquire(timeout=batas)
    except Exception:                                # noqa: BLE001
        dapat = False
    try:
        yield dapat
    finally:
        if dapat:
            try:
                gerbang_cpu.release()
            except Exception:                        # noqa: BLE001
                pass


_PINDAI_BERSAMAAN = max(1, int(os.getenv("OMNICLIP_PINDAI_BERSAMAAN", "1")))
_GERBANG_PINDAI = threading.BoundedSemaphore(_PINDAI_BERSAMAAN)

# Kolam utas SENDIRI untuk pemindaian, terpisah dari kolam bersama.
#
# `asyncio.to_thread` memakai satu kolam untuk seluruh aplikasi, dan di mesin
# pemiliknya kolam itu berisi dua belas utas. Pemindaian yang menunggu giliran
# di `_GERBANG_PINDAI` tetap MEMEGANG utasnya selama menunggu, jadi belasan
# klip yang dibuka berturut-turut menghabiskan kolam itu — dan permintaan yang
# tidak ada hubungannya dengan pemindaian ikut antre di belakangnya.
#
# Terukur dan bisa ditirukan: dengan 14 pemindaian mengantre, `/api/projects`
# yang biasanya dijawab 26 milidetik butuh 26 DETIK. Itulah "Memuat daftar
# project..." yang berputar tanpa selesai pada laptop pemiliknya, dan dengan
# antrean yang lebih panjang ia memang tidak pernah selesai.
#
# Dengan kolam sendiri, pemindaian yang mengantre menunggu di dalam kolam ini,
# dan kolam bersama tetap kosong untuk halaman yang sedang dibuka orangnya.
_PINDAI_EXEC = ThreadPoolExecutor(max_workers=_PINDAI_BERSAMAAN,
                                  thread_name_prefix="omniclip-pindai")


async def _di_kolam_pindai(fn, /, *a, **kw):
    """Menjalankan pemindaian di kolam utasnya sendiri."""
    import functools
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_PINDAI_EXEC, functools.partial(fn, *a, **kw))

# Pemindaian yang sedang berjalan, supaya permintaan kembar MENUNGGU hasilnya
# alih-alih memindai ulang video yang sama. Terlihat pada laptop pemiliknya:
# dua ffmpeg dengan `-ss` dan `-t` yang sama persis, berjalan berdampingan.
_SEDANG_DIHITUNG: dict[tuple, threading.Event] = {}
_SEDANG_KUNCI = threading.Lock()

# Rencana wajah yang BARU SAJA dihitung, supaya pekerjaan berikutnya untuk klip
# yang sama tidak menghitungnya lagi.
#
# Membuka satu klip game memanggil dua pemindaian berturut-turut: `/clip-reframe`
# untuk jejak wajah, lalu `/clip-facecam` untuk letak kamera pemain. Yang kedua
# butuh rencana wajah yang sama persis, dan sampai 29 September 2026 ia
# menghitungnya sendiri dari nol: terukur sepuluh detik untuk jawaban yang sudah
# ada di memori sedetik sebelumnya. Dilaporkan pemiliknya sebagai "sangat lemot
# untuk melihat satu klip di studio".
#
# Hanya BEBERAPA yang terakhir: rencana membawa larik per sampel, dan menyimpan
# semuanya berarti memori yang tumbuh sepanjang sesi.
_PLAN_TERAKHIR: "OrderedDict[tuple, Any]" = OrderedDict()
_PLAN_MAKS = 3


def _kunci_plan(src: str, segments: list[dict]) -> tuple:
    return (str(src), tuple((round(float(x["start"]), 3), round(float(x["end"]), 3))
                            for x in segments))


def _ingat_plan(src: str, segments: list[dict], plan) -> None:
    if plan is None:
        return
    _PLAN_TERAKHIR[_kunci_plan(src, segments)] = plan
    while len(_PLAN_TERAKHIR) > _PLAN_MAKS:
        _PLAN_TERAKHIR.popitem(last=False)


# Versi rencana bingkai. Dinaikkan setiap kali CARA menghitungnya berubah.
#
# Tanpa ini, perbaikan pada penghalus tidak pernah sampai ke klip yang sudah
# pernah dibuka: kuncinya hanya berisi permintaan, jadi rencana lama dipakai
# ulang selamanya dan satu-satunya cara melihat perbaikannya adalah menghapus
# seluruh simpanan. Dilewatkan sekali pada 9 Oktober 2026, saat potongan
# adegan dikecualikan dari jeda antar batas di `reframe._smooth`.
BINGKAI_VERSI = 4


def _kunci_reframe(key: tuple) -> str:
    import hashlib
    return ("bingkai:" + hashlib.sha1(
        f"{key!r}|v{BINGKAI_VERSI}".encode()).hexdigest())


def rencana_tersimpan(*, video_id: str, segments: list[dict], aspect_ratio: str = "9:16",
                      turns: tuple = (), subjek: str = "wajah") -> bool:
    """
    Apakah rencana bingkai klip ini BENAR-BENAR ada di simpanan.

    Dipakai penjadwal pemanasan untuk memastikan "sudah pernah selesai" berarti
    hasilnya masih ada. Kuncinya dibangun dengan cara yang sama persis dengan
    `hitung_reframe`, karena kunci yang sedikit berbeda akan menjawab "tidak
    ada" untuk rencana yang sebenarnya ada.
    """
    key = (video_id, aspect_ratio,
           tuple((s["start"], s["end"]) for s in segments),
           tuple(turns), None, (), "smooth", subjek)
    return _reframe_tersimpan(key) is not None


def _reframe_tersimpan(key: tuple):
    """Rencana yang sudah pernah dihitung, dari memori lalu dari basis data."""
    if key in _REFRAME_CACHE:
        return _REFRAME_CACHE[key]
    from ..repos import cache as cache_repo
    try:
        # Isi sebuah potongan video tidak pernah basi, jadi tidak ada TTL.
        simpan = cache_repo.ambil(_kunci_reframe(key), ttl=float("inf"))
    except Exception:
        return None
    if simpan is not None:
        _simpan_memori(key, simpan)
    return simpan


def _simpan_memori(key: tuple, payload: dict) -> None:
    if len(_REFRAME_CACHE) >= _REFRAME_CACHE_MAX:
        _REFRAME_CACHE.pop(next(iter(_REFRAME_CACHE)), None)
    _REFRAME_CACHE[key] = payload


def _simpan_reframe(key: tuple, payload: dict) -> None:
    _simpan_memori(key, payload)
    from ..repos import cache as cache_repo
    try:
        cache_repo.simpan(_kunci_reframe(key), payload)
    except Exception:           # simpanan yang gagal bukan alasan menggagalkan
        pass


def hitung_reframe(*, video_id: str, segments: list[dict], aspect_ratio: str = "9:16",
                   turns: tuple = (), lock_person=None, person_keys=(),
                   frame_motion: str = "smooth", subjek: str = "wajah") -> dict:
    """
    Rencana crop yang mengikuti wajah, untuk digambar di pratinjau editor.

    Tanpa ini pratinjau menampilkan frame 16:9 apa adanya, sehingga pengguna
    tidak punya cara melihat bagaimana hasil 9:16-nya nanti membingkai
    pembicara: satu-satunya cara mengetahuinya adalah dengan merender.

    Bentuknya sinkron karena dua pemanggil membutuhkannya. Endpoint di bawah
    menjalankannya di utas terpisah saat editor meminta satu klip; job
    pemanasan menjalankannya lebih awal untuk SELURUH klip sebuah video,
    supaya membuka klip keenam tidak terasa berbeda dari membuka klip pertama.
    """
    turns = tuple(turns)
    person_keys = list(person_keys)
    # Bawaan `frame_motion` dulu `False`, sebuah BOOL, sementara endpoint di
    # bawah meneruskan `"smooth"` atau `"cut"` dari Studio. `plan_reframe` hanya
    # memeriksa `== "cut"`, jadi hasilnya sama-sama benar — tapi keduanya masuk
    # ke KUNCI SIMPANAN, dan `False` bukan `"smooth"`.
    #
    # Akibatnya pemanasan bingkai menghitung rencana yang benar untuk semua
    # klip, menyimpannya, lalu Studio memintanya dengan kunci yang lain dan
    # menghitungnya lagi dari nol. Pemanasan itu tidak pernah sekalipun
    # menolong, dan itulah "sudah menunggu beberapa menit, satu klip pun
    # bingkainya belum tersusun" yang dilaporkan pemiliknya. Terukur sesudah
    # bawaannya disamakan: 26,6 detik jadi milidetik.
    key = (video_id, aspect_ratio,
           tuple((s["start"], s["end"]) for s in segments),
           turns, lock_person,
           tuple((round(float(k["t"]), 3), k["person"]) for k in person_keys),
           frame_motion, subjek)
    sudah = _reframe_tersimpan(key)
    if sudah is not None:
        return sudah

    # Permintaan kembar menunggu yang pertama, bukan memindai ulang.
    with _SEDANG_KUNCI:
        menunggu = _SEDANG_DIHITUNG.get(key)
        if menunggu is None:
            selesai = threading.Event()
            _SEDANG_DIHITUNG[key] = selesai
        else:
            selesai = None
    if selesai is None:
        # Batas waktunya longgar: pemindaian klip panjang pada mesin pelan bisa
        # semenit lebih, dan menyerah lebih awal berarti memindai dua kali,
        # persis yang sedang dihindari.
        menunggu.wait(timeout=600)
        sudah = _reframe_tersimpan(key)
        if sudah is not None:
            return sudah
        # Yang pertama gagal atau kehabisan waktu; hitung sendiri.
        return _hitung_reframe_sekarang(
            video_id=video_id, segments=segments, aspect_ratio=aspect_ratio,
            turns=turns, lock_person=lock_person, person_keys=person_keys,
            frame_motion=frame_motion, subjek=subjek, key=key)
    try:
        return _hitung_reframe_sekarang(
            video_id=video_id, segments=segments, aspect_ratio=aspect_ratio,
            turns=turns, lock_person=lock_person, person_keys=person_keys,
            frame_motion=frame_motion, subjek=subjek, key=key)
    finally:
        with _SEDANG_KUNCI:
            _SEDANG_DIHITUNG.pop(key, None)
        selesai.set()


def _hitung_reframe_sekarang(*, video_id: str, segments: list[dict], aspect_ratio: str,
                             turns: tuple, lock_person, person_keys,
                             frame_motion: str, subjek: str, key: tuple) -> dict:
    """Pemindaian sebenarnya, satu per satu (lihat `_GERBANG_PINDAI`)."""
    from ..services.paths import find_local_video
    from ..services.reframe import SAMPLE_FPS, plan_reframe

    source = find_local_video(video_id)
    if source is None:
        raise NotFound("Video sumber belum diunduh.")

    # track_only: jejaknya juga dipakai bingkai buatan pengguna, yang lebar
    # jendelanya tidak diturunkan dari rasio kanvas. Tanpa itu, video yang
    # sumbernya sudah tegak dijawab "tidak tersedia" padahal bingkai sempit di
    # dalamnya masih punya ruang untuk bergeser.
    # Satu pemindaian pada satu waktu, seluruh aplikasi. Lihat `_GERBANG_PINDAI`.
    with _GERBANG_PINDAI, _giliran_cpu():
        # Diperiksa lagi sesudah menunggu giliran: selama antre, yang di depan
        # bisa saja sudah menghitung persis rencana ini.
        sudah = _reframe_tersimpan(key)
        if sudah is not None:
            return sudah
        plan = plan_reframe(str(source), segments, aspect_ratio=aspect_ratio,
                            track_only=True, speaker_turns=list(turns),
                            lock_person=lock_person, person_keys=person_keys,
                            frame_motion=frame_motion, subjek=subjek)
        # Disimpan untuk `/clip-facecam` yang datang sedetik kemudian.
        if subjek == "wajah" and not person_keys and lock_person is None:
            _ingat_plan(str(source), segments, plan)
    if plan is None:
        payload = {"available": False,
                   "reason": "no_motion" if subjek == "gerak" else "unsupported"}
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

    _simpan_reframe(key, payload)
    return payload


def _buang_kunci_otomatis(video_id: str) -> int:
    """
    Membuang kunci bingkai bikinan mesin dari semua klip video ini.

    Mengembalikan jumlah klip yang berubah. Kunci buatan pengguna — yang
    `asal`-nya bukan "otomatis" maupun "ai" — tidak pernah disentuh, dan satu
    saja kunci seperti itu membuat seluruh klipnya dilewati: setengah susunan
    pengguna lebih buruk daripada susunan yang utuh.
    """
    cached = analyses_repo.latest_for_video(video_id)
    if not cached:
        return 0
    hasil = dict(cached["result"] or {})
    klip = list(hasil.get("clips") or [])
    n = 0
    for i, c in enumerate(klip):
        kunci = [k for k in (c.get("frame_keys") or []) if isinstance(k, dict)]
        if not kunci:
            continue
        if any((k.get("asal") or "pengguna") not in ("otomatis", "ai") for k in kunci):
            continue
        klip[i] = {**c, "frame_keys": []}
        n += 1
    if n:
        hasil["clips"] = klip
        analyses_repo.replace_result(cached["id"], hasil)
    return n


@router.post("/projects/{video_id}/siapkan-bingkai", status_code=202)
async def siapkan_bingkai(video_id: str, ulang: bool = False):
    """
    Menghitung bingkai semua klip video ini SEKARANG, tanpa mengulang auto-klip.

    Pemanasan biasanya berjalan sendiri sesudah auto-klip. Video yang sudah
    terlanjur diklip sebelum sakelarnya dinyalakan, atau yang pemanasannya
    gagal, tidak punya jalan lain selain "Cari ulang" yang memakan jatah AI dan
    mengganti seluruh daftar klipnya. Tombol ini yang menutup celah itu.
    """
    vid = _resolve_video_id(video_id)
    cached = analyses_repo.latest_for_video(vid)
    if not cached:
        raise NotFound("Belum ada analisis untuk video ini.")
    klip = (cached["result"] or {}).get("clips") or []
    if not klip:
        raise InvalidInput("Video ini belum punya klip yang bisa disiapkan.")

    # `ulang`: simpanan dibuang LEBIH DULU, supaya pemanasan benar-benar
    # menghitung. Tanpa itu ia membaca simpanan yang sama dan selesai dalam
    # 0,06 detik — tombolnya terlihat tidak mengerjakan apa pun. Hanya tombol
    # "hitung ulang dari nol" yang meminta ini; "Siapkan bingkai" biasa tetap
    # memakai simpanan, karena itu memang gunanya.
    if ulang:
        dibuang = _buang_simpanan_bingkai(vid)
        # Hanya milik video INI yang dibuang dari simpanan di memori. Kuncinya
        # (video_id, segmen), jadi menyaringnya mudah — dan mengosongkan
        # seluruh simpanan berarti klip video LAIN ikut menghitung ulang
        # penggolongan yang memakan 10-60 detik, padahal jawabannya masih sah.
        for k in [k for k in _JENIS_CACHE if k and k[0] == vid]:
            _JENIS_CACHE.pop(k, None)
        # Kunci bingkai OTOMATIS ikut dibuang.
        #
        # Sejak pemanasan menuliskan susunannya sendiri ke klip, simpanan yang
        # dibuang saja tidak cukup: `_tulis_bingkai` melewati klip yang sudah
        # punya kunci, jadi hitung-ulang akan memindai lagi dari nol lalu
        # menyimpan hasilnya ke tempat yang tidak pernah dibaca. Yang terlihat:
        # tombolnya bekerja belasan menit dan tidak ada yang berubah.
        #
        # Hanya yang `asal`-nya otomatis. Kunci buatan pengguna tidak pernah
        # disentuh, aturan yang sama dengan yang dipakai Studio.
        dikosongkan = _buang_kunci_otomatis(vid)
        log.info("Hitung ulang bingkai %s: %d simpanan dibuang, %d klip dikosongkan",
                 vid, dibuang, dikosongkan)

    from ..services.pipeline import _jadwalkan_jejak_sekarang
    # `paksa`: yang menekan tombolnya sudah menyatakan maunya untuk video ini,
    # dan sakelar pemanasan otomatis (bawaannya mati) tidak boleh membatalkannya.
    job_id = _jadwalkan_jejak_sekarang(vid, klip,
                                       (cached["result"] or {}).get("aspect_ratio"),
                                       paksa=True)
    if not job_id:
        # Pesannya dulu selalu "sedang berjalan", padahal kosongnya `job_id`
        # juga berarti "daftar klip ini sudah pernah selesai dipanaskan". Dua
        # keadaan yang menuntut tindakan berbeda diberi satu kalimat yang
        # hanya benar untuk salah satunya.
        raise InvalidInput(
            "Bingkai video ini sudah pernah dihitung, atau perhitungannya sedang "
            "berjalan. Pakai tombol hitung ulang kalau ingin memaksanya dari nol.")
    return {"job_id": job_id, "klip": len(klip)}


@router.post("/clip-reframe")
async def clip_reframe(req: ReframePlanRequest):
    """Rencana bingkai untuk satu klip, diminta editor saat klip dibuka."""
    import asyncio

    video_id = _resolve_video_id(req.video_id)
    segments = [{"start": round(s.start, 3), "end": round(s.end, 3)}
                for s in req.segments if s.end - s.start > 0.2]
    if not segments:
        raise NotFound("Rentang klip tidak valid.")
    # Bentuk gilirannya diambil dari satu pembantu bersama, yang dipakai juga
    # oleh pemanasan bingkai. Giliran ini bagian dari kunci simpanan rencana,
    # jadi dua cara menuliskannya berarti dua kunci untuk klip yang sama.
    from ..services.clipmodel import giliran_bicara
    turns = giliran_bicara(req.subtitles or [])
    return await _di_kolam_pindai(
        hitung_reframe, video_id=video_id, segments=segments,
        aspect_ratio=req.aspect_ratio, turns=turns,
        lock_person=req.lock_person,
        person_keys=[k.model_dump() for k in req.person_keys],
        frame_motion=req.frame_motion, subjek=req.subjek)


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
    stored = (await asyncio.to_thread(tx_repo.get_best, video_id))
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
    stored = (await asyncio.to_thread(tx_repo.get_best, video_id))
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


class TerbitRequest(BaseModel):
    clip_name: str
    platform: str
    sudah: bool = True


@router.post("/clip-terbit")
async def clip_terbit(req: TerbitRequest):
    """
    Menandai bahwa klip ini sudah diterbitkan ke sebuah platform.

    Ditulis ke sidecar klipnya sendiri, bukan ke basis data: penandanya milik
    berkas itu, dan harus ikut ke mana pun berkasnya disalin. Ini yang
    mencegah klip yang sama naik dua kali ke tempat yang sama — kesalahan
    yang paling mudah terjadi saat mengunggah dengan tangan.
    """
    import json as _json

    from ..services import keterangan as kt
    from ..services import profil
    from ..services.paths import safe_media_path

    if req.platform not in kt.PLATFORM:
        raise InvalidInput(f"Platform '{req.platform}' tidak dikenali.")
    jalur = safe_media_path(profil.kategori_klip(profil.kini()), req.clip_name)
    sidecar = jalur.with_suffix(".json")
    try:
        meta = _json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.is_file() else {}
    except (OSError, _json.JSONDecodeError):
        meta = {}
    terbit = [p for p in (meta.get("terbit") or []) if p != req.platform]
    if req.sudah:
        terbit.append(req.platform)
    meta["terbit"] = terbit
    sidecar.write_text(_json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    # Daftar klip dibaca dari cache berbasis waktu ubah folder; sidecar yang
    # berubah tidak mengubahnya, jadi cachenya dikosongkan di sini.
    from ..services import render as render_svc
    render_svc._DAFTAR_KLIP = None
    return {"status": "ok", "terbit": terbit}


class KeteranganRequest(BaseModel):
    clip_name: str
    pakai_ai: bool = True
    # True = tulis ulang, walau sudah pernah disusun. Dipakai tombol "tulis
    # ulang" saat captionnya kurang pas.
    segarkan: bool = False


def kunci_tema(video_id: str, meta: dict) -> str:
    """
    Kunci simpanan untuk pilihan tema sebuah klip.

    Dipakai dua pemanggil, dan harus SAMA PERSIS di keduanya: endpoint saat
    tombolnya ditekan, dan job pemanasan yang menyiapkan jawabannya lebih awal.
    Kunci yang berbeda sedikit saja membuat pemanasannya menghitung sesuatu yang
    tidak pernah dibaca siapa pun.
    """
    import hashlib

    from ..services import tema as tema_svc

    baris = (meta.get("subtitles") or [])[:60]
    sidik = hashlib.sha1(
        (video_id + "|" + str(meta.get("title") or "") + "|"
         + str(meta.get("jenis") or "") + "|"
         + "|".join(f"{l.get('start')}:{(l.get('text') or '')[:40]}" for l in baris)
         ).encode()
    ).hexdigest()[:16]
    return f"tema:{tema_svc.VERSI}:{sidik}"


class GayaRequest(BaseModel):
    """Klip yang temanya ingin dipilihkan. Isinya datang dari editor."""
    video_id: str = Field(..., max_length=200)
    title: str = Field("", max_length=300)
    duration: float = Field(0.0, ge=0)
    jenis: str = Field("", max_length=32)
    subtitles: list[dict] = Field(default_factory=list)
    pakai_ai: bool = True
    segarkan: bool = False


@router.post("/clip-gaya")
async def clip_gaya(req: GayaRequest):
    """
    Tema subtitle yang cocok untuk satu klip, dipilih dari isinya.

    Yang dikembalikan hanya id tema dan alasannya. Wujud tiap tema tinggal di
    antarmuka, dan antarmuka yang menerapkannya, supaya tidak ada dua tempat
    yang menyimpan rupa yang sama dan perlahan berbeda.

    Disimpan per (klip, versi tema): menekan tombol yang sama dua kali tidak
    memanggil model dua kali, dan kuota Gemini terbatas.
    """
    import asyncio
    import hashlib

    from ..config import get_api_key, get_model_override
    from ..repos import cache as cache_repo
    from ..services import tema as tema_svc
    from ..services.peringkat_model import rantai

    vid = _resolve_video_id(req.video_id)
    meta = {"title": req.title, "duration": req.duration, "jenis": req.jenis,
            "subtitles": req.subtitles}
    kunci = kunci_tema(vid, meta)

    if not req.segarkan:
        try:
            simpan = cache_repo.ambil(kunci, ttl=float("inf"))
        except Exception:
            simpan = None
        if simpan:
            return {**simpan, "dari_simpanan": True}

    key = get_api_key() or ""
    hasil = await asyncio.to_thread(
        tema_svc.pilih, meta, api_key=key,
        models=rantai(key, get_model_override() or None) if key else [],
        pakai_ai=req.pakai_ai)
    try:
        cache_repo.simpan(kunci, hasil)
    except Exception:
        pass
    return {**hasil, "dari_simpanan": False}


@router.get("/tema-subtitle")
async def daftar_tema():
    """Daftar tema beserta untuk klip seperti apa masing-masing cocok."""
    from ..services import tema as tema_svc
    return {"tema": tema_svc.TEMA, "bawaan": tema_svc.BAWAAN}


@router.post("/clip-keterangan")
async def clip_keterangan(req: KeteranganRequest):
    """
    Caption dan tagar siap tempel untuk satu klip yang sudah jadi.

    Dihitung dari sidecar klipnya (judul, subtitle, durasi), bukan dari yang
    dikirim peramban — supaya yang jadi caption benar-benar isi klip itu, dan
    supaya hasilnya sama siapa pun yang memintanya.

    Disimpan sesudahnya: menekan tombol yang sama dua kali tidak memanggil
    model dua kali.
    """
    import asyncio
    import json as _json

    from ..config import get_api_key, get_model_override
    from ..repos import cache as cache_repo
    from ..services import keterangan as kt
    from ..services import profil
    from ..services.paths import safe_media_path
    from ..services.peringkat_model import rantai

    jalur = safe_media_path(profil.kategori_klip(profil.kini()), req.clip_name)
    sidecar = jalur.with_suffix(".json")
    if not sidecar.is_file():
        raise NotFound("Klip ini tidak punya catatan isinya, jadi captionnya "
                       "tidak bisa disusun.")
    try:
        meta = _json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError) as e:
        raise NotFound("Catatan klip ini tidak terbaca.") from e

    # Judul dan kanal video sumber ikut, karena keduanya konteks yang tidak ada
    # di dalam klipnya sendiri.
    vid = meta.get("video_id") or ""
    if vid:
        video = media_repo.get_video(vid) or {}
        meta.setdefault("video_title", video.get("title") or "")
        meta.setdefault("channel", video.get("channel") or "")

    kunci = f"keterangan:{req.clip_name}:v{kt.VERSI}:{'ai' if req.pakai_ai else 'lokal'}"
    tersimpan = None if req.segarkan else cache_repo.ambil(kunci, ttl=30 * 24 * 3600)
    if tersimpan:
        return {**tersimpan, "dari_simpanan": True}

    api_key = get_api_key() if req.pakai_ai else ""
    hasil = await asyncio.to_thread(
        kt.paket, meta, api_key=api_key,
        models=rantai(api_key, get_model_override() or None) if api_key else [],
        pakai_ai=req.pakai_ai)
    cache_repo.simpan(kunci, hasil)
    return {**hasil, "dari_simpanan": False}


class BarisKomentar(BaseModel):
    start: float
    end: float
    text: str = Field("", max_length=600)


class KomentarRequest(BaseModel):
    video_id: str = Field("", max_length=64)
    title: str = Field("", max_length=300)
    konteks: str = Field("", max_length=1000)
    duration: float = Field(0, ge=0, le=7200)
    subtitles: List[BarisKomentar] = Field(default_factory=list, max_length=600)
    # True = tulis ulang walau sudah pernah disusun untuk isi yang sama.
    segarkan: bool = False


@router.post("/clip-komentar")
async def clip_komentar(req: KomentarRequest):
    """
    Draf komentar pemilik kanal untuk satu klip di Studio (JOB-2 F1-2).

    Diambil dari yang sedang dilihat di Studio, bukan dari klip jadi: komentar
    ditulis SEBELUM render, dan subtitle di Studio sudah mengikuti batas klip
    yang mungkin digeser orangnya.

    Disimpan menurut isinya. Klip yang sama dengan gaya yang sama tidak
    memanggil model dua kali; begitu batasnya digeser, isinya berubah dan
    drafnya disusun ulang.
    """
    import hashlib
    import json as _json

    from ..config import get_api_key, get_model_override
    from ..repos import cache as cache_repo
    from ..repos import profil as profil_repo
    from ..services import komentar as km
    from ..services import profil
    from ..services.peringkat_model import rantai

    gaya = str((profil_repo.setelan(profil.kini(), "komentar") or {}).get("gaya") or "")[:300]
    klip = {
        "title": req.title, "konteks": req.konteks, "duration": req.duration,
        "subtitles": [b.model_dump() for b in req.subtitles],
    }
    if req.video_id:
        video = media_repo.get_video(req.video_id) or {}
        klip["video_title"] = video.get("title") or ""
        klip["channel"] = video.get("channel") or ""

    sidik = hashlib.sha1(_json.dumps([klip, gaya], sort_keys=True,
                                     ensure_ascii=False).encode("utf-8")).hexdigest()
    kunci = f"komentar:v{km.VERSI}:{sidik}"
    tersimpan = None if req.segarkan else cache_repo.ambil(kunci, ttl=30 * 24 * 3600)
    if tersimpan:
        return {**tersimpan, "dari_simpanan": True}

    api_key = get_api_key()
    hasil = await asyncio.to_thread(
        km.draf, klip, api_key=api_key,
        models=rantai(api_key, get_model_override() or None) if api_key else [],
        gaya=gaya)
    # Draf kosong tidak disimpan: penyebabnya (kuota, kunci belum diisi)
    # biasanya hilang sendiri, dan menekan tombolnya lagi harus mencoba lagi.
    if hasil.get("sumber"):
        cache_repo.simpan(kunci, hasil)
    return {**hasil, "dari_simpanan": False}


class PeriksaFypRequest(BaseModel):
    clip_name: str = Field(..., max_length=400)


@router.post("/clip-periksa")
async def clip_periksa(req: PeriksaFypRequest):
    """
    Daftar periksa sebelum unggah: hal-hal yang diketahui membuat penonton pergi.

    Bukan ramalan jangkauan, dan jawabannya mengatakan itu sendiri. Dihitung
    dari sidecar klipnya, tanpa model dan tanpa jaringan — jadi ia tidak
    memakan kuota dan tidak pernah membuat orang menunggu.
    """
    import json as _json

    from ..services import fyp
    from ..services import profil
    from ..services.paths import safe_media_path

    jalur = safe_media_path(profil.kategori_klip(profil.kini()), req.clip_name)
    sidecar = jalur.with_suffix(".json")
    if not sidecar.is_file():
        raise NotFound("Klip ini tidak punya catatan isinya, jadi tidak ada yang "
                       "bisa diperiksa.")
    try:
        meta = _json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError) as e:
        raise NotFound("Catatan klip ini tidak terbaca.") from e
    return fyp.periksa(meta)


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
            "frame_zoom": req.frame_zoom,
            "frame_geser_y": req.frame_geser_y,
            "lock_person": req.lock_person,
            "person_keys": [k.model_dump() for k in req.person_keys],
            "title_card": (req.title_card.model_dump() if req.title_card else None),
            "judul_video": (req.judul_video.model_dump() if req.judul_video else None),
            "frame_layout": (req.frame_layout.model_dump()
                             if req.frame_layout else None),
            "frame_keys": [k.model_dump(exclude_none=True) for k in req.frame_keys],
            "media_layers": [l.model_dump(exclude_none=True) for l in req.media_layers],
            "komentar": [k.model_dump(exclude_none=True) for k in req.komentar],
            "transisi": req.transisi,
            "pakai_merek": req.pakai_merek,
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


# Berapa kali penghapusan dicoba ulang, dan jedanya.
#
# Windows menolak menghapus berkas yang MASIH DIBUKA siapa pun, dan di sini
# yang membukanya hampir selalu aplikasi ini sendiri: tiap kartu di Klip jadi
# memasang sebuah <video> yang menarik berkasnya lewat /api/media, dan
# pemindai antivirus memegangnya beberapa detik lagi sesudah itu ditutup.
# Jedanya pendek dan beberapa kali, karena pegangan seperti itu lepas sendiri.
HAPUS_PERCOBAAN = 6
HAPUS_JEDA = 0.4


def _buang_berkas(path) -> None:
    """Menghapus klip beserta catatannya, sabar terhadap kuncian sesaat."""
    import time as _time

    galat = None
    for i in range(HAPUS_PERCOBAAN):
        try:
            path.unlink(missing_ok=True)
            galat = None
            break
        except PermissionError as e:              # Windows: berkas sedang dibuka
            galat = e
            _time.sleep(HAPUS_JEDA * (i + 1))
        except OSError as e:
            galat = e
            break
    if galat is not None:
        raise AppError(
            "Berkas klip ini sedang dipakai program lain, jadi belum bisa "
            "dihapus. Biasanya pemutar video di halaman ini sendiri atau "
            "pemindai antivirus. Tutup pratinjaunya, tunggu sebentar, lalu "
            "coba lagi.",
            code="KLIP_TERKUNCI", status=409) from galat
    try:
        path.with_suffix(".json").unlink(missing_ok=True)
    except OSError:
        # Catatan yang tertinggal tidak merugikan siapa pun; videonya sudah
        # hilang, dan itu yang diminta.
        pass


@router.delete("/clips/{filename}")
async def delete_clip(filename: str):
    """
    Menghapus satu klip jadi.

    DI UTAS LAIN, dan itu bukan kerapian: `unlink` pada cakram luar yang sedang
    sibuk melayani pemutar video bisa menahan gelung peristiwa beberapa detik,
    dan selama itu SELURUH server berhenti menjawab. Yang dilihat pengguna lalu
    "tidak bisa terhubung ke server" — dilaporkan pemiliknya 7 Oktober 2026 —
    padahal yang terjadi cuma satu berkas yang lambat dihapus.
    """
    from ..services import profil
    path = safe_media_path(profil.kategori_klip(profil.kini()), filename)
    await asyncio.to_thread(_buang_berkas, path)
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

    stored = (await asyncio.to_thread(tx_repo.get_best, vid))
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
    hasil = await _di_kolam_pindai(jenis_klip_tersimpan, video_id, src, segments)
    # Yang paling lama masuk dibuang SATU, bukan semuanya. Mengosongkan 200
    # entri sekaligus berarti tiap klip sesudah yang ke-200 menghitung ulang
    # penggolongan yang memakan 10-60 detik, padahal 199 jawaban di antaranya
    # masih sah.
    if len(_JENIS_CACHE) >= 200:
        _JENIS_CACHE.pop(next(iter(_JENIS_CACHE)), None)
    _JENIS_CACHE[key] = hasil
    return hasil


# Dinaikkan setiap kali CARA facecam dipindai berubah, supaya hasil lama tidak
# dipakai lagi. Simpanan ini sengaja tanpa batas umur, jadi tanpa nomor ini
# perbaikan pemindainya tidak akan pernah terlihat pada video yang sudah pernah
# dipindai. v2: wajah dikelompokkan per panel dan jendelanya 4 detik, supaya
# video multi-POV terbaca (27 September 2026). v3: jendelanya 2 detik, dan
# hasilnya ikut membawa `potongan` — bagian klip yang bingkainya berbeda
# (29 September 2026). Tanpa naik ke v3, hasil lama yang tidak punya
# `potongan` tetap dipakai dan Studio tidak pernah melihat pemecahannya.
# v10 (7 Oktober 2026): klip panjang dipindai dengan cuplikan, panel
# distabilkan terhadap dirinya sendiri, dan potongan "hanya wajah" dibidik dari
# ukuran wajahnya, bukan setinggi bingkai penuh.
# v11 (8 Oktober 2026): panel yang timpang diluruskan ke wajahnya, dan panel
# yang wajahnya hilang lebih dari tiga detik dianggap tidak ada — dua perubahan
# yang mengubah HASIL pemindaian, jadi simpanan lama tidak boleh dipakai lagi.
FACECAM_VERSI = 11


def _kunci_facecam(video_id: str, segments: list[dict]) -> str:
    """Kunci simpanan facecam: video plus batas tiap potongannya."""
    import hashlib

    tanda = ";".join(f"{float(s['start']):.3f}-{float(s['end']):.3f}" for s in segments)
    # Nomor videonya ikut di kuncinya, bukan hanya di dalam sidiknya.
    #
    # Tanpa itu simpanan sebuah video tidak bisa dibuang tanpa membuang
    # simpanan SEMUA video, dan tombol "hitung ulang dari nol" karena itu tidak
    # pernah benar-benar menghitung dari nol — ia memanggil pemanasan yang
    # membaca simpanan yang sama lalu selesai dalam 0,06 detik. Terlihat
    # langsung pemiliknya 1 Oktober 2026: tidak ada bilah kemajuan yang muncul,
    # dan bingkainya tidak berubah.
    return (f"facecam:{video_id}:"
            + hashlib.sha1(f"{tanda}|v{FACECAM_VERSI}".encode()).hexdigest()[:24])


def _buang_simpanan_bingkai(video_id: str) -> int:
    """
    Membuang SEMUA simpanan bingkai milik satu video: letak facecam dan
    penggolongan jenis klipnya.

    Dipakai tombol "hitung ulang dari nol". Tanpa ini tombol itu hanya
    mengantrekan pekerjaan yang membaca simpanan yang sama.
    """
    from ..db import get_conn

    try:
        cur = get_conn().execute(
            "DELETE FROM search_cache WHERE cache_key LIKE ? OR cache_key LIKE ?",
            (f"facecam:{video_id}:%", f"jenis:%:{video_id}:%"))
        return cur.rowcount or 0
    except Exception as e:                           # noqa: BLE001
        log.warning("Simpanan bingkai %s tidak bisa dibuang: %s", video_id, str(e)[:160])
        return 0


def _facecam_tersimpan(video_id: str, segments: list[dict]):
    """
    Hasil PEMINDAIAN facecam untuk potongan yang sama persis.

    Sampai 25 September 2026 endpoint ini tidak punya simpanan apa pun, jadi
    SETIAP klip yang dibuka memindai ulang videonya, dan menutup aplikasi
    menghapus seluruhnya. Pada video gameplay 1 jam 45 menit berisi 28 klip,
    itu berarti dua puluh delapan kali pemindaian, tiap kali orangnya menunggu
    di depan layar. Terlapor: "sudah menunggu beberapa menit, satu klip pun
    bingkainya belum tersusun".

    Isi sebuah potongan video tidak pernah basi, jadi tidak ada TTL.

    Yang disimpan hanya letak panel facecam-nya, BUKAN susunan jadinya.
    Sebelumnya susunan ikut tersimpan, dan begitu aturan susunannya berubah —
    misalnya batas tinggi bidang wajah turun dari 50% ke 40% — klip yang pernah
    dibuka tetap memakai susunan lama selamanya. Terlihat saat mengujinya: satu
    video masih 47,5% padahal batas barunya 40%. Pemindaian itu yang mahal
    (23,9 detik); menyusun ulang dari kotak yang sudah ada hampir tanpa biaya.
    """
    from ..repos import cache as cache_repo
    try:
        return cache_repo.ambil(_kunci_facecam(video_id, segments), ttl=float("inf"))
    except Exception:                                # noqa: BLE001
        return None


def _simpan_facecam(video_id: str, segments: list[dict], payload: dict) -> None:
    from ..repos import cache as cache_repo
    try:
        cache_repo.simpan(_kunci_facecam(video_id, segments), payload)
    except Exception:           # simpanan yang gagal bukan alasan menggagalkan
        pass


def _layout_bidikan(tata: dict, r: dict, *, src_w: int, src_h: int,
                    out_w: int, out_h: int) -> dict:
    """
    Susunan untuk SATU bidikan: bidang permainan milik seluruh klip, bidang
    wajah milik bidikan ini.

    Bidang permainan sengaja tidak dihitung ulang. Tinggi dan potongannya tetap
    sama sepanjang klip, supaya permainan tidak melompat tiap kali bidikan
    berganti; yang boleh berubah hanya bidang wajahnya, karena tiap POV menaruh
    panel facecam dengan bentuk yang berbeda.

    Dipanggil dua kali: saat potongan dihitung, dan saat simpanan lama dibaca.
    Yang kedua penting — simpanan menyimpan susunan yang sudah dipanggang, jadi
    tanpa ini aturan bidang wajah yang baru tidak pernah sampai ke klip yang
    sudah pernah dipindai, kecuali dengan memindai ulang videonya.
    """
    from ..services.render import susun_layout_gaming

    satu = dict(tata)
    satu["reaksi"] = [{**r, "t": 0.0}]
    bingkai = [dict(f) for f in (tata.get("frames") or [])]
    if not r.get("kotak") or len(bingkai) < 2:
        satu["frames"] = bingkai
        return satu
    panel = {**r["kotak"], "awan_kotak": r.get("muka")}
    gaming = tata.get("gaming") or {}
    sendiri = susun_layout_gaming(
        [{"t": 0.0, "facecam": panel}], src_w=src_w, src_h=src_h,
        out_w=out_w, out_h=out_h, wajah=gaming.get("wajah"),
        permainan=gaming.get("permainan") or "isi")
    if len(sendiri.get("frames") or []) > 1:
        bingkai[1] = dict(sendiri["frames"][1])
        satu["reaksi"] = [{**sendiri["reaksi"][0], "t": 0.0}]
    satu["frames"] = bingkai
    return satu


def _potongan_game(src: str, segments: list[dict],
                   posisi: Optional[list] = None) -> list[dict]:
    """
    Klip game dipecah menurut ISINYA: bagian mana permainan, bagian mana wajah.

    Video gameplay jarang permainan dari awal sampai akhir. Bagian pembuka dan
    penutup sering wajah SATU LAYAR PENUH, orangnya bicara ke kamera. Susunan
    dua bidang di situ salah: bidang wajah menyorot dinding di belakangnya dan
    wajahnya sendiri terdorong ke bidang permainan. Terlihat pada render klip
    skor 98 milik pemiliknya, detik 3 dan 12 dari 47.

    Perhitungannya sudah ada dan sudah dipakai jalur Sutradara AI
    (`sutradara_ai._dasar_per_waktu`); yang kurang hanyalah memakainya tanpa AI.
    Kegagalan di sini bukan kegagalan: tanpa potongan, Studio memakai satu
    susunan untuk seluruh klip seperti sebelumnya.
    """
    try:
        from ..services.render import PLAY_RES
        from ..services.reframe import plan_reframe
        from ..services.sutradara_ai import _dasar_per_waktu

        durasi = sum(float(s["end"]) - float(s["start"]) for s in segments)
        # Rencana wajah yang baru saja dihitung `/clip-reframe` dipakai ulang.
        # Menghitungnya lagi memakan sepuluh detik untuk jawaban yang sama.
        plan = _PLAN_TERAKHIR.get(_kunci_plan(src, segments))
        if plan is None:
            plan = plan_reframe(src, segments, aspect_ratio="9:16", track_only=True)
        if plan is None or not plan.people:
            return []
        out_w, out_h = PLAY_RES.get("9:16", (1080, 1920))
        potongan = _dasar_per_waktu(plan, Path(src), segments, durasi, out_w, out_h,
                                    facecam_waktu=posisi)
        sw, sh = plan.source_w, plan.source_h
    except Exception as e:                           # noqa: BLE001
        log.info("Potongan bingkai game tidak terbaca: %s", str(e)[:160])
        return []
    keluar: list[dict] = []
    for a, b, d in potongan:
        mode = d.get("mode") or "gaming"
        tata = d.get("layout")
        posisi = (tata or {}).get("reaksi") or []
        # Potongan game DIPECAH LAGI di tiap perpindahan facecam.
        #
        # Diminta pemiliknya sesudah mengukur sendiri berapa banyak yang
        # meleset: "buat agar timelinenya terpotong setiap ada perpindahan
        # bingkai agar saya bisa menyesuaikan secara manual ukuran dan letaknya
        # serta lamanya". Itu jalan keluar yang benar. Pelacakan otomatis
        # terukur 88,7% tepat pada klipnya, dan sisanya berkumpul persis di
        # sekitar pergantian POV — yang paling menolong bukan mengejar seratus
        # persen, melainkan memberi tiap bidikan satu kunci yang bisa diseret.
        if mode == "gaming" and len(posisi) > 1:
            for i, r in enumerate(posisi):
                mulai = float(a) + float(r.get("t") or 0.0)
                henti = (float(a) + float(posisi[i + 1]["t"])) if i + 1 < len(posisi) else float(b)
                if henti - mulai < 0.35:
                    continue
                # Tiap kunci membawa SATU letak facecam, jadi menyeretnya di
                # Studio hanya mengubah bidikan itu, bukan seluruh klip.
                #
                # Susunannya dihitung ULANG untuk bidikan ini, bukan disalin
                # dari susunan seluruh klip: lebar bidang wajah mengikuti bentuk
                # panel facecam, dan tiap POV menaruh panelnya dengan bentuk
                # yang berbeda. Menyalin satu susunan untuk semuanya berarti
                # sebagian bidikan memakai bidang yang bentuknya milik bidikan
                # lain.
                satu = _layout_bidikan(tata, r, src_w=sw, src_h=sh,
                                       out_w=out_w, out_h=out_h)
                keluar.append({"t": round(mulai, 2), "akhir": round(henti, 2),
                               "mode": mode, "alasan": d.get("alasan") or "",
                               "layout": satu})
            continue
        keluar.append({"t": round(float(a), 2), "akhir": round(float(b), 2),
                       "mode": mode, "alasan": d.get("alasan") or "",
                       "layout": tata})
    # Satu potongan berarti tidak ada yang berubah; biarkan jalur lama.
    return keluar if len(keluar) > 1 else []


@router.get("/clip-bingkai/kemajuan")
async def kemajuan_bingkai():
    """
    Kemajuan pemindaian bingkai yang SEDANG berjalan, dalam hitungan sungguhan.

    Diminta pemiliknya 7 Oktober 2026: bilah kemajuan di Studio sebelumnya
    perkiraan (`6 + 0,36 x panjang klip`), dan sesudah pemindaiannya dipercepat
    perkiraan itu meleset jauh — menyebut empat menit untuk pekerjaan empat
    puluh detik.

    Yang dijawab di sini: tahap apa yang sedang berjalan, langkah keberapa dari
    berapa, dan sudah berapa lama. Jawaban yang BASI (lebih dari lima detik
    tanpa kabar baru) ditandai `segar: false`, supaya layar tidak menampilkan
    angka dari pemindaian yang sudah selesai.
    """
    import time as _t

    from ..services.reframe import kemajuan_pindai

    k = kemajuan_pindai()
    umur = _t.time() - float(k.get("pada") or 0)
    total = float(k.get("total") or 1)
    selesai = float(k.get("selesai") or 0)
    return {
        "tahap": k.get("tahap") or "",
        "selesai": selesai,
        "total": total,
        "persen": max(0.0, min(1.0, selesai / total)) if total else 0.0,
        "umur": round(umur, 1),
        "segar": bool(k.get("tahap")) and umur < 5.0,
    }


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
    from ..services.render import PLAY_RES, rasio_bidang_wajah, susun_layout_gaming

    out_w, out_h = PLAY_RES.get("9:16", (1080, 1920))
    src = find_local_video(req.video_id)
    if not src:
        raise NotFound("Video sumber belum diunduh.")
    segs = [s.model_dump() for s in req.segments] or [{"start": 0.0, "end": 30.0}]

    def susun(pindai: dict) -> dict:
        """Kotak facecam -> jawaban lengkap. Selalu dihitung ulang, tidak disimpan."""
        posisi = pindai.get("posisi") or []
        if not posisi:
            return {"ditemukan": False, "layout": None}
        w, h = int(pindai["src_w"]), int(pindai["src_h"])
        tata = susun_layout_gaming(posisi, src_w=w, src_h=h)
        # Susunan tiap bidikan DIHITUNG ULANG dari simpanan, bukan dibaca apa
        # adanya: yang disimpan hanyalah letak facecam dan batas waktunya, dan
        # aturan bidang wajah masih bisa berubah sesudah simpanan itu dibuat.
        potongan = []
        for bagian in (pindai.get("potongan") or []):
            tiap = dict(bagian)
            r = ((bagian.get("layout") or {}).get("reaksi") or [None])[0]
            if bagian.get("mode") == "gaming" and r:
                tiap["layout"] = _layout_bidikan(tata, r, src_w=w, src_h=h,
                                                 out_w=out_w, out_h=out_h)
            potongan.append(tiap)
        return {"ditemukan": True, "facecam": posisi[0]["facecam"],
                "src_w": w, "src_h": h, "layout": tata,
                # Bagian-bagian klip yang bingkainya BERBEDA. Lihat `_potongan_game`.
                "potongan": potongan}

    tersimpan = _facecam_tersimpan(req.video_id, segs)
    if tersimpan is not None and "posisi" in tersimpan:
        # Simpanan yang belum punya `potongan` DILENGKAPI, bukan dipakai apa
        # adanya.
        #
        # Ada dua penulis simpanan ini: endpoint ini, dan pemanasan bingkai di
        # services/bingkai_awal.py. Yang kedua hanya memindai letak facecam dan
        # menyimpannya tanpa pemecahan klip. Jadi video yang bingkainya sempat
        # dipanaskan lebih dulu membuat Studio membaca simpanan tanpa
        # `potongan`, dan lajur Bingkai tidak pernah terpotong sama sekali.
        # Terlapor pemiliknya 29 September 2026, dan terbukti: simpanan untuk
        # klipnya hanya berisi posisi, src_w, src_h.
        #
        # Bedanya "belum pernah dihitung" dan "sudah dihitung, hasilnya kosong"
        # dijaga: kunci yang TIDAK ADA berarti yang pertama, daftar kosong
        # berarti yang kedua.
        if "potongan" not in tersimpan:
            lengkap = dict(tersimpan)
            lengkap["potongan"] = await _di_kolam_pindai(
                _potongan_game, str(src), segs, tersimpan.get("posisi") or [])
            _simpan_facecam(req.video_id, segs, lengkap)
            return susun(lengkap)
        return susun(tersimpan)

    def kerja():
        info = probe(str(src))
        w = int(info.get("width") or 1920)
        h = int(info.get("height") or 1080)
        # Ikut antre di gerbang CPU: lihat `_giliran_cpu`. Tanpa ini,
        # pemindaian ini dan pemanasan bingkai di latar berjalan bersamaan,
        # dan mesin empat inti kehabisan napas untuk keduanya.
        with _giliran_cpu():
            posisi = deteksi_facecam_waktu(str(src), segs, w, h,
                                           rasio_potongan=rasio_bidang_wajah(1080, 1920))
            return {"posisi": posisi or [], "src_w": w, "src_h": h,
                    "potongan": _potongan_game(str(src), segs, posisi)}

    pindai = await _di_kolam_pindai(kerja)
    _simpan_facecam(req.video_id, segs, pindai)
    return susun(pindai)
