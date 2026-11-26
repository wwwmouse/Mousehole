from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient

from app.modules.conversation import tools as chat_tools
from app.modules.file.models import File
from app.modules.ocr import repository as ocr_repository
from app.modules.task.models import Task


def _prepare_task_with_file(client: TestClient, db_session) -> tuple[str, str]:
    task = client.post("/api/v1/tasks", json={"title": "tool file test"}).json()
    uploaded = client.post(
        "/api/v1/files",
        files={"file": ("notes.md", b"# Notes\n\nimportant fact 42", "text/markdown")},
    ).json()
    linked = client.post(
        f"/api/v1/tasks/{task['id']}/files",
        json={"file_id": uploaded["id"], "action": "include"},
    )
    assert linked.status_code in (200, 201), linked.text
    return task["id"], uploaded["id"]


def test_read_task_file_accepts_filename(client: TestClient, db_session) -> None:
    task_id, file_id = _prepare_task_with_file(client, db_session)
    task_row = db_session.get(Task, uuid.UUID(task_id))

    by_name = asyncio.run(
        chat_tools.execute_tool(
            db_session, task_row, "read_task_file", {"filename": "notes.md"}
        )
    )
    assert by_name["ok"] is True
    assert "important fact 42" in by_name["content"]

    by_path = asyncio.run(
        chat_tools.execute_tool(
            db_session, task_row, "read_task_file", {"path": "some/notes.md"}
        )
    )
    assert by_path["ok"] is True

    by_id = asyncio.run(
        chat_tools.execute_tool(
            db_session, task_row, "read_task_file", {"file_id": file_id}
        )
    )
    assert by_id["ok"] is True


def test_read_task_file_uses_upload_limit(client: TestClient, db_session) -> None:
    task_id, file_id = _prepare_task_with_file(client, db_session)
    task_row = db_session.get(Task, uuid.UUID(task_id))
    file_row = db_session.get(File, uuid.UUID(file_id))
    assert file_row is not None
    # 上传上限当前为 50MB；30MB 的文件应允许工具读取，而不是固定卡在 25MB。
    file_row.size = 30 * 1024 * 1024
    db_session.commit()

    result = asyncio.run(
        chat_tools.execute_tool(
            db_session, task_row, "read_task_file", {"filename": "notes.md"}
        )
    )
    assert result["ok"] is True
    assert "important fact 42" in result["content"]


def test_read_task_file_prefers_page_text(
    client: TestClient, db_session
) -> None:
    task_id, file_id = _prepare_task_with_file(client, db_session)
    task_row = db_session.get(Task, uuid.UUID(task_id))
    ocr_repository.add_page(
        db_session,
        file_id=uuid.UUID(file_id),
        page_no=1,
        text="这是 OCR 页文本",
        text_source="ocr",
    )
    db_session.commit()

    result = asyncio.run(
        chat_tools.execute_tool(
            db_session, task_row, "read_task_file", {"file_id": file_id}
        )
    )
    assert result["ok"] is True
    assert "第 1 页" in result["content"]
    assert "这是 OCR 页文本" in result["content"]


def test_read_task_file_supports_paging(client: TestClient, db_session) -> None:
    task = client.post("/api/v1/tasks", json={"title": "paging"}).json()
    content = "\n".join(f"line-{index}" for index in range(2000))
    uploaded = client.post(
        "/api/v1/files",
        files={"file": ("long.md", content.encode(), "text/markdown")},
    ).json()
    client.post(
        f"/api/v1/tasks/{task['id']}/files",
        json={"file_id": uploaded["id"], "action": "include"},
    )
    task_row = db_session.get(Task, uuid.UUID(task["id"]))

    first = asyncio.run(
        chat_tools.execute_tool(
            db_session,
            task_row,
            "read_task_file",
            {"filename": "long.md", "offset": 0, "limit": 5000},
        )
    )
    assert first["ok"] is True
    assert first["has_more"] is True
    assert first["next_offset"] == 5000
    assert first["total_chars"] > 5000

    second = asyncio.run(
        chat_tools.execute_tool(
            db_session,
            task_row,
            "read_task_file",
            {"filename": "long.md", "offset": first["next_offset"], "limit": 5000},
        )
    )
    assert second["ok"] is True
    assert second["offset"] == 5000
    assert second["next_offset"] == 10000
    assert "line-" in second["content"]


def test_read_task_file_reports_available_names(client: TestClient, db_session) -> None:
    task_id, _ = _prepare_task_with_file(client, db_session)
    task_row = db_session.get(Task, uuid.UUID(task_id))

    missing = asyncio.run(
        chat_tools.execute_tool(
            db_session, task_row, "read_task_file", {"filename": "missing.md"}
        )
    )
    assert missing["ok"] is False
    assert "notes.md" in missing["summary"]
