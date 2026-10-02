# ADR-007: Evidence-constrained generation through a provider gateway

Status: Accepted  
Date: 2026-10-02

## Decision

Use Groq as the initial inference provider behind a provider-independent `LLMGateway`. Select the configured model only after live account discovery and a strict JSON Schema smoke test. Use non-streaming strict structured output, minimized EvidenceBundles, deterministic post-generation grounding/reference validation, and immutable generation metadata.

Do not automatically fall back to another model. Do not transmit raw resumes or contact/auth/storage data. Do not enable provider web search, code execution, or reasoning disclosure. Temporary provider unavailability degrades only new generation.

## Context

Roadmaps need synthesis, but CareerPilot already owns canonical role requirements, student evidence status, and retrieved resources. Allowing a model to rediscover or modify those facts would erase provenance and create unsafe private state. Groq catalogs and project permissions also change independently of application releases.

## Consequences

Provider replacement does not change roadmap rules. Every persisted item is auditable to supplied IDs, and provider-valid JSON can still be rejected by domain validation. Model changes require explicit configuration and fresh verification. The design adds validation/persistence complexity and may refuse or partially cover a roadmap when the small corpus lacks resources; this is intentional.
