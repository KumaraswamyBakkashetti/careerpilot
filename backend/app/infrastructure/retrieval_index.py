import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

import numpy as np

from app.modules.retrieval.corpus import CHUNKING_VERSION, corpus_fingerprint
from app.modules.retrieval.embedding import EmbeddingProvider
from app.modules.retrieval.models import (
    CanonicalResource,
    IndexManifest,
    ResourceChunk,
    VectorEvidence,
)


class IndexUnavailableError(RuntimeError):
    pass


class IndexIncompatibleError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class FaissIndexStore:
    """Owns the disposable FAISS artifact and its JSON provenance mapping."""

    def __init__(self, root: Path, embedding: EmbeddingProvider) -> None:
        self.root = root.resolve()
        self.embedding = embedding
        self._index: Any | None = None
        self._chunks: list[ResourceChunk] = []
        self._manifest: IndexManifest | None = None
        self._load_error: Exception | None = None

    @property
    def manifest(self) -> IndexManifest:
        if self._manifest is None:
            raise IndexUnavailableError("Retrieval index is not loaded")
        return self._manifest

    def build(
        self,
        resources: list[CanonicalResource],
        chunks: list[ResourceChunk],
        knowledge_version: str,
        corpus_version: str,
        chunk_size: int,
        overlap: int,
    ) -> IndexManifest:
        import faiss

        started = perf_counter()
        fingerprint = corpus_fingerprint(resources)
        logical = hashlib.sha256(
            f"{fingerprint}|{CHUNKING_VERSION}|{chunk_size}|{overlap}|{self.embedding.model_id}|{self.embedding.model_version}".encode()
        ).hexdigest()[:24]
        try:
            existing = self.load(
                knowledge_version, corpus_version, fingerprint, chunk_size, overlap
            )
            if existing.index_version == f"retrieval-{logical}":
                return existing
        except (IndexUnavailableError, IndexIncompatibleError):
            pass
        embedding_started = perf_counter()
        vectors = self.embedding.embed_documents([chunk.text for chunk in chunks])
        embedding_ms = (perf_counter() - embedding_started) * 1000
        if vectors.ndim != 2 or vectors.shape != (len(chunks), self.embedding.dimension):
            raise ValueError("Embedding output shape does not match index configuration")
        index: Any = faiss.IndexFlatIP(self.embedding.dimension)
        index.add(np.ascontiguousarray(vectors, dtype=np.float32))
        self.root.mkdir(parents=True, exist_ok=True)
        build_id = uuid4().hex
        temporary = self.root / f".build-{build_id}"
        final = self.root / f"index-{build_id}"
        temporary.mkdir()
        try:
            index_path = temporary / "vectors.faiss"
            metadata_path = temporary / "chunks.json"
            faiss.write_index(index, str(index_path))
            metadata_path.write_text(
                json.dumps(
                    [chunk.model_dump(mode="json") for chunk in chunks],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            manifest = IndexManifest(
                index_version=f"retrieval-{logical}",
                embedding_model=self.embedding.model_id,
                embedding_revision=self.embedding.model_version,
                embedding_dimension=self.embedding.dimension,
                normalized=True,
                similarity="cosine_via_normalized_inner_product",
                chunking_version=CHUNKING_VERSION,
                chunk_size=chunk_size,
                chunk_overlap=overlap,
                knowledge_dataset_version=knowledge_version,
                resource_corpus_version=corpus_version,
                corpus_hash=fingerprint,
                created_at=datetime.now(UTC),
                resource_count=len(resources),
                chunk_count=len(chunks),
                index_sha256=_sha256(index_path),
                metadata_sha256=_sha256(metadata_path),
                embedding_duration_ms=round(embedding_ms, 3),
                build_duration_ms=round((perf_counter() - started) * 1000, 3),
            )
            (temporary / "manifest.json").write_text(
                manifest.model_dump_json(indent=2), encoding="utf-8"
            )
            os.replace(temporary, final)
            pointer_temp = self.root / f".active-{build_id}.json"
            pointer_temp.write_text(json.dumps({"directory": final.name}), encoding="utf-8")
            os.replace(pointer_temp, self.root / "active.json")
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        self._index, self._chunks, self._manifest = index, chunks, manifest
        self._load_error = None
        return manifest

    def load(
        self,
        knowledge_version: str,
        corpus_version: str,
        corpus_hash: str,
        chunk_size: int,
        overlap: int,
    ) -> IndexManifest:
        import faiss

        try:
            pointer = json.loads((self.root / "active.json").read_text("utf-8"))
            directory_name = str(pointer["directory"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise IndexUnavailableError(
                "Active retrieval index pointer is missing or invalid"
            ) from exc
        if not directory_name.startswith("index-") or Path(directory_name).name != directory_name:
            raise IndexUnavailableError("Active retrieval index pointer is unsafe")
        directory = self.root / directory_name
        try:
            manifest = IndexManifest.model_validate_json(
                (directory / "manifest.json").read_text("utf-8")
            )
        except (OSError, ValueError) as exc:
            raise IndexUnavailableError("Retrieval index manifest is missing or invalid") from exc
        expected = (
            self.embedding.model_id,
            self.embedding.model_version,
            self.embedding.dimension,
            knowledge_version,
            corpus_version,
            corpus_hash,
            CHUNKING_VERSION,
            chunk_size,
            overlap,
        )
        actual = (
            manifest.embedding_model,
            manifest.embedding_revision,
            manifest.embedding_dimension,
            manifest.knowledge_dataset_version,
            manifest.resource_corpus_version,
            manifest.corpus_hash,
            manifest.chunking_version,
            manifest.chunk_size,
            manifest.chunk_overlap,
        )
        if actual != expected:
            error = IndexIncompatibleError("Retrieval index configuration or corpus is stale")
            self._load_error = error
            raise error
        index_path, metadata_path = directory / "vectors.faiss", directory / "chunks.json"
        if not index_path.is_file() or not metadata_path.is_file():
            raise IndexUnavailableError("Retrieval index artifact is incomplete")
        if (
            _sha256(index_path) != manifest.index_sha256
            or _sha256(metadata_path) != manifest.metadata_sha256
        ):
            raise IndexUnavailableError("Retrieval index artifact failed integrity validation")
        try:
            index: Any = faiss.read_index(str(index_path))
            raw = cast(list[dict[str, object]], json.loads(metadata_path.read_text("utf-8")))
            chunks = [ResourceChunk.model_validate(value) for value in raw]
        except Exception as exc:
            raise IndexUnavailableError("Retrieval index artifact cannot be loaded") from exc
        if index.d != manifest.embedding_dimension or index.ntotal != len(chunks):
            raise IndexUnavailableError("Retrieval index dimensions or mapping are inconsistent")
        self._index, self._chunks, self._manifest = index, chunks, manifest
        self._load_error = None
        return manifest

    def search(
        self, query: str, top_k: int, skill_id: str | None = None, resource_id: str | None = None
    ) -> tuple[list[VectorEvidence], list[tuple[str, str]]]:
        if self._index is None or self._manifest is None:
            if isinstance(self._load_error, IndexIncompatibleError):
                raise self._load_error
            raise IndexUnavailableError("Retrieval index is not loaded")
        candidate_k = min(len(self._chunks), max(top_k * 4, top_k))
        vector = np.ascontiguousarray(self.embedding.embed_query(query)[None, :], dtype=np.float32)
        scores, identifiers = self._index.search(vector, candidate_k)
        selected: list[VectorEvidence] = []
        rejected: list[tuple[str, str]] = []
        for score, identifier in zip(scores[0], identifiers[0], strict=True):
            if identifier < 0:
                continue
            chunk = self._chunks[int(identifier)]
            skills = chunk.metadata.get("skill_ids", [])
            reason = None
            if skill_id and skill_id not in skills:
                reason = "CANONICAL_SKILL_MISMATCH"
            elif resource_id and chunk.resource_id != resource_id:
                reason = "RESOURCE_MISMATCH"
            if reason:
                rejected.append((chunk.chunk_id, reason))
                continue
            selected.append(
                VectorEvidence(
                    chunk_id=chunk.chunk_id,
                    resource_id=chunk.resource_id,
                    source_id=chunk.source_id,
                    text=chunk.text,
                    similarity_score=round(float(score), 6),
                    rank=len(selected) + 1,
                    metadata=chunk.metadata,
                    index_version=self._manifest.index_version,
                    embedding_model=self._manifest.embedding_model,
                )
            )
            if len(selected) == top_k:
                break
        return selected, rejected

    def health(self) -> dict[str, object]:
        return {
            "status": "ready" if self._manifest is not None else "unavailable",
            "manifest": self._manifest.model_dump(mode="json") if self._manifest else None,
        }
