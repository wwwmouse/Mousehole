from fastapi import APIRouter

from app.api.v1 import (
    chat,
    files,
    health,
    models,
    projects,
    providers,
    task_files,
    tasks,
    workspaces,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(chat.router, prefix="/tasks", tags=["chat"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(task_files.router, prefix="/tasks", tags=["task-files"])
