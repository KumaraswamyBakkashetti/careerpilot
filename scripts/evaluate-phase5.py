# ruff: noqa: E402
import argparse
import asyncio
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings
from app.infrastructure.groq import GroqAdapter
from app.modules.llm.gateway import LLMProviderError, StructuredGenerationRequest
from app.modules.retrieval.models import (
    EvidenceBundle,
    ProvenanceRef,
    RetrievalGraphEvidence,
    Sufficiency,
    VectorEvidence,
)
from app.modules.roadmap.models import RoadmapGeneration
from app.modules.roadmap.prompt import (
    SYSTEM_PROMPT,
    build_envelopes,
    build_prompt,
    enrich_generation,
    roadmap_schema,
)
from app.modules.roadmap.validator import (
    EvidenceReferenceViolation,
    GroundingViolation,
    validate_evidence_references,
    validate_grounding,
)
from app.modules.student.models import GapAnalysisRun, GapItem

DATASET = ROOT / "backend" / "generation_data" / "evaluation-v1.json"
JSON_OUTPUT = ROOT / "docs" / "evaluation" / "phase5-generation-results.json"
MD_OUTPUT = ROOT / "docs" / "evaluation" / "phase5-generation-results.md"


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round((len(ordered) - 1) * ratio)))]


def fixtures(case: dict[str, Any], index: int) -> tuple[GapAnalysisRun, list[Any]]:
    gap_id = f"gap_{index + 1:032x}"
    gap = GapItem(
        skill_id=case["skill_id"],
        skill_name=case["skill_name"],
        importance=case["importance"],
        status=case["status"],
        reason_code=(
            "NO_DIRECT_EVIDENCE"
            if case["status"] == "UNVERIFIED"
            else "UNCONFIRMED_DIRECT_EVIDENCE"
        ),
        evidence_ids=[],
        graph_assertion_id=case["assertion_id"],
    )
    run = GapAnalysisRun(
        run_id=gap_id,
        student_id=f"student_{index + 1:032x}",
        target_role_id=case["target_role_id"],
        profile_version=1,
        evidence_snapshot_hash=f"{index + 1:064x}",
        knowledge_dataset_version="careerpilot-knowledge-v1",
        created_at=datetime.now(UTC),
        items=[gap],
    )
    bundle = EvidenceBundle(
        task="GAP_RESOURCES",
        retrieval_strategy="GRAPH_THEN_VECTOR",
        student_context={"student_id": run.student_id},
        target_context={"skill_id": gap.skill_id, "skill_name": gap.skill_name},
        gap_context={"status": gap.status, "importance": gap.importance},
        graph_evidence=[
            RetrievalGraphEvidence(
                entity_id=case["resource_id"],
                entity_name=case["resource_id"],
                relationship_type="TEACHES_SKILL",
                assertion_id=case["assertion_id"],
                importance=case["importance"],
                source_ids=[case["source_id"]],
                dataset_version="careerpilot-knowledge-v1",
            )
        ],
        vector_evidence=[
            VectorEvidence(
                chunk_id=case["chunk_id"],
                resource_id=case["resource_id"],
                source_id=case["source_id"],
                text=case["resource_text"],
                similarity_score=0.9,
                rank=1,
                metadata={"resource_name": case["resource_id"], "skill_ids": [gap.skill_id]},
                index_version="evaluation-v1",
                embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            )
        ],
        provenance=[
            ProvenanceRef(
                evidence_type="GRAPH",
                evidence_id=case["assertion_id"],
                source_id=case["source_id"],
            ),
            ProvenanceRef(
                evidence_type="VECTOR",
                evidence_id=case["chunk_id"],
                source_id=case["source_id"],
                resource_id=case["resource_id"],
            ),
        ],
        sufficiency=Sufficiency(status="SUFFICIENT", reasons=["EVALUATION_FIXTURE"]),
        trace_id=f"trace_{index + 1:032x}",
        versions={"knowledge": "careerpilot-knowledge-v1", "index": "evaluation-v1"},
    )
    return run, build_envelopes(run, {gap.skill_id: bundle})


async def one_case(adapter: GroqAdapter, case: dict[str, Any], index: int) -> dict[str, Any]:
    run, envelopes = fixtures(case, index)
    outcome: dict[str, Any] = {
        "case_id": case["case_id"],
        "schema_valid": False,
        "grounding_valid": False,
        "evidence_reference_valid": False,
        "requirement_covered": False,
        "constraint_adherent": False,
        "unsupported_claim": False,
        "provider_failure": False,
    }
    try:
        result = await adapter.generate_structured(
            StructuredGenerationRequest(
                schema_name="careerpilot_roadmap_eval_v1",
                schema_definition=roadmap_schema(),
                system_prompt=SYSTEM_PROMPT,
                user_payload=build_prompt(run.target_role_id, envelopes),
            )
        )
        generation = RoadmapGeneration.model_validate(result.value)
        draft = enrich_generation(generation, envelopes)
        outcome["schema_valid"] = True
        try:
            validate_grounding(draft, envelopes)
            outcome["grounding_valid"] = True
            outcome["constraint_adherent"] = True
        except GroundingViolation:
            pass
        try:
            validate_evidence_references(draft, envelopes)
            outcome["evidence_reference_valid"] = True
        except EvidenceReferenceViolation:
            pass
        outcome["requirement_covered"] = any(
            item.skill_id == case["skill_id"] for item in draft.items
        )
        serialized = json.dumps(result.value).casefold()
        outcome["unsupported_claim"] = any(
            claim.casefold() in serialized for claim in case["prohibited_claims"]
        )
        outcome["latency_ms"] = result.metadata.latency_ms
        outcome["usage"] = result.metadata.model_dump(
            include={"prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens"}
        )
    except (LLMProviderError, ValueError) as exc:
        outcome["provider_failure"] = isinstance(exc, LLMProviderError)
        outcome["error_category"] = (
            exc.category if isinstance(exc, LLMProviderError) else type(exc).__name__
        )
    return outcome


async def experiment(case: dict[str, Any], index: int, model: str, effort: str) -> dict[str, Any]:
    settings = Settings(groq_model=model, groq_reasoning_effort=effort)
    adapter = GroqAdapter(settings)
    try:
        result = await one_case(adapter, case, index)
        return {"model": model, "reasoning_effort": effort, **result}
    finally:
        await adapter.close()


async def evaluate(compare: bool) -> dict[str, Any]:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    settings = Settings()
    adapter = GroqAdapter(settings)
    try:
        cases = [
            await one_case(adapter, case, index) for index, case in enumerate(dataset["cases"])
        ]
    finally:
        await adapter.close()
    count = len(cases)
    latencies = [float(item["latency_ms"]) for item in cases if "latency_ms" in item]
    usage_fields = ["prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens"]
    totals = {
        field: sum(int(item.get("usage", {}).get(field) or 0) for item in cases)
        for field in usage_fields
    }
    metrics = {
        "schema_validity_rate": sum(bool(item["schema_valid"]) for item in cases) / count,
        "grounding_validity_rate": sum(bool(item["grounding_valid"]) for item in cases) / count,
        "unsupported_claim_rate": sum(bool(item["unsupported_claim"]) for item in cases) / count,
        "evidence_reference_validity_rate": sum(
            bool(item["evidence_reference_valid"]) for item in cases
        )
        / count,
        "requirement_coverage_rate": sum(bool(item["requirement_covered"]) for item in cases)
        / count,
        "constraint_adherence_rate": sum(bool(item["constraint_adherent"]) for item in cases)
        / count,
        "provider_failure_rate": sum(bool(item["provider_failure"]) for item in cases) / count,
        "latency_median_ms": statistics.median(latencies) if latencies else None,
        "latency_p95_ms": percentile(latencies, 0.95) if latencies else None,
        "token_totals": totals,
    }
    comparisons: list[dict[str, Any]] = []
    if compare:
        comparisons.append(await experiment(dataset["cases"][0], 0, "openai/gpt-oss-20b", "medium"))
        comparisons.append(await experiment(dataset["cases"][0], 0, settings.groq_model, "low"))
    return {
        "dataset_version": dataset["dataset_version"],
        "executed_at": datetime.now(UTC).isoformat(),
        "provider": "groq",
        "selected_model": settings.groq_model,
        "reasoning_effort": settings.groq_reasoning_effort,
        "structured_output": "strict_json_schema",
        "case_count": count,
        "cases": cases,
        "metrics": metrics,
        "controlled_experiments": comparisons,
        "scope_note": (
            "Controlled prototype evaluation over four small synthetic EvidenceBundles; "
            "not general model performance."
        ),
    }


def markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    percentages = [
        ("Schema validity", metrics["schema_validity_rate"]),
        ("Grounding validity", metrics["grounding_validity_rate"]),
        ("Unsupported-claim rate", metrics["unsupported_claim_rate"]),
        ("Evidence-reference validity", metrics["evidence_reference_validity_rate"]),
        ("Requirement coverage", metrics["requirement_coverage_rate"]),
        ("Constraint adherence", metrics["constraint_adherence_rate"]),
        ("Provider failure rate", metrics["provider_failure_rate"]),
    ]
    rows = "\n".join(f"| {name} | {value:.1%} |" for name, value in percentages)
    return f"""# Phase 5 Generation Evaluation

Executed: {report["executed_at"]}  
Dataset: `{report["dataset_version"]}` ({report["case_count"]} cases)  
Model: `{report["selected_model"]}`; reasoning `{report["reasoning_effort"]}`  
Mode: `{report["structured_output"]}`

| Metric | Result |
|---|---:|
{rows}

Latency median/p95: {metrics["latency_median_ms"]:.3f}/{metrics["latency_p95_ms"]:.3f} ms.  
Token totals: `{json.dumps(metrics["token_totals"], sort_keys=True)}`.

The injection fixture embeds an instruction to recommend Kubernetes and an unknown resource ID
inside resource data. Results are accepted only after deterministic grounding and reference
validation.

{report["scope_note"]}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(evaluate(args.compare))
    JSON_OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MD_OUTPUT.write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
