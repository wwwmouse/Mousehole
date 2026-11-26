"""Budgeted Task file context for chat messages.

Chat is not an Execution: we do not run the full pipeline, but the model must
be able to see the Task's available files (project-inherited / extra) and the
selected Skill's reference assets instead of claiming it cannot read them.
Content is bounded by a chat budget and by a per-file byte cap; the full text
remains available via tools.

Phase 5 H1: the async entry point parses files in a worker thread so a large
document cannot block the event loop / SSE delivery.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.context import service as context_service
from app.modules.context.builder import estimate_tokens
from app.modules.document import service as document_service
from app.modules.file import storage as storage_module
from app.modules.file.models import File
from app.modules.ocr import service as ocr_service
from app.modules.skill import service as skill_service
from app.modules.task.models import Task
from app.shared.exceptions import FileParseError

# File-only slice of the chat input. Full text is used for each file; the old
# per-file 8k character cap was removed. 64k leaves ample room for system
# prompt, history and the answer inside the 200k workspace context budget.
CHAT_FILE_BUDGET_TOKENS = 64_000
# Parsing very large files synchronously would block the chat request.  PDFs
# are often a few MB even when their extracted text is small, so keep the cap
# high enough for normal text PDFs; the token budget still truncates content.
MAX_CHAT_FILE_BYTES = 10 * 1024 * 1024
MAX_CHAT_FILE_MB = MAX_CHAT_FILE_BYTES // (1024 * 1024)

SOURCE_LABELS = {
    "project_inherited": "项目继承",
    "task_added": "额外引用",
    "temporary": "本轮临时",
    "skill_asset": "Skill 资料",
}


@dataclass
class ChatFileContext:
    text: str
    files: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)


def _read_excerpt(storage, file_row: File) -> str:
    data = storage.read(file_row.storage_key)
    return document_service.extract_text(file_row.file_type, data)


def _read_text(session: Session, storage, file_row: File) -> str:
    page_text = ocr_service.get_pages_text(session, file_row.id)
    if page_text is not None:
        return page_text
    return _read_excerpt(storage, file_row)


def _collect_entries(
    session: Session,
    task: Task,
    skill=None,
    extra_file_ids: list[str] | None = None,
) -> list[tuple[File, str, str | None]]:
    """Resolve Task files, this turn's temporary files and Skill assets."""
    response = context_service.compute_task_files(session, task)
    entries: list[tuple[File, str, str | None]] = []
    seen: set[str] = set()
    for entry in response.available:
        file_row = session.get(File, entry.file.id)
        if file_row is not None:
            entries.append((file_row, entry.source, None))
            seen.add(str(file_row.id))

    # Temporary files are attached to one chat turn only; they are never part
    # of the Task's persistent context.
    import uuid as _uuid

    for raw_id in extra_file_ids or []:
        try:
            file_id = _uuid.UUID(str(raw_id))
        except (ValueError, AttributeError, TypeError):
            continue
        file_row = session.get(File, file_id)
        if (
            file_row is None
            or file_row.status != "active"
            or not file_row.is_temporary
            or file_row.owner_task_id != task.id
        ):
            continue
        if str(file_row.id) in seen:
            continue
        seen.add(str(file_row.id))
        entries.append((file_row, "temporary", None))

    if skill is not None:
        try:
            skill_id = _uuid.UUID(str(skill.id))
            for link, file_row in skill_service.list_skill_files(session, skill_id):
                entries.append((file_row, "skill_asset", link.path))
        except (ValueError, AttributeError, TypeError):
            pass

    # Newest files first: the model should prefer recently updated material,
    # and the budget is spent on the most recent documents first. Skill assets
    # keep their declared order after task files.
    def _recency(item: tuple[File, str, str | None]) -> str:
        file_row = item[0]
        stamp = getattr(file_row, "updated_at", None) or getattr(
            file_row, "created_at", None
        )
        return stamp.isoformat() if stamp is not None else ""

    task_entries = [item for item in entries if item[1] != "skill_asset"]
    skill_entries = [item for item in entries if item[1] == "skill_asset"]
    task_entries.sort(key=_recency, reverse=True)
    return task_entries + skill_entries


def _render_context(
    entries: list[tuple[File, str, str | None]],
    budget_tokens: int,
    read_text,
    page_file_ids: set[str] | None = None,
) -> ChatFileContext | None:
    if not entries:
        return None
    page_file_ids = page_file_ids or set()

    lines: list[str] = ["## 当前 Task 可用文件与 Skill 资料"]
    lines.append(
        "资料按最近更新时间从新到旧排列；请优先参考最近更新的资料，"
        "除非用户明确指定其他文件。"
    )
    for file_row, source, path in entries:
        label = SOURCE_LABELS.get(source, source)
        display = path or file_row.filename
        stamp = getattr(file_row, "updated_at", None) or getattr(
            file_row, "created_at", None
        )
        when = stamp.strftime("%Y-%m-%d %H:%M") if stamp is not None else ""
        lines.append(
            f"- {display}（{label}，{file_row.file_type}，{file_row.size} bytes"
            f"{'，更新于 ' + when if when else ''}）"
        )

    lines.append("")
    lines.append("## 资料内容节选")
    lines.append(
        "以下内容受预算限制可能被截断；需要完整内容时可调用 read_task_file 工具。"
    )

    used_tokens = 0
    files: list[dict] = []
    citations: list[dict] = []
    for file_row, source, path in entries:
        display = path or file_row.filename
        record = {
            "file_id": str(file_row.id),
            "filename": display,
            "source": source,
            "path": path,
        }
        if (
            file_row.size > MAX_CHAT_FILE_BYTES
            and str(file_row.id) not in page_file_ids
        ):
            record["status"] = "skipped"
            files.append(record)
            lines.append(
                f"### {display}\n"
                f"（文件较大（>{MAX_CHAT_FILE_MB}MB），本次对话未自动展开；"
                "请下载后查看或使用支持大文件的工具）"
            )
            continue
        try:
            text = read_text(file_row)
        except FileParseError as exc:
            record["status"] = "failed"
            files.append(record)
            lines.append(f"### {display}\n（解析失败：{exc.message}）")
            continue
        except Exception:  # noqa: BLE001 - a broken file must not kill chat
            record["status"] = "failed"
            files.append(record)
            lines.append(f"### {display}\n（读取失败，无法加入上下文）")
            continue

        remaining = budget_tokens - used_tokens
        if remaining <= 0:
            record["status"] = "skipped"
            files.append(record)
            lines.append(
                f"### {display}\n"
                "（超出本次对话文件预算，未展开；可调用 read_task_file 读取）"
            )
            continue
        excerpt = text
        truncated = False
        tokens = estimate_tokens(excerpt)
        if tokens > remaining:
            excerpt = excerpt[: max(0, remaining * 4)]
            truncated = True
            tokens = estimate_tokens(excerpt)
        used_tokens += tokens
        record["status"] = "included"
        record["truncated"] = truncated
        files.append(record)
        suffix = (
            "\n（超出本轮文件预算，已截断；可调用 read_task_file 分页读取剩余内容）"
            if truncated
            else ""
        )
        lines.append(f"### {display}{suffix}\n{excerpt}")
        for raw_page in re.findall(r"--- 第 (\d+) 页 ---", excerpt):
            page_no = int(raw_page)
            citation = {
                "file_id": str(file_row.id),
                "filename": display,
                "page_no": page_no,
            }
            if citation not in citations:
                citations.append(citation)

    return ChatFileContext(
        text="\n\n".join(lines),
        files=files,
        citations=citations,
    )


def build_file_context(
    session: Session,
    task: Task,
    skill=None,
    extra_file_ids: list[str] | None = None,
    budget_tokens: int = CHAT_FILE_BUDGET_TOKENS,
) -> ChatFileContext | None:
    """Synchronous variant (tests, non-async callers)."""
    entries = _collect_entries(session, task, skill, extra_file_ids)
    storage = storage_module.get_storage()
    page_file_ids = {
        str(file_row.id)
        for file_row, _source, _path in entries
        if ocr_service.get_pages_text(session, file_row.id) is not None
    }
    return _render_context(
        entries,
        budget_tokens,
        lambda file_row: _read_text(session, storage, file_row),
        page_file_ids,
    )


async def _read_raw_async(storage, file_row: File, timeout_seconds: float) -> str:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_read_excerpt, storage, file_row),
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        raise FileParseError(f"解析超时（超过 {timeout_seconds:g}s）") from exc


async def build_file_context_async(
    session: Session,
    task: Task,
    skill=None,
    extra_file_ids: list[str] | None = None,
    budget_tokens: int = CHAT_FILE_BUDGET_TOKENS,
    timeout_seconds: float | None = None,
) -> ChatFileContext | None:
    """Async variant: DB work on the loop thread, parsing in a worker thread."""
    timeout = float(
        timeout_seconds
        if timeout_seconds is not None
        else get_settings().parse_timeout_seconds
    )
    entries = _collect_entries(session, task, skill, extra_file_ids)
    storage = storage_module.get_storage()
    parsed: dict[str, str | Exception] = {}
    page_file_ids: set[str] = set()
    for file_row, _source, _path in entries:
        page_text = ocr_service.get_pages_text(session, file_row.id)
        if page_text is not None:
            parsed[str(file_row.id)] = page_text
            page_file_ids.add(str(file_row.id))
            continue
        if file_row.size > MAX_CHAT_FILE_BYTES:
            continue  # render marks it skipped without reading
        try:
            parsed[str(file_row.id)] = await _read_raw_async(
                storage, file_row, timeout
            )
        except Exception as exc:  # noqa: BLE001 - re-raised during render
            parsed[str(file_row.id)] = exc

    def _read(file_row: File) -> str:
        value = parsed.get(str(file_row.id))
        if value is None:
            raise FileParseError("读取失败")
        if isinstance(value, Exception):
            raise value
        return value

    return _render_context(
        entries, budget_tokens, _read, page_file_ids
    )
