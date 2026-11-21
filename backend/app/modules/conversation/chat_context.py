"""Budgeted Task file context for chat messages.

Chat is not an Execution: we do not run the full pipeline, but the model must
be able to see the Task's available files (project-inherited / extra) and the
selected Skill's reference assets instead of claiming it cannot read them.
Content is bounded by a chat budget and by a per-file character cap; the full
text remains available via tools.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.modules.context import service as context_service
from app.modules.context.builder import estimate_tokens
from app.modules.document import service as document_service
from app.modules.file import storage as storage_module
from app.modules.file.models import File
from app.modules.skill import service as skill_service
from app.modules.task.models import Task
from app.shared.exceptions import FileParseError

# File-only slice of the chat input. Full text is used for each file; the old
# per-file 8k character cap was removed. 64k leaves ample room for system
# prompt, history and the answer inside the 200k workspace context budget.
CHAT_FILE_BUDGET_TOKENS = 64_000
# Parsing very large files synchronously would block the chat request.
MAX_CHAT_FILE_BYTES = 2 * 1024 * 1024

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


def _read_excerpt(storage, file_row: File) -> str:
    data = storage.read(file_row.storage_key)
    return document_service.extract_text(file_row.file_type, data)


def build_file_context(
    session: Session,
    task: Task,
    skill=None,
    extra_file_ids: list[str] | None = None,
    budget_tokens: int = CHAT_FILE_BUDGET_TOKENS,
) -> ChatFileContext | None:
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
            import uuid as _uuid

            skill_id = _uuid.UUID(str(skill.id))
            for link, file_row in skill_service.list_skill_files(session, skill_id):
                entries.append((file_row, "skill_asset", link.path))
        except (ValueError, AttributeError, TypeError):
            pass

    if not entries:
        return None

    # Newest files first: the model should prefer recently updated material,
    # and the budget is spent on the most recent documents first.
    def _recency(item) -> str:
        file_row = item[0]
        stamp = getattr(file_row, "updated_at", None) or getattr(
            file_row, "created_at", None
        )
        return stamp.isoformat() if stamp is not None else ""

    task_entries = [item for item in entries if item[1] != "skill_asset"]
    skill_entries = [item for item in entries if item[1] == "skill_asset"]
    task_entries.sort(key=_recency, reverse=True)
    entries = task_entries + skill_entries

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

    storage = storage_module.get_storage()
    used_tokens = 0
    files: list[dict] = []
    for file_row, source, path in entries:
        display = path or file_row.filename
        record = {
            "filename": display,
            "source": source,
            "path": path,
        }
        if file_row.size > MAX_CHAT_FILE_BYTES:
            record["status"] = "skipped"
            files.append(record)
            lines.append(
                f"### {display}\n"
                "（文件较大（>2MB），本次对话未自动展开；请下载后查看或使用支持大文件的工具）"
            )
            continue
        try:
            text = _read_excerpt(storage, file_row)
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

    return ChatFileContext(text="\n\n".join(lines), files=files)
