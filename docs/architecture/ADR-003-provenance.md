# ADR-003: Source nodes with assertion evidence

Status: accepted, 2026-10-01.

Canonical relationships remain direct graph edges. Each stores its validated assertion payload and source IDs; `KnowledgeSource` nodes store shared metadata and hashes. Read DTOs combine both.

Relationship properties alone would duplicate publisher and collection metadata. Reifying every assertion would add two hops to ordinary role-to-skill queries. This hybrid keeps traversals clear while retaining exact evidence, locator, method, validation time, and source metadata. Confidence scores are excluded because the seed has no calibrated basis for them.
