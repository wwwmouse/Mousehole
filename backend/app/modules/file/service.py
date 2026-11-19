"""File domain service.

Responsibilities (see docs/ARCHITECTURE.md 3.5):
- upload + metadata + hash
- querying and reference resolution
- soft delete with reference protection
- Project file links and Task include/exclude overrides

The module never converts PDF/markdown into model text itself; that belongs to
app.modules.document.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.core.config import get_settings
from app.modules.document import service as document_service
from app.modules.file import repository
from app.modules.file.models import File
from app.modules.file.schemas import (
    FileContentRead,
    FileDetail,
    FileRead,
    FileReference,
)
from app.modules.file.storage import get_storage
from app.shared.enums import FILE_STATUSES, OVERRIDE_ACTIONS
from app.shared.exceptions import (
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedFileTypeError,
    UnprocessableError,
)

# extension -> (canonical file_type, mime_type)
ALLOWED_EXTENSIONS: dict[str, tuple[str, str]] = {
    ".pdf": ("pdf", "application/pdf"),
    ".md": ("md", "text/markdown"),
    ".markdown": ("md", "text/markdown"),
    ".txt": ("txt", "text/plain"),
}

MAX_FILENAME_LENGTH = 512


def _safe_filename(raw: str | None) -> str:
    """Strip any client-side directory component from the uploaded filename."""
    filename = (raw or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return filename


def _extension_of(filename: str) -> str:
    return Path(filename).suffix.lower()


def _file_type_for(
    filename: str, original: str | None
) -> tuple[str, str]:
    extension = _extension_of(filename)
    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"不支持的文件类型：{extension or '未知'}",
            details={
                "filename": original,
                "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
            },
        )
    return ALLOWED_EXTENSIONS[extension]


def _get_active_file(session: Session, file_id: uuid.UUID) -> File:
    file = repository.get(session, file_id)
    if file is None or file.status != "active":
        raise NotFoundError("文件不存在", details={"file_id": str(file_id)})
    return file


@dataclass(frozen=True)
class TaskOverrideEntry:
    """A Task override together with the referenced file."""

    action: str
    file: FileRead


def upload_file(session: Session, upload: UploadFile) -> FileRead:
    filename = _safe_filename(upload.filename)
    file_type, mime_type = _file_type_for(filename, upload.filename)
    if len(filename) > MAX_FILENAME_LENGTH:
        raise UnprocessableError(
            "文件名过长", details={"max_length": MAX_FILENAME_LENGTH}
        )

    settings = get_settings()
    max_bytes = settings.max_upload_bytes
    data = upload.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise PayloadTooLargeError(
            "文件超过上传大小限制",
            details={"max_bytes": max_bytes},
        )
    if not data:
        raise UnprocessableError("文件内容为空", details={"filename": filename})

    storage_key, content_hash, size = get_storage().save(data, _extension_of(filename))

    # Content-addressed storage can yield the same key for an identical upload.
    # storage_key is unique in the database, so re-uploading identical content
    # reuses (or restores) the existing File row instead of failing.
    existing = repository.get_by_storage_key(session, storage_key)
    if existing is not None:
        if existing.status != "active":
            existing.status = "active"
            existing.filename = filename
            existing.file_type = file_type
            existing.mime_type = mime_type
            existing.size = size
            existing.content_hash = content_hash
            session.commit()
            session.refresh(existing)
        return FileRead.model_validate(existing)

    file = repository.create(
        session,
        filename=filename,
        storage_key=storage_key,
        file_type=file_type,
        mime_type=mime_type,
        size=size,
        content_hash=content_hash,
    )
    session.commit()
    session.refresh(file)
    return FileRead.model_validate(file)


def list_files(
    session: Session,
    *,
    search: str | None = None,
    file_type: str | None = None,
    status: str | None = "active",
    limit: int = 50,
    offset: int = 0,
) -> list[FileRead]:
    if status and status not in FILE_STATUSES:
        raise UnprocessableError(
            "非法的文件状态", details={"allowed": list(FILE_STATUSES)}
        )
    # Accept both the canonical short type ("md") and the extension/long form.
    filter_type = document_service.normalize_file_type(file_type)
    if filter_type == "markdown":
        filter_type = "md"
    files = repository.list_files(
        session,
        search=search.strip() if search else None,
        file_type=filter_type or None,
        status=status or "",
        limit=limit,
        offset=offset,
    )
    # created_at has second precision in SQLite; break ties deterministically.
    files.sort(key=lambda item: (item.created_at, str(item.id)), reverse=True)
    return [FileRead.model_validate(file) for file in files]


def _references(
    session: Session, file_id: uuid.UUID
) -> tuple[list[FileReference], list[FileReference]]:
    project_refs = [
        FileReference(kind="project", id=project.id, name=project.name)
        for project in repository.list_project_references(session, file_id)
    ]
    task_refs = [
        FileReference(kind="task", id=task.id, name=task.title)
        for task in repository.list_task_references(session, file_id)
    ]
    return project_refs, task_refs


def get_file_detail(session: Session, file_id: uuid.UUID) -> FileDetail:
    file = _get_active_file(session, file_id)
    project_refs, task_refs = _references(session, file.id)
    detail = FileDetail.model_validate(file)
    return detail.model_copy(update={"references": [*project_refs, *task_refs]})


def get_file_content(
    session: Session, file_id: uuid.UUID, max_chars: int = 20000
) -> FileContentRead:
    file = _get_active_file(session, file_id)
    data = get_storage().read(file.storage_key)
    text = document_service.extract_text(file.file_type, data)
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]
    return FileContentRead(
        file=FileRead.model_validate(file), text=text, truncated=truncated
    )


def delete_file(session: Session, file_id: uuid.UUID) -> None:
    file = _get_active_file(session, file_id)
    projects = repository.list_project_references(session, file.id)
    tasks = repository.list_task_references(session, file.id)
    if projects or tasks:
        raise ConflictError(
            "文件仍被引用，无法删除",
            details={
                "projects": [
                    {"id": str(project.id), "name": project.name}
                    for project in projects
                ],
                "tasks": [{"id": str(task.id), "title": task.title} for task in tasks],
            },
        )
    # Soft delete only; physical storage is kept so history stays traceable.
    file.status = "deleted"
    session.commit()


# --- Task file overrides -------------------------------------------------


def list_task_overrides(
    session: Session, task_id: uuid.UUID
) -> list[TaskOverrideEntry]:
    return [
        TaskOverrideEntry(action=override.action, file=FileRead.model_validate(file))
        for override, file in repository.list_overrides_with_files(session, task_id)
    ]


def apply_task_override(
    session: Session,
    *,
    task_id: uuid.UUID,
    project_id: uuid.UUID | None,
    file_id: uuid.UUID,
    action: str,
) -> bool:
    """Create or update one Task file override.

    Returns True when a new override row was created, False when an existing
    override was reused (idempotent) or updated.
    """
    if action not in OVERRIDE_ACTIONS:
        raise UnprocessableError(
            "非法的文件上下文动作", details={"allowed": list(OVERRIDE_ACTIONS)}
        )
    file = repository.get(session, file_id)
    if file is None or file.status != "active":
        raise NotFoundError("文件不存在或已删除", details={"file_id": str(file_id)})

    project_link = (
        repository.get_project_file(session, project_id, file_id)
        if project_id is not None
        else None
    )
    if action == "include":
        # DATA_MODEL rule 7: project files are inherited, no include needed.
        if project_link is not None:
            raise UnprocessableError(
                "文件已属于该任务所属项目，无需额外引用",
                details={"file_id": str(file_id), "project_id": str(project_id)},
            )
    else:
        if project_id is None:
            raise UnprocessableError(
                "不属于任何项目的 Task 无法排除 Project 继承文件",
                details={"file_id": str(file_id)},
            )
        if project_link is None:
            raise UnprocessableError(
                "只能排除属于任务所属项目的文件",
                details={"file_id": str(file_id), "project_id": str(project_id)},
            )

    existing = repository.get_override(session, task_id, file_id)
    if existing is None:
        repository.add_override(session, task_id, file_id, action)
        session.commit()
        return True
    if existing.action != action:
        # Same file, opposite action: update the single effective override.
        existing.action = action
        session.commit()
    return False


def remove_task_override(
    session: Session, task_id: uuid.UUID, file_id: uuid.UUID
) -> None:
    existing = repository.get_override(session, task_id, file_id)
    if existing is None:
        raise NotFoundError(
            "该任务未对文件设置 include/exclude",
            details={"task_id": str(task_id), "file_id": str(file_id)},
        )
    session.delete(existing)
    session.commit()
