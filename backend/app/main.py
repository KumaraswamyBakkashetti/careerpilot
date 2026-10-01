import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware

from app.api.routes import health_router, system_router
from app.application.health import Dependency, HealthService
from app.core.config import Settings
from app.core.errors import (
    ApplicationError,
    ErrorResponse,
    application_error_handler,
    http_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, SanitizedErrorsMiddleware
from app.infrastructure.knowledge import Neo4jKnowledgeRepository
from app.infrastructure.mongodb import MongoDBAdapter
from app.infrastructure.neo4j import Neo4jAdapter
from app.infrastructure.student import MongoStudentRepository
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.routes import router as knowledge_router
from app.modules.knowledge.service import KnowledgeService
from app.modules.student.repository import StudentRepository
from app.modules.student.routes import router as student_router
from app.modules.student.service import StudentService
from app.modules.student.storage import LocalResumeStorage


def create_app(
    settings: Settings | None = None,
    dependencies: dict[str, Dependency] | None = None,
    knowledge_repository: KnowledgeRepository | None = None,
    student_repository: StudentRepository | None = None,
    resume_storage: LocalResumeStorage | None = None,
) -> FastAPI:
    config = settings if settings is not None else Settings()
    configure_logging(config.log_level)
    logger = logging.getLogger("careerpilot.lifecycle")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        resources: dict[str, Dependency] = (
            dependencies
            if dependencies is not None
            else {"mongodb": MongoDBAdapter(config), "neo4j": Neo4jAdapter(config)}
        )
        if set(resources) != {"mongodb", "neo4j"}:
            raise ValueError("Phase 1 requires MongoDB and Neo4j adapters")

        async def initialize(name: str, dependency: Dependency) -> None:
            try:
                async with asyncio.timeout(config.dependency_timeout_seconds):
                    await dependency.start()
            except Exception as exc:
                logger.warning(
                    "dependency_initialization_failed",
                    extra={"dependency": name, "category": type(exc).__name__},
                )

        async def shutdown(name: str, dependency: Dependency) -> None:
            try:
                async with asyncio.timeout(config.dependency_timeout_seconds):
                    await dependency.close()
            except Exception as exc:
                logger.error(
                    "dependency_close_failed",
                    extra={"dependency": name, "category": type(exc).__name__},
                )

        async with AsyncExitStack() as stack:
            for name, dependency in resources.items():
                stack.push_async_callback(shutdown, name, dependency)
            await asyncio.gather(*(initialize(name, dep) for name, dep in resources.items()))
            application.state.health = HealthService(resources, config.dependency_timeout_seconds)
            neo = resources["neo4j"]
            repository = (
                knowledge_repository
                if knowledge_repository is not None
                else Neo4jKnowledgeRepository(
                    neo if isinstance(neo, Neo4jAdapter) else Neo4jAdapter(config)
                )
            )
            application.state.knowledge = KnowledgeService(repository)
            mongo = resources["mongodb"]
            student_repo = (
                student_repository
                if student_repository is not None
                else MongoStudentRepository(
                    mongo if isinstance(mongo, MongoDBAdapter) else MongoDBAdapter(config)
                )
            )
            student = StudentService(
                config,
                student_repo,
                repository,
                resume_storage or LocalResumeStorage(config.resume_storage_root),
            )
            if student_repository is not None or isinstance(mongo, MongoDBAdapter):
                try:
                    await student.initialize()
                except Exception as exc:
                    logger.warning(
                        "student_initialization_failed",
                        extra={"dependency": "mongodb", "category": type(exc).__name__},
                    )
            application.state.student = student
            # Probe at startup, but preserve liveness even during dependency outages.
            await application.state.health.readiness()
            logger.info("application_started")
            try:
                yield
            finally:
                logger.info("application_stopping")
        logger.info("application_stopped")

    application = FastAPI(
        title="CareerPilot",
        version="0.3.0",
        debug=False,  # Never expose traceback pages, even when local DEBUG is enabled.
        description="Phase 3 private student evidence and deterministic career gap analysis.",
        lifespan=lifespan,
        responses={
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    application.add_exception_handler(ApplicationError, application_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(HTTPException, http_error_handler)
    application.add_middleware(SanitizedErrorsMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    application.add_middleware(RequestContextMiddleware)
    application.include_router(health_router)
    application.include_router(system_router, prefix=config.api_prefix)
    application.include_router(knowledge_router, prefix=config.api_prefix)
    application.include_router(student_router, prefix=config.api_prefix)
    return application
