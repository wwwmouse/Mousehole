from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.modules.conversation.chat_context import build_file_context
from app.modules.file.models import File, ProjectFile
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
