"""Session event bus.

Each session has exactly one EventBus. Subscribers receive every event; the bus
maintains a small ring buffer so late-joining subscribers can backfill recent
history.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List


@dataclass
class Event:
    seq: int
    kind: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "event",
            "seq": self.seq,
            "kind": self.kind,
            "payload": self.payload,
            "ts": self.ts,
        }


class EventBus:
    """Asyncio-friendly pub/sub with bounded history."""

    def __init__(self, history: int = 256) -> None:
        self._seq = 0
        self._history: Deque[Event] = deque(maxlen=history)
        self._subscribers: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def publish(self, kind: str, payload: Dict[str, Any] | None = None) -> Event:
        async with self._lock:
            self._seq += 1
            event = Event(seq=self._seq, kind=kind, payload=payload or {})
            self._history.append(event)
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
        return event

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1024)
        async with self._lock:
            self._subscribers.append(q)
            for e in list(self._history):
                q.put_nowait(e)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)
