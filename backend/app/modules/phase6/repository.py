from typing import Protocol

from app.modules.phase6.models import (
    CompanyPreparation,
    InterviewSession,
    OrchestrationRun,
    ReadinessSnapshot,
    SpecialistGenerationRun,
)


class Phase6Repository(Protocol):
    async def initialize(self) -> None: ...
    async def save_preparation(self, value: CompanyPreparation, identity: str) -> bool: ...
    async def preparation_by_identity(
        self, student_id: str, identity: str
    ) -> CompanyPreparation | None: ...
    async def preparation(self, student_id: str, identifier: str) -> CompanyPreparation | None: ...
    async def save_session(self, value: InterviewSession, identity: str) -> bool: ...
    async def session_by_identity(
        self, student_id: str, identity: str
    ) -> InterviewSession | None: ...
    async def session(self, student_id: str, identifier: str) -> InterviewSession | None: ...
    async def replace_session(self, value: InterviewSession) -> None: ...
    async def save_readiness(self, value: ReadinessSnapshot, identity: str) -> bool: ...
    async def readiness_by_identity(
        self, student_id: str, identity: str
    ) -> ReadinessSnapshot | None: ...
    async def readiness(self, student_id: str, identifier: str) -> ReadinessSnapshot | None: ...
    async def latest_readiness(self, student_id: str) -> ReadinessSnapshot | None: ...
    async def next_readiness_version(self, student_id: str) -> int: ...
    async def sessions(self, student_id: str, limit: int = 100) -> list[InterviewSession]: ...
    async def save_orchestration(self, value: OrchestrationRun) -> None: ...
    async def save_generation(self, value: SpecialistGenerationRun) -> None: ...
    async def orchestration(self, student_id: str, identifier: str) -> OrchestrationRun | None: ...


class InMemoryPhase6Repository:
    def __init__(self) -> None:
        self.preparations: dict[str, tuple[str, CompanyPreparation]] = {}
        self.interviews: dict[str, tuple[str, InterviewSession]] = {}
        self.snapshots: dict[str, tuple[str, ReadinessSnapshot]] = {}
        self.runs: dict[str, OrchestrationRun] = {}
        self.generations: dict[str, SpecialistGenerationRun] = {}

    async def initialize(self) -> None:
        return None

    async def save_preparation(self, value: CompanyPreparation, identity: str) -> bool:
        if await self.preparation_by_identity(value.student_id, identity):
            return False
        self.preparations[value.preparation_id] = (identity, value)
        return True

    async def preparation_by_identity(
        self, student_id: str, identity: str
    ) -> CompanyPreparation | None:
        return next(
            (
                v
                for key, v in self.preparations.values()
                if key == identity and v.student_id == student_id
            ),
            None,
        )

    async def preparation(self, student_id: str, identifier: str) -> CompanyPreparation | None:
        pair = self.preparations.get(identifier)
        return pair[1] if pair and pair[1].student_id == student_id else None

    async def save_session(self, value: InterviewSession, identity: str) -> bool:
        if await self.session_by_identity(value.student_id, identity):
            return False
        self.interviews[value.session_id] = (identity, value)
        return True

    async def session_by_identity(self, student_id: str, identity: str) -> InterviewSession | None:
        return next(
            (
                v
                for key, v in self.interviews.values()
                if key == identity and v.student_id == student_id
            ),
            None,
        )

    async def session(self, student_id: str, identifier: str) -> InterviewSession | None:
        pair = self.interviews.get(identifier)
        return pair[1] if pair and pair[1].student_id == student_id else None

    async def replace_session(self, value: InterviewSession) -> None:
        identity = self.interviews[value.session_id][0]
        self.interviews[value.session_id] = (identity, value)

    async def save_readiness(self, value: ReadinessSnapshot, identity: str) -> bool:
        if await self.readiness_by_identity(value.student_id, identity):
            return False
        self.snapshots[value.snapshot_id] = (identity, value)
        return True

    async def readiness_by_identity(
        self, student_id: str, identity: str
    ) -> ReadinessSnapshot | None:
        return next(
            (
                v
                for key, v in self.snapshots.values()
                if key == identity and v.student_id == student_id
            ),
            None,
        )

    async def readiness(self, student_id: str, identifier: str) -> ReadinessSnapshot | None:
        pair = self.snapshots.get(identifier)
        return pair[1] if pair and pair[1].student_id == student_id else None

    async def latest_readiness(self, student_id: str) -> ReadinessSnapshot | None:
        values = [v for _, v in self.snapshots.values() if v.student_id == student_id]
        return max(values, key=lambda x: x.version) if values else None

    async def next_readiness_version(self, student_id: str) -> int:
        latest = await self.latest_readiness(student_id)
        return (latest.version + 1) if latest else 1

    async def sessions(self, student_id: str, limit: int = 100) -> list[InterviewSession]:
        values = [v for _, v in self.interviews.values() if v.student_id == student_id]
        return sorted(values, key=lambda x: x.created_at, reverse=True)[:limit]

    async def save_orchestration(self, value: OrchestrationRun) -> None:
        self.runs[value.run_id] = value

    async def save_generation(self, value: SpecialistGenerationRun) -> None:
        self.generations[value.run_id] = value

    async def orchestration(self, student_id: str, identifier: str) -> OrchestrationRun | None:
        value = self.runs.get(identifier)
        return value if value and value.student_id == student_id else None
