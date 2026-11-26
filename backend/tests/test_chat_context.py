from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.modules.conversation.chat_context import build_file_context
from app.modules.file.models import File, ProjectFile
from app.modules.ocr import repository as ocr_repository
from app.modules.project.models import Project
from app.modules.task.models import Task


def _file(name: str, updated: datetime) -> File:
    return File(
        filename=name,
        storage_key=f"objects/test/{uuid.uuid4().hex}.md",
        file_type="md",
        mime_type="text/markdown",
        size=10,
        content_hash=uuid.uuid4().hex * 2,
        created_at=updated,
        updated_at=updated,
    )


def test_chat_context_uses_page_text_and_builds_citations(
    db_session, workspace
) -> None:
    now = datetime.now(timezone.utc)
    pdf = File(
        filename="manual.pdf",
        storage_key=f"objects/test/{uuid.uuid4().hex}.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        size=3 * 1024 * 1024,
        content_hash=uuid.uuid4().hex * 2,
        created_at=now,
        updated_at=now,
    )
    project = Project(workspace_id=workspace.id, name="OCR")
    db_session.add_all([pdf, project])
    db_session.flush()
    db_session.add(ProjectFile(project_id=project.id, file_id=pdf.id))
    task = Task(
        workspace_id=workspace.id, project_id=project.id, title="OCR task"
    )
    db_session.add(task)
    ocr_repository.add_page(
        db_session,
        file_id=pdf.id,
        page_no=1,
        text="第一页正文",
        text_source="ocr",
    )
    ocr_repository.add_page(
        db_session,
        file_id=pdf.id,
        page_no=2,
        text="第二页正文",
        text_source="ocr",
    )
    db_session.commit()
    db_session.refresh(task)

    context = build_file_context(db_session, task)
    assert context is not None
    assert "--- 第 1 页 ---" in context.text
    assert "--- 第 2 页 ---" in context.text
    assert context.citations == [
        {"file_id": str(pdf.id), "filename": "manual.pdf", "page_no": 1},
        {"file_id": str(pdf.id), "filename": "manual.pdf", "page_no": 2},
    ]


def test_chat_context_orders_newest_files_first(db_session, workspace) -> None:
    now = datetime.now(timezone.utc)
    old = _file("old.md", now - timedelta(days=2))
    new = _file("new.md", now)
    project = Project(workspace_id=workspace.id, name="Recency")
    db_session.add_all([old, new, project])
    db_session.flush()
    db_session.add_all(
        [
            ProjectFile(project_id=project.id, file_id=old.id),
            ProjectFile(project_id=project.id, file_id=new.id),
        ]
    )
    task = Task(
        workspace_id=workspace.id, project_id=project.id, title="Recency task"
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    context = build_file_context(db_session, task)
    assert context is not None
    assert context.text.index("new.md") < context.text.index("old.md")
    assert "优先参考最近更新" in context.text


def test_chat_context_reads_full_article(
    monkeypatch, db_session, workspace
) -> None:
    now = datetime.now(timezone.utc)
    article = "# 长文章\n" + ("正文内容。" * 3_000) + "\nTAIL-MARKER"
    file = _file("article.md", now)
    file.size = len(article.encode())
    project = Project(workspace_id=workspace.id, name="Full article")
    db_session.add_all([file, project])
    db_session.flush()
    db_session.add(ProjectFile(project_id=project.id, file_id=file.id))
    task = Task(
        workspace_id=workspace.id, project_id=project.id, title="Read all"
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    monkeypatch.setattr(
        "app.modules.conversation.chat_context._read_excerpt",
        lambda storage, file_row: article,
    )
    context = build_file_context(db_session, task)
    assert context is not None
    assert "TAIL-MARKER" in context.text
    assert "已截断" not in context.text
    assert context.files[0]["status"] == "included"
