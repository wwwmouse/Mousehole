"""Controlled tools the chat model may call.

Hard boundaries: no arbitrary filesystem access, no shell, no external writes.
Every tool only touches the current Task's files, artifacts and executions.
"""
from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.modules.artifact import service as artifact_service
from app.modules.context import service as context_service
from app.modules.document import service as document_service
from app.modules.execution import service as execution_service
from app.modules.execution.scheduler import scheduler
from app.modules.file import storage as storage_module
from app.modules.file.models import File
from app.modules.model import service as model_service
from app.modules.skill import service as skill_service
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace
from app.shared.exceptions import AppError, NotFoundError

MAX_FILE_CHARS = 12_000

TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_task_files",
            "description": "列出当前 Task 的可用文件（只返回文件名、类型、大小、来源，不含内容）。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_task_file",
            "description": "读取当前 Task 中某个可用文件的解析文本（受控、超长会截断）。",
            "parameters": {
                "type": "object",
                "properties": {"file_id": {"type": "string"}},
                "required": ["file_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_artifact",
            "description": "把生成好的 Markdown 内容保存为当前 Task 的成果（自动进入版本体系）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "series_title": {"type": "string"},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_execution",
            "description": "启动一次正式 Execution（多文档分析等），由后端 Scheduler 异步执行。",
            "parameters": {
                "type": "object",
                "properties": {"skill_id": {"type": "string"}},
                "required": [],
            },
        },
    },
]


def _result(ok: bool, summary: str, **payload) -> dict:
    data: dict = {"ok": ok, "summary": summary}
    data.update(payload)
    return data


async def execute_tool(
    session: Session,
    task: Task,
    name: str,
    arguments: dict,
    *,
    conversation_id: uuid.UUID | None = None,
) -> dict:
    try:
        if name == "read_task_files":
            return _read_task_files(session, task)
        if name == "read_task_file":
            return _read_task_file(session, task, str(arguments.get("file_id", "")))
        if name == "save_artifact":
            return _save_artifact(session, task, arguments)
        if name == "create_execution":
            return await _create_execution(session, task, arguments)
        return _result(False, f"未知工具：{name}")
    except AppError as exc:
        return _result(False, exc.message)
    except Exception as exc:  # noqa: BLE001 - tool failure must be reported, not crash chat
        return _result(False, f"工具执行失败：{exc.__class__.__name__}")


def _read_task_files(session: Session, task: Task) -> dict:
    response = context_service.compute_task_files(session, task)
    files = [
        {
            "file_id": str(entry.file.id),
            "filename": entry.file.filename,
            "file_type": entry.file.file_type,
            "size": entry.file.size,
            "source": entry.source,
        }
        for entry in response.available
    ]
    return _result(True, f"共 {len(files)} 个可用文件", files=files)


def _read_task_file(session: Session, task: Task, file_id: str) -> dict:
    try:
        parsed_id = uuid.UUID(file_id)
    except (ValueError, AttributeError):
        return _result(False, "file_id 不合法")
    response = context_service.compute_task_files(session, task)
    entry = next((item for item in response.available if item.file.id == parsed_id), None)
    if entry is None:
        return _result(False, "该文件不在当前 Task 的可用文件中")
    file_row = session.get(File, parsed_id)
    if file_row is None:
        return _result(False, "文件不存在")
    data = storage_module.get_storage().read(file_row.storage_key)
    text = document_service.extract_text(file_row.file_type, data)
    truncated = len(text) > MAX_FILE_CHARS
    return _result(
        True,
        f"已读取 {file_row.filename}（{len(text)} 字符{'，已截断' if truncated else ''}）",
        filename=file_row.filename,
        content=text[:MAX_FILE_CHARS],
        truncated=truncated,
    )


def _save_artifact(session: Session, task: Task, arguments: dict) -> dict:
    title = str(arguments.get("title") or "").strip()
    content = str(arguments.get("content") or "").strip()
    if not title:
        return _result(False, "title 不能为空")
    if not content:
        return _result(False, "content 不能为空")
    series_title = (
        str(arguments.get("series_title") or "").strip()
        or f"{task.title} · 对话成果"
    )
    series = artifact_service.get_or_create_series(session, task, series_title)
    artifact = artifact_service.append_artifact(
        session,
        series,
        title=title,
        content=content,
        source_type="chat",
    )
    session.commit()
    return _result(
        True,
        f"已保存成果「{title}」v{artifact.version}",
        artifact_id=str(artifact.id),
        artifact_title=artifact.title,
        artifact_version=artifact.version,
        series_id=str(series.id),
        series_title=series.title,
    )


async def _create_execution(session: Session, task: Task, arguments: dict) -> dict:
    skill = skill_service.resolve_skill(
        session, str(arguments.get("skill_id") or "") or None
    )
    provider, model, _config = model_service.resolve_model(
        task.model_provider, task.model_name
    )
    workspace = session.get(Workspace, task.workspace_id)
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
        session,
        task=task,
        model_provider=provider,
        model_name=model,
        temperature=temperature,
        max_tokens=max_tokens,
        input_summary=f"{task.title} · {skill.name}",
        skill_id=skill.id,
        skill_name=skill.name,
    )
    session.commit()
    try:
        await scheduler.enqueue(execution.id)
    except RuntimeError:
        pass
    return _result(
        True,
        f"已启动执行「{skill.name}」（{execution.id}）",
        execution_id=str(execution.id),
        execution_status=execution.status,
        skill_name=skill.name,
    )
