from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status

from app.core.logging import request_id_context
from app.modules.llm.gateway import LLMHealth
from app.modules.roadmap.models import (
    Roadmap,
    RoadmapCreateRequest,
    RoadmapEvidenceResponse,
    RoadmapList,
    RoadmapRegenerateRequest,
)
from app.modules.roadmap.service import RoadmapService
from app.modules.student.models import StudentIdentity
from app.modules.student.routes import identity

router = APIRouter(prefix="/roadmaps", tags=["Grounded roadmaps"])
Identity = Annotated[StudentIdentity, Depends(identity)]
RoadmapPath = Annotated[str, Path(pattern=r"^roadmap_[a-f0-9]{32}$")]


def service(request: Request) -> RoadmapService:
    value: RoadmapService = request.app.state.roadmaps
    return value


Service = Annotated[RoadmapService, Depends(service)]


@router.post("", response_model=Roadmap, status_code=status.HTTP_201_CREATED)
async def create(body: RoadmapCreateRequest, owner: Identity, value: Service) -> Roadmap:
    return await value.generate(
        owner.student_id,
        request_id_context.get() or "unknown",
        body.gap_run_id,
        body.idempotency_key,
    )


@router.get("", response_model=RoadmapList)
async def list_roadmaps(
    owner: Identity,
    value: Service,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> RoadmapList:
    return await value.list(owner.student_id, limit)


@router.get("/model-health", response_model=LLMHealth)
async def model_health(owner: Identity, value: Service) -> LLMHealth:
    return await value.gateway.health_check()


@router.get("/{roadmap_id}", response_model=Roadmap)
async def get_roadmap(roadmap_id: RoadmapPath, owner: Identity, value: Service) -> Roadmap:
    return await value.get(owner.student_id, roadmap_id)


@router.get("/{roadmap_id}/evidence", response_model=RoadmapEvidenceResponse)
async def evidence(
    roadmap_id: RoadmapPath, owner: Identity, value: Service
) -> RoadmapEvidenceResponse:
    return await value.evidence(owner.student_id, roadmap_id)


@router.post("/{roadmap_id}/regenerate", response_model=Roadmap, status_code=201)
async def regenerate(
    roadmap_id: RoadmapPath,
    body: RoadmapRegenerateRequest,
    owner: Identity,
    value: Service,
) -> Roadmap:
    current = await value.get(owner.student_id, roadmap_id)
    return await value.generate(
        owner.student_id,
        request_id_context.get() or "unknown",
        current.gap_run_id,
        body.idempotency_key,
    )
