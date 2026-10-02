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
from app.modules.phase6.models import (
    DimensionEvaluation,
    InterviewEvaluation,
    InterviewQuestion,
    InterviewSession,
)
from app.modules.phase6.prompts import (
    COMPANY_SYSTEM,
    EVALUATION_SYSTEM,
    QUESTION_SYSTEM,
    company_schema,
    evaluation_schema,
    payload,
    question_schema,
)
from app.modules.phase6.service import Phase6Service
from app.modules.student.models import GapAnalysisRun, GapItem, SkillEvidence

DATA = ROOT / "backend" / "generation_data"
OUTPUT = ROOT / "docs" / "evaluation" / "phase6-results.json"
MARKDOWN = ROOT / "docs" / "evaluation" / "phase6-results.md"


def load(name: str) -> list[dict[str, Any]]:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def rate(values: list[bool]) -> float:
    return round(100 * sum(values) / len(values), 2) if values else 0


def percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    return (
        ordered[min(len(ordered) - 1, round((len(ordered) - 1) * ratio))]
        if ordered
        else 0
    )


def readiness_results() -> dict[str, Any]:
    cases = load("phase6-readiness-v1.json")
    checks: list[bool] = []
    for index, case in enumerate(cases, 1):
        now = datetime.now(UTC)
        student_id = f"student_{index:032x}"
        gap = GapAnalysisRun(
            run_id=f"gap_{index:032x}",
            student_id=student_id,
            target_role_id="role_backend_developer",
            profile_version=1,
            evidence_snapshot_hash=f"{index:064x}",
            knowledge_dataset_version="careerpilot-knowledge-v1",
            created_at=now,
            items=[
                GapItem(
                    skill_id="skill_python",
                    skill_name="Python",
                    importance="CORE",
                    status=case["status"],
                    reason_code="NO_DIRECT_EVIDENCE"
                    if case["status"] == "UNVERIFIED"
                    else "UNCONFIRMED_DIRECT_EVIDENCE"
                    if case["status"] == "PARTIALLY_SUPPORTED"
                    else "CONFIRMED_DIRECT_EVIDENCE",
                    evidence_ids=[],
                    graph_assertion_id="assertion_role_python",
                )
            ],
        )
        evidence = []
        if case["evidence"]:
            evidence = [
                SkillEvidence(
                    evidence_id=f"evidence_{index:032x}",
                    student_id=student_id,
                    raw_text="Python",
                    section="OTHER",
                    evidence_text="Controlled evaluation evidence.",
                    skill_id="skill_python",
                    skill_name="Python",
                    normalization_status="EXACT",
                    observed_at=now,
                    created_at=now,
                    updated_at=now,
                )
            ]
        sessions: list[InterviewSession] = []
        if case["interview"]:
            question = InterviewQuestion(
                question_id=f"question_{index:032x}",
                sequence=1,
                text="Explain Python exception handling.",
                topic_id="topic_error_handling",
                topic_name="Error handling",
                skill_ids=["skill_python"],
                evidence_ids=["chunk_python_one"],
                difficulty="INTERMEDIATE",
                rubric=Phase6Service.rubric(),
            )
            evaluation = InterviewEvaluation(
                evaluation_id=f"evaluation_{index:032x}",
                question_id=question.question_id,
                response_id=f"response_{index:032x}",
                status="COMPLETED",
                dimensions=[
                    DimensionEvaluation(
                        dimension=item.dimension,
                        rating="ADEQUATE",
                        feedback="Controlled fixture feedback.",
                        evidence_ids=question.evidence_ids,
                    )
                    for item in question.rubric
                ],
                strengths=[],
                improvements=[],
                practice_evidence_ids=[],
                generation_run_id=f"generation_{index:032x}",
                model_id="fixture",
                provider_latency_ms=0,
                created_at=now,
            )
            sessions = [
                InterviewSession(
                    session_id=f"interview_{index:032x}",
                    student_id=student_id,
                    company_role_id="companyrole_demo_backend",
                    company_role_name="Demo",
                    interview_type="ROLE_SPECIFIC",
                    difficulty="INTERMEDIATE",
                    status="COMPLETED",
                    model_id="fixture",
                    generation_run_id=f"generation_{index:032x}",
                    provider_latency_ms=0,
                    retrieval_trace_ids=[],
                    questions=[question],
                    evaluations=[evaluation],
                    created_at=now,
                    completed_at=now,
                )
            ]
        result = Phase6Service.calculate_readiness(
            student_id, gap, evidence, sessions, 1
        )
        checks.append(
            result.score == case["expected_score"]
            and result.category == case["expected_category"]
        )
    return {
        "dataset_size": len(cases),
        "exact_correctness_percent": rate(checks),
        "passed": sum(checks),
    }


async def live_results(include_consistency: bool = False) -> dict[str, Any]:
    adapter = GroqAdapter(Settings())
    latencies: list[float] = []
    token_totals = {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0}
    failures: list[str] = []
    try:
        company_checks: list[bool] = []
        for case in load("phase6-company-v1.json"):
            result = await safe_generate(
                adapter,
                StructuredGenerationRequest(
                    schema_name="phase6_company_eval",
                    schema_definition=company_schema(),
                    system_prompt=COMPANY_SYSTEM,
                    user_payload=payload(
                        "COMPANY_PREPARATION",
                        {
                            "synthetic": case["synthetic"],
                            "skills": [
                                {**case, "allowed_evidence_ids": ["chunk_validated"]}
                            ],
                            "untrusted_resources": [case["resource"]],
                        },
                    ),
                ),
                failures,
            )
            if result is None:
                break
            items = result.value.get("items", [])
            company_checks.append(
                len(items) == 1
                and items[0].get("skill_id") == case["skill_id"]
                and "hire" not in items[0].get("recommendation", "").casefold()
            )
            collect(result.metadata, latencies, token_totals)
        question_checks: list[bool] = []
        for case in load("phase6-questions-v1.json"):
            if failures:
                break
            result = await safe_generate(
                adapter,
                StructuredGenerationRequest(
                    schema_name="phase6_question_eval",
                    schema_definition=question_schema(),
                    system_prompt=QUESTION_SYSTEM,
                    user_payload=payload(
                        "INTERVIEW_QUESTIONS",
                        {
                            "question_count": 1,
                            "difficulty": case["difficulty"],
                            "topics": [case],
                            "untrusted_resources": [case["evidence"]],
                        },
                    ),
                ),
                failures,
            )
            if result is None:
                break
            items = result.value.get("items", [])
            question_checks.append(
                len(items) == 1 and items[0].get("topic_id") == case["topic_id"]
            )
            collect(result.metadata, latencies, token_totals)
        evaluation_checks: list[bool] = []
        rating_vectors: list[list[str]] = []
        evaluation_cases = load("phase6-evaluations-v1.json")
        for case in evaluation_cases:
            if failures:
                break
            result = await safe_generate(
                adapter,
                StructuredGenerationRequest(
                    schema_name="phase6_evaluation_eval",
                    schema_definition=evaluation_schema(),
                    system_prompt=EVALUATION_SYSTEM,
                    user_payload=payload(
                        "EVALUATE_ANSWER",
                        {
                            "question": "Explain bounded Python exception handling.",
                            "fixed_rubric": [
                                item.model_dump() for item in Phase6Service.rubric()
                            ],
                            "allowed_evidence_ids": ["chunk_python_one"],
                            "untrusted_student_answer": case["answer"],
                        },
                    ),
                ),
                failures,
            )
            if result is None:
                break
            ratings = [
                result.value[name]["rating"]
                for name in [
                    "technical_accuracy",
                    "role_relevance",
                    "clarity",
                    "grounding",
                ]
            ]
            rating_vectors.append(ratings)
            evaluation_checks.append(
                not case["expect_not_all_strong"]
                or not all(value == "STRONG" for value in ratings)
            )
            collect(result.metadata, latencies, token_totals)
        consistency_vectors: list[list[str]] = []
        if include_consistency and not failures and rating_vectors:
            selected_index = next(
                index
                for index, case in enumerate(evaluation_cases)
                if case["case_id"] == "prompt-injection"
            )
            selected = evaluation_cases[selected_index]
            consistency_vectors.append(rating_vectors[selected_index])
            for _ in range(2):
                result = await safe_generate(
                    adapter,
                    StructuredGenerationRequest(
                        schema_name="phase6_evaluation_consistency",
                        schema_definition=evaluation_schema(),
                        system_prompt=EVALUATION_SYSTEM,
                        user_payload=payload(
                            "EVALUATE_ANSWER",
                            {
                                "question": "Explain bounded Python exception handling.",
                                "fixed_rubric": [
                                    item.model_dump() for item in Phase6Service.rubric()
                                ],
                                "allowed_evidence_ids": ["chunk_python_one"],
                                "untrusted_student_answer": selected["answer"],
                            },
                        ),
                    ),
                    failures,
                )
                if result is None:
                    break
                consistency_vectors.append(
                    [
                        result.value[name]["rating"]
                        for name in [
                            "technical_accuracy",
                            "role_relevance",
                            "clarity",
                            "grounding",
                        ]
                    ]
                )
                collect(result.metadata, latencies, token_totals)
        return {
            "company": {
                "dataset_size": len(load("phase6-company-v1.json")),
                "completed": len(company_checks),
                "grounded_percent": rate(company_checks),
            },
            "questions": {
                "dataset_size": len(load("phase6-questions-v1.json")),
                "completed": len(question_checks),
                "constraint_pass_percent": rate(question_checks),
            },
            "evaluations": {
                "dataset_size": len(evaluation_cases),
                "completed": len(evaluation_checks),
                "rubric_adherence_percent": rate(evaluation_checks),
                "consistency_runs": len(consistency_vectors),
                "exact_rating_agreement_percent": (
                    rate(
                        [
                            value == consistency_vectors[0]
                            for value in consistency_vectors
                        ]
                    )
                    if consistency_vectors
                    else 0
                ),
                "distinct_rating_vectors": len(
                    {tuple(value) for value in consistency_vectors}
                ),
            },
            "provider": {
                "model": adapter.model_id,
                "calls": len(latencies),
                "latency_median_ms": round(statistics.median(latencies), 3)
                if latencies
                else 0,
                "latency_p95_ms": round(percentile(latencies, 0.95), 3),
                "tokens": token_totals,
                "failure": failures[0] if failures else None,
            },
        }
    finally:
        await adapter.close()


async def safe_generate(
    adapter: GroqAdapter, request: StructuredGenerationRequest, failures: list[str]
) -> Any:
    try:
        return await adapter.generate_structured(request)
    except LLMProviderError as exc:
        failures.append(exc.category)
        return None


async def consistency_results() -> dict[str, Any]:
    adapter = GroqAdapter(Settings())
    failures: list[str] = []
    latencies: list[float] = []
    totals = {"prompt": 0, "completion": 0, "reasoning": 0, "total": 0}
    vectors: list[list[str]] = []
    selected = next(
        case
        for case in load("phase6-evaluations-v1.json")
        if case["case_id"] == "prompt-injection"
    )
    try:
        for _ in range(3):
            result = await safe_generate(
                adapter,
                StructuredGenerationRequest(
                    schema_name="phase6_evaluation_consistency",
                    schema_definition=evaluation_schema(),
                    system_prompt=EVALUATION_SYSTEM,
                    user_payload=payload(
                        "EVALUATE_ANSWER",
                        {
                            "question": "Explain bounded Python exception handling.",
                            "fixed_rubric": [
                                item.model_dump() for item in Phase6Service.rubric()
                            ],
                            "allowed_evidence_ids": ["chunk_python_one"],
                            "untrusted_student_answer": selected["answer"],
                        },
                    ),
                ),
                failures,
            )
            if result is None:
                break
            vectors.append(
                [
                    result.value[name]["rating"]
                    for name in [
                        "technical_accuracy",
                        "role_relevance",
                        "clarity",
                        "grounding",
                    ]
                ]
            )
            collect(result.metadata, latencies, totals)
        return {
            "runs": len(vectors),
            "exact_rating_agreement_percent": (
                rate([value == vectors[0] for value in vectors]) if vectors else 0
            ),
            "distinct_rating_vectors": len({tuple(value) for value in vectors}),
            "latency_median_ms": round(statistics.median(latencies), 3)
            if latencies
            else 0,
            "tokens": totals,
            "failure": failures[0] if failures else None,
        }
    finally:
        await adapter.close()


def collect(metadata: Any, latencies: list[float], totals: dict[str, int]) -> None:
    latencies.append(metadata.latency_ms)
    totals["prompt"] += metadata.prompt_tokens or 0
    totals["completion"] += metadata.completion_tokens or 0
    totals["reasoning"] += metadata.reasoning_tokens or 0
    totals["total"] += metadata.total_tokens or 0


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--consistency-only", action="store_true")
    args = parser.parse_args()
    if args.consistency_only:
        results = json.loads(OUTPUT.read_text(encoding="utf-8"))
        consistency = await consistency_results()
        results["generated_at"] = datetime.now(UTC).isoformat()
        results["evaluations"]["consistency_runs"] = consistency["runs"]
        results["evaluations"]["exact_rating_agreement_percent"] = consistency[
            "exact_rating_agreement_percent"
        ]
        results["evaluations"]["distinct_rating_vectors"] = consistency[
            "distinct_rating_vectors"
        ]
        results["provider_consistency"] = consistency
        OUTPUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        write_markdown(results)
        print(json.dumps(results, indent=2))
        return
    results: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "readiness": readiness_results(),
        "live": args.live,
    }
    if results.get("live"):
        results.update(await live_results())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    write_markdown(results)
    print(json.dumps(results, indent=2))


def write_markdown(results: dict[str, Any]) -> None:
    lines = [
        "# Phase 6 evaluation results",
        f"Generated: {results['generated_at']}",
        f"Readiness exact correctness: {results['readiness']['exact_correctness_percent']}% ({results['readiness']['dataset_size']} cases).",
    ]
    if results.get("live"):
        lines.extend(
            [
                f"Company grounding: {results['company']['grounded_percent']}% ({results['company']['dataset_size']} cases).",
                f"Question constraint pass: {results['questions']['constraint_pass_percent']}% ({results['questions']['dataset_size']} cases).",
                f"Evaluation rubric adherence: {results['evaluations']['rubric_adherence_percent']}% ({results['evaluations']['dataset_size']} cases).",
                f"Repeated injection-answer rating agreement: {results['evaluations']['exact_rating_agreement_percent']}% ({results['evaluations']['consistency_runs']} runs).",
                f"Provider latency median/p95: {results['provider']['latency_median_ms']}/{results['provider']['latency_p95_ms']} ms.",
            ]
        )
    MARKDOWN.write_text("\n\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
