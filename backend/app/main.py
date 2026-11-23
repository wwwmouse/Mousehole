from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import RequestIDMiddleware, configure_logging
from app.infrastructure.database.session import dispose_engine, get_session_factory
from app.modules.execution import repository as execution_repository
from app.modules.skill import service as skill_service
from app.modules.execution import service as execution_service
from app.modules.execution.scheduler import scheduler
from app.modules.workspace.service import ensure_default_workspace
from app.shared.exceptions import AppError

logger = logging.getLogger("mousehole")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()
    try:
        with get_session_factory()() as session:
            ensure_default_workspace(session, settings.default_workspace_name)
            skill_service.ensure_builtin_skills(session)
            recovered = execution_service.recover_interrupted(session)
            pending_ids = execution_repository.list_pending_ids(session)
        if recovered:
            logger.warning("marked %s interrupted execution(s) as failed", recovered)
        scheduler.configure(
            session_factory=get_session_factory(),
            max_concurrency=settings.max_concurrency,
        )
        await scheduler.start()
        for execution_id in pending_ids:
            await scheduler.enqueue(execution_id)
    except SQLAlchemyError as exc:  # migrations may not have run yet
        logger.warning("database not ready during startup: %s", exc)
    yield
    await scheduler.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="mousehole API",
        version="0.1.0",
        description="Local-first AI workspace backend (MVP)",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": jsonable_encoder(exc.details),
                }
            },
        )

    @app.exception_handler(ConnectionError)
    async def connection_error_handler(
        _: Request, exc: ConnectionError
    ) -> JSONResponse:
        # pg8000 can surface a raw ConnectionAbortedError on a stale pooled
        # socket (e.g. right after PostgreSQL restarts). Treat it as retryable.
        dispose_engine()
        logger.warning("database connection error: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "database_unavailable",
                    "message": "数据库暂时不可用，请稍后重试",
                    "details": None,
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        # Foreign-key / unique conflicts are client-visible conflicts, not a
        # "database unavailable" incident. Do not leak SQL details.
        logger.warning("data integrity conflict: %s", exc)
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "conflict",
                    "message": "操作与现有数据冲突（存在引用或唯一约束）",
                    "details": None,
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        # A restarted / briefly unavailable database must surface as a retryable
        # failure, never as a fake success. Resetting the pool makes the next
        # request reconnect cleanly.
        if isinstance(exc, DBAPIError):
            dispose_engine()
        logger.warning("database error: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "database_unavailable",
                    "message": "数据库暂时不可用，请稍后重试",
                    "details": None,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "请求参数不合法",
                    "details": jsonable_encoder(exc.errors()),
                }
            },
        )

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
