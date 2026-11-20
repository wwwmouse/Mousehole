from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession
from app.modules.artifact import repository as artifact_repository
from app.modules.execution import repository as execution_repository
from app.modules.execution import service as execution_service
from app.modules.execution.events import event_bus
from app.modules.execution.schemas import (
    ExecutionDetail,
    ExecutionRead,
    ExecutionSnapshotRead,
    ExecutionStepRead,
)
from app.modules.execution.scheduler import scheduler
from app.modules.model import service as model_service
from app.modules.task import service as task_service
from app.modules.workspace.models import Workspace
from app.shared.exceptions import ConflictError

router = APIRouter()

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post(
    "/tasks/{task_id}/executions",
    response_model=ExecutionRead,
    status_code=202,
)
async def create_execution(task_id: uuid.UUID, db: DbSession) -> ExecutionRead:
    task = task_service.get_task(db, task_id)
    provider, model, _config = model_service.resolve_model(
        task.model_provider, task.model_name
    )
    workspace = db.get(Workspace, task.workspace_id)
    temperature = (
        task.temperature
        if task.temperature is not None
        else (workspace.default_temperature if workspace else None)
    )
    max_tokens = (
        task.max_tokens
        if task.max_tokens is not None
        else (workspace.default_max_tokens if workspace else None)
    )
    execution = execution_service.create_execution(
        db,
        task=task,
        model_provider=provider,
        model_name=model,
        temperature=temperature,
        max_tokens=max_tokens,
        input_summary=f"{task.title} · 多文档分析",
    )
    db.commit()
    db.refresh(execution)
    try:
        await scheduler.enqueue(execution.id)
    except RuntimeError:
        # Scheduler is not running (e.g. tests without lifespan); execution
        # stays pending and is picked up on the next startup.
        pass
    return ExecutionRead.model_validate(execution)


@router.get(
    "/tasks/{task_id}/executions", response_model=list[ExecutionRead]
)
def list_executions(task_id: uuid.UUID, db: DbSession) -> list[ExecutionRead]:
    task_service.get_task(db, task_id)
    return [
        ExecutionRead.model_validate(item)
        for item in execution_service.list_executions(db, task_id)
    ]


@router.get("/executions/{execution_id}", response_model=ExecutionDetail)
def get_execution(execution_id: uuid.UUID, db: DbSession) -> ExecutionDetail:
    execution = execution_service.get_execution(db, execution_id)
    detail = ExecutionDetail.model_validate(execution)
    detail.steps = [
        ExecutionStepRead.model_validate(step)
        for step in execution_repository.list_steps(db, execution.id)
    ]
    detail.snapshots = [
        ExecutionSnapshotRead.model_validate(snapshot)
        for snapshot in execution_repository.list_snapshots(db, execution.id)
    ]
    detail.artifact_ids = [
        artifact.id
        for artifact in artifact_repository.list_by_execution(db, execution.id)
    ]
    return detail


@router.post("/executions/{execution_id}/cancel", response_model=ExecutionRead)
def cancel_execution(execution_id: uuid.UUID, db: DbSession) -> ExecutionRead:
    execution = execution_service.get_execution(db, execution_id)
    if execution.status == "pending":
        scheduler.request_cancel(execution.id)
        execution_service.cancel(db, execution)
        db.commit()
        db.refresh(execution)
    elif execution.status == "running":
        # Cooperative cancellation: the pipeline stops at the next checkpoint.
        scheduler.request_cancel(execution.id)
    else:
        raise ConflictError("该执行已结束，无法取消")
    return ExecutionRead.model_validate(execution)


@router.get("/executions/{execution_id}/events")
async def execution_events(
    execution_id: uuid.UUID, db: DbSession
) -> StreamingResponse:
    execution = execution_service.get_execution(db, execution_id)
    status = execution.status
    provider = execution.model_provider
    model = execution.model_name

    queue = event_bus.subscribe(execution.id)

    async def event_stream():
        try:
            yield _sse(
                "snapshot",
                {
                    "id": str(execution.id),
                    "status": status,
                    "model_provider": provider,
                    "model_name": model,
                },
            )
            if status in TERMINAL_STATUSES:
                yield _sse(
                    f"execution.{'completed' if status == 'completed' else status}",
                    {"status": status},
                )
                return
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield _sse(event.get("type", "message"), event)
                if event.get("type") in {
                    "execution.completed",
                    "execution.failed",
                    "execution.cancelled",
                }:
                    return
        finally:
            event_bus.unsubscribe(execution.id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
