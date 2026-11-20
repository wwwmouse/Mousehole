from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Callable

from sqlalchemy.orm import Session, sessionmaker

from app.modules.artifact import service as artifact_service
from app.modules.context import builder
from app.modules.context import service as context_service
from app.modules.execution import repository
from app.modules.execution import service as execution_service
from app.modules.execution.events import event_bus
from app.modules.execution.prompts import analysis_messages, summary_messages
from app.modules.model import service as model_service
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace
from app.shared.exceptions import FileParseError, ProviderError
from app.shared.usage import add_usage

logger = logging.getLogger("mousehole.execution")

ModelStream = Callable[..., AsyncIterator[dict]]
CancelCheck = Callable[[uuid.UUID], bool]


class PipelineCancelled(Exception):
    """Raised at a safety checkpoint when the user cancels the execution."""


def _publish(execution_id: uuid.UUID, event: dict) -> None:
    event_bus.publish(execution_id, event)


def _step_payload(step) -> dict:
    return {
        "id": str(step.id),
        "sequence": step.sequence,
        "step_type": step.step_type,
        "name": step.name,
        "status": step.status,
    }


def _check_cancel(cancel_check: CancelCheck | None, execution_id: uuid.UUID) -> None:
    if cancel_check is not None and cancel_check(execution_id):
        raise PipelineCancelled()


async def _collect_model(
    stream: ModelStream,
    execution_id: uuid.UUID,
    *,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float | None,
    max_tokens: int | None,
    cancel_check: CancelCheck | None,
    retry_transient: bool = True,
) -> tuple[str, dict | None]:
    """Consume a model stream; retry exactly once for transient errors."""
    attempts = 2 if retry_transient else 1
    last_error: ProviderError | None = None
    for attempt in range(attempts):
        chunks: list[str] = []
        usage: dict | None = None
        try:
            async for event in stream(
                provider,
                model,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                _check_cancel(cancel_check, execution_id)
                if event["type"] == "delta":
                    chunks.append(event["text"])
                elif event["type"] == "usage":
                    usage = event["usage"]
            return "".join(chunks).strip(), usage
        except ProviderError as exc:
            last_error = exc
            if attempt == 0 and exc.transient:
                _check_cancel(cancel_check, execution_id)
                await asyncio.sleep(0.5)
                continue
            raise
    assert last_error is not None
    raise last_error


def _merge_usage(total: dict | None, delta: dict | None) -> dict | None:
    merged = add_usage(total, delta)
    return merged or total


async def run_execution(
    execution_id: uuid.UUID,
    *,
    session_factory: sessionmaker,
    model_stream: ModelStream | None = None,
    cancel_check: CancelCheck | None = None,
) -> None:
    stream = model_stream or model_service.stream_chat
    session: Session = session_factory()
    current_step = None

    def start_step(step_type: str, name: str, input_summary: str | None = None):
        nonlocal current_step
        current_step = execution_service.open_step(
            session,
            execution,
            step_type=step_type,
            name=name,
            input_summary=input_summary,
        )
        session.commit()
        _publish(execution_id, {"type": "step.started", "step": _step_payload(current_step)})
        return current_step

    def finish_step(status: str = "completed", output_summary: str | None = None, error: str | None = None):
        nonlocal current_step
        if current_step is None:
            return
        execution_service.finish_step(
            session,
            current_step,
            status=status,
            output_summary=output_summary,
            error_message=error,
        )
        session.commit()
        event = "step.completed" if status == "completed" else "step.failed"
        if status == "skipped":
            event = "step.skipped"
        _publish(execution_id, {"type": event, "step": _step_payload(current_step)})
        current_step = None

    try:
        execution = execution_service.get_execution(session, execution_id)
        if execution.status != "pending":
            return
        try:
            _check_cancel(cancel_check, execution_id)
        except PipelineCancelled:
            execution_service.cancel(session, execution)
            session.commit()
            _publish(execution_id, {"type": "execution.cancelled", "status": "cancelled"})
            return

        task = session.get(Task, execution.task_id)
        workspace = session.get(Workspace, task.workspace_id) if task else None
        if task is None:
            execution_service.fail(
                session, execution, message="任务不存在", code="task_not_found"
            )
            session.commit()
            _publish(execution_id, {"type": "execution.failed", "status": "failed"})
            return

        execution_service.mark_running(session, execution)
        session.commit()
        _publish(execution_id, {"type": "execution.started", "status": "running"})

        provider = execution.model_provider or task.model_provider or ""
        model = execution.model_name or task.model_name or ""
        temperature = (
            execution.temperature
            if execution.temperature is not None
            else task.temperature
        )
        max_tokens = (
            execution.max_tokens if execution.max_tokens is not None else task.max_tokens
        )
        usage_total: dict | None = None

        # 1) resolve available files
        start_step("resolve_files", "解析可用文件")
        available = context_service.compute_task_files(session, task)
        finish_step(output_summary=f"{len(available.available)} 个可用文件")
        _check_cancel(cancel_check, execution_id)

        # 2) parse documents (explicit failure, never silently skipped)
        start_step("parse_documents", "解析文档")
        texts = builder.collect_file_texts(session, task)
        estimated = sum(builder.estimate_tokens(item.text) for item in texts)
        finish_step(output_summary=f"{len(texts)} 个文件，约 {estimated} tokens")
        _check_cancel(cancel_check, execution_id)

        # 3) build context (direct or two-stage summary; no embeddings/RAG)
        start_step("build_context", "构建上下文")
        budget = builder.compute_budget(workspace, provider, model, max_tokens)
        plan = builder.plan_context(texts, budget)
        if plan.mode == "summarized":
            summaries: list[str] = []
            for index, batch in enumerate(plan.batches, start=1):
                _check_cancel(cancel_check, execution_id)
                batch_context = builder.render_context(batch)
                summary, usage = await _collect_model(
                    stream,
                    execution_id,
                    provider=provider,
                    model=model,
                    messages=summary_messages(f"批次 {index}", batch_context),
                    temperature=temperature,
                    max_tokens=min(max_tokens or 1024, 1024),
                    cancel_check=cancel_check,
                )
                usage_total = _merge_usage(usage_total, usage)
                summaries.append(summary)
                for item in batch:
                    execution_service.record_file_usage(
                        session,
                        execution,
                        file=item.file,
                        source_type=item.source_type,
                        usage_mode="summarized",
                    )
            session.commit()
            context_text = "\n\n".join(
                f"### 批次 {index} 摘要\n{text}"
                for index, text in enumerate(summaries, start=1)
            )
            finish_step(
                output_summary=f"分批摘要：{len(plan.batches)} 批 / {len(texts)} 个文件"
            )
        else:
            context_text = plan.context_text
            for item in plan.files:
                execution_service.record_file_usage(
                    session,
                    execution,
                    file=item.file,
                    source_type=item.source_type,
                    usage_mode="direct",
                )
            session.commit()
            finish_step(output_summary=f"直接上下文：{len(texts)} 个文件")
        _check_cancel(cancel_check, execution_id)

        # 4) model inference
        start_step("model_call", "模型推理")
        content, usage = await _collect_model(
            stream,
            execution_id,
            provider=provider,
            model=model,
            messages=analysis_messages(task, context_text),
            temperature=temperature,
            max_tokens=max_tokens,
            cancel_check=cancel_check,
        )
        usage_total = _merge_usage(usage_total, usage)
        if not content:
            raise ProviderError("模型没有返回任何内容", transient=False)
        finish_step(output_summary=f"生成 {len(content)} 字符")
        _check_cancel(cancel_check, execution_id)

        # 5) generate artifact payload
        start_step("generate_artifact", "生成成果")
        title = f"{task.title} 分析报告"
        finish_step(output_summary=title)

        # 6) save artifact (failure here must never be marked completed)
        start_step("save_artifact", "保存成果")
        series = artifact_service.get_or_create_series(
            session, task, f"{task.title} · 分析报告"
        )
        artifact = artifact_service.append_artifact(
            session,
            series,
            title=title,
            content=content,
            source_execution_id=execution.id,
        )
        session.commit()
        finish_step(output_summary=f"Artifact v{artifact.version}")

        execution_service.complete(session, execution, usage=usage_total or None)
        session.commit()
        _publish(
            execution_id,
            {
                "type": "execution.completed",
                "status": "completed",
                "artifact_id": str(artifact.id),
                "artifact_version": artifact.version,
                "series_id": str(series.id),
            },
        )

    except PipelineCancelled:
        if current_step is not None:
            finish_step(status="skipped", error="用户取消")
        execution_service.cancel(session, execution)
        session.commit()
        _publish(execution_id, {"type": "execution.cancelled", "status": "cancelled"})
    except FileParseError as exc:
        if current_step is not None:
            finish_step(status="failed", error=exc.message)
        execution_service.fail(
            session, execution, message=exc.message, code="file_parse_error"
        )
        session.commit()
        _publish(
            execution_id,
            {"type": "execution.failed", "status": "failed", "error_code": "file_parse_error"},
        )
    except ProviderError as exc:
        if current_step is not None:
            finish_step(status="failed", error=exc.message)
        execution_service.fail(
            session, execution, message=exc.message, code="provider_error"
        )
        session.commit()
        _publish(
            execution_id,
            {"type": "execution.failed", "status": "failed", "error_code": "provider_error"},
        )
    except Exception as exc:  # noqa: BLE001 - never fake success
        logger.exception("execution %s failed unexpectedly", execution_id)
        if current_step is not None:
            finish_step(status="failed", error=str(exc))
        execution_service.fail(
            session,
            execution,
            message=f"执行失败：{exc.__class__.__name__}",
            code="execution_failed",
        )
        session.commit()
        _publish(
            execution_id,
            {"type": "execution.failed", "status": "failed", "error_code": "execution_failed"},
        )
    finally:
        session.close()
