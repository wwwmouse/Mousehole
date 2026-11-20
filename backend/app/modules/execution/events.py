from __future__ import annotations

import asyncio
import uuid
from typing import Any


class ExecutionEventBus:
    """In-process pub/sub for execution progress (SSE). Not an event store."""

    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, set[asyncio.Queue]] = {}

    def subscribe(self, execution_id: uuid.UUID) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(execution_id, set()).add(queue)
        return queue

    def unsubscribe(self, execution_id: uuid.UUID, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(execution_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(execution_id, None)

    def publish(self, execution_id: uuid.UUID, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(execution_id, ())):
            queue.put_nowait(event)


event_bus = ExecutionEventBus()
