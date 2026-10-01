from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Request

from app.core.logging import request_id_context
from app.modules.retrieval.models import EvidenceBundle, RetrievalRequest, RetrievalTrace
from app.modules.retrieval.service import RetrievalService
from app.modules.student.models import StudentIdentity
from app.modules.student.routes import identity

router = APIRouter(prefix="/retrieval", tags=["Evidence retrieval"])
Identity = Annotated[StudentIdentity, Depends(identity)]
CanonicalPath = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{2,79}$")]
TracePath = Annotated[str, Path(pattern=r"^trace_[a-f0-9]{32}$")]
GapPath = Annotated[str, Path(pattern=r"^gap_[a-f0-9]{32}$")]


def service(request: Request) -> RetrievalService:
    value: RetrievalService = request.app.state.retrieval
    return value


Service = Annotated[RetrievalService, Depends(service)]


@router.post("/search", response_model=EvidenceBundle)
async def search(body: RetrievalRequest, owner: Identity, value: Service) -> EvidenceBundle:
    return await value.execute(owner.student_id, request_id_context.get() or "unknown", body)


@router.post("/skills/{skill_id}/resources", response_model=EvidenceBundle)
async def skill_resources(
    skill_id: CanonicalPath,
    owner: Identity,
    value: Service,
    top_k: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> EvidenceBundle:
    return await value.execute(
        owner.student_id,
        request_id_context.get() or "unknown",
        RetrievalRequest(task="SKILL_RESOURCES", skill_id=skill_id, top_k=top_k),
    )


@router.post("/gaps/{run_id}/evidence", response_model=EvidenceBundle)
async def gap_resources(
    run_id: GapPath,
    skill_id: Annotated[str, Body(embed=True, pattern=r"^[a-z][a-z0-9_]{2,79}$")],
    owner: Identity,
    value: Service,
    top_k: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> EvidenceBundle:
    return await value.gap_evidence(
        owner.student_id, request_id_context.get() or "unknown", run_id, skill_id, top_k
    )


@router.get("/traces/{trace_id}", response_model=RetrievalTrace)
async def trace(trace_id: TracePath, owner: Identity, value: Service) -> RetrievalTrace:
    return await value.trace(owner.student_id, trace_id)
