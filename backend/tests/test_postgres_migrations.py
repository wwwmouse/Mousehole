"""PostgreSQL integration tests for the Alembic migration chain and DB constraints.

These tests are opt-in: they only run when ``TEST_DATABASE_URL`` points at a
**disposable** PostgreSQL database. Without that variable the module is skipped
(see the ``postgres`` marker hook in ``tests/conftest.py``). Run them with::

    $env:TEST_DATABASE_URL = "postgresql+pg8000://mousehole:mousehole@localhost:5433/mousehole_test"
    .\\scripts\\test.ps1 -Postgres

The suite owns the target database: it drops the tables it manages before and
after the session and runs ``alembic upgrade head`` itself. A guard below
refuses to run against the application database configured in ``.env``.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, UniqueConstraint, create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.pool import NullPool

from app.core import config as app_config
from app.infrastructure.database import models  # noqa: F401  (register all tables)
from app.infrastructure.database.base import Base
from app.modules.artifact.models import Artifact, ArtifactSeries
from app.modules.conversation.models import Conversation, Message
from app.modules.execution.models import (
    Execution,
    ExecutionFileSnapshot,
    ExecutionStep,
)
from app.modules.file.models import File, ProjectFile, TaskFileOverride
from app.modules.project.models import Project
from app.modules.skill.models import Skill, SkillFile, TaskSkill
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace

BACKEND_DIR = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.postgres


# ---------------------------------------------------------------------------
# Alembic helpers
# ---------------------------------------------------------------------------


def _alembic_config() -> Config:
    """Build an Alembic config that targets the test database.

    ``alembic/env.py`` always reads the URL from ``app.core.config`` and calls
    ``fileConfig()`` when an ini file is attached. We therefore skip the ini
    logging config (to keep pytest's log handlers) and temporarily patch
    ``get_settings`` while a command runs.
    """

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.config_file_name = None
    return config


@contextmanager
def _alembic_settings(database_url: str) -> Iterator[None]:
    settings = app_config.get_settings().model_copy(
        update={"database_url": database_url}
    )
    with mock.patch.object(app_config, "get_settings", return_value=settings):
        yield


def _upgrade(database_url: str, revision: str = "head") -> None:
    with _alembic_settings(database_url):
        command.upgrade(_alembic_config(), revision)


def _downgrade(database_url: str, revision: str) -> None:
    with _alembic_settings(database_url):
        command.downgrade(_alembic_config(), revision)


def _current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _managed_table_names() -> list[str]:
    return ["alembic_version", *Base.metadata.tables.keys()]


def _drop_managed_tables(engine: Engine) -> None:
    """Remove every table this suite may have created (idempotent)."""

    with engine.begin() as connection:
        for name in _managed_table_names():
            connection.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL is not set; skipping PostgreSQL integration tests"
        )

    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        pytest.fail(
            f"TEST_DATABASE_URL must be a PostgreSQL URL, got {parsed.drivername!r}"
        )
    if parsed.database in (None, "", "postgres", "template0", "template1"):
        pytest.fail(
            "TEST_DATABASE_URL must point at a dedicated test database, "
            f"not the maintenance database {parsed.database!r}"
        )

    app_url = make_url(app_config.get_settings().database_url)
    same_target = (parsed.host, parsed.port, parsed.database) == (
        app_url.host,
        app_url.port,
        app_url.database,
    )
    if same_target:
        pytest.fail(
            "TEST_DATABASE_URL points at the application database configured in "
            ".env; refusing to run destructive migration tests against it"
        )
    return _prefer_loopback(url)


def _prefer_loopback(database_url: str) -> str:
    """Use 127.0.0.1 instead of ``localhost`` when both reach the same server.

    On Windows/Docker Desktop ``localhost`` resolves to ``::1`` first and each
    pg8000 connect then stalls for ~2 seconds before falling back to IPv4. That
    would make this suite minutes long. The probe keeps the original URL when
    the IPv4 loopback is not reachable.
    """

    parsed = make_url(database_url)
    if parsed.host != "localhost":
        return database_url

    loopback_url = parsed.set(host="127.0.0.1").render_as_string(hide_password=False)
    probe = create_engine(loopback_url, poolclass=NullPool, connect_args={"timeout": 5})
    try:
        with probe.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:  # pragma: no cover - fall back to the user's host
        return database_url
    finally:
        probe.dispose()
    return loopback_url


@pytest.fixture(scope="session")
def postgres_engine(postgres_url: str) -> Iterator[Engine]:
    engine = create_engine(postgres_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:  # pragma: no cover - environment failure
        engine.dispose()
        pytest.fail(f"cannot connect to TEST_DATABASE_URL ({postgres_url}): {exc}")

    try:
        _drop_managed_tables(engine)
        _upgrade(postgres_url)
        yield engine
    finally:
        try:
            _drop_managed_tables(engine)
        finally:
            engine.dispose()


@pytest.fixture()
def pg_conn(postgres_engine: Engine) -> Iterator[Connection]:
    """A connection whose transaction is rolled back after each test.

    Tests that create rows do so inside this transaction, so the migrated schema
    is never polluted with data.
    """

    connection = postgres_engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


# ---------------------------------------------------------------------------
# Seed data (rolled back by the pg_conn fixture)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Seed:
    workspace: uuid.UUID
    project: uuid.UUID
    task: uuid.UUID
    file: uuid.UUID
    second_file: uuid.UUID
    project_file: uuid.UUID
    override: uuid.UUID
    conversation: uuid.UUID
    message: uuid.UUID
    execution: uuid.UUID
    step: uuid.UUID
    snapshot: uuid.UUID
    series: uuid.UUID
    artifact: uuid.UUID
    skill: uuid.UUID
    skill_name: str
    skill_code: str
    file_storage_key: str


def _insert(connection: Connection, model: Any, **values: Any) -> uuid.UUID | None:
    table = model.__table__
    if "id" in table.c and "id" not in values:
        values["id"] = uuid.uuid4()
    connection.execute(table.insert().values(**values))
    return values.get("id")


def _seed_core(connection: Connection) -> Seed:
    workspace = _insert(
        connection,
        Workspace,
        name="Postgres integration workspace",
        description="H3 migration/constraint tests",
    )
    project = _insert(
        connection,
        Project,
        workspace_id=workspace,
        name="Postgres Project",
        status="active",
    )
    task = _insert(
        connection,
        Task,
        workspace_id=workspace,
        project_id=project,
        title="Postgres Task",
        status="active",
    )

    content_hash = "a" * 64
    file_storage_key = f"objects/pg-test/{uuid.uuid4().hex}.md"
    file = _insert(
        connection,
        File,
        filename="notes.md",
        storage_key=file_storage_key,
        file_type="md",
        mime_type="text/markdown",
        size=12,
        content_hash=content_hash,
        status="active",
    )
    second_file = _insert(
        connection,
        File,
        filename="second.md",
        storage_key=f"objects/pg-test/{uuid.uuid4().hex}.md",
        file_type="md",
        mime_type="text/markdown",
        size=8,
        content_hash="b" * 64,
        status="active",
    )

    project_file = _insert(
        connection, ProjectFile, project_id=project, file_id=file
    )
    override = _insert(
        connection,
        TaskFileOverride,
        task_id=task,
        file_id=file,
        action="include",
    )

    conversation = _insert(connection, Conversation, task_id=task)
    message = _insert(
        connection,
        Message,
        conversation_id=conversation,
        role="user",
        content="hello from postgres tests",
        sequence=1,
    )

    execution = _insert(
        connection, Execution, task_id=task, sequence=1, status="pending"
    )
    step = _insert(
        connection,
        ExecutionStep,
        execution_id=execution,
        sequence=1,
        step_type="parse",
        name="parse files",
        status="pending",
    )
    snapshot = _insert(
        connection,
        ExecutionFileSnapshot,
        execution_id=execution,
        file_id=file,
        filename_snapshot="notes.md",
        content_hash_snapshot=content_hash,
        source_type="task_added",
        usage_mode="direct",
    )

    series = _insert(
        connection, ArtifactSeries, task_id=task, title="Postgres Report"
    )
    artifact = _insert(
        connection,
        Artifact,
        series_id=series,
        version=1,
        title="Postgres Report",
        content_type="text/markdown",
        content="# v1",
    )

    skill_name = f"pg-skill-{uuid.uuid4().hex[:8]}"
    skill_code = f"pg-{uuid.uuid4().hex[:8]}"
    skill = _insert(
        connection,
        Skill,
        name=skill_name,
        code=skill_code,
        system_prompt="",
        instruction="",
        output_type="text/markdown",
        is_builtin=False,
    )
    _insert(connection, TaskSkill, task_id=task, skill_id=skill)
    _insert(connection, SkillFile, skill_id=skill, file_id=second_file)

    return Seed(
        workspace=workspace,
        project=project,
        task=task,
        file=file,
        second_file=second_file,
        project_file=project_file,
        override=override,
        conversation=conversation,
        message=message,
        execution=execution,
        step=step,
        snapshot=snapshot,
        series=series,
        artifact=artifact,
        skill=skill,
        skill_name=skill_name,
        skill_code=skill_code,
        file_storage_key=file_storage_key,
    )


@pytest.fixture()
def pg_seed(pg_conn: Connection) -> Seed:
    return _seed_core(pg_conn)


# ---------------------------------------------------------------------------
# Small assertion helpers
# ---------------------------------------------------------------------------


# PostgreSQL SQLSTATEs for integrity violations. pg8000 only maps 23505
# (unique violation) to sqlalchemy.exc.IntegrityError, so CHECK (23514) and
# foreign-key (23503) failures surface as ProgrammingError; assert on the
# SQLSTATE instead of the SQLAlchemy exception subclass.
_INTEGRITY_SQLSTATES = {"23503", "23505", "23514", "23P01"}


def _sqlstate(exc: DBAPIError) -> str | None:
    args = getattr(exc.orig, "args", ())
    if args and isinstance(args[0], dict):
        return args[0].get("C")
    return None


def _constraint_name(exc: DBAPIError) -> str | None:
    """Extract the PostgreSQL constraint name from a pg8000 DBAPI error."""

    args = getattr(exc.orig, "args", ())
    if args and isinstance(args[0], dict):
        return args[0].get("n")
    return None


def _assert_integrity_error(
    connection: Connection,
    model: Any,
    values: dict[str, Any],
    expected_constraint: str,
) -> None:
    with pytest.raises(DBAPIError) as excinfo:
        with connection.begin_nested():
            connection.execute(model.__table__.insert().values(**values))
    assert _sqlstate(excinfo.value) in _INTEGRITY_SQLSTATES
    assert _constraint_name(excinfo.value) == expected_constraint


# ---------------------------------------------------------------------------
# Migration chain / alembic state
# ---------------------------------------------------------------------------


def test_migration_graph_is_linear_with_single_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    revisions = list(script.walk_revisions())  # head -> base

    assert script.get_heads(), "alembic must declare at least one head"
    assert len(script.get_heads()) == 1, (
        f"migration chain has multiple heads: {script.get_heads()}"
    )
    assert revisions, "no Alembic revisions found"
    assert revisions[-1].down_revision is None, "oldest revision must be the base"

    # Every revision is the parent of exactly one child (a linear chain).
    parents = [item.down_revision for item in revisions if item.down_revision]
    assert len(parents) == len(set(parents)), "migration chain branches or merges"


def test_database_is_at_migration_head(postgres_engine: Engine) -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    head = script.get_current_head()
    assert head is not None
    assert _current_revision(postgres_engine) == head, (
        "test database is not at the Alembic head; run alembic upgrade head"
    )

    with postgres_engine.connect() as connection:
        versions = (
            connection.execute(text("SELECT version_num FROM alembic_version"))
            .scalars()
            .all()
        )
    assert versions == [head]


def test_upgrade_head_is_idempotent(
    postgres_engine: Engine, postgres_url: str
) -> None:
    before = _current_revision(postgres_engine)
    _upgrade(postgres_url)
    assert _current_revision(postgres_engine) == before


def test_migrated_schema_matches_orm_metadata(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        diffs = compare_metadata(context, Base.metadata)

    # PostgreSQL silently omits a UNIQUE constraint whose columns are exactly
    # the primary key (task_skills has PK(task_id, skill_id) and a redundant
    # uq_task_skills_task_skill). Reflection can never see it, so autogenerate
    # always reports it as "missing"; the PK enforces the same uniqueness.
    unexpected = [diff for diff in diffs if not _is_redundant_task_skills_unique(diff)]
    assert unexpected == [], (
        "migrated PostgreSQL schema drifted from the ORM metadata:\n"
        + "\n".join(repr(diff) for diff in unexpected)
    )


def _is_redundant_task_skills_unique(diff: Any) -> bool:
    if not isinstance(diff, tuple) or len(diff) != 2 or diff[0] != "add_constraint":
        return False
    constraint = diff[1]
    if not isinstance(constraint, UniqueConstraint):
        return False
    table = constraint.table
    if table is None or table.name != "task_skills":
        return False
    return {column.name for column in constraint.columns} == {"task_id", "skill_id"}


def test_downgrade_and_upgrade_roundtrip(
    postgres_engine: Engine, postgres_url: str
) -> None:
    head = _current_revision(postgres_engine)
    assert head is not None
    try:
        _downgrade(postgres_url, "g7b8c9d0e1f2")
        assert _current_revision(postgres_engine) == "g7b8c9d0e1f2"

        with postgres_engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            artifact_columns = {
                column["name"]
                for column in inspect(connection).get_columns("artifacts")
            }
            file_columns = {
                column["name"] for column in inspect(connection).get_columns("files")
            }
            message_columns = {
                column["name"]
                for column in inspect(connection).get_columns("messages")
            }

        assert {"skills", "skill_files", "task_skills"}.isdisjoint(tables)
        assert {"source_type", "source_message_id"}.isdisjoint(artifact_columns)
        assert "is_temporary" not in file_columns
        assert "metadata" not in message_columns
    finally:
        # Restore head even if an assertion above fails.
        _upgrade(postgres_url)

    assert _current_revision(postgres_engine) == head
    with postgres_engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        artifact_columns = {
            column["name"] for column in inspect(connection).get_columns("artifacts")
        }
    assert {"skills", "skill_files", "task_skills"} <= tables
    assert {"source_type", "source_message_id"} <= artifact_columns


def test_full_downgrade_to_base(
    postgres_engine: Engine, postgres_url: str
) -> None:
    try:
        _downgrade(postgres_url, "base")
        with postgres_engine.connect() as connection:
            remaining = set(inspect(connection).get_table_names())
        assert remaining <= {"alembic_version"}, (
            f"tables left after downgrade base: {sorted(remaining)}"
        )
    finally:
        _upgrade(postgres_url)


# ---------------------------------------------------------------------------
# Table / column structure and PostgreSQL-specific types
# ---------------------------------------------------------------------------


CORE_TABLES = {
    "alembic_version",
    "workspaces",
    "projects",
    "tasks",
    "files",
    "project_files",
    "task_file_overrides",
    "conversations",
    "messages",
    "executions",
    "execution_steps",
    "execution_file_snapshots",
    "artifact_series",
    "artifacts",
    "skills",
    "skill_files",
    "task_skills",
}

REQUIRED_COLUMNS = {
    "workspaces": {
        "id",
        "name",
        "description",
        "default_temperature",
        "default_max_tokens",
        "context_budget_tokens",
        "created_at",
        "updated_at",
    },
    "projects": {"id", "workspace_id", "name", "description", "status"},
    "tasks": {
        "id",
        "workspace_id",
        "project_id",
        "title",
        "description",
        "status",
        "model_provider",
        "model_name",
        "usage",
        "temperature",
        "max_tokens",
    },
    "files": {
        "id",
        "filename",
        "storage_key",
        "file_type",
        "mime_type",
        "size",
        "content_hash",
        "status",
        "is_temporary",
        "owner_task_id",
        "owner_project_id",
    },
    "project_files": {"id", "project_id", "file_id", "added_at"},
    "task_file_overrides": {"id", "task_id", "file_id", "action", "created_at"},
    "conversations": {
        "id",
        "task_id",
        "context_start_sequence",
        "created_at",
        "updated_at",
    },
    "messages": {
        "id",
        "conversation_id",
        "role",
        "content",
        "sequence",
        "usage",
        "metadata",
        "created_at",
    },
    "executions": {
        "id",
        "task_id",
        "sequence",
        "status",
        "skill_id",
        "skill_name",
        "model_provider",
        "model_name",
        "temperature",
        "max_tokens",
        "input_summary",
        "error_message",
        "error_code",
        "usage",
        "started_at",
        "completed_at",
        "created_at",
    },
    "execution_steps": {
        "id",
        "execution_id",
        "sequence",
        "step_type",
        "name",
        "status",
        "input_summary",
        "output_summary",
        "started_at",
        "completed_at",
        "error_message",
    },
    "execution_file_snapshots": {
        "id",
        "execution_id",
        "file_id",
        "filename_snapshot",
        "content_hash_snapshot",
        "source_type",
        "usage_mode",
        "used_at",
    },
    "artifact_series": {
        "id",
        "task_id",
        "title",
        "description",
        "current_artifact_id",
        "created_at",
        "updated_at",
    },
    "artifacts": {
        "id",
        "series_id",
        "source_execution_id",
        "source_type",
        "source_message_id",
        "version",
        "title",
        "content_type",
        "content",
        "storage_key",
        "created_at",
    },
    "skills": {
        "id",
        "code",
        "name",
        "description",
        "system_prompt",
        "instruction",
        "output_type",
        "is_builtin",
        "created_at",
        "updated_at",
    },
    "skill_files": {"skill_id", "file_id", "path", "created_at"},
    "task_skills": {"task_id", "skill_id", "created_at"},
}


def test_core_tables_and_columns_exist(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        assert CORE_TABLES <= tables, (
            f"missing tables: {sorted(CORE_TABLES - tables)}"
        )
        for table, expected_columns in REQUIRED_COLUMNS.items():
            actual_columns = {
                column["name"] for column in inspector.get_columns(table)
            }
            missing = expected_columns - actual_columns
            assert not missing, f"{table} is missing columns: {sorted(missing)}"


@dataclass(frozen=True)
class ColumnType:
    table: str
    column: str
    data_type: str


POSTGRES_COLUMN_TYPES = [
    ColumnType("workspaces", "id", "uuid"),
    ColumnType("projects", "id", "uuid"),
    ColumnType("projects", "workspace_id", "uuid"),
    ColumnType("tasks", "id", "uuid"),
    ColumnType("tasks", "workspace_id", "uuid"),
    ColumnType("tasks", "usage", "jsonb"),
    ColumnType("messages", "usage", "jsonb"),
    ColumnType("messages", "metadata", "jsonb"),
    ColumnType("executions", "usage", "jsonb"),
    ColumnType("executions", "id", "uuid"),
    ColumnType("execution_steps", "execution_id", "uuid"),
    ColumnType("execution_file_snapshots", "file_id", "uuid"),
    ColumnType("artifacts", "id", "uuid"),
    ColumnType("artifacts", "series_id", "uuid"),
    ColumnType("skills", "id", "uuid"),
    ColumnType("skill_files", "skill_id", "uuid"),
    ColumnType("task_skills", "task_id", "uuid"),
    ColumnType("files", "created_at", "timestamp with time zone"),
    ColumnType("workspaces", "created_at", "timestamp with time zone"),
    ColumnType("executions", "created_at", "timestamp with time zone"),
    ColumnType("messages", "created_at", "timestamp with time zone"),
]


@pytest.mark.parametrize(
    "column_type",
    POSTGRES_COLUMN_TYPES,
    ids=[f"{item.table}.{item.column}" for item in POSTGRES_COLUMN_TYPES],
)
def test_postgres_native_column_types(
    postgres_engine: Engine, column_type: ColumnType
) -> None:
    with postgres_engine.connect() as connection:
        data_type = connection.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND table_name = :table AND column_name = :column"
            ),
            {"table": column_type.table, "column": column_type.column},
        ).scalar_one()
    assert data_type == column_type.data_type


# ---------------------------------------------------------------------------
# Foreign keys
# ---------------------------------------------------------------------------


# (table, column) -> (referenced table, referenced column, on delete action)
EXPECTED_FOREIGN_KEYS: dict[tuple[str, str], tuple[str, str, str]] = {
    ("projects", "workspace_id"): ("workspaces", "id", "RESTRICT"),
    ("tasks", "workspace_id"): ("workspaces", "id", "RESTRICT"),
    ("tasks", "project_id"): ("projects", "id", "RESTRICT"),
    ("project_files", "project_id"): ("projects", "id", "RESTRICT"),
    ("project_files", "file_id"): ("files", "id", "RESTRICT"),
    ("task_file_overrides", "task_id"): ("tasks", "id", "RESTRICT"),
    ("task_file_overrides", "file_id"): ("files", "id", "RESTRICT"),
    ("conversations", "task_id"): ("tasks", "id", "RESTRICT"),
    ("messages", "conversation_id"): ("conversations", "id", "RESTRICT"),
    ("executions", "task_id"): ("tasks", "id", "RESTRICT"),
    ("execution_steps", "execution_id"): ("executions", "id", "RESTRICT"),
    ("execution_file_snapshots", "execution_id"): (
        "executions",
        "id",
        "RESTRICT",
    ),
    ("execution_file_snapshots", "file_id"): ("files", "id", "RESTRICT"),
    ("artifact_series", "task_id"): ("tasks", "id", "RESTRICT"),
    ("artifacts", "series_id"): ("artifact_series", "id", "RESTRICT"),
    ("artifacts", "source_execution_id"): ("executions", "id", "RESTRICT"),
    ("artifacts", "source_message_id"): ("messages", "id", "SET NULL"),
    ("task_skills", "task_id"): ("tasks", "id", "CASCADE"),
    ("task_skills", "skill_id"): ("skills", "id", "CASCADE"),
    ("skill_files", "skill_id"): ("skills", "id", "CASCADE"),
    ("skill_files", "file_id"): ("files", "id", "CASCADE"),
}

_ON_DELETE_LABELS = {
    "a": "NO ACTION",
    "r": "RESTRICT",
    "c": "CASCADE",
    "n": "SET NULL",
    "d": "SET DEFAULT",
}


def _actual_foreign_keys(connection: Connection) -> dict[tuple[str, str], tuple[str, str, str]]:
    rows = connection.execute(
        text(
            """
            SELECT
                child.relname AS table_name,
                child_column.attname AS column_name,
                parent.relname AS ref_table,
                parent_column.attname AS ref_column,
                constraint_record.confdeltype AS on_delete
            FROM pg_constraint AS constraint_record
            JOIN pg_class AS child
              ON child.oid = constraint_record.conrelid
            JOIN pg_class AS parent
              ON parent.oid = constraint_record.confrelid
            JOIN unnest(
                constraint_record.conkey, constraint_record.confkey
            ) AS key_columns(attnum, ref_attnum) ON true
            JOIN pg_attribute AS child_column
              ON child_column.attrelid = constraint_record.conrelid
             AND child_column.attnum = key_columns.attnum
            JOIN pg_attribute AS parent_column
              ON parent_column.attrelid = constraint_record.confrelid
             AND parent_column.attnum = key_columns.ref_attnum
            WHERE constraint_record.contype = 'f'
              AND child.relnamespace = 'public'::regnamespace
            """
        )
    ).all()

    actual: dict[tuple[str, str], tuple[str, str, str]] = {}
    for table, column, ref_table, ref_column, on_delete in rows:
        actual[(table, column)] = (
            ref_table,
            ref_column,
            _ON_DELETE_LABELS.get(on_delete, on_delete),
        )
    return actual


def test_foreign_key_ondelete_actions(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        actual = _actual_foreign_keys(connection)
    assert actual == EXPECTED_FOREIGN_KEYS


def test_ondelete_restrict_blocks_parent_deletion(
    pg_conn: Connection, pg_seed: Seed
) -> None:
    for table, identifier in [
        ("workspaces", pg_seed.workspace),
        ("projects", pg_seed.project),
        ("tasks", pg_seed.task),
        ("files", pg_seed.file),
        ("executions", pg_seed.execution),
        ("artifact_series", pg_seed.series),
    ]:
        with pytest.raises(DBAPIError) as excinfo:
            with pg_conn.begin_nested():
                pg_conn.execute(
                    text(f'DELETE FROM "{table}" WHERE id = :id'),
                    {"id": identifier},
                )
        assert _sqlstate(excinfo.value) == "23503", table


def test_missing_foreign_key_target_is_rejected(
    pg_conn: Connection,
) -> None:
    with pytest.raises(DBAPIError) as excinfo:
        with pg_conn.begin_nested():
            pg_conn.execute(
                Task.__table__.insert().values(
                    id=uuid.uuid4(),
                    workspace_id=uuid.uuid4(),
                    title="orphan task",
                    status="active",
                )
            )
    assert _sqlstate(excinfo.value) == "23503"
    assert _constraint_name(excinfo.value) == "fk_tasks_workspace_id_workspaces"


def test_ondelete_cascade_removes_dependent_rows(
    pg_conn: Connection, pg_seed: Seed
) -> None:
    with pg_conn.begin_nested():
        task_skill_count = pg_conn.execute(
            text("SELECT count(*) FROM task_skills WHERE skill_id = :id"),
            {"id": pg_seed.skill},
        ).scalar_one()
        skill_file_count = pg_conn.execute(
            text("SELECT count(*) FROM skill_files WHERE skill_id = :id"),
            {"id": pg_seed.skill},
        ).scalar_one()
        assert (task_skill_count, skill_file_count) == (1, 1)

        pg_conn.execute(
            text("DELETE FROM skills WHERE id = :id"), {"id": pg_seed.skill}
        )
        task_skill_count = pg_conn.execute(
            text("SELECT count(*) FROM task_skills WHERE skill_id = :id"),
            {"id": pg_seed.skill},
        ).scalar_one()
        skill_file_count = pg_conn.execute(
            text("SELECT count(*) FROM skill_files WHERE skill_id = :id"),
            {"id": pg_seed.skill},
        ).scalar_one()
        assert (task_skill_count, skill_file_count) == (0, 0)


def test_ondelete_set_null_clears_artifact_source_message(
    pg_conn: Connection, pg_seed: Seed
) -> None:
    artifact_id = uuid.uuid4()
    with pg_conn.begin_nested():
        pg_conn.execute(
            Artifact.__table__.insert().values(
                id=artifact_id,
                series_id=pg_seed.series,
                source_type="chat",
                source_message_id=pg_seed.message,
                version=2,
                title="Chat report",
                content_type="text/markdown",
                content="# chat",
            )
        )
        pg_conn.execute(
            text("DELETE FROM messages WHERE id = :id"), {"id": pg_seed.message}
        )
        source_message_id = pg_conn.execute(
            text("SELECT source_message_id FROM artifacts WHERE id = :id"),
            {"id": artifact_id},
        ).scalar_one()
        assert source_message_id is None


# ---------------------------------------------------------------------------
# CHECK constraints (status enumerations, version > 0, ...)
# ---------------------------------------------------------------------------


CHECK_CONSTRAINT_NAMES = {
    "ck_files_file_status_valid",
    "ck_projects_project_status_valid",
    "ck_tasks_task_status_valid",
    "ck_task_file_overrides_override_action_valid",
    "ck_messages_message_role_valid",
    "ck_executions_execution_status_valid",
    "ck_execution_steps_execution_step_status_valid",
    "ck_execution_file_snapshots_snapshot_source_type_valid",
    "ck_execution_file_snapshots_snapshot_usage_mode_valid",
    "ck_artifacts_artifact_version_positive",
}


def test_check_constraints_are_declared(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        names = set(
            connection.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE contype = 'c' "
                    "AND connamespace = 'public'::regnamespace"
                )
            ).scalars()
        )
    assert CHECK_CONSTRAINT_NAMES <= names, (
        f"missing check constraints: {sorted(CHECK_CONSTRAINT_NAMES - names)}"
    )


def _invalid_case(
    label: str,
    model: Any,
    build: Callable[[Seed], dict[str, Any]],
    constraint: str,
) -> tuple[str, Any, Callable[[Seed], dict[str, Any]], str]:
    return label, model, build, constraint


CHECK_VIOLATION_CASES = [
    _invalid_case(
        "project_status",
        Project,
        lambda seed: {
            "workspace_id": seed.workspace,
            "name": "invalid project",
            "status": "deleted",
        },
        "ck_projects_project_status_valid",
    ),
    _invalid_case(
        "task_status",
        Task,
        lambda seed: {
            "workspace_id": seed.workspace,
            "title": "invalid task",
            "status": "deleted",
        },
        "ck_tasks_task_status_valid",
    ),
    _invalid_case(
        "file_status",
        File,
        lambda seed: {
            "filename": "invalid.md",
            "storage_key": f"objects/pg-test/{uuid.uuid4().hex}.md",
            "file_type": "md",
            "mime_type": "text/markdown",
            "size": 1,
            "content_hash": "c" * 64,
            "status": "gone",
        },
        "ck_files_file_status_valid",
    ),
    _invalid_case(
        "execution_status",
        Execution,
        lambda seed: {
            "task_id": seed.task,
            "sequence": 99,
            "status": "archived",
        },
        "ck_executions_execution_status_valid",
    ),
    _invalid_case(
        "execution_step_status",
        ExecutionStep,
        lambda seed: {
            "execution_id": seed.execution,
            "sequence": 99,
            "step_type": "parse",
            "name": "invalid step",
            "status": "cancelled",
        },
        "ck_execution_steps_execution_step_status_valid",
    ),
    _invalid_case(
        "message_role",
        Message,
        lambda seed: {
            "conversation_id": seed.conversation,
            "role": "robot",
            "content": "invalid",
            "sequence": 99,
        },
        "ck_messages_message_role_valid",
    ),
    _invalid_case(
        "override_action",
        TaskFileOverride,
        lambda seed: {
            "task_id": seed.task,
            "file_id": seed.second_file,
            "action": "delete",
        },
        "ck_task_file_overrides_override_action_valid",
    ),
    _invalid_case(
        "snapshot_source_type",
        ExecutionFileSnapshot,
        lambda seed: {
            "execution_id": seed.execution,
            "file_id": seed.second_file,
            "filename_snapshot": "second.md",
            "content_hash_snapshot": "b" * 64,
            "source_type": "other",
            "usage_mode": "direct",
        },
        "ck_execution_file_snapshots_snapshot_source_type_valid",
    ),
    _invalid_case(
        "snapshot_usage_mode",
        ExecutionFileSnapshot,
        lambda seed: {
            "execution_id": seed.execution,
            "file_id": seed.second_file,
            "filename_snapshot": "second.md",
            "content_hash_snapshot": "b" * 64,
            "source_type": "task_added",
            "usage_mode": "full",
        },
        "ck_execution_file_snapshots_snapshot_usage_mode_valid",
    ),
    _invalid_case(
        "artifact_version",
        Artifact,
        lambda seed: {
            "series_id": seed.series,
            "version": 0,
            "title": "invalid version",
            "content_type": "text/markdown",
        },
        "ck_artifacts_artifact_version_positive",
    ),
]


@pytest.mark.parametrize(
    "model,build,constraint",
    [case[1:] for case in CHECK_VIOLATION_CASES],
    ids=[case[0] for case in CHECK_VIOLATION_CASES],
)
def test_check_constraints_reject_invalid_values(
    pg_conn: Connection,
    pg_seed: Seed,
    model: Any,
    build: Callable[[Seed], dict[str, Any]],
    constraint: str,
) -> None:
    _assert_integrity_error(pg_conn, model, build(pg_seed), constraint)


# ---------------------------------------------------------------------------
# UNIQUE constraints
# ---------------------------------------------------------------------------


UNIQUE_CONSTRAINT_NAMES = {
    "uq_files_storage_key",
    "project_file_unique",
    "task_file_override_unique",
    "conversation_task_unique",
    "message_sequence_unique",
    "execution_sequence_unique",
    "execution_step_sequence_unique",
    "execution_file_unique",
    "artifact_series_title_unique",
    "artifact_version_unique",
    "uq_skills_code",
    "uq_skills_name",
}


def test_unique_constraints_are_declared(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        names = set(
            connection.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE contype = 'u' "
                    "AND connamespace = 'public'::regnamespace"
                )
            ).scalars()
        )
    assert UNIQUE_CONSTRAINT_NAMES <= names, (
        f"missing unique constraints: {sorted(UNIQUE_CONSTRAINT_NAMES - names)}"
    )


def _duplicate_case(
    label: str,
    model: Any,
    build: Callable[[Seed], dict[str, Any]],
    constraint: str,
) -> tuple[str, Any, Callable[[Seed], dict[str, Any]], str]:
    return label, model, build, constraint


# NOTE: task_skills has PK(task_id, skill_id) and a redundant unique constraint.
# PostgreSQL silently skips the UNIQUE (primary-key columns are already unique),
# so a duplicate insert is reported against pk_task_skills.
DUPLICATE_VIOLATION_CASES = [
    _duplicate_case(
        "artifact_version",
        Artifact,
        lambda seed: {
            "series_id": seed.series,
            "version": 1,
            "title": "duplicate version",
            "content_type": "text/markdown",
        },
        "artifact_version_unique",
    ),
    _duplicate_case(
        "execution_sequence",
        Execution,
        lambda seed: {"task_id": seed.task, "sequence": 1, "status": "pending"},
        "execution_sequence_unique",
    ),
    _duplicate_case(
        "execution_step_sequence",
        ExecutionStep,
        lambda seed: {
            "execution_id": seed.execution,
            "sequence": 1,
            "step_type": "parse",
            "name": "duplicate step",
            "status": "pending",
        },
        "execution_step_sequence_unique",
    ),
    _duplicate_case(
        "execution_file_snapshot",
        ExecutionFileSnapshot,
        lambda seed: {
            "execution_id": seed.execution,
            "file_id": seed.file,
            "filename_snapshot": "notes.md",
            "content_hash_snapshot": "a" * 64,
            "source_type": "task_added",
            "usage_mode": "direct",
        },
        "execution_file_unique",
    ),
    _duplicate_case(
        "conversation_task",
        Conversation,
        lambda seed: {"task_id": seed.task},
        "conversation_task_unique",
    ),
    _duplicate_case(
        "message_sequence",
        Message,
        lambda seed: {
            "conversation_id": seed.conversation,
            "role": "assistant",
            "content": "duplicate sequence",
            "sequence": 1,
        },
        "message_sequence_unique",
    ),
    _duplicate_case(
        "artifact_series_title",
        ArtifactSeries,
        lambda seed: {"task_id": seed.task, "title": "Postgres Report"},
        "artifact_series_title_unique",
    ),
    _duplicate_case(
        "skill_name",
        Skill,
        lambda seed: {
            "name": seed.skill_name,
            "code": f"pg-{uuid.uuid4().hex[:8]}",
            "system_prompt": "",
            "instruction": "",
            "output_type": "text/markdown",
            "is_builtin": False,
        },
        "uq_skills_name",
    ),
    _duplicate_case(
        "skill_code",
        Skill,
        lambda seed: {
            "name": f"pg-skill-{uuid.uuid4().hex[:8]}",
            "code": seed.skill_code,
            "system_prompt": "",
            "instruction": "",
            "output_type": "text/markdown",
            "is_builtin": False,
        },
        "uq_skills_code",
    ),
    _duplicate_case(
        "task_skill_primary_key",
        TaskSkill,
        lambda seed: {"task_id": seed.task, "skill_id": seed.skill},
        "pk_task_skills",
    ),
    _duplicate_case(
        "project_file",
        ProjectFile,
        lambda seed: {"project_id": seed.project, "file_id": seed.file},
        "project_file_unique",
    ),
    _duplicate_case(
        "task_file_override",
        TaskFileOverride,
        lambda seed: {
            "task_id": seed.task,
            "file_id": seed.file,
            "action": "include",
        },
        "task_file_override_unique",
    ),
    _duplicate_case(
        "file_storage_key",
        File,
        lambda seed: {
            "filename": "duplicate.md",
            "storage_key": seed.file_storage_key,
            "file_type": "md",
            "mime_type": "text/markdown",
            "size": 1,
            "content_hash": "d" * 64,
            "status": "active",
        },
        "uq_files_storage_key",
    ),
]


@pytest.mark.parametrize(
    "model,build,constraint",
    [case[1:] for case in DUPLICATE_VIOLATION_CASES],
    ids=[case[0] for case in DUPLICATE_VIOLATION_CASES],
)
def test_unique_constraints_reject_duplicates(
    pg_conn: Connection,
    pg_seed: Seed,
    model: Any,
    build: Callable[[Seed], dict[str, Any]],
    constraint: str,
) -> None:
    _assert_integrity_error(pg_conn, model, build(pg_seed), constraint)


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------


EXPECTED_INDEXES: set[tuple[str, str]] = {
    ("files", "ix_files_content_hash"),
    ("files", "ix_files_owner_task_id"),
    ("projects", "ix_projects_workspace_id"),
    ("project_files", "ix_project_files_file_id"),
    ("project_files", "ix_project_files_project_id"),
    ("tasks", "ix_tasks_project_id"),
    ("tasks", "ix_tasks_workspace_id"),
    ("task_file_overrides", "ix_task_file_overrides_file_id"),
    ("task_file_overrides", "ix_task_file_overrides_task_id"),
    ("conversations", "ix_conversations_task_id"),
    ("messages", "ix_messages_conversation_id"),
    ("executions", "ix_executions_task_id"),
    ("execution_steps", "ix_execution_steps_execution_id"),
    ("execution_file_snapshots", "ix_execution_file_snapshots_execution_id"),
    ("execution_file_snapshots", "ix_execution_file_snapshots_file_id"),
    ("artifact_series", "ix_artifact_series_task_id"),
    ("artifacts", "ix_artifacts_series_id"),
    ("artifacts", "ix_artifacts_source_execution_id"),
    ("artifacts", "ix_artifacts_source_message_id"),
}


def test_key_indexes_exist(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT tablename, indexname FROM pg_indexes "
                "WHERE schemaname = 'public'"
            )
        ).all()
    actual = {(table, index) for table, index in rows}
    assert EXPECTED_INDEXES <= actual, (
        f"missing indexes: {sorted(EXPECTED_INDEXES - actual)}"
    )
