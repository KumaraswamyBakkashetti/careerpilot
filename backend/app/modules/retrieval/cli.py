import argparse
import json
from pathlib import Path

from app.core.config import Settings
from app.infrastructure.retrieval_index import FaissIndexStore
from app.modules.retrieval.corpus import chunk_resource, load_corpus
from app.modules.retrieval.embedding import SentenceTransformerEmbeddingProvider


def build(settings: Settings) -> dict[str, object]:
    knowledge_root = Path(__file__).resolve().parents[3] / "knowledge_data"
    knowledge_version, resources = load_corpus(knowledge_root)
    chunks = [
        chunk
        for resource in resources
        for chunk in chunk_resource(
            resource, settings.retrieval_chunk_size, settings.retrieval_chunk_overlap
        )
    ]
    embedding = SentenceTransformerEmbeddingProvider(
        settings.retrieval_embedding_model,
        settings.retrieval_embedding_revision,
        settings.retrieval_embedding_dimension,
    )
    store = FaissIndexStore(settings.retrieval_index_root, embedding)
    manifest = store.build(
        resources,
        chunks,
        knowledge_version,
        resources[0].corpus_version,
        settings.retrieval_chunk_size,
        settings.retrieval_chunk_overlap,
    )
    return manifest.model_dump(mode="json")


def main() -> None:
    parser = argparse.ArgumentParser(description="CareerPilot controlled retrieval-index operation")
    parser.add_argument("command", choices=["build"])
    args = parser.parse_args()
    if args.command == "build":
        print(json.dumps(build(Settings()), indent=2))


if __name__ == "__main__":
    main()
