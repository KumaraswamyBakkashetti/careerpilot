from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status

from app.core.logging import request_id_context
from app.modules.knowledge.models import EntityPage, RelationsPage
from app.modules.phase6.models import (
    AnswerRequest,
    CompanyPreparation,
    CompanyPreparationRequest,
    InterviewSession,
    InterviewStartRequest,
    OrchestrationRun,
    ReadinessRequest,
    ReadinessSnapshot,
)
from app.modules.phase6.service import Phase6Service
from app.modules.student.models import StudentIdentity
from app.modules.student.routes import identity

router = APIRouter(tags=["Phase 6 specialist workflows"])
Identity = Annotated[StudentIdentity, Depends(identity)]
PrivatePath = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{2,79}$")]


def service(request: Request) -> Phase6Service:
    value: Phase6Service = request.app.state.phase6
    return value


Service = Annotated[Phase6Service, Depends(service)]


@router.get("/companies", response_model=EntityPage)
async def companies(owner: Identity, value: Service) -> EntityPage:
    return await value.companies()


@router.get("/companies/{company_id}/roles", response_model=RelationsPage)
async def company_roles(company_id: PrivatePath, owner: Identity, value: Service) -> RelationsPage:
    return await value.company_roles(company_id)


@router.post("/company-preparations", response_model=CompanyPreparation, status_code=201)
async def prepare(
    body: CompanyPreparationRequest, owner: Identity, value: Service
) -> CompanyPreparation:
    return await value.prepare(owner.student_id, request_id_context.get() or "unknown", body)


@router.get("/company-preparations/{preparation_id}", response_model=CompanyPreparation)
async def preparation(
    preparation_id: PrivatePath, owner: Identity, value: Service
) -> CompanyPreparation:
    return await value.get_preparation(owner.student_id, preparation_id)


@router.get("/company-preparations/{preparation_id}/evidence", response_model=CompanyPreparation)
async def preparation_evidence(
    preparation_id: PrivatePath, owner: Identity, value: Service
) -> CompanyPreparation:
    return await value.get_preparation(owner.student_id, preparation_id)


@router.post("/interviews", response_model=InterviewSession, status_code=status.HTTP_201_CREATED)
async def start_interview(
    body: InterviewStartRequest, owner: Identity, value: Service
) -> InterviewSession:
    return await value.start_interview(
        owner.student_id, request_id_context.get() or "unknown", body
    )


@router.get("/interviews/{session_id}", response_model=InterviewSession)
async def interview(session_id: PrivatePath, owner: Identity, value: Service) -> InterviewSession:
    return await value.get_session(owner.student_id, session_id)


@router.post("/interviews/{session_id}/responses", response_model=InterviewSession)
async def answer(
    session_id: PrivatePath, body: AnswerRequest, owner: Identity, value: Service
) -> InterviewSession:
    return await value.answer(owner.student_id, session_id, body)


@router.post("/interviews/{session_id}/complete", response_model=InterviewSession)
async def complete(session_id: PrivatePath, owner: Identity, value: Service) -> InterviewSession:
    return await value.complete_interview(owner.student_id, session_id)


@router.get("/interviews/{session_id}/results", response_model=InterviewSession)
async def results(session_id: PrivatePath, owner: Identity, value: Service) -> InterviewSession:
    return await value.get_session(owner.student_id, session_id)


@router.post("/readiness", response_model=ReadinessSnapshot, status_code=201)
async def readiness(body: ReadinessRequest, owner: Identity, value: Service) -> ReadinessSnapshot:
    return await value.readiness(owner.student_id, body)


@router.get("/readiness/latest", response_model=ReadinessSnapshot)
async def latest_readiness(owner: Identity, value: Service) -> ReadinessSnapshot:
    return await value.latest_readiness(owner.student_id)


@router.get("/readiness/{snapshot_id}", response_model=ReadinessSnapshot)
async def readiness_snapshot(
    snapshot_id: PrivatePath, owner: Identity, value: Service
) -> ReadinessSnapshot:
    return await value.get_readiness(owner.student_id, snapshot_id)


@router.get("/readiness/{snapshot_id}/evidence", response_model=ReadinessSnapshot)
async def readiness_evidence(
    snapshot_id: PrivatePath, owner: Identity, value: Service
) -> ReadinessSnapshot:
    return await value.get_readiness(owner.student_id, snapshot_id)


@router.get("/orchestration/{run_id}", response_model=OrchestrationRun)
async def orchestration(run_id: PrivatePath, owner: Identity, value: Service) -> OrchestrationRun:
    return await value.orchestration(owner.student_id, run_id)
