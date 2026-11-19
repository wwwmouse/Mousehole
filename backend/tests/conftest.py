from __future__ import annotations

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
from app.infrastructure.database.session import get_db
from app.main import create_app
from app.modules.file import storage as storage_module
from app.modules.file.models import File
from app.modules.workspace.models import Workspace


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
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
