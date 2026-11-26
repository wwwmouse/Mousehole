# 模块职责：成果系列/版本、当前版本指针、来源、删除和导出 Library。
# 对外函数：
# - attach_source_message(session, artifact_ids, message_id)：把成果来源回填到生成它的消息。
# - get_or_create_series(session, task, title)：获取/创建成果系列。
# - append_artifact(session, series, *, title, content, ...)：追加新版本，不覆盖历史。
# - rename_series / set_current_artifact：重命名系列、切换当前版本。
# - delete_artifact(session, artifact_id)：删除单个版本并移动当前指针。
# - list_task_series / list_project_series：按 Task/Project 查询系列。
# - get_series / list_series_artifacts / get_artifact：读取系列/版本。
# - export_to_library(session, artifact)：把成果 Markdown 导出为普通 Library 文件。
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.artifact import repository
from app.modules.artifact.models import Artifact, ArtifactSeries
from app.modules.file import service as file_service
from app.modules.file.schemas import FileRead
from app.modules.task.models import Task
from app.shared.exceptions import ConflictError, NotFoundError, UnprocessableError


def attach_source_message(
    session: Session,
    artifact_ids: list[uuid.UUID],
    message_id: uuid.UUID,
) -> None:
    """把成果来源回填到生成它的 assistant message。"""
    repository.update_source_message(session, artifact_ids, message_id)


def get_or_create_series(session: Session, task: Task, title: str) -> ArtifactSeries:
    series = repository.get_series_by_title(session, task.id, title)
    if series is not None:
        return series
    return repository.create_series(session, task_id=task.id, title=title)


def append_artifact(
    session: Session,
    series: ArtifactSeries,
    *,
    title: str,
    content: str,
    content_type: str = "text/markdown",
    source_execution_id: uuid.UUID | None = None,
    storage_key: str | None = None,
    source_type: str = "execution",
    source_message_id: uuid.UUID | None = None,
) -> Artifact:
    """Append a new version; historical artifacts are never overwritten."""
    version = repository.next_version(session, series.id)
    artifact = repository.create_artifact(
        session,
        series_id=series.id,
        version=version,
        title=title,
        content=content,
        content_type=content_type,
        source_execution_id=source_execution_id,
        storage_key=storage_key,
        source_type=source_type,
        source_message_id=source_message_id,
    )
    series.current_artifact_id = artifact.id
    session.flush()
    return artifact


def rename_series(session: Session, series: ArtifactSeries, new_title: str) -> ArtifactSeries:
    title = new_title.strip()
    if not title:
        raise UnprocessableError("系列标题不能为空")
    existing = repository.get_series_by_title(session, series.task_id, title)
    if existing is not None and existing.id != series.id:
        raise ConflictError("同一 Task 下已存在同名成果系列", details={"title": title})
    series.title = title
    session.flush()
    return series


def set_current_artifact(
    session: Session, series: ArtifactSeries, artifact_id: uuid.UUID
) -> ArtifactSeries:
    artifact = repository.get_artifact(session, artifact_id)
    if artifact is None or artifact.series_id != series.id:
        raise UnprocessableError("目标成果不属于该系列")
    series.current_artifact_id = artifact.id
    session.flush()
    return series


def delete_artifact(session: Session, artifact_id: uuid.UUID) -> None:
    """Delete one version; keep other versions and move the current pointer."""
    artifact = get_artifact(session, artifact_id)
    series = get_series(session, artifact.series_id)
    session.delete(artifact)
    session.flush()
    remaining = repository.list_artifacts(session, series.id)
    if not remaining:
        session.delete(series)
        session.flush()
        return
    if series.current_artifact_id == artifact.id:
        series.current_artifact_id = remaining[0].id
    session.flush()


def list_task_series(session: Session, task_id: uuid.UUID) -> list[ArtifactSeries]:
    return repository.list_series(session, task_id)


def list_project_series(session: Session, project_id: uuid.UUID) -> list[ArtifactSeries]:
    return repository.list_by_project(session, project_id)


def get_series(session: Session, series_id: uuid.UUID) -> ArtifactSeries:
    series = repository.get_series(session, series_id)
    if series is None:
        raise NotFoundError("成果系列不存在", details={"series_id": str(series_id)})
    return series


def list_series_artifacts(session: Session, series_id: uuid.UUID) -> list[Artifact]:
    get_series(session, series_id)
    return repository.list_artifacts(session, series_id)


def get_artifact(session: Session, artifact_id: uuid.UUID) -> Artifact:
    artifact = repository.get_artifact(session, artifact_id)
    if artifact is None:
        raise NotFoundError("成果不存在", details={"artifact_id": str(artifact_id)})
    return artifact


def export_to_library(session: Session, artifact: Artifact) -> FileRead:
    """Copy an artifact's Markdown into the Global Library as a normal File.

    The artifact remains an independent, versioned result; the exported File is
    a snapshot that can be attached to any Project/Task through the existing
    file-linking rules. The original title + version keep it recognizable.
    """
    if not artifact.content:
        raise UnprocessableError(
            "该成果没有可导出的 Markdown 内容",
            details={"artifact_id": str(artifact.id)},
        )
    filename = f"{(artifact.title or '').strip() or '成果'}.md"
    return file_service.create_global_text_file(
        session,
        filename=filename,
        content=artifact.content,
    )
