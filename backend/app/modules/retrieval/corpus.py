import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from app.modules.knowledge.models import Dataset
from app.modules.retrieval.models import CanonicalResource, ResourceChunk

CHUNKING_VERSION = "deterministic-structure-v1"


def normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in value.splitlines()).strip()


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_corpus(knowledge_root: Path) -> tuple[str, list[CanonicalResource]]:
    dataset = Dataset.model_validate_json((knowledge_root / "seed.json").read_text("utf-8"))
    sources = {item.id: item for item in dataset.sources}
    skills_by_resource: dict[str, list[str]] = {}
    for assertion in dataset.assertions:
        if assertion.type == "TEACHES_SKILL":
            skills_by_resource.setdefault(assertion.source_id, []).append(assertion.target_id)
    resources: list[CanonicalResource] = []
    for entity in sorted(
        (item for item in dataset.entities if item.kind == "Resource"), key=lambda item: item.id
    ):
        source_id = entity.source_ids[0]
        source = sources[source_id]
        if entity.content_ref is None:
            raise ValueError(f"Canonical resource has no content reference: {entity.id}")
        source_path = knowledge_root / source.snapshot_path
        raw = source_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source.content_hash:
            raise ValueError(f"Canonical resource hash mismatch: {entity.id}")
        text = normalize_text(raw.decode("utf-8"))
        resources.append(
            CanonicalResource(
                resource_id=entity.id,
                source_id=source_id,
                content_ref=entity.content_ref,
                name=entity.name,
                url=str(entity.url),
                text=text,
                content_hash=source.content_hash,
                skill_ids=sorted(skills_by_resource.get(entity.id, [])),
                corpus_version=f"{dataset.version}-resources-v1",
            )
        )
    return dataset.version, resources


def _segments(text: str) -> list[str]:
    return [value.strip() for value in re.split(r"\n(?=#{1,6}\s)|\n\s*\n", text) if value.strip()]


def chunk_resource(
    resource: CanonicalResource, chunk_size: int, overlap: int
) -> list[ResourceChunk]:
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Invalid chunk configuration")
    pieces: list[str] = []
    for segment in _segments(resource.text):
        start = 0
        while start < len(segment):
            end = min(start + chunk_size, len(segment))
            if end < len(segment):
                boundary = segment.rfind(" ", start + chunk_size // 2, end)
                if boundary > start:
                    end = boundary
            pieces.append(segment[start:end].strip())
            if end == len(segment):
                break
            start = max(end - overlap, start + 1)
    now = datetime.now(UTC)
    return [
        ResourceChunk(
            chunk_id=f"chunk_{hashlib.sha256(f'{resource.resource_id}|{CHUNKING_VERSION}|{chunk_size}|{overlap}|{sequence}|{text}'.encode()).hexdigest()[:32]}",
            resource_id=resource.resource_id,
            source_id=resource.source_id,
            sequence=sequence,
            text=text,
            content_hash=content_hash(text),
            chunking_version=CHUNKING_VERSION,
            metadata={
                "resource_name": resource.name,
                "resource_type": resource.resource_type,
                "url": resource.url,
                "skill_ids": resource.skill_ids,
            },
            created_at=now,
        )
        for sequence, text in enumerate(pieces)
        if text
    ]


def corpus_fingerprint(resources: list[CanonicalResource]) -> str:
    payload = [(item.resource_id, item.content_hash, item.skill_ids) for item in resources]
    return content_hash(json.dumps(payload, separators=(",", ":"), sort_keys=True))
