"""Endpoint job: snapshot, pembatalan, dan stream progress SSE."""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..errors import NotFound
from ..repos import jobs as repo
from ..services.events import broker
from ..services.jobs import queue

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

KEEPALIVE_SECONDS = 15.0

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    # Menonaktifkan buffering di proxy; tanpa ini event bisa tertahan.
    "X-Accel-Buffering": "no",
}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _stream(request: Request, job_id: Optional[str]):
    """
    Snapshot dulu, baru delta.

    Tanpa snapshot awal, klien yang berlangganan setelah job mencapai 60% tidak
    melihat apa pun sampai tick berikutnya — dan job yang sudah selesai tidak
    akan pernah mengirim apa pun sama sekali.
    """
    if job_id:
        snap = queue.snapshot(job_id)
        if snap is None:
            raise NotFound("Job tidak ditemukan.")
        yield _sse(snap)
        if snap["status"] in ("done", "failed", "cancelled"):
            return
    else:
        for job in repo.active():
            snap = queue.snapshot(job["id"])
            if snap:
                yield _sse(snap)

    events = broker.subscribe(job_id)
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(anext(events), timeout=KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            except StopAsyncIteration:
                break

            yield _sse(event)
            if job_id and event.get("status") in ("done", "failed", "cancelled"):
                break
    finally:
        await events.aclose()


@router.get("/events")
async def stream_all_jobs(request: Request):
    """Stream semua job — untuk indikator job-center global."""
    return StreamingResponse(_stream(request, None), media_type="text/event-stream",
                             headers=SSE_HEADERS)


@router.get("/{job_id}/events")
async def stream_job(request: Request, job_id: str):
    return StreamingResponse(_stream(request, job_id), media_type="text/event-stream",
                             headers=SSE_HEADERS)


@router.get("/{job_id}")
async def get_job(job_id: str):
    snap = queue.snapshot(job_id)
    if snap is None:
        raise NotFound("Job tidak ditemukan.")
    return snap


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    if queue.get(job_id) is None:
        raise NotFound("Job tidak ditemukan.")
    cancelled = queue.cancel(job_id)
    return {"cancelled": cancelled, "job": queue.snapshot(job_id)}


@router.get("")
async def list_jobs(limit: int = 30):
    return repo.recent(min(limit, 100))


@router.post("/demo")
async def create_demo_job(steps: int = 20, delay: float = 0.25):
    """Job sintetis untuk memeriksa kesehatan antrean, progress, SSE, dan cancel."""
    job_id, created = queue.enqueue(
        "demo", {"steps": max(1, min(steps, 500)), "delay": max(0.01, min(delay, 5.0))}
    )
    return {"job_id": job_id, "created": created}
