# ADR-005: Keep private student evidence outside the canonical graph

- Status: Accepted
- Date: 2026-10-01

## Context

Resume observations are private, mutable, student-reviewed records. Canonical roles and skills are reviewed shared knowledge with source provenance. Combining them as authoritative `Student-HAS_SKILL->Skill` graph edges would erase the difference between a mention, a confirmation, and demonstrated proficiency, while making ownership and deletion harder.

## Decision

MongoDB owns accounts, profiles, resume metadata, processing runs, `SkillEvidence`, and gap snapshots. Private files use a `ResumeStorage` boundary backed by a non-public local directory in Phase 3. Evidence references Neo4j canonical IDs, but resume processing has read-only access to the canonical graph and cannot publish skills or student edges.

Processing is synchronous and bounded for the Phase 3 document limits. It uses deterministic PDF/DOCX extraction and conservative canonical alias matching. Gap classification is the versioned `gap-rules-v1` table documented in [student-evidence.md](student-evidence.md); no LLM or numeric proficiency model participates.

## Consequences

Student ownership can be enforced with MongoDB owner filters, and resume deletion does not mutate shared knowledge. Evidence and canonical graph versions can evolve independently. Cross-store analysis is an application-service operation rather than a database join. A future worker may replace synchronous processing at the existing service boundary, and a future storage adapter may replace local files.

