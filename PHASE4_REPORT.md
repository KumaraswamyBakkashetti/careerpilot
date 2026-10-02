# CareerPilot Phase 4 Implementation Report

Verification date: 2026-10-01  
Scope: local graph-enhanced hybrid retrieval, provenance, tracing and evaluation; no generation

## 1. Executive Summary

Phase 4 implements a working retrieval foundation inside the modular monolith. Four canonical Phase 2 resources produce 21 stable chunks, 384-dimensional normalized Sentence Transformer embeddings and an integrity-checked FAISS `IndexFlatIP`. Authenticated workflows combine Neo4j relationships, MongoDB-owned gap snapshots, filtered passages, deterministic sufficiency and owner-scoped MongoDB traces. No LLM is installed or called for generation, planning, reranking or sufficiency.

## 2. Phase 3 Baseline

The working tree was clean. The initial `scripts/check.ps1` stopped before tests because the local uv trampoline referenced a missing Python child process. This was recorded as a pre-existing environment failure. Recreating the locked environment restored the gate. Phase 3's report recorded 76 unit, 12 integration and 31 frontend tests at its exit.

## 3. Architecture

The architecture remains React -> FastAPI modular monolith -> MongoDB/Neo4j/private storage, with FAISS added as a derived local artifact. MongoDB owns private state/traces, Neo4j canonical relationships, source files canonical content, and FAISS rebuildable vectors. See `docs/architecture/hybrid-retrieval.md`.

## 4. Resource Corpus

The corpus is the four reviewed Phase 2 documentation resources: Python, PostgreSQL, MDN and pytest. Each has stable resource/content/source IDs, HTTPS provenance, a verified source-file SHA-256 and graph-derived skill metadata. Corpus version is `careerpilot-knowledge-v1-resources-v1`. No student content is loaded.

## 5. Chunk Model

`ResourceChunk` contains stable chunk/resource/source IDs, sequence, text, SHA-256, chunking version, metadata and timestamp. The active corpus produces 21 chunks.

## 6. Chunking Strategy

`deterministic-structure-v1` splits normalized Markdown on headings and paragraphs before applying bounded character windows. IDs include resource, configuration, sequence and text. Default size/overlap is 420/40.

## 7. Chunking Experiment

Generated evaluation compared 420/40, 900/120 and 1400/160. All produced 21 chunks and identical quality because v1 semantic sections are shorter than every window. The smallest was selected as the forward-looking default; this is not evidence that size never matters.

## 8. Embedding Candidates

`all-MiniLM-L6-v2` revision `1110a243...` and `multi-qa-MiniLM-L6-cos-v1` revision `b2073673...` were executed locally. Both are 384-dimensional Sentence Transformer models suitable for English semantic retrieval. The immutable revisions are recorded.

## 9. Selected Embedding Model

`all-MiniLM-L6-v2` was selected at revision `1110a243...`. The evaluated multi-qa candidate achieved slightly higher VECTOR_ONLY Precision@3 (0.944 versus 0.917) and lower warm latency, but its pinned model card did not declare a license; the selected model's pinned card explicitly declares Apache-2.0. Both reached Recall@3/MRR 1.0 and hybrid P@3 1.0. The small dataset limits generalization.

## 10. Embedding Versioning

The manifest records model ID, exact revision, dimension, normalization, similarity, corpus/dataset versions, chunking version/configuration and build version. Runtime configuration must match.

## 11. FAISS Architecture

The implementation uses actual FAISS `IndexFlatIP`. Normalized document/query vectors make inner product cosine similarity. FAISS types do not cross the infrastructure boundary.

## 12. Index Manifest

The active manifest is `retrieval-f6569969bb200688298acd23`, 384 dimensions, 4 resources, 21 chunks. It hashes both `vectors.faiss` and `chunks.json`. Its files total 47,588 bytes (32,301 index + 14,252 metadata + 1,035 manifest).

## 13. Index Lifecycle

The CLI stages a new versioned directory, writes and hashes artifacts, then atomically replaces `active.json`. A logically equivalent active build is reused after compatibility validation. Missing, malformed, stale, corrupt, incomplete and count/dimension-inconsistent artifacts fail safely.

## 14. Metadata Mapping

FAISS row order maps to JSON `ResourceChunk` objects, retaining `chunkId -> resourceId -> sourceId`, skill associations, name, type and URL. Counts and hashes are checked at load.

## 15. Graph Retrieval

The existing `KnowledgeRepository` supplies `REQUIRES_SKILL` and incoming `TEACHES_SKILL`; no second Cypher architecture was introduced. Typed graph evidence retains entity, relation, assertion, importance, source IDs and dataset version.

## 16. Vector Retrieval

Typed results expose chunk/resource/source IDs, text, cosine score, rank, metadata, index version and model ID. Default k is 3, configurable and capped at 20. There is no unvalidated similarity threshold.

## 17. Retrieval Planner

The finite planner is deterministic: role requirements -> GRAPH_ONLY; canonical skill plus explicit query -> VECTOR_ONLY; canonical skill resource workflow -> GRAPH_THEN_VECTOR. Inputs outside those contracts are rejected.

## 18. GRAPH_ONLY

Implemented for role requirements and verified by unit/Phase 2 real graph coverage. It does not call FAISS.

## 19. VECTOR_ONLY

Implemented for explicit semantic queries constrained to a validated canonical skill. It uses the same typed result/filter/trace boundary.

## 20. GRAPH_THEN_VECTOR

Implemented and verified through the real authenticated gap flow: MongoDB gap -> Neo4j `TEACHES_SKILL` -> deterministic query -> Sentence Transformer -> FAISS -> bundle/trace.

## 21. PARALLEL_HYBRID

The strategy is part of the finite contract but is deliberately not dispatched. The v1 use cases are graph-dependent or already have validated canonical context, and evaluation did not establish an independent parallel workload or end-to-end latency benefit. This exit item is intentionally not applicable rather than falsely claimed.

## 22. Evidence Fusion

Fusion is rule-based: graph validates structure, gap status preserves student support state, vector evidence supplies text, filtering removes metadata mismatches, and provenance stays distinct. No weighted graph/vector formula exists.

## 23. Relevance Filtering

The over-fetched nearest-neighbor set is filtered outside FAISS by canonical skill/resource metadata and valid source-linked chunks. Rejected chunk IDs and reasons enter the trace. Nearest neighbor is never relabelled graph fact.

## 24. Sufficiency Rules

`retrieval-sufficiency-v1`: all required channels present is SUFFICIENT; one present is PARTIAL; none is INSUFFICIENT. Graph-only requires graph evidence. No LLM participates.

## 25. Retrieval Trace

MongoDB stores owner ID, request/trace IDs, task/strategy, graph operations, deterministic queries, counts, selected/rejected IDs, sufficiency, duration and versions. Resume/evidence text, JWTs and embeddings are absent. Reads are owner-filtered.

## 26. APIs

Added authenticated search, skill-resource, gap-evidence and trace routes under `/api/v1/retrieval`. No embedding, arbitrary path, raw FAISS or rebuild endpoint is exposed.

## 27. Frontend

The student gap view adds **Retrieve evidence**. It renders graph evidence under “Why this skill matters” and passages under “Learning evidence,” with source identity, cosine score, strategy, sufficiency and trace ID. It does not generate a roadmap.

## 28. Evaluation Dataset

`careerpilot-retrieval-eval-v1` has 12 manually curated skill-resource queries and expected resource IDs. Labels derive from reviewed canonical assertions, not either evaluated model.

## 29. Retrieval Metrics

At selected 420/40 and k=3: VECTOR_ONLY P@3 0.917, R@3 1.000, MRR 1.000, hit rate 1.000; GRAPH_THEN_VECTOR P@3/R@3/MRR/hit rate are all 1.000. “Accuracy” is not reported.

## 30. Graph/Vector/Hybrid Comparison

Graph filtering removed unrelated semantic matches and improved P@3 by 0.083 for the selected model without changing recall/MRR. GRAPH_ONLY is not assigned passage precision because the graph does not contain explanatory text; it remains the correct structural-query strategy.

## 31. Chunking Results

Quality tied across all three configurations. Selected-run index sizes were approximately 47.6 KB. Warm query variance exceeded configuration effects, so no unsupported chunk-size superiority is claimed.

## 32. Embedding Results

The multi-qa candidate improved vector P@3 by 0.027 over the selected all-MiniLM model on this dataset. Both reached perfect first-hit/recall. Licensing evidence determined the final choice. Cold first-model build measurements include model initialization and are reported transparently in JSON; warm builds were roughly 3.4–4.2 seconds.

## 33. Top-K Results

For selected model/hybrid: P@3 1.000, P@5 0.950 and P@10 0.525, with recall 1.000 throughout. k=3 is selected. Lower precision at larger k reflects extra nearest chunks, not model “accuracy.”

## 34. Performance

Selected 420/40 warm query evaluation: VECTOR_ONLY median/p95 6.674/8.358 ms; graph-constrained vector stage 6.122/7.344 ms. These numbers exclude live Neo4j/MongoDB HTTP overhead and were measured on this local Windows CPU environment.

## 35. Index Build Metrics

Selected real CLI build: 4 resources, 21 chunks, 384 dimensions, 16,256.886 ms embedding, 16,265.394 ms total cached-process build, 47,588 artifact bytes. Repeating an equivalent build reuses the compatible logical artifact.

## 36. Failure Testing

Unit tests cover missing pointer/index, corruption, configuration incompatibility, mapping integrity, invalid chunk configuration and safe exceptions. Manifest/file hashes and dimensions/counts are verified. Model-unavailable behavior is an explicit retrieval failure; no empty-success fabrication occurs.

## 37. Outage/Recovery

A live Phase 4 run stopped only the isolated Neo4j container: the same FastAPI process returned `VECTOR_ONLY_FALLBACK` with `PARTIAL`, then returned `GRAPH_THEN_VECTOR` after Neo4j recovered. Stopping MongoDB returned 503; restarting it restored `GRAPH_THEN_VECTOR` without restarting FastAPI. FAISS missing/corrupt/stale behavior is covered by real-index tests.

## 38. Concurrency

The provider is process-reused, CPU inference runs off the event loop, and a lock protects shared model inference; FAISS performs read-only search. Eight authenticated gap-retrieval requests were issued through a four-thread pool against real MongoDB, Neo4j, Sentence Transformer and FAISS; all returned 200 `GRAPH_THEN_VECTOR`. This is a correctness check, not a high-load capacity benchmark.

## 39. Security

The shared index contains only canonical public/curated resource notes. Paths are configuration-owned, artifacts are not routed publicly, JSON/FAISS replace pickle, rebuild is CLI-only, traces omit private text, and authenticated ownership protects gap and trace access.

## 40. Scaling Assessment

At 10x/100x the current 47.6 KB exact index remains small, but embedding build time and per-process model/index memory grow linearly. Measure before selecting IVF/HNSW. A distributed vector system is deferred until corpus, concurrency or availability data justify it.

## 41. Regression Results

Backend non-integration regression: 83 passed, 0 failed, 12 integration deselected. Real integration: 12 passed, 0 failed, 83 deselected. Existing health, knowledge, auth, resume and gap behavior remained green.

## 42. Backend Tests

Final executed total: 95 passes across explicit unit and real integration runs. Real FAISS build/load/search is covered; the integration workflow used real MongoDB 8.0, Neo4j 5.26, Sentence Transformer inference and FAISS.

## 43. Frontend Tests

The final frontend gate has 28 passing tests and 3 opt-in integration skips, plus a successful production build. The React retrieval inspection assertion covers separate graph/passage/source rendering. Skipped opt-in live HTTP tests are not called passes.

## 44. Quality Gates

Ruff format/check and strict mypy pass. Backend unit and real integration tests pass. Frontend Prettier, ESLint, TypeScript, tests and production build pass. The backend Docker image builds successfully with a CPU-only PyTorch lock (no CUDA dependency payload).

## 45. Files Added/Modified

Major additions are the retrieval domain, FAISS and Mongo trace adapters, build CLI, corpus/evaluation data, evaluation generator/results, APIs, frontend inspection UI, tests, configuration/Compose updates, architecture/ADR documents, README and this report.

## 46. Known Limitations

The corpus and labelled set are intentionally tiny; resource notes are summaries, not full archived pages. No calibrated similarity threshold or reranker exists. PARALLEL_HYBRID is undispatched. Live browser gestures and broad capacity/load testing remain unverified.

## 47. Technical Debt

Add broader independently reviewed resources/labels, graded relevance/nDCG, a retained-build cleanup policy, measured concurrent load and live recovery automation. Consider content-store abstraction before full-page corpora and model artifact pre-provisioning for offline containers.

## 48. Phase 4 Exit Checklist

Corpus, chunks, embeddings, real FAISS, typed retrieval, graph/vector/hybrid paths, deterministic fusion/sufficiency, privacy-safe traces, labelled evaluation, corruption checks, cross-store integration, live outage/recovery, bounded concurrency and quality/build gates pass. PARALLEL_HYBRID was not justified and a manual interactive browser walkthrough is not verified; therefore the literal answer that every possible exit criterion passed is **No**.

## 49. Phase 5 Readiness

The typed, provenance-preserving EvidenceBundle is a safe technical input boundary for Phase 5 experimentation. Phase 5 may begin behind feature flags, but production claims should wait for broader corpus/evaluation coverage and the unverified operational checks above. Generation must not collapse graph assertions and retrieved passages into equivalent facts.

## 50. Reproduction Commands

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
.\.tools\uv.exe sync --project backend --frozen
cd backend
.\.venv\Scripts\python.exe -m app.modules.retrieval.cli build
cd ..
.\backend\.venv\Scripts\python.exe -m pytest -q -m "not integration" backend/tests
$env:CP_RUN_INTEGRATION='1'
$env:TEST_NEO4J_PASSWORD=(Select-String .env '^NEO4J_LOCAL_PASSWORD=').Line.Split('=',2)[1]
.\backend\.venv\Scripts\python.exe -m pytest -q -m integration backend/tests
.\backend\.venv\Scripts\python.exe scripts/evaluate-phase4.py
npm.cmd run check --prefix frontend
docker compose build backend
```

Generated results: `docs/evaluation/phase4-retrieval-results.json` and `.md`.
