# Grounded LLM generation

## Boundary

Phase 5 adds one task-oriented generative workflow: personalized learning roadmaps. MongoDB student evidence, Neo4j requirements, and FAISS resource passages remain authoritative. The model receives a minimized, versioned projection and cannot write canonical knowledge or student evidence.

```text
GapAnalysisRun -> per-gap EvidenceBundle -> deterministic priority envelope
  -> PromptBuilder (roadmap-prompt-v1) -> LLMGateway -> GroqAdapter
  -> strict JSON Schema -> Pydantic -> GroundingValidator
  -> evidence-reference validation -> MongoDB Roadmap + GenerationRun
```

## Provider and model discovery

`LLMGateway` owns the provider-independent `generate_structured`, `health_check`, and `model_info` contract. `GroqAdapter` owns HTTPS authentication, request construction, timeouts, bounded transient retries, safe error classification, usage, and provider latency. Roadmap modules do not import provider HTTP types.

The model is configuration-driven. The discovery CLI queries the live Models API, checks the configured ID, and can perform a strict-schema smoke request:

```bat
cd backend
.venv\Scripts\python.exe -m app.modules.llm.cli --smoke
```

Startup never changes models. Authenticated LLM health at `GET /api/v1/roadmaps/model-health` does not affect liveness or core MongoDB/Neo4j readiness.

## Structured output and reasoning

The adapter uses non-streaming Chat Completions with strict JSON Schema, medium reasoning, temperature zero, no tools, and hidden reasoning excluded. Every object requires all properties and denies additional properties. Pydantic revalidates the response.

No browser search, code execution, chain-of-thought return, or automatic model fallback is enabled.

## Deterministic responsibility

The application chooses actionable gaps, priority, finite reason codes, ordering, and allowed skill/evidence/resource IDs. The provider returns only canonical skill ID, recommendation wording, and suggested activities. CareerPilot attaches priority, reason, sequence, evidence IDs, and resource IDs deterministically. Validation then requires exactly the supplied skills and immutable envelope fields. Each final item references its role assertion, student-status fact, and at least one supplied resource chunk and resource.

## Sufficiency and partial coverage

An insufficient gap is never sent to Groq. If no actionable gap has both a canonical role assertion and a validated resource, generation stops with `ROADMAP_EVIDENCE_INSUFFICIENT`. If only a subset is grounded, V1 generates that subset and stores `coverage_status=PARTIAL` plus `omitted_skill_ids`; the UI names omissions. Full coverage stores `SUFFICIENT`.

This policy is necessary for the four-resource prototype corpus and prevents the model from filling corpus gaps.

## Prompt and privacy

`roadmap-prompt-v1` contains target role ID, gap statuses, deterministic envelopes, graph assertions, selected resource chunks, and allowed IDs. Resource text is inside a user-data delimiter and labeled untrusted. The system prompt says retrieved content is data, never instructions.

The projection excludes student ID, name, email, phone, address, raw resume, filename, JWT, password, storage path, and unrelated evidence. Logs record IDs, versions, categories, latency, and token counts—not prompts, roadmap bodies, secrets, raw resumes, or reasoning.

## Persistence, idempotency, and versioning

MongoDB stores owner-scoped immutable Roadmaps and GenerationRuns. A SHA-256 request identity covers student, gap snapshot, prompt version, model, retrieval/index versions, and the client idempotency key (or default identity). Equivalent create requests return the existing completed roadmap. Regeneration requires a client idempotency key and creates history rather than overwriting.

Invalid output is never persisted as a Roadmap.

## Failure policy

- 401 -> `INVALID_PROVIDER_CONFIGURATION`; no retry.
- 403 -> `MODEL_FORBIDDEN`; no retry.
- 404 -> `MODEL_UNAVAILABLE`; no retry.
- 429 -> `RATE_LIMITED`; no aggressive retry.
- deterministic 400/schema rejection -> `INVALID_STRUCTURED_OUTPUT_CONFIGURATION`; no retry.
- selected network/timeout/5xx failures -> bounded exponential retry (default one retry).
- malformed successful response -> `ROADMAP_SCHEMA_INVALID`.

Existing gap analysis, retrieval, and stored roadmap reads remain independent of provider health.

## Scaling

At 10 students synchronous generation is adequate. Around 1,000 students, measure quotas, bound concurrency, reuse stable retrieval, and introduce request admission before queues. At 100,000 students, durable queueing, worker pools, per-tenant quotas, cancellation, operational model discovery, and token/cost observability are required. Current measurements do not justify that infrastructure in Phase 5.
