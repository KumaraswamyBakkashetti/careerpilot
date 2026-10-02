from app.modules.roadmap.models import RoadmapDraft
from app.modules.roadmap.prompt import Envelope


class GroundingViolation(ValueError):
    pass


class EvidenceReferenceViolation(ValueError):
    pass


def validate_grounding(draft: RoadmapDraft, envelopes: list[Envelope]) -> None:
    expected = {item.gap.skill_id: item for item in envelopes}
    if len(draft.items) != len(expected) or {item.skill_id for item in draft.items} != set(
        expected
    ):
        raise GroundingViolation("roadmap skills differ from deterministic envelope")
    for item in draft.items:
        envelope = expected[item.skill_id]
        if (
            item.priority != envelope.priority
            or item.reason_code != envelope.reason_code
            or item.sequence != envelope.sequence
        ):
            raise GroundingViolation("model changed deterministic roadmap constraints")
        if (
            "you lack" in item.recommendation.casefold()
            or "you are bad" in item.recommendation.casefold()
        ):
            raise GroundingViolation("unsupported student ability claim")


def validate_evidence_references(draft: RoadmapDraft, envelopes: list[Envelope]) -> None:
    expected = {item.gap.skill_id: item for item in envelopes}
    for item in draft.items:
        envelope = expected[item.skill_id]
        if not set(item.evidence_ids).issubset(envelope.evidence_ids):
            raise EvidenceReferenceViolation("unknown evidence ID")
        if not set(item.resource_ids).issubset(envelope.resource_ids):
            raise EvidenceReferenceViolation("unknown resource ID")
        if envelope.gap.graph_assertion_id not in item.evidence_ids:
            raise EvidenceReferenceViolation("role requirement evidence is missing")
        if envelope.status_evidence_id not in item.evidence_ids:
            raise EvidenceReferenceViolation("student status evidence is missing")
        if not item.resource_ids or not any(
            chunk.chunk_id in item.evidence_ids for chunk in envelope.bundle.vector_evidence
        ):
            raise EvidenceReferenceViolation("resource evidence is missing")
