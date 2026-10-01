import hashlib
import json
from pathlib import Path

from app.modules.knowledge.models import Dataset

DEFAULT_SEED = Path(__file__).resolve().parents[3] / "knowledge_data" / "seed.json"


def load_dataset(path: Path = DEFAULT_SEED) -> Dataset:
    if path.stat().st_size > 10_000_000:
        raise ValueError("Seed exceeds bounded ingestion size")
    dataset = Dataset.model_validate_json(path.read_text(encoding="utf-8"))
    base = path.parent.resolve()
    snapshots: dict[str, str] = {}
    for source in dataset.sources:
        snapshot = (base / source.snapshot_path).resolve()
        if not snapshot.is_relative_to(base):
            raise ValueError("Source snapshot escapes dataset directory")
        if hashlib.sha256(snapshot.read_bytes()).hexdigest() != source.content_hash:
            raise ValueError("Source snapshot hash mismatch")
        snapshots[source.id] = snapshot.read_text(encoding="utf-8")
    for assertion in dataset.assertions:
        for citation in assertion.provenance:
            note = snapshots[citation.source_id]
            if f"## {citation.locator}" not in note or citation.evidence not in note:
                raise ValueError("Citation locator/evidence is absent from its source note")
    return dataset


def dataset_hash(dataset: Dataset) -> str:
    values = dataset.model_dump(mode="json")
    for key in ("sources", "entities", "assertions"):
        values[key] = sorted(values[key], key=lambda item: item["id"])
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
