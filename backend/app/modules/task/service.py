from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.project import repository as project_repository
from app.modules.task import repository
from app.modules.task.models import Task
from app.modules.task.schemas import TaskCreate, TaskRead, TaskUpdate
from app.modules.workspace import service as workspace_service
from app.shared.enums import TASK_STATUSES
from app.shared.exceptions import NotFoundError, UnprocessableError


def _apply_project_binding(
    session: Session, task: Task, new_project_id: uuid.UUID | None
) -> None:
    """MVP 规则：Task 可绑定 Project 一次，绑定后不可变更/解除。

    - 未绑定（project_id is None）且传入有效 project → 校验同一 Workspace 后绑定。
    - 已绑定 → 只允许传入相同值（幂等），否则 422。
    - 已绑定后不允许解除（传 None → 422）。
    """
    if new_project_id is None:
        if task.project_id is not None:
            raise UnprocessableError(
                "Task 已绑定 Project，不可解除",
                details={"project_id": str(task.project_id)},
            )
        return
    if task.project_id is not None:
        if new_project_id != task.project_id:
            raise UnprocessableError(
                "Task 已绑定 Project，不可变更",
                details={"current_project_id": str(task.project_id)},
            )
        return
    project = project_repository.get(session, new_project_id)
    if project is None:
        raise NotFoundError("项目不存在", details={"project_id": str(new_project_id)})
    if project.workspace_id != task.workspace_id:
        raise UnprocessableError(
            "Task 与 Project 必须属于同一个 Workspace",
            details={"workspace_id": str(task.workspace_id)},
        )
    task.project_id = project.id


def _workspace_id_for(
    session: Session, payload: TaskCreate
) -> tuple[uuid.UUID, uuid.UUID | None]:
    settings = get_settings()
    if payload.project_id is not None:
        project = project_repository.get(session, payload.project_id)
        if project is None:
            raise NotFoundError(
                "项目不存在", details={"project_id": str(payload.project_id)}
            )
        if (
            payload.workspace_id is not None
            and payload.workspace_id != project.workspace_id
        ):
            raise UnprocessableError(
                "Task 与 Project 必须属于同一个 Workspace",
                details={
                    "task_workspace_id": str(payload.workspace_id),
                    "project_workspace_id": str(project.workspace_id),
                },
            )
        return project.workspace_id, project.id
    if payload.workspace_id is not None:
        workspace_service.get_workspace(session, payload.workspace_id)
        return payload.workspace_id, None
    workspace = workspace_service.get_default_workspace(
        session, settings.default_workspace_name
    )
    return workspace.id, None


def list_tasks(
    session: Session,
    *,
    workspace_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    status: str | None,
    limit: int = 50,
    offset: int = 0,
) -> list[TaskRead]:
    tasks = repository.list_tasks(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [TaskRead.model_validate(task) for task in tasks]


def get_task(session: Session, task_id: uuid.UUID) -> Task:
    task = repository.get(session, task_id)
    if task is None:
        raise NotFoundError("任务不存在", details={"task_id": str(task_id)})
    return task


def get_task_read(session: Session, task_id: uuid.UUID) -> TaskRead:
    return TaskRead.model_validate(get_task(session, task_id))


def create_task(session: Session, payload: TaskCreate) -> TaskRead:
    workspace_id, project_id = _workspace_id_for(session, payload)
    task = repository.create(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        title=payload.title.strip(),
        description=payload.description,
        model_provider=payload.model_provider,
        model_name=payload.model_name,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )
    session.commit()
    session.refresh(task)
    return TaskRead.model_validate(task)


def update_task(session: Session, task_id: uuid.UUID, payload: TaskUpdate) -> TaskRead:
    task = get_task(session, task_id)
    data = payload.model_dump(exclude_unset=True)
    if "project_id" in data:
        _apply_project_binding(session, task, data["project_id"])
    if data.get("status") is not None:
        if data["status"] not in TASK_STATUSES:
            raise UnprocessableError(
                "非法的任务状态", details={"allowed": list(TASK_STATUSES)}
            )
        task.status = data["status"]
    if data.get("title") is not None:
        task.title = data["title"].strip()
    if "description" in data:
        task.description = data["description"]
    if "model_provider" in data:
        task.model_provider = data["model_provider"]
    if "model_name" in data:
        task.model_name = data["model_name"]
    if "temperature" in data:
        task.temperature = data["temperature"]
    if "max_tokens" in data:
        task.max_tokens = data["max_tokens"]
    session.commit()
    session.refresh(task)
    return TaskRead.model_validate(task)


def delete_task(session: Session, task_id: uuid.UUID) -> None:
    task = get_task(session, task_id)
    repository.delete(session, task)
    session.commit()
    # Task-scoped temporary files are hidden from the Library; discard them.
    from app.modules.file import service as file_service

    file_service.cleanup_task_temporary_files(session, task_id)
