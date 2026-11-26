from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.modules.context import service as context_service
from app.modules.document import service as document_service
from app.modules.file.models import File
from app.modules.file.storage import get_storage
from app.modules.ocr import service as ocr_service
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace
from app.shared.exceptions import FileParseError

# Unknown models fall back to DEFAULT_WINDOW; known windows come from settings
# (Settings.model_context_windows, keyed "provider/model") so they can be
# overridden without a code change (Phase 5 H5).
DEFAULT_WINDOW = 32_000
OUTPUT_RESERVE = 4_096
OVERHEAD_RESERVE = 1_024
MIN_BUDGET = 2_000

# Heuristic token estimate; good enough for budgeting without a tokenizer dependency.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def compute_budget(
    workspace: Workspace | None,
    provider: str,
    model: str,
    max_tokens: int | None = None,
) -> int:
    windows = get_settings().model_context_windows
    window = windows.get(f"{provider}/{model}", DEFAULT_WINDOW)
    reserve_output = max_tokens or OUTPUT_RESERVE
    budget = window - reserve_output - OVERHEAD_RESERVE
    if workspace is not None and workspace.context_budget_tokens:
        budget = min(budget, workspace.context_budget_tokens)
    return max(MIN_BUDGET, budget)


@dataclass
class FileText:
    file: File
    source_type: str  # project_inherited | task_added | skill_asset
    text: str
    path: str | None = None


@dataclass
class ContextPlan:
    mode: str  # direct | summarized
    context_text: str
    files: list[FileText] = field(default_factory=list)
    batches: list[list[FileText]] = field(default_factory=list)


def collect_file_texts(session, task: Task) -> list[FileText]:
    """Read and parse every available file. Parse errors fail explicitly."""
    response = context_service.compute_task_files(session, task)
    storage = get_storage()
    texts: list[FileText] = []
    for entry in response.available:
        file_row = session.get(File, entry.file.id)
        if file_row is None:
            continue
        page_text = ocr_service.get_pages_text(session, file_row.id)
        if page_text is not None:
            text = page_text
        else:
            data = storage.read(file_row.storage_key)
            try:
                text = document_service.extract_text(
                    file_row.file_type, data
                )
            except FileParseError as exc:
                raise FileParseError(
                    f"文件解析失败：{file_row.filename}（{exc.message}）",
                    details={"filename": file_row.filename},
                ) from exc
        texts.append(
            FileText(file=file_row, source_type=entry.source, text=text)
        )
    return texts


def _parse_timeout(timeout_seconds: float | None) -> float:
    if timeout_seconds is not None:
        return max(0.1, float(timeout_seconds))
    return max(0.1, float(get_settings().parse_timeout_seconds))


def _read_and_parse_sync(file_row: File) -> str:
    """Blocking storage read + text extraction; always run in a worker thread."""
    data = get_storage().read(file_row.storage_key)
    return document_service.extract_text(file_row.file_type, data)


async def _extract_text_async(file_row: File, timeout_seconds: float | None) -> str:
    timeout = _parse_timeout(timeout_seconds)
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_read_and_parse_sync, file_row), timeout=timeout
        )
    except TimeoutError as exc:
        raise FileParseError(
            f"解析超时（超过 {timeout:g}s）",
            details={"filename": file_row.filename},
        ) from exc


async def collect_file_texts_async(
    session, task: Task, *, timeout_seconds: float | None = None
) -> list[FileText]:
    """Async variant of collect_file_texts (Phase 5 H1).

    DB access stays on the event-loop thread; storage read + parsing run in a
    worker thread with a bounded timeout, so a large file cannot block the API
    or SSE delivery. Parse errors still fail explicitly.
    """
    response = context_service.compute_task_files(session, task)
    texts: list[FileText] = []
    for entry in response.available:
        file_row = session.get(File, entry.file.id)
        if file_row is None:
            continue
        page_text = ocr_service.get_pages_text(session, file_row.id)
        try:
            text = (
                page_text
                if page_text is not None
                else await _extract_text_async(
                    file_row, timeout_seconds
                )
            )
        except FileParseError as exc:
            raise FileParseError(
                f"文件解析失败：{file_row.filename}（{exc.message}）",
                details={"filename": file_row.filename},
            ) from exc
        texts.append(
            FileText(file=file_row, source_type=entry.source, text=text)
        )
    return texts


SOURCE_LABELS = {
    "project_inherited": "项目继承",
    "task_added": "额外引用",
    "skill_asset": "Skill 资料",
}


def _header(item: FileText) -> str:
    label = SOURCE_LABELS.get(item.source_type, item.source_type)
    name = item.path or item.file.filename
    return f"### 文件：{name}（{label}）"


def render_context(items: list[FileText]) -> str:
    if not items:
        return "（本任务没有可用文件）"
    blocks = [f"{_header(item)}\n\n{item.text}" for item in items]
    return "\n\n".join(blocks)


def collect_skill_asset_texts(session, skill) -> list[FileText]:
    """Files/folders attached to the selected Skill, used as reference assets."""
    from app.modules.skill import service as skill_service

    if skill is None:
        return []
    try:
        skill_id = uuid.UUID(str(skill.id))
    except (ValueError, AttributeError, TypeError):
        return []
    storage = get_storage()
    texts: list[FileText] = []
    for link, file_row in skill_service.list_skill_files(session, skill_id):
        data = storage.read(file_row.storage_key)
        try:
            text = document_service.extract_text(file_row.file_type, data)
        except FileParseError as exc:
            raise FileParseError(
                f"Skill 资料解析失败：{file_row.filename}（{exc.message}）",
                details={"filename": file_row.filename},
            ) from exc
        texts.append(
            FileText(
                file=file_row,
                source_type="skill_asset",
                text=text,
                path=link.path,
            )
        )
    return texts


async def collect_skill_asset_texts_async(
    session, skill, *, timeout_seconds: float | None = None
) -> list[FileText]:
    """Async variant of collect_skill_asset_texts (Phase 5 H1)."""
    from app.modules.skill import service as skill_service

    if skill is None:
        return []
    try:
        skill_id = uuid.UUID(str(skill.id))
    except (ValueError, AttributeError, TypeError):
        return []
    texts: list[FileText] = []
    for link, file_row in skill_service.list_skill_files(session, skill_id):
        try:
            text = await _extract_text_async(file_row, timeout_seconds)
        except FileParseError as exc:
            raise FileParseError(
                f"Skill 资料解析失败：{file_row.filename}（{exc.message}）",
                details={"filename": file_row.filename},
            ) from exc
        texts.append(
            FileText(
                file=file_row,
                source_type="skill_asset",
                text=text,
                path=link.path,
            )
        )
    return texts


def plan_context(items: list[FileText], budget: int) -> ContextPlan:
    """Direct context when it fits; otherwise split into batches for summarization."""
    total = sum(estimate_tokens(item.text) + 40 for item in items)
    if not items:
        return ContextPlan(mode="direct", context_text=render_context(items), files=[])
    if total <= budget:
        return ContextPlan(
            mode="direct",
            context_text=render_context(items),
            files=items,
        )

    # Two-stage mode: each batch gets roughly half the budget so summaries fit
    # in the final synthesis prompt. Never recurse further than this.
    batch_budget = max(MIN_BUDGET // 2, budget // 2)
    batches: list[list[FileText]] = []
    current: list[FileText] = []
    current_tokens = 0
    for item in items:
        item_tokens = estimate_tokens(item.text) + 40
        if current and current_tokens + item_tokens > batch_budget:
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(item)
        current_tokens += item_tokens
    if current:
        batches.append(current)
    return ContextPlan(
        mode="summarized",
        context_text="",
        files=items,
        batches=batches,
    )
