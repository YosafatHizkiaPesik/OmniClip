"""Channel, langganan, dan riwayat tontonan (JOB-3). Lihat services/channel.py."""

import asyncio
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ..errors import AppError, InvalidInput, NotFound
from ..services import channel as ch

router = APIRouter(prefix="/api", tags=["channel"])


def _pid() -> int:
    from ..services import profil
    return profil.kini()


@router.get("/channel/avatar")
async def avatar(ids: str = Query("", max_length=3000)):
    return {"channel": await asyncio.to_thread(ch.avatar, [i.strip() for i in ids.split(",") if i.strip()])}


@router.get("/channel/ikuti")
async def daftar_ikuti():
    return {"channel": await asyncio.to_thread(ch.diikuti, _pid())}


class IkutiModel(BaseModel):
    channel_id: str = Field(..., max_length=40)
    nama: str = Field("", max_length=120)
    avatar: str = Field("", max_length=600)


@router.post("/channel/ikuti")
async def ikuti(req: IkutiModel):
    try:
        return {"channel": await asyncio.to_thread(ch.ikuti, _pid(), req.channel_id, req.nama, req.avatar)}
    except ValueError as e:
        raise InvalidInput(str(e)) from e


@router.delete("/channel/ikuti/{channel_id}")
async def berhenti(channel_id: str):
    return {"channel": await asyncio.to_thread(ch.berhenti_ikuti, _pid(), channel_id)}


@router.get("/langganan")
async def langganan():
    return {"video": await asyncio.to_thread(ch.feed_langganan, _pid()),
            "channel": await asyncio.to_thread(ch.diikuti, _pid())}


@router.get("/riwayat-tonton")
async def riwayat():
    return {"video": await asyncio.to_thread(ch.riwayat, _pid())}


class TontonModel(BaseModel):
    id: str = Field(..., max_length=20)
    title: str = Field("", max_length=300)
    channel: str = Field("", max_length=150)
    channel_id: str = Field("", max_length=40)
    thumbnail: str = Field("", max_length=600)
    duration: Optional[float] = None
    views: Optional[int] = None


@router.post("/riwayat-tonton")
async def catat(req: TontonModel):
    try:
        await asyncio.to_thread(ch.catat_tonton, _pid(), req.model_dump())
    except ValueError as e:
        raise InvalidInput(str(e)) from e
    return {"ok": True}


@router.delete("/riwayat-tonton")
async def hapus(video_id: str = ""):
    return {"video": await asyncio.to_thread(ch.hapus_riwayat, _pid(), video_id)}


@router.get("/channel/{ref}")
async def halaman(ref: str, tab: str = "videos", urut: str = "terbaru", batas: int = 60):
    try:
        return await asyncio.to_thread(ch.halaman, ref, tab, urut, batas)
    except ValueError as e:
        raise InvalidInput(str(e)) from e
    except LookupError as e:
        raise NotFound(str(e)) from e
