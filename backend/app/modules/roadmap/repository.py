from typing import Protocol

from app.modules.roadmap.models import GenerationRun, Roadmap


class RoadmapRepository(Protocol):
    async def initialize(self) -> None: ...
    async def save_run(self, run: GenerationRun) -> bool: ...
    async def replace_run(self, run: GenerationRun) -> None: ...
    async def save_roadmap(self, roadmap: Roadmap) -> None: ...
    async def by_identity(self, student_id: str, identity: str) -> Roadmap | None: ...
    async def get(self, student_id: str, roadmap_id: str) -> Roadmap | None: ...
    async def list(self, student_id: str, limit: int) -> list[Roadmap]: ...
    async def next_version(self, student_id: str) -> int: ...


class InMemoryRoadmapRepository:
    def __init__(self) -> None:
        self.runs: dict[str, GenerationRun] = {}
        self.roadmaps: dict[str, Roadmap] = {}

    async def initialize(self) -> None:
        return None

    async def save_run(self, run: GenerationRun) -> bool:
        if any(
            item.student_id == run.student_id and item.request_identity == run.request_identity
            for item in self.runs.values()
        ):
            return False
        self.runs[run.run_id] = run
        return True

    async def replace_run(self, run: GenerationRun) -> None:
        self.runs[run.run_id] = run

    async def save_roadmap(self, roadmap: Roadmap) -> None:
        self.roadmaps[roadmap.roadmap_id] = roadmap

    async def by_identity(self, student_id: str, identity: str) -> Roadmap | None:
        run = next(
            (
                item
                for item in self.runs.values()
                if item.student_id == student_id
                and item.request_identity == identity
                and item.output_roadmap_id
            ),
            None,
        )
        return self.roadmaps.get(run.output_roadmap_id) if run and run.output_roadmap_id else None

    async def get(self, student_id: str, roadmap_id: str) -> Roadmap | None:
        value = self.roadmaps.get(roadmap_id)
        return value if value and value.student_id == student_id else None

    async def list(self, student_id: str, limit: int) -> list[Roadmap]:
        values = [item for item in self.roadmaps.values() if item.student_id == student_id]
        return sorted(values, key=lambda item: item.generated_at, reverse=True)[:limit]

    async def next_version(self, student_id: str) -> int:
        return 1 + max(
            (item.version for item in self.roadmaps.values() if item.student_id == student_id),
            default=0,
        )
