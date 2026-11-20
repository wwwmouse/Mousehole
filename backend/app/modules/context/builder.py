from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.context import service as context_service
from app.modules.document import service as document_service
from app.modules.file.models import File
from app.modules.file.storage import get_storage
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace
from app.shared.exceptions import FileParseError

# Known context windows (tokens). Unknown models fall back to DEFAULT_WINDOW.
MODEL_CONTEXT_WINDOWS: dict[tuple[str, str], int] = {
    ("deepseek", "deepseek-flash"): 1_000_000,
    ("deepseek", "deepseek-v4-pro"): 1_000_000,
    ("openai", "gpt-4o"): 128_000,
    ("openai", "gpt-4o-mini"): 128_000,
}
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
    window = MODEL_CONTEXT_WINDOWS.get((provider, model), DEFAULT_WINDOW)
    reserve_output = max_tokens or OUTPUT_RESERVE
    budget = window - reserve_output - OVERHEAD_RESERVE
    if workspace is not None and workspace.context_budget_tokens:
        budget = min(budget, workspace.context_budget_tokens)
    return max(MIN_BUDGET, budget)


@dataclass
class FileText:
    file: File
    source_type: str  # project_inherited | task_added
    text: str


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
        data = storage.read(file_row.storage_key)
        try:
            text = document_service.extract_text(file_row.file_type, data)
        except FileParseError as exc:
            raise FileParseError(
                f"文件解析失败：{file_row.filename}（{exc.message}）",
                details={"filename": file_row.filename},
            ) from exc
        texts.append(
            FileText(file=file_row, source_type=entry.source, text=text)
        )
    return texts


def _header(item: FileText) -> str:
    label = "项目继承" if item.source_type == "project_inherited" else "额外引用"
    return f"### 文件：{item.file.filename}（{label}）"


def render_context(items: list[FileText]) -> str:
    if not items:
        return "（本任务没有可用文件）"
    blocks = [f"{_header(item)}\n\n{item.text}" for item in items]
    return "\n\n".join(blocks)


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
