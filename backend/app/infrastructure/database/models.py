"""Import every model so Alembic and create_all see the full metadata."""

from app.infrastructure.database.base import Base
from app.modules.file.models import File, ProjectFile, TaskFileOverride
from app.modules.project.models import Project
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace

__all__ = [
    "Base",
    "File",
    "Project",
    "ProjectFile",
    "Task",
    "TaskFileOverride",
    "Workspace",
]
