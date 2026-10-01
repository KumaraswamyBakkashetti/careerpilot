from app.modules.retrieval.models import RetrievalRequest, RetrievalStrategy


class RetrievalPlanner:
    """Finite, deterministic strategy selection; no generated planning."""

    def plan(self, request: RetrievalRequest) -> RetrievalStrategy:
        if request.task == "ROLE_REQUIREMENTS":
            if request.role_id is None:
                raise ValueError("ROLE_REQUIREMENTS requires role_id")
            return "GRAPH_ONLY"
        if request.skill_id is None:
            raise ValueError("SKILL_RESOURCES requires skill_id")
        return "VECTOR_ONLY" if request.query else "GRAPH_THEN_VECTOR"


def build_skill_query(skill_name: str, role_name: str | None = None) -> str:
    context = f" for the {role_name} role" if role_name else ""
    return f"Learn and practice {skill_name}{context} using canonical documentation."
