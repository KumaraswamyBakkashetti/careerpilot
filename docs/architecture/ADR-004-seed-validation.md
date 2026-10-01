# ADR-004: Versioned snapshot ingestion

Status: accepted, 2026-10-01.

The canonical seed is deterministic, human-readable JSON with hashed Markdown observation notes. Strict application validation runs before Neo4j access. A controlled CLI performs schema creation and one-transaction snapshot ingestion after explicit curated-data acceptance.

Stable IDs, immutable same-version hashes, rejected downgrades, dataset ownership, and owned-record pruning make updates explicit and repeatable. Public CRUD and arbitrary Cypher endpoints are excluded. This favors reviewability and rollback over a high-volume import pipeline.
