# 模块职责：定义并执行模型可调用的受控工具；工具菜单从 TOOLS_SPECS 动态生成。
# 对外常量：
# - TOOL_SPECS：read_task_files / read_task_file / save_artifact / create_execution 的唯一 allowlist。
# 对外函数：
# - tool_prompt()：把 TOOL_SPECS 渲染成系统提示里的工具菜单。
# - execute_tool(session, task, name, arguments, *, conversation_id=None)：按 allowlist 分发并执行一个工具。
"""Controlled tools the chat model may call.

Hard boundaries: no arbitrary filesystem access, no shell, no external writes.
Every tool only touches the current Task's files, artifacts and executions.
"""
from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.artifact import service as artifact_service
from app.modules.context import service as context_service
from app.modules.document import service as document_service
from app.modules.execution import service as execution_service
from app.modules.execution.scheduler import scheduler
from app.modules.file import storage as storage_module
from app.modules.file.models import File
from app.modules.model import service as model_service
from app.modules.ocr import service as ocr_service
from app.modules.skill import service as skill_service
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace
from app.shared.exceptions import AppError, NotFoundError

DEFAULT_READ_CHARS = 12_000
MAX_READ_CHARS = 40_000


def _wrap(
    name: str,
    description: str,
    properties: dict[str, dict],
    required: list[str] | None = None,
) -> dict:
    """Build one OpenAI-compatible tool schema.

    name/description/parameters are the only things the model sees; keep the
    description explicit about *when* to use (and not use) the tool, and declare
    every parameter with type + meaning so the model can fill it correctly.
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


TOOL_SPECS: list[dict] = [
    _wrap(
        "read_task_files",
        "列出当前 Task 的可用文件（文件名、类型、大小、来源），帮助模型判断有哪些资料、以及获取 file_id。"
        "不返回文件内容；需要内容时再用 read_task_file。",
        {},
    ),
    _wrap(
        "read_task_file",
        "读取当前 Task 某个可用文件的解析文本。适合精读单份资料；大文件可用 offset/limit 分页读取"
        "（每次最多 40000 字符，返回 total_chars/next_offset/has_more）。优先传 file_id，也可传 filename。",
        {
            "file_id": {"type": "string", "description": "文件 ID（推荐，来自 read_task_files）"},
            "filename": {"type": "string", "description": "文件名，例如 notes.md"},
            "path": {"type": "string", "description": "文件路径或文件名（兼容写法）"},
            "offset": {
                "type": "integer",
                "description": "从第几个字符开始读取，默认 0；用于分页读大文件",
            },
            "limit": {
                "type": "integer",
                "description": f"本次最多返回多少字符，默认 {DEFAULT_READ_CHARS}，最大 {MAX_READ_CHARS}",
            },
        },
    ),
    _wrap(
        "save_artifact",
        "把 Markdown 内容保存为当前 Task 的成果（进入 ArtifactSeries 版本体系，历史版本不覆盖）。"
        "当用户要求生成、撰写、保存文档/报告/总结/成果时必须调用；不要只在聊天里输出内容就结束。",
        {
            "title": {"type": "string", "description": "成果标题（同一系列内版本会递增）"},
            "content": {"type": "string", "description": "完整 Markdown 内容"},
            "series_title": {
                "type": "string",
                "description": "可选：成果系列名，默认「{Task 标题} · 对话成果」",
            },
        },
        ["title", "content"],
    ),
    _wrap(
        "create_execution",
        "启动一次正式 Execution（多文档分析 Pipeline，由 Scheduler 异步执行）。"
        "仅当用户需要完整的多文档分析流程时使用；普通问答或简单成果保存不要用。",
        {
            "skill_id": {
                "type": "string",
                "description": "可选：Skill Library 中的 Skill ID；不传则使用默认 Skill",
            },
        },
    ),
]


def tool_prompt() -> str:
    """Render the tool menu for the system prompt from TOOL_SPECS (no hardcoding)."""
    lines = ["你可以使用以下受控工具（由后端 allowlist 执行）："]
    for spec in TOOL_SPECS:
        function = spec["function"]
        properties = function["parameters"]["properties"]
        required = set(function["parameters"]["required"])
        params = []
        for field, meta in properties.items():
            suffix = "（必填）" if field in required else ""
            params.append(f"{field}: {meta.get('description', '')}{suffix}")
        params_text = "；".join(params) if params else "无参数"
        lines.append(f"- {function['name']}：{function['description']} 参数：{params_text}")
    lines.append("工具调用必须使用原生 function calling，不要输出 <tool_call> 或其他文本标记。")
    lines.append("工具只能操作当前 Task，不能访问任意文件系统、Shell 或外部服务。")
    return "\n".join(lines)


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
            return _read_task_file(session, task, arguments)
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


def _read_task_file(session: Session, task: Task, arguments: dict) -> dict:
    response = context_service.compute_task_files(session, task)
    available = [
        (item.file.id, session.get(File, item.file.id))
        for item in response.available
    ]
    available = [(file_id, file_row) for file_id, file_row in available if file_row]

    raw = str(
        arguments.get("file_id")
        or arguments.get("filename")
        or arguments.get("path")
        or ""
    ).strip()
    if not raw:
        names = "、".join(file_row.filename for _, file_row in available) or "（无）"
        return _result(False, f"缺少文件参数；可用文件：{names}")

    target = None
    try:
        parsed_id = uuid.UUID(raw)
    except (ValueError, AttributeError):
        parsed_id = None
    if parsed_id is not None:
        target = next((row for file_id, row in available if file_id == parsed_id), None)
    if target is None:
        needle = raw.replace("\\", "/").split("/")[-1].strip().casefold()
        target = next(
            (
                row
                for _, row in available
                if row.filename.casefold() == needle
            ),
            None,
        )
    if target is None:
        names = "、".join(row.filename for _, row in available) or "（无）"
        return _result(False, f"找不到文件「{raw}」；可用文件：{names}")

    # 与上传上限保持一致：能上传的文件，就应该允许工具读取。
    # 注意这只是“可读取”上限，不是一次返回给模型的字符上限。
    max_tool_file_bytes = get_settings().max_upload_bytes
    if target.size > max_tool_file_bytes:
        return _result(
            False,
            f"文件过大（>{max_tool_file_bytes // (1024 * 1024)}MB），无法在对话中读取；请下载后查看",
        )
    try:
        offset = max(0, int(arguments.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = int(arguments.get("limit") or DEFAULT_READ_CHARS)
    except (TypeError, ValueError):
        limit = DEFAULT_READ_CHARS
    limit = max(500, min(limit, MAX_READ_CHARS))

    page_text = ocr_service.get_pages_text(session, target.id)
    if page_text is not None:
        text = page_text
    else:
        data = storage_module.get_storage().read(target.storage_key)
        text = document_service.extract_text(target.file_type, data)
    total = len(text)
    if total == 0:
        return _result(True, f"文件 {target.filename} 没有可读文本", content="")
    if offset >= total:
        return _result(
            True,
            f"已到文件末尾（{target.filename} 共 {total} 字符）",
            filename=target.filename,
            content="",
            total_chars=total,
            offset=offset,
            next_offset=total,
            has_more=False,
        )
    chunk = text[offset : offset + limit]
    next_offset = offset + len(chunk)
    has_more = next_offset < total
    return _result(
        True,
        f"已读取 {target.filename} 第 {offset}-{next_offset} 字符（共 {total} 字符"
        f"{'，还有后续内容，可继续用 offset=' + str(next_offset) + ' 读取' if has_more else '，已到末尾'}）",
        filename=target.filename,
        content=chunk,
        total_chars=total,
        offset=offset,
        next_offset=next_offset,
        has_more=has_more,
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
    from app.shared.defaults import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE

    execution = execution_service.create_execution(
        session,
        task=task,
        model_provider=provider,
        model_name=model,
        temperature=temperature if temperature is not None else DEFAULT_TEMPERATURE,
        max_tokens=max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
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
