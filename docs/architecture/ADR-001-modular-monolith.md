# ADR-001: Begin with a modular monolith

Status: accepted for Phase 1. Date: 2026-10-01.

## Context

CareerPilot will coordinate student state, canonical knowledge, retrieval, evidence and preparation workflows. Its domain contracts and workload are not mature enough to justify distributed deployment. Phase 1 must prove a reliable engineering foundation without premature business schemas or orchestration frameworks.

## Decision

Use one FastAPI application with HTTP, application-service and infrastructure boundaries. React is a separate browser client. Application services depend on protocols; the composition root creates driver adapters. MongoDB owns student/application state; Neo4j owns canonical career knowledge. Later semantic indexes are rebuildable derived data.

## Rationale

One deployable backend reduces operational and transaction-coordination costs. Explicit boundaries permit isolated tests and later module ownership without multiplying network failure modes. Microservices initially would require stable contracts, deployment automation, distributed observability and ownership that this phase cannot justify.

## Consequences

Modules share a process and resource budget. Internal dependency direction needs continued review. Phase 1 therefore includes no empty domain packages: `application.health` is the actual first application service. New module interfaces should be introduced alongside working use cases. Drivers stay in infrastructure and may not be imported into future domain logic.

## Future extraction strategy

Measure throughput, memory pressure and independently changing ownership first. Resume processing or retrieval could become extraction candidates when evidence supports it. Stabilize application contracts, explicit data ownership and idempotency before replacing an internal implementation with a network adapter. Do not share direct cross-service access to authoritative stores after extraction.
