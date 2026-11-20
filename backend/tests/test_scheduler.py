from __future__ import annotations

import asyncio
import uuid

import pytest

import app.modules.execution.scheduler as scheduler_module
from app.modules.execution import service as execution_service
from app.modules.execution.models import Execution
from app.modules.execution.scheduler import ExecutionScheduler
from app.modules.project.models import Project
from app.modules.task.models import Task


def test_scheduler_bounded_concurrency_and_fifo(monkeypatch) -> None:
    started: list[uuid.UUID] = []
    state = {"active": 0, "peak": 0}

    async def fake_run(execution_id, **kwargs):
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        started.append(execution_id)
        await asyncio.sleep(0.05)
        state["active"] -= 1

    monkeypatch.setattr(scheduler_module, "run_execution", fake_run)

    async def scenario() -> list[uuid.UUID]:
        scheduler = ExecutionScheduler()
        scheduler.configure(session_factory=lambda: None, max_concurrency=2)
        await scheduler.start()
        ids = [uuid.uuid4() for _ in range(5)]
        for execution_id in ids:
            await scheduler.enqueue(execution_id)
        await asyncio.sleep(0.4)
        await scheduler.shutdown()
        return ids

    ids = asyncio.run(scenario())
    assert state["peak"] == 2
    assert started == ids  # FIFO


def test_scheduler_cancel_flag() -> None:
    scheduler = ExecutionScheduler()
    execution_id = uuid.uuid4()
    assert scheduler.is_cancelled(execution_id) is False
    scheduler.request_cancel(execution_id)
    assert scheduler.is_cancelled(execution_id) is True
    scheduler.clear_cancel(execution_id)
    assert scheduler.is_cancelled(execution_id) is False


def test_recovery_marks_running_as_failed(db_session, workspace) -> None:
    project = Project(workspace_id=workspace.id, name="Recovery")
    db_session.add(project)
    db_session.flush()
    task = Task(workspace_id=workspace.id, project_id=project.id, title="T")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    execution = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    execution_service.mark_running(db_session, execution)
    db_session.commit()

    recovered = execution_service.recover_interrupted(db_session)
    db_session.refresh(execution)
    assert recovered == 1
    assert execution.status == "failed"
    assert execution.error_code == "interrupted"
