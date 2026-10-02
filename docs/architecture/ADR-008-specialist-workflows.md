# ADR-008: Bounded specialist workflows and practice evidence

Status: accepted, 2026-10-02.

## Decision

Implement Phase 6 as specialist services inside the modular monolith. Route explicit tasks deterministically, share the existing knowledge/retrieval/LLM boundaries, persist owner-scoped orchestration traces, and calculate readiness with versioned rules rather than an LLM.

Interview answers are immutable and stored before provider evaluation. Successful bounded evaluations may create `INTERVIEW_PRACTICE` SkillEvidence with `EXTRACTED` status and complete provenance. Gap analysis consumes it through the existing evidence path as partial support only.

## Consequences

This yields testable workflows, safe retries, visible provenance and a decomposable readiness result. It does not provide autonomous planning, broad company coverage, hiring prediction or confirmed mastery from practice. The current single fictional company is always labeled synthetic.
