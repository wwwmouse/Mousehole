from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Callable

from sqlalchemy.orm import sessionmaker

from app.modules.execution.pipeline import run_execution

logger = logging.getLogger("mousehole.execution")

ModelStream = Callable[..., AsyncIterator[dict]]


class ExecutionScheduler:
    """Lightweight in-process scheduler: FIFO queue, bounded concurrency.

    PostgreSQL remains the source of truth; pending executions are re-queued on
    startup by the recovery routine, and stale running executions are failed.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue | None = None
        self._workers: list[asyncio.Task] = []
        self._cancelled: set[uuid.UUID] = set()
        self._session_factory: sessionmaker | None = None
        self._model_stream: ModelStream | None = None
        self.max_concurrency = 2
        self._started = False

    def configure(
        self,
        *,
        session_factory: sessionmaker,
        model_stream: ModelStream | None = None,
        max_concurrency: int = 2,
    ) -> None:
        self._session_factory = session_factory
        self._model_stream = model_stream
        self.max_concurrency = max(1, max_concurrency)

    async def start(self) -> None:
        if self._started:
            return
        self._queue = asyncio.Queue()
        self._workers = [
            asyncio.create_task(self._worker(index))
            for index in range(self.max_concurrency)
        ]
        self._started = True

    async def shutdown(self) -> None:
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []
        self._queue = None
        self._started = False

    async def enqueue(self, execution_id: uuid.UUID) -> None:
        if self._queue is None:
            raise RuntimeError("ExecutionScheduler 尚未启动")
        await self._queue.put(execution_id)

    def request_cancel(self, execution_id: uuid.UUID) -> None:
        self._cancelled.add(execution_id)

    def is_cancelled(self, execution_id: uuid.UUID) -> bool:
        return execution_id in self._cancelled

    def clear_cancel(self, execution_id: uuid.UUID) -> None:
        self._cancelled.discard(execution_id)

    async def _worker(self, index: int) -> None:
        assert self._queue is not None
        while True:
            execution_id = await self._queue.get()
            try:
                if self._session_factory is None:
                    continue
                await run_execution(
                    execution_id,
                    session_factory=self._session_factory,
                    model_stream=self._model_stream,
                    cancel_check=self.is_cancelled,
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - a worker must never die
                logger.exception("execution %s failed in worker %s", execution_id, index)
            finally:
                self.clear_cancel(execution_id)
                self._queue.task_done()


scheduler = ExecutionScheduler()
