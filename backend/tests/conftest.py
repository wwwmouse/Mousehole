from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.infrastructure.database import models  # noqa: F401  (register all tables)
from app.api.deps import get_db_factory
from app.infrastructure.database.session import get_db
from app.main import create_app
from app.modules.file import storage as storage_module
from app.modules.model import service as model_service
from app.modules.file.models import File
from app.modules.skill import service as skill_service
from app.modules.workspace.models import Workspace


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip opt-in PostgreSQL integration tests when no test database is configured.

    SQLite remains the default, fast test path; ``TEST_DATABASE_URL`` turns the
    ``postgres`` marker tests on (see ``scripts/test.ps1 -Postgres``).
    """

    if os.environ.get("TEST_DATABASE_URL", "").strip():
        return

    skip_postgres = pytest.mark.skip(
        reason="TEST_DATABASE_URL is not set; skipping PostgreSQL integration tests"
    )
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip_postgres)


@pytest.fixture(autouse=True)
def disable_real_tool_prepass(monkeypatch):
    """Never hit a real provider from tests: tool pre-pass is opt-in per test."""

    async def _disabled(*args, **kwargs):
        raise RuntimeError("tool pre-pass disabled in tests")

    monkeypatch.setattr(model_service, "complete_chat", _disabled)


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as seed:
        skill_service.ensure_builtin_skills(seed)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def session_factory(db_engine) -> sessionmaker[Session]:
    return sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db_session(session_factory) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def workspace(db_session: Session) -> Workspace:
    item = Workspace(name="Test Workspace", description="pytest workspace")
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


@pytest.fixture()
def test_storage_root() -> Iterator:
    """A writable, disposable-on-reboot directory inside the workspace.

    pytest's tmp_path deletes its base directory at session end, which the
    workspace sandbox forbids; keep test artifacts in an ignored directory
    instead and never depend on deletion.
    """
    root = (
        Path(__file__).resolve().parents[1]
        / ".test-artifacts"
        / uuid.uuid4().hex
        / "storage"
    )
    root.mkdir(parents=True, exist_ok=True)
    yield root


@pytest.fixture()
def test_data_root() -> Iterator[Path]:
    """Isolated data directory for provider config tests (never relies on deletion)."""
    root = (
        Path(__file__).resolve().parents[1]
        / ".test-artifacts"
        / uuid.uuid4().hex
        / "data"
    )
    root.mkdir(parents=True, exist_ok=True)
    yield root


@pytest.fixture()
def client(session_factory, workspace, test_storage_root, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setattr(
        storage_module, "_storage", storage_module.LocalFileStorage(test_storage_root)
    )
    app = create_app()

    def override_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_db_factory] = lambda: session_factory
    # No context manager: lifespan is skipped so tests never touch the real database.
    yield TestClient(app)


@pytest.fixture()
def sample_file(db_session: Session, workspace) -> File:
    """Insert a File row without going through the upload endpoint."""
    item = File(
        filename="notes.md",
        storage_key=f"objects/test/{uuid.uuid4().hex}.md",
        file_type="md",
        mime_type="text/markdown",
        size=12,
        content_hash=uuid.uuid4().hex * 2,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item
