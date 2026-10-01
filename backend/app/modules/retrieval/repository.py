from typing import Protocol

from app.modules.retrieval.models import RetrievalTrace


class RetrievalTraceRepository(Protocol):
    async def initialize(self) -> None: ...
    async def save(self, trace: RetrievalTrace) -> None: ...
    async def get(self, student_id: str, trace_id: str) -> RetrievalTrace | None: ...


class InMemoryRetrievalTraceRepository:
    """Test boundary used only when the application was constructed with fake dependencies."""

    def __init__(self) -> None:
        self.values: dict[str, RetrievalTrace] = {}

    async def initialize(self) -> None:
        return None

    async def save(self, trace: RetrievalTrace) -> None:
        self.values[trace.trace_id] = trace

    async def get(self, student_id: str, trace_id: str) -> RetrievalTrace | None:
        value = self.values.get(trace_id)
        return value if value and value.student_id == student_id else None
