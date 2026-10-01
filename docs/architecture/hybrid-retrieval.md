# Hybrid retrieval architecture

Phase 4 adds retrieval inside the existing modular monolith. It does not add generation.

```text
private student evidence (MongoDB)       canonical requirements (Neo4j)
                 \                         /
                  deterministic gap snapshot
                            |
                   deterministic planner
                     /             \
          graph assertions       semantic passages
              Neo4j              FAISS IndexFlatIP
                     \             /
                    rule-based fusion
                  relevance + sufficiency
                            |
              typed EvidenceBundle + MongoDB trace
```

## Ownership and corpus

MongoDB owns private student/application state and retrieval-run history. Neo4j owns canonical entities and assertions. The Phase 2 source snapshots under `backend/knowledge_data/sources` are the canonical resource content. FAISS is a disposable derived artifact under the configured index root; it never contains private resumes and is never the only copy of content.

The loader accepts only Phase 2 `Resource` entities with a stable `content_ref`, HTTPS URL, source ID, verified source-file SHA-256 and at least the metadata needed for provenance. `TEACHES_SKILL` assertions populate canonical skill filters. The four-resource v1 corpus is deliberately small and reviewed.

## Chunks and embeddings

`deterministic-structure-v1` normalizes newlines, splits Markdown at headings/paragraphs, then applies bounded character windows. IDs hash resource ID, chunking version/configuration, sequence and text, so unchanged inputs are stable. The selected defaults are 420 characters and 40 overlap. Because v1 source sections are already shorter, all three tested configurations produced 21 chunks; 420/40 was retained as the safer starting point for longer future notes.

`EmbeddingProvider` isolates inference. The selected provider is `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384 dimensions. Its pinned model card explicitly declares Apache-2.0; the evaluated multi-qa candidate's pinned card did not declare a license, so it was not selected despite a small P@3/latency advantage. Documents and queries are normalized. A process creates one lazy provider; CPU inference runs via `asyncio.to_thread` and is serialized by a lock rather than blocking FastAPI's event loop or creating a model per request.

## FAISS lifecycle

The index is `IndexFlatIP`. Since vectors are normalized, inner product is cosine similarity. No similarity threshold is claimed or configured; relevance uses canonical metadata and source validity. `top_k` defaults to 3 and is centrally capped at 20.

Builds write a new versioned directory containing `vectors.faiss`, `chunks.json`, and `manifest.json`, hash both artifacts, validate dimensions/counts, and atomically replace `active.json`. An equivalent active logical version is reused. Loading rejects missing/unsafe pointers, missing files, malformed JSON, hash corruption, model/revision/dimension changes, corpus/hash changes, chunking changes, and vector-to-metadata count mismatches. Serialization is FAISS plus JSON; pickle is not used.

```text
canonical resource -> deterministic chunks -> normalized embeddings
       -> new IndexFlatIP + JSON mapping + manifest
       -> integrity/compatibility validation -> atomic active pointer
```

Build locally:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.modules.retrieval.cli build
```

Index build is intentionally not an HTTP endpoint. The index root is fixed by configuration; requests cannot supply filesystem paths.

## Planning, filtering and fusion

- `GRAPH_ONLY`: canonical role requirements; FAISS is not called.
- `VECTOR_ONLY`: an authenticated caller supplies a validated canonical skill and explicit semantic query.
- `GRAPH_THEN_VECTOR`: Neo4j validates the skill/resource relationship, then the deterministic query builder and FAISS retrieve passages constrained by `skill_ids`. This is the gap workflow.
- `PARALLEL_HYBRID`: represented by the finite contract but not dispatched in v1. The corpus and local latency did not justify independent parallel graph/vector work, and model inference remains the dominant bounded CPU operation.

FAISS first returns nearest candidates. Post-search filtering rejects chunks whose canonical skill/resource metadata does not match and records rejection reasons. Fusion applies no weighted score: graph evidence establishes relationships, the gap snapshot establishes student support status, vector results add text, and provenance remains separate.

Sufficiency rule `retrieval-sufficiency-v1` is explicit: both required channels (or graph results for a graph-only task) are `SUFFICIENT`; one channel is `PARTIAL`; no validated evidence is `INSUFFICIENT`. Dependency failures are explicit errors and are never relabelled as graph-verified results.

## API and traces

Authenticated routes are:

```text
POST /api/v1/retrieval/search
POST /api/v1/retrieval/skills/{skill_id}/resources
POST /api/v1/retrieval/gaps/{gap_run_id}/evidence
GET  /api/v1/retrieval/traces/{trace_id}
```

Traces are owner-filtered MongoDB records. They store IDs, operation descriptions, deterministic queries, counts, selected/rejected evidence IDs, versions, sufficiency and latency. They do not store resume text, evidence context, JWTs, embeddings, or arbitrary request bodies.

## Failure, concurrency and scale

Missing/corrupt/stale FAISS is a 503 with a distinct safe code. Neo4j failure prevents graph-grounded success. MongoDB failure prevents student-aware retrieval and trace persistence. Zero filtered results are an explicit partial/insufficient bundle, never a fabricated resource. Read-only FAISS search shares the loaded index; query inference is moved off the event loop and guarded for model safety.

At 10x this corpus, `IndexFlatIP` and in-memory JSON remain trivial. At 100x, memory/search are still modest but build time and process replication should be measured. At much larger scale, first consider FAISS IVF/HNSW with measured recall and a compact metadata store; a distributed vector database is justified only by measured corpus/concurrency/availability needs. FAISS remains the Phase 4 boundary.

## Evaluation

Ground truth is the manually reviewed `backend/retrieval_data/evaluation-v1.json`; it was not generated by an evaluated model. `scripts/evaluate-phase4.py` emits machine- and human-readable results under `docs/evaluation`. It compares two models, three chunk configurations, k=3/5/10, VECTOR_ONLY and GRAPH_THEN_VECTOR using Precision@k, Recall@k, MRR, hit rate, build size/time and median/p95 query latency. GRAPH_ONLY is not assigned passage metrics because it cannot retrieve text.
