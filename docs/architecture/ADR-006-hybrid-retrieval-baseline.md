# ADR-006: deterministic local hybrid retrieval baseline

Status: Accepted — 2026-10-01

## Decision

Keep retrieval in the modular monolith. Canonical content remains in the Phase 2 dataset; Neo4j remains authoritative for relationships; MongoDB owns private retrieval traces; a rebuildable FAISS `IndexFlatIP` stores normalized 384-dimensional Sentence Transformer vectors and JSON chunk mappings.

Use `all-MiniLM-L6-v2` at immutable revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, deterministic structure-aware 420/40 chunking, default k=3, canonical metadata filtering, rule-based fusion and versioned deterministic sufficiency. Its pinned model card explicitly declares Apache-2.0; the evaluated multi-qa candidate's pinned card did not declare a license. Do not use an LLM planner, reranker or weighted graph/vector formula. Do not dispatch `PARALLEL_HYBRID` until an independently parallel workload and latency benefit are measured.

## Evidence

The generated 12-case experiment found multi-qa slightly improved VECTOR_ONLY Precision@3 (0.944 vs 0.917), while both reached Recall@3/MRR 1.0 and graph filtering raised Precision@3 to 1.0. That small result on 12 cases did not outweigh the missing license declaration in the pinned multi-qa model card. Chunk configurations were tied because the reviewed source sections are short. See `docs/evaluation/phase4-retrieval-results.json`.

## Consequences

The system is local, inspectable, provenance-preserving and cheap to rebuild. Exact search is appropriate for the tiny corpus but not a claim about large-scale performance. Model binaries are external build/runtime dependencies. Every corpus, model, revision, dimension or chunking change invalidates the active index and requires a controlled rebuild.
