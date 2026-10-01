"""Execute Phase 4 retrieval experiments and generate both report formats."""

import argparse
import json
import statistics
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
REVISIONS = {
    "sentence-transformers/all-MiniLM-L6-v2": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
    "sentence-transformers/multi-qa-MiniLM-L6-cos-v1": "b207367332321f8e44f96e224ef15bc607f4dbf0",
}

from app.infrastructure.retrieval_index import FaissIndexStore
from app.modules.retrieval.corpus import chunk_resource, load_corpus
from app.modules.retrieval.embedding import (
    SentenceTransformerEmbeddingProvider,
)


def metrics(resource_ids: list[str], expected: set[str], k: int) -> dict[str, float]:
    selected = resource_ids[:k]
    relevant = [identifier in expected for identifier in selected]
    first = next((rank for rank, value in enumerate(relevant, 1) if value), None)
    found = set(selected) & expected
    return {
        "precision_at_k": sum(relevant) / k,
        "recall_at_k": len(found) / len(expected),
        "mrr": 0.0 if first is None else 1.0 / first,
        "hit_rate_at_k": float(bool(found)),
    }


def aggregate(values: list[dict[str, float]]) -> dict[str, float]:
    return {
        key: round(statistics.fmean(item[key] for item in values), 6)
        for key in values[0]
    }


def evaluate(
    model_id: str, size: int, overlap: int, cases: list[dict[str, Any]]
) -> dict[str, Any]:
    knowledge_version, resources = load_corpus(ROOT / "backend" / "knowledge_data")
    chunks = [
        item
        for resource in resources
        for item in chunk_resource(resource, size, overlap)
    ]
    provider = SentenceTransformerEmbeddingProvider(model_id, REVISIONS[model_id], 384)
    with tempfile.TemporaryDirectory(prefix="careerpilot-eval-") as directory:
        store = FaissIndexStore(Path(directory), provider)
        manifest = store.build(
            resources,
            chunks,
            knowledge_version,
            resources[0].corpus_version,
            size,
            overlap,
        )
        results: dict[str, Any] = {}
        for k in (3, 5, 10):
            vector_metrics, hybrid_metrics, vector_latency, hybrid_latency = (
                [],
                [],
                [],
                [],
            )
            for case in cases:
                started = perf_counter()
                vector, _ = store.search(case["query"], k)
                vector_latency.append((perf_counter() - started) * 1000)
                started = perf_counter()
                hybrid, _ = store.search(case["query"], k, case["skill_id"])
                hybrid_latency.append((perf_counter() - started) * 1000)
                expected = set(case["expected_resource_ids"])
                vector_metrics.append(
                    metrics([item.resource_id for item in vector], expected, k)
                )
                hybrid_metrics.append(
                    metrics([item.resource_id for item in hybrid], expected, k)
                )
            results[str(k)] = {
                "VECTOR_ONLY": aggregate(vector_metrics),
                "GRAPH_THEN_VECTOR": aggregate(hybrid_metrics),
                "vector_latency_ms": {
                    "median": round(statistics.median(vector_latency), 3),
                    "p95": round(
                        sorted(vector_latency)[
                            max(0, int(len(vector_latency) * 0.95) - 1)
                        ],
                        3,
                    ),
                },
                "hybrid_latency_ms": {
                    "median": round(statistics.median(hybrid_latency), 3),
                    "p95": round(
                        sorted(hybrid_latency)[
                            max(0, int(len(hybrid_latency) * 0.95) - 1)
                        ],
                        3,
                    ),
                },
            }
        return {
            "model": model_id,
            "model_revision": provider.model_version,
            "dimension": provider.dimension,
            "chunk_size": size,
            "chunk_overlap": overlap,
            "chunk_count": len(chunks),
            "index_size_bytes": manifest.model_dump()["index_sha256"]
            and sum(
                path.stat().st_size
                for path in Path(directory).rglob("*")
                if path.is_file()
            ),
            "embedding_duration_ms": manifest.embedding_duration_ms,
            "index_build_duration_ms": manifest.build_duration_ms,
            "top_k": results,
        }


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase 4 retrieval evaluation",
        "",
        f"Generated from `{payload['dataset_version']}` with {payload['case_count']} manually labelled cases.",
        "",
        "Graph-only is evaluated for structural role-requirement coverage elsewhere; it cannot return resource passages, so text-retrieval precision is not assigned to it.",
        "",
        "| Model | Chunk / overlap | Chunks | k | Strategy | P@k | R@k | MRR | Median ms | p95 ms |",
        "| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for experiment in payload["experiments"]:
        for k, result in experiment["top_k"].items():
            for strategy, latency_key in (
                ("VECTOR_ONLY", "vector_latency_ms"),
                ("GRAPH_THEN_VECTOR", "hybrid_latency_ms"),
            ):
                value, latency = result[strategy], result[latency_key]
                lines.append(
                    f"| {experiment['model']} | {experiment['chunk_size']} / {experiment['chunk_overlap']} | {experiment['chunk_count']} | {k} | {strategy} | {value['precision_at_k']:.3f} | {value['recall_at_k']:.3f} | {value['mrr']:.3f} | {latency['median']:.3f} | {latency['p95']:.3f} |"
                )
    lines.extend(
        [
            "",
            "All numbers above are emitted by the evaluation program; none are hand-entered.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        nargs="+",
        default=[
            "sentence-transformers/all-MiniLM-L6-v2",
            "sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
        ],
    )
    args = parser.parse_args()
    dataset = json.loads(
        (ROOT / "backend" / "retrieval_data" / "evaluation-v1.json").read_text("utf-8")
    )
    experiments = [
        evaluate(model, size, overlap, dataset["cases"])
        for model in args.models
        for size, overlap in ((420, 40), (900, 120), (1400, 160))
    ]
    payload = {
        "dataset_version": dataset["dataset_version"],
        "case_count": len(dataset["cases"]),
        "label_policy": dataset["label_policy"],
        "knowledge_dataset_version": "careerpilot-knowledge-v1",
        "corpus_version": "careerpilot-knowledge-v1-resources-v1",
        "experiments": experiments,
    }
    output = ROOT / "docs" / "evaluation"
    output.mkdir(parents=True, exist_ok=True)
    (output / "phase4-retrieval-results.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    (output / "phase4-retrieval-results.md").write_text(
        markdown(payload), encoding="utf-8"
    )
    print(json.dumps({"experiments": len(experiments), "cases": len(dataset["cases"])}))


if __name__ == "__main__":
    main()
