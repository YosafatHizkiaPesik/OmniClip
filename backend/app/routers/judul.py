"""
Judul bertema: daftar temanya, dan gambar pratinjaunya.

Gambar pratinjau dibuat oleh libass, mesin yang SAMA dengan yang membakar
judul ke MP4. Bukan ditiru dengan CSS: CSS dan libass mengukur huruf dengan
cara yang berbeda (terukur, Montserrat ukuran 100 selebar 436 piksel di libass
tapi 688 bila diartikan sebagai em seperti CSS), dan judul yang di pratinjau
berbeda dari hasil render baru ketahuan sesudah render sepuluh menit selesai.
"""

import asyncio
import hashlib
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..config import FONTS_DIR
from ..errors import AppError
from ..services import tema_judul

log = logging.getLogger("omniclip.judul")
router = APIRouter(prefix="/api/judul", tags=["judul"])

# Gambar yang sudah dibuat disimpan di sini, dinamai sidik parameternya. Menyeret
# penggeser ukuran membuat puluhan permintaan untuk nilai yang sama berulang.
_SIMPANAN = Path(tempfile.gettempdir()) / "omniclip-judul"
_SIMPANAN_MAKS = 400

# Kanvas pratinjau: separuh ukuran keluaran. Cukup tajam untuk kotak pratinjau
# yang tingginya jarang lewat 800 piksel, dan empat kali lebih murah digambar.
_KANVAS = {"9:16": (540, 960), "16:9": (960, 540), "1:1": (720, 720), "4:5": (640, 800)}

_KEPALA = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


@router.get("/tema")
async def daftar_tema():
    """Tema yang tersedia, untuk galeri pilihan."""
    return {"tema": [{"id": t.id, "label": t.label, "catatan": t.catatan,
                      "gerak": t.gerak, "latar": t.latar}
                     for t in tema_judul.TEMA.values()],
            "bawaan": tema_judul.BAWAAN}


class GambarRequest(BaseModel):
    tema: str = Field(tema_judul.BAWAAN, max_length=40)
    teks: str = Field(..., max_length=240)
    pos_x: float = Field(50.0, ge=0, le=100)
    pos_y: float = Field(22.0, ge=0, le=100)
    box_w: float = Field(84.0, ge=10, le=100)
    ukuran: float = Field(96.0, ge=20, le=260)
    aspek: Literal["9:16", "16:9", "1:1", "4:5"] = "9:16"


@router.post("/gambar")
async def gambar(req: GambarRequest):
    """
    Judul bertema sebagai PNG tembus pandang seukuran kanvas pratinjau.

    Seukuran KANVAS, bukan dipotong ke judulnya: pratinjau cukup merentangkannya
    di atas video, dan letaknya otomatis benar, termasuk tema pita yang
    memang selebar layar.
    """
    if req.tema not in tema_judul.TEMA:
        raise AppError("Tema judul tidak dikenal.", code="TEMA_TIDAK_ADA", status=422)
    w, h = _KANVAS[req.aspek]
    kunci = hashlib.sha1(repr((req.model_dump(), w, h, _VERSI)).encode()).hexdigest()[:20]
    berkas = _SIMPANAN / f"{kunci}.png"
    if not berkas.is_file():
        ok = await asyncio.to_thread(_gambar, req, w, h, berkas)
        if not ok:
            raise AppError("Judul gagal digambar.", code="JUDUL_GAGAL", status=500)
    return Response(berkas.read_bytes(), media_type="image/png",
                    headers={"Cache-Control": "private, max-age=3600"})


# Dinaikkan setiap kali rupa tema berubah, supaya gambar lama tidak dipakai lagi.
_VERSI = 2


def _gambar(req: GambarRequest, w: int, h: int, berkas: Path) -> bool:
    """
    Menggambar judul ke PNG tembus pandang.

    Filter `ass` ffmpeg mencampur warna judul ke kanvas tapi TIDAK menulis kanal
    alfanya, digambar di atas kanvas tembus, hasilnya tetap tembus seluruhnya
    (terlihat pada percobaan pertama: PNG 14 KB yang kosong). Jadi judulnya
    digambar dua kali, di atas hitam dan di atas putih, dan alfanya dihitung dari
    selisih keduanya: piksel yang tertutup penuh sama di kedua latar, piksel
    yang tembus berbeda sebesar 255. Tepat untuk tepi yang halus sekalipun.
    """
    import numpy as np

    _SIMPANAN.mkdir(parents=True, exist_ok=True)
    baris = tema_judul.ass_judul(
        req.tema, req.teks, mulai=0.0, akhir=5.0, pos_x=req.pos_x, pos_y=req.pos_y,
        box_w=req.box_w, ukuran=req.ukuran, out_w=w, out_h=h, dengan_gerak=False)
    ass = berkas.with_suffix(".ass")
    ass.write_text(_KEPALA.format(w=w, h=h) + "\n".join(baris) + "\n", encoding="utf-8")
    jalur_ass = str(ass).replace("\\", "/").replace(":", "\\:")
    jalur_fon = str(FONTS_DIR).replace("\\", "/").replace(":", "\\:")

    def render(warna: str) -> "np.ndarray | None":
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c={warna}:s={w}x{h}:d=1",
             "-vf", f"ass='{jalur_ass}':fontsdir='{jalur_fon}'",
             "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True)
        if r.returncode != 0 or len(r.stdout) != w * h * 3:
            log.warning("Judul gagal digambar: %s", r.stderr[-300:].decode("utf-8", "replace"))
            return None
        return np.frombuffer(r.stdout, dtype=np.uint8).reshape(h, w, 3).astype(np.float32)

    try:
        hitam, putih = render("black"), render("white")
    finally:
        ass.unlink(missing_ok=True)
    if hitam is None or putih is None:
        return False
    alfa = 1.0 - (putih - hitam).mean(axis=2) / 255.0
    alfa = np.clip(alfa, 0.0, 1.0)
    warna = np.where(alfa[..., None] > 1e-3, hitam / np.maximum(alfa[..., None], 1e-3), 0.0)
    rgba = np.dstack([np.clip(warna, 0, 255), alfa * 255.0]).astype(np.uint8)
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{w}x{h}", "-i", "-", "-frames:v", "1", str(berkas)],
        input=rgba.tobytes(), capture_output=True)
    if r.returncode != 0:
        log.warning("PNG judul gagal ditulis: %s", r.stderr[-300:].decode("utf-8", "replace"))
        return False
    _pangkas_simpanan()
    return True


def _pangkas_simpanan() -> None:
    try:
        ada = sorted(_SIMPANAN.glob("*.png"), key=lambda p: p.stat().st_mtime)
        for p in ada[:-_SIMPANAN_MAKS]:
            p.unlink(missing_ok=True)
    except OSError:
        pass
