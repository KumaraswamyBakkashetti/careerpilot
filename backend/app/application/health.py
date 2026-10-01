import asyncio
import logging
from typing import Literal, Protocol

from pydantic import BaseModel

from app.core.errors import ErrorDetail, error_detail


class Dependency(Protocol):
    async def start(self) -> None: ...
    async def ping(self) -> None: ...
    async def close(self) -> None: ...


class LivenessResponse(BaseModel):
    status: Literal["alive"] = "alive"


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: dict[str, Literal["up", "down"]]
    error: ErrorDetail | None = None


class HealthService:
    def __init__(self, dependencies: dict[str, Dependency], timeout_seconds: float) -> None:
        self.dependencies = dependencies
        self.timeout_seconds = timeout_seconds

    async def _check(self, name: str, dependency: Dependency) -> Literal["up", "down"]:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                await dependency.ping()
            return "up"
        except Exception as exc:
            logging.getLogger("careerpilot.health").warning(
                "dependency_unavailable", extra={"dependency": name, "category": type(exc).__name__}
            )
            return "down"

    async def readiness(self) -> ReadinessResponse:
        names = list(self.dependencies)
        states = await asyncio.gather(
            *(self._check(name, self.dependencies[name]) for name in names)
        )
        dependencies = dict(zip(names, states, strict=True))
        ready = all(state == "up" for state in states)
        return ReadinessResponse(
            status="ready" if ready else "not_ready",
            dependencies=dependencies,
            error=None
            if ready
            else error_detail("DEPENDENCY_UNAVAILABLE", "A required service is unavailable."),
        )
