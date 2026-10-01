"""Local controlled dataset operations, never registered as HTTP write endpoints."""

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from app.core.config import Settings
from app.infrastructure.knowledge import GraphWriter
from app.infrastructure.neo4j import Neo4jAdapter
from app.modules.knowledge.dataset import DEFAULT_SEED, dataset_hash, load_dataset


async def run(args: argparse.Namespace) -> dict[str, object] | list[dict[str, object]]:
    # Always validate bytes/snapshots before opening a database connection.
    dataset = load_dataset(args.seed)
    if args.command == "validate":
        return {
            "dataset_version": dataset.version,
            "content_hash": dataset_hash(dataset),
            "nodes": dict(Counter(e.kind for e in dataset.entities)),
            "relationships": dict(Counter(a.type for a in dataset.assertions)),
            "sources": len(dataset.sources),
            "validation": "passed",
        }
    if args.command == "ingest" and not args.accept_curated:
        raise ValueError("Review the curated dataset then supply --accept-curated")
    adapter = Neo4jAdapter(Settings())
    try:
        await adapter.start()
        await adapter.ping()
        writer = GraphWriter(adapter)
        if args.command == "schema":
            await writer.schema()
            return {"schema": "initialized", "constraints": 15}
        if args.command == "ingest":
            await writer.schema()
            return await writer.ingest(dataset)
        if args.command == "profile":
            return await writer.profile()
        return await writer.inspect()
    finally:
        await adapter.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "schema", "ingest", "inspect", "profile"))
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument(
        "--accept-curated", action="store_true", help="Acknowledge reviewed curated/synthetic scope"
    )
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(run(args)), indent=2))
    except Exception as exc:
        # No driver text, connection URI, credentials, or potentially sensitive input.
        print(json.dumps({"error": "Knowledge operation failed", "category": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
