"""Import every model so Alembic and create_all see the full metadata."""

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
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace

__all__ = [
    "Artifact",
    "ArtifactSeries",
    "Base",
    "Conversation",
    "Execution",
    "ExecutionFileSnapshot",
    "ExecutionStep",
    "File",
    "Message",
    "Project",
    "ProjectFile",
    "Task",
    "TaskFileOverride",
    "Workspace",
]
