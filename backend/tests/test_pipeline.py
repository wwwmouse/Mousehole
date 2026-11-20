from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from app.modules.artifact.models import Artifact, ArtifactSeries
from app.modules.execution import service as execution_service
from app.modules.execution.models import Execution, ExecutionFileSnapshot, ExecutionStep
from app.modules.execution.pipeline import run_execution
from app.modules.file import storage as storage_module
from app.modules.file.models import File, ProjectFile
from app.modules.project.models import Project
from app.modules.task.models import Task
from app.shared.exceptions import ProviderError


@pytest.fixture()
def storage_env(test_storage_root, monkeypatch):
    store = storage_module.LocalFileStorage(test_storage_root)
    monkeypatch.setattr(storage_module, "_storage", store)
    return store


def _make_file(db_session, store, filename, content, file_type="md", mime="text/markdown"):
    key, digest, size = store.save(content.encode("utf-8"), f".{file_type}")
    file = File(
        filename=filename,
        storage_key=key,
        file_type=file_type,
        mime_type=mime,
        size=size,
        content_hash=digest,
    )
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


@pytest.fixture()
def scenario(db_session, workspace, storage_env):
    project = Project(workspace_id=workspace.id, name="Pipeline Project")
    db_session.add(project)
    db_session.flush()
    task = Task(
        workspace_id=workspace.id,
        project_id=project.id,
        title="分析任务",
        description="整理要点",
        model_provider="deepseek",
        model_name="deepseek-flash",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    file = _make_file(db_session, storage_env, "notes.md", "# 标题\n\n内容要点")
    db_session.add(ProjectFile(project_id=project.id, file_id=file.id))
    db_session.commit()
    return task, workspace, file


def _make_stream(calls, summary="摘要内容", report="报告内容"):
    async def fake(provider, model, messages, *, temperature=None, max_tokens=None):
        calls.append({"messages": messages, "temperature": temperature})
        prompt = messages[-1]["content"]
        if "请为文件" in prompt:
            yield {"type": "delta", "text": summary}
            yield {
                "type": "usage",
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            }
        else:
            for index in range(0, len(report), 2):
                yield {"type": "delta", "text": report[index : index + 2]}
            yield {
                "type": "usage",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

    return fake


def _run(execution_id, session_factory, stream, cancel=False):
    asyncio.run(
        run_execution(
            execution_id,
            session_factory=session_factory,
            model_stream=stream,
            cancel_check=lambda _: cancel,
        )
    )


def _fresh(session_factory, execution_id):
    session = session_factory()
    execution = session.get(Execution, execution_id)
    steps = list(
        session.scalars(
            select(ExecutionStep).where(ExecutionStep.execution_id == execution_id)
        )
    )
    snapshots = list(
        session.scalars(
            select(ExecutionFileSnapshot).where(
                ExecutionFileSnapshot.execution_id == execution_id
            )
        )
    )
    artifacts = list(session.scalars(select(Artifact)))
    session.close()
    return execution, steps, snapshots, artifacts


def test_pipeline_direct_context_creates_artifact(db_session, session_factory, scenario):
    task, workspace, file = scenario
    execution = execution_service.create_execution(
        db_session,
        task=task,
        model_provider="deepseek",
        model_name="deepseek-flash",
    )
    db_session.commit()
    calls: list = []
    _run(execution.id, session_factory, _make_stream(calls))

    execution, steps, snapshots, artifacts = _fresh(session_factory, execution.id)
    assert execution.status == "completed"
    assert execution.completed_at is not None
    assert execution.skill_id == "multi_doc_analysis"
    assert execution.skill_name == "多文档分析"
    assert execution.usage["total_tokens"] == 15
    assert [step.step_type for step in steps] == [
        "resolve_files",
        "parse_documents",
        "build_context",
        "model_call",
        "generate_artifact",
        "save_artifact",
    ]
    assert all(step.status == "completed" for step in steps)
    assert len(snapshots) == 1
    assert snapshots[0].usage_mode == "direct"
    assert snapshots[0].filename_snapshot == "notes.md"
    assert len(artifacts) == 1
    assert artifacts[0].content == "报告内容"
    assert artifacts[0].version == 1


def test_pipeline_uses_selected_skill(db_session, session_factory, scenario):
    task, workspace, file = scenario
    execution = execution_service.create_execution(
        db_session,
        task=task,
        model_provider="deepseek",
        model_name="deepseek-flash",
        skill_id="content_summary",
        skill_name="内容摘要",
    )
    db_session.commit()
    calls: list = []
    _run(execution.id, session_factory, _make_stream(calls))

    execution, steps, snapshots, artifacts = _fresh(session_factory, execution.id)
    assert execution.status == "completed"
    assert execution.skill_id == "content_summary"
    assert artifacts[0].title.endswith("内容摘要")
    assert "总结" in calls[-1]["messages"][-1]["content"]
    session = session_factory()
    series = list(session.scalars(select(ArtifactSeries)))
    session.close()
    assert series[0].title.endswith("· 内容摘要")


def test_pipeline_second_run_appends_version(db_session, session_factory, scenario):
    task, workspace, file = scenario
    first = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    db_session.commit()
    _run(first.id, session_factory, _make_stream([]))
    second = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    db_session.commit()
    _run(second.id, session_factory, _make_stream([]))

    execution, _, _, artifacts = _fresh(session_factory, second.id)
    assert execution.status == "completed"
    assert sorted(item.version for item in artifacts) == [1, 2]
    session = session_factory()
    series = list(session.scalars(select(ArtifactSeries)))
    session.close()
    assert len(series) == 1
    assert series[0].title.endswith("· 多文档分析")


def test_pipeline_failure_is_explicit_and_creates_no_artifact(
    db_session, session_factory, scenario
):
    task, workspace, file = scenario
    execution = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    db_session.commit()

    async def failing(provider, model, messages, *, temperature=None, max_tokens=None):
        raise ProviderError("模拟服务故障", transient=False)
        yield  # pragma: no cover

    _run(execution.id, session_factory, failing)

    execution, steps, snapshots, artifacts = _fresh(session_factory, execution.id)
    assert execution.status == "failed"
    assert execution.error_code == "provider_error"
    assert artifacts == []
    assert any(step.status == "failed" for step in steps)


def test_pipeline_cancel_is_not_failure(db_session, session_factory, scenario):
    task, workspace, file = scenario
    execution = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    db_session.commit()
    _run(execution.id, session_factory, _make_stream([]), cancel=True)

    execution, _, _, artifacts = _fresh(session_factory, execution.id)
    assert execution.status == "cancelled"
    assert execution.error_message is None
    assert artifacts == []


def test_pipeline_summarizes_when_over_budget(
    db_session, session_factory, scenario
):
    task, workspace, file = scenario
    workspace.context_budget_tokens = 2000
    large = _make_file(
        db_session,
        storage_module.get_storage(),
        "large.md",
        "内容" * 20_000,
    )
    db_session.add(ProjectFile(project_id=task.project_id, file_id=large.id))
    db_session.commit()

    execution = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    db_session.commit()
    calls: list = []
    _run(execution.id, session_factory, _make_stream(calls))

    execution, steps, snapshots, artifacts = _fresh(session_factory, execution.id)
    assert execution.status == "completed"
    assert len(calls) >= 2  # at least one summary call + final call
    assert all(item.usage_mode == "summarized" for item in snapshots)
    assert len(artifacts) == 1
    build_step = next(step for step in steps if step.step_type == "build_context")
    assert "分批摘要" in (build_step.output_summary or "")


def test_pipeline_parse_failure_marks_execution_failed(
    db_session, session_factory, scenario
):
    task, workspace, file = scenario
    broken = _make_file(
        db_session,
        storage_module.get_storage(),
        "broken.pdf",
        "this is not a pdf",
        file_type="pdf",
        mime="application/pdf",
    )
    db_session.add(ProjectFile(project_id=task.project_id, file_id=broken.id))
    db_session.commit()

    execution = execution_service.create_execution(
        db_session, task=task, model_provider="deepseek", model_name="deepseek-flash"
    )
    db_session.commit()
    _run(execution.id, session_factory, _make_stream([]))

    execution, steps, _, artifacts = _fresh(session_factory, execution.id)
    assert execution.status == "failed"
    assert execution.error_code == "file_parse_error"
    assert artifacts == []
    parse_step = next(step for step in steps if step.step_type == "parse_documents")
    assert parse_step.status == "failed"
