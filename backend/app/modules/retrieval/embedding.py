from threading import Lock
from typing import Any, Protocol, cast

import numpy as np
from numpy.typing import NDArray


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...
    @property
    def model_id(self) -> str: ...
    @property
    def model_version(self) -> str: ...
    def embed_documents(self, texts: list[str]) -> NDArray[np.float32]: ...
    def embed_query(self, text: str) -> NDArray[np.float32]: ...


class SentenceTransformerEmbeddingProvider:
    """One reusable local Sentence Transformer, normalized for cosine search."""

    def __init__(self, model_id: str, revision: str = "main", dimension: int = 384) -> None:
        self._model_id = model_id
        self._revision = revision
        self._model: Any | None = None
        self._dimension = dimension
        self._inference_lock = Lock()

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            model: Any = SentenceTransformer(self._model_id, revision=self._revision)
            actual = model.get_embedding_dimension()
            if actual is None or int(actual) != self._dimension:
                raise ValueError("Embedding model dimension does not match configuration")
            self._model = model
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def model_version(self) -> str:
        return self._revision

    def embed_documents(self, texts: list[str]) -> NDArray[np.float32]:
        with self._inference_lock:
            values = self._load().encode(
                texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
            )
        return cast(NDArray[np.float32], np.asarray(values, dtype=np.float32))

    def embed_query(self, text: str) -> NDArray[np.float32]:
        return cast(NDArray[np.float32], self.embed_documents([text])[0])
