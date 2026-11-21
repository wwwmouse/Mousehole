"""Context module: compute the file context available to a Task.

Implements the DATA_MODEL 6.3 rule:

    Project Task:  available = (Project files - Task excludes) + Task includes
    Global Task:   available = Task includes

Available context is not the same as actual model input; this module only
resolves what the Task is allowed to use.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.file import service as file_service
from app.modules.file.schemas import (
    FileRead,
    TaskFileEntry,
    TaskFileOverrideRequest,
    TaskFilesResponse,
)
from app.modules.project import service as project_service
from app.modules.task import service as task_service
from app.modules.task.models import Task


def _sort_key(file: FileRead) -> tuple[str, str, str]:
    return (file.filename.lower(), file.filename, str(file.id))


def compute_task_files(session: Session, task: Task) -> TaskFilesResponse:
    """Compute the effective file context for an already-loaded Task."""
    overrides = file_service.list_task_overrides(session, task.id)

    include_files: dict[uuid.UUID, FileRead] = {}
    exclude_files: dict[uuid.UUID, FileRead] = {}
    for entry in overrides:
        # Overrides may point at files that were soft-deleted afterwards.
        if entry.file.status != "active":
            continue
        # Temporary files are per-message attachments, never Task context.
        if entry.file.is_temporary:
            continue
        if entry.action == "include":
            include_files[entry.file.id] = entry.file
        else:
            exclude_files[entry.file.id] = entry.file

    project_files: dict[uuid.UUID, FileRead] = {}
    if task.project_id is not None:
        for project_file in project_service.list_project_files(session, task.project_id):
            if project_file.file.status == "active":
                project_files[project_file.file.id] = project_file.file

    inherited = [
        file
        for file_id, file in project_files.items()
        if file_id not in exclude_files
    ]
    excluded = [
        file for file_id, file in project_files.items() if file_id in exclude_files
    ]
    # A file that is part of the project is inherited even if it once had an
    # include override; never list it twice.
    added = [
        file
        for file_id, file in include_files.items()
        if file_id not in project_files
    ]

    available_entries = [
        TaskFileEntry(file=file, source="project_inherited") for file in inherited
    ] + [TaskFileEntry(file=file, source="task_added") for file in added]
    available_entries.sort(key=lambda entry: _sort_key(entry.file))
    excluded.sort(key=_sort_key)

    return TaskFilesResponse(
        available=available_entries,
        excluded=excluded,
        project_file_count=len(project_files),
        task_include_count=len(added),
        task_exclude_count=len(excluded),
    )


def get_task_files(session: Session, task_id: uuid.UUID) -> TaskFilesResponse:
    task = task_service.get_task(session, task_id)
    return compute_task_files(session, task)


@dataclass(frozen=True)
class TaskFileMutation:
    """Result of an include/exclude mutation."""

    files: TaskFilesResponse
    created: bool


def add_task_file(
    session: Session, task_id: uuid.UUID, payload: TaskFileOverrideRequest
) -> TaskFileMutation:
    task = task_service.get_task(session, task_id)
    created = file_service.apply_task_override(
        session,
        task_id=task.id,
        project_id=task.project_id,
        file_id=payload.file_id,
        action=payload.action,
    )
    return TaskFileMutation(files=compute_task_files(session, task), created=created)


def remove_task_file(
    session: Session, task_id: uuid.UUID, file_id: uuid.UUID
) -> None:
    task_service.get_task(session, task_id)
    file_service.remove_task_override(session, task_id, file_id)
