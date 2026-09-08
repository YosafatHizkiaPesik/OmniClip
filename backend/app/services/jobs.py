"""
Antrean job in-process dengan persistensi SQLite.

Kenapa bukan Celery/RQ + Redis: worker mereka adalah *proses* terpisah, jadi
setiap worker memuat model faster-whisper sendiri (300-900 MB). Dengan ~2,9 GB
RAM tersedia, itu selisih antara jalan dan OOM. Thread berbagi memori sehingga
satu model tetap hangat lintas job — dan hampir semua pekerjaan di sini melepas
GIL (yt-dlp network-bound, ffmpeg subprocess, ctranslate2 melepas GIL di loop
C++, numpy/OpenCV juga).

Kenapa bukan BackgroundTasks: mati bersama siklus request, tanpa progress,
tanpa pembatalan, tanpa persistensi.
"""

import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..config import JOB_PROGRESS_MIN_INTERVAL, LANE_LIMITS
from ..db import close_conn
from ..errors import JobCancelled
from ..repos import jobs as repo
from .events import broker

log = logging.getLogger("omniclip.jobs")


@dataclass
class JobContext:
    job_id: str
    type: str
    payload: dict
    queue: "JobQueue"
    _cancel: threading.Event
    _started: float = field(default_factory=time.time)
    _last_write: float = 0.0
    _last_stage: Optional[str] = None

    def progress(self, frac: float, *, stage: str | None = None,
                 message: str | None = None, eta: float | None = None) -> None:
        """
        Melaporkan kemajuan. Tulisan ke DB di-throttle (>=250 ms, dan selalu
        ditulis saat stage berubah) agar render yang memuntahkan puluhan baris
        progress per detik tidak menghantam SQLite. Stream SSE tidak di-throttle.
        """
        frac = max(0.0, min(1.0, frac))
        now = time.time()
        stage_changed = stage is not None and stage != self._last_stage

        if eta is None and frac > 0.02:
            elapsed = now - self._started
            eta = max(0.0, elapsed / frac - elapsed)

        # Emit hanya saat benar-benar menulis ke DB. `emit()` membaca ulang dari
        # DB, jadi memancarkan event di antara tulisan hanya akan mengirim nilai
        # lama yang identik — SSE terisi duplikat tanpa informasi baru.
        if stage_changed or (now - self._last_write) >= JOB_PROGRESS_MIN_INTERVAL:
            repo.update_progress(self.job_id, progress=frac, stage=stage,
                                 message=message, eta_seconds=eta)
            self._last_write = now
            if stage is not None:
                self._last_stage = stage
            self.queue.emit(self.job_id)

    def check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise JobCancelled()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def spawn_child(self, type_: str, payload: dict, *, lane: str = "cpu") -> str:
        job_id, _ = self.queue.enqueue(type_, payload, parent_id=self.job_id, lane=lane)
        return job_id


JobHandler = Callable[[JobContext], dict]


class JobQueue:
    def __init__(self) -> None:
        self._handlers: dict[str, tuple[JobHandler, str]] = {}
        self._threads: list[threading.Thread] = []
        self._wake: dict[str, threading.Event] = {}
        self._stop = threading.Event()
        self._cancels: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    # --- pendaftaran ---------------------------------------------------------
    def register(self, type_: str, handler: JobHandler, *, lane: str = "cpu") -> None:
        if lane not in LANE_LIMITS:
            raise ValueError(f"lane tidak dikenal: {lane}")
        self._handlers[type_] = (handler, lane)

    # --- siklus hidup --------------------------------------------------------
    def start(self) -> None:
        recovered = repo.recover_interrupted()
        if recovered:
            log.warning("%d job ditandai gagal karena backend berhenti di tengah jalan", recovered)

        for lane, count in LANE_LIMITS.items():
            self._wake[lane] = threading.Event()
            for i in range(count):
                t = threading.Thread(target=self._worker, args=(lane,),
                                     name=f"omniclip-{lane}-{i}", daemon=True)
                t.start()
                self._threads.append(t)
        log.info("JobQueue aktif: %s", ", ".join(f"{k}={v}" for k, v in LANE_LIMITS.items()))

    def stop(self, grace: float = 5.0) -> None:
        self._stop.set()
        for ev in self._wake.values():
            ev.set()
        with self._lock:
            for ev in self._cancels.values():
                ev.set()
        deadline = time.time() + grace
        for t in self._threads:
            t.join(timeout=max(0.1, deadline - time.time()))
        self._threads.clear()

    # --- API publik ----------------------------------------------------------
    def enqueue(self, type_: str, payload: dict, *, lane: str | None = None,
                priority: int = 100, parent_id: str | None = None,
                video_id: str | None = None, dedupe_key: str | None = None) -> tuple[str, bool]:
        if type_ not in self._handlers:
            raise ValueError(f"tidak ada handler untuk job '{type_}'")
        resolved_lane = lane or self._handlers[type_][1]
        job_id, created = repo.create(
            type_=type_, payload=payload, lane=resolved_lane, priority=priority,
            parent_id=parent_id, video_id=video_id, dedupe_key=dedupe_key,
        )
        if created:
            self._wake[resolved_lane].set()
            self.emit(job_id)
        return job_id, created

    def cancel(self, job_id: str) -> bool:
        ok = repo.request_cancel(job_id)
        with self._lock:
            ev = self._cancels.get(job_id)
        if ev is not None:
            ev.set()
        if ok:
            self.emit(job_id)
        return ok

    def get(self, job_id: str) -> Optional[dict]:
        return repo.get(job_id)

    def snapshot(self, job_id: str) -> Optional[dict]:
        """Bentuk event yang sama dipakai untuk SSE maupun polling."""
        job = repo.get(job_id)
        if job is None:
            return None
        kids = repo.children(job_id)
        return {
            "job_id": job["id"],
            "type": job["type"],
            "status": job["status"],
            "progress": job["progress"],
            "stage": job["stage"],
            "message": job["message"],
            "eta_seconds": job["eta_seconds"],
            "error": job["error"],
            "error_code": job["error_code"],
            "video_id": job["video_id"],
            "result": job["result"],
            "children": [
                {"id": k["id"], "type": k["type"], "status": k["status"],
                 "progress": k["progress"], "stage": k["stage"], "message": k["message"]}
                for k in kids
            ],
        }

    def emit(self, job_id: str) -> None:
        snap = self.snapshot(job_id)
        if snap is not None:
            broker.publish(job_id, snap)

    # --- worker --------------------------------------------------------------
    def _worker(self, lane: str) -> None:
        wake = self._wake[lane]
        try:
            while not self._stop.is_set():
                job = repo.claim_next(lane)
                if job is None:
                    wake.wait(timeout=1.0)
                    wake.clear()
                    continue
                self._run(job)
        finally:
            close_conn()

    def _run(self, job: dict) -> None:
        job_id = job["id"]
        handler, _ = self._handlers.get(job["type"], (None, None))

        if handler is None:
            repo.finish(job_id, status="failed",
                        error=f"Tidak ada handler untuk job '{job['type']}'.",
                        error_code="NO_HANDLER")
            self.emit(job_id)
            return

        cancel_ev = threading.Event()
        with self._lock:
            self._cancels[job_id] = cancel_ev

        ctx = JobContext(job_id=job_id, type=job["type"], payload=job["payload"],
                         queue=self, _cancel=cancel_ev)
        self.emit(job_id)

        try:
            result = handler(ctx)
            if cancel_ev.is_set():
                repo.finish(job_id, status="cancelled", error="Dibatalkan oleh pengguna.",
                            error_code="CANCELLED")
            else:
                repo.finish(job_id, status="done", result=result if isinstance(result, dict) else {})
        except JobCancelled:
            repo.finish(job_id, status="cancelled", error="Dibatalkan oleh pengguna.",
                        error_code="CANCELLED")
        except Exception as exc:
            log.error("Job %s (%s) gagal:\n%s", job_id, job["type"], traceback.format_exc())
            code = getattr(exc, "code", None) or type(exc).__name__
            message = getattr(exc, "message", None) or str(exc) or "Pekerjaan gagal."
            repo.finish(job_id, status="failed", error=message[:500], error_code=str(code)[:60])
        finally:
            with self._lock:
                self._cancels.pop(job_id, None)
            self.emit(job_id)


queue = JobQueue()
