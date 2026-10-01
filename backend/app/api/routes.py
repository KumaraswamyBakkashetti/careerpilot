from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.application.health import HealthService, LivenessResponse, ReadinessResponse

health_router = APIRouter(tags=["Operations"])
system_router = APIRouter(tags=["System"])


@health_router.get("/health/live", response_model=LivenessResponse, summary="Process liveness")
async def liveness() -> LivenessResponse:
    """Return 200 while the process can serve HTTP, independently of database availability."""
    return LivenessResponse()


@health_router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    response_model_exclude_none=True,
    responses={503: {"model": ReadinessResponse, "description": "Required dependency unavailable"}},
    summary="Database readiness",
)
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    """Check MongoDB and the configured Neo4j database concurrently with bounded timeouts."""
    service: HealthService = request.app.state.health
    result = await service.readiness()
    if result.status != "ready":
        response.status_code = 503
    return result


class SystemResponse(BaseModel):
    name: Literal["CareerPilot"] = "CareerPilot"
    subtitle: str = (
        "A Multi-Agent Placement Intelligence System Using Knowledge Graph-Enhanced Agentic RAG"
    )
    phase: Literal[1] = 1
    version: str = "0.1.0"


@system_router.get("/system", response_model=SystemResponse, summary="Foundation metadata")
async def system_metadata() -> SystemResponse:
    """Identify the implemented phase; this endpoint makes no business capability claims."""
    return SystemResponse()
