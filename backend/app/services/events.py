"""
Broker pub/sub in-memory yang memberi makan stream SSE.

Worker berjalan di thread biasa, sedangkan konsumen SSE adalah coroutine asyncio.
Jembatannya adalah `loop.call_soon_threadsafe`, jadi publish aman dipanggil dari
thread mana pun.
"""

import asyncio
import threading
from typing import Any, AsyncIterator, Optional


class EventBroker:
    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._subscribers: set[tuple[Optional[str], asyncio.Queue]] = set()
        self._lock = threading.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, job_id: str, event: dict[str, Any]) -> None:
        """Aman dipanggil dari worker thread."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        with self._lock:
            targets = [q for (want, q) in self._subscribers if want is None or want == job_id]
        for q in targets:
            try:
                loop.call_soon_threadsafe(q.put_nowait, event)
            except RuntimeError:
                pass  # loop sedang ditutup

    async def subscribe(self, job_id: Optional[str] = None) -> AsyncIterator[dict]:
        """job_id=None berlangganan semua job (untuk indikator job-center)."""
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        entry = (job_id, q)
        with self._lock:
            self._subscribers.add(entry)
        try:
            while True:
                yield await q.get()
        finally:
            with self._lock:
                self._subscribers.discard(entry)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)


broker = EventBroker()
