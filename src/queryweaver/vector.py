from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

from queryweaver.models import Chunk, SearchHit
from queryweaver.retrieval import tokenize


class Embedder(Protocol):
    """Provider boundary for local, hosted, or test embedding implementations."""

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _normalize(vector: Sequence[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else [0.0 for value in vector]


class HashingEmbedder:
    """Deterministic, API-free vector baseline—not a semantic embedding model."""

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be at least 8")
        self.dimensions = dimensions

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        return _normalize(vector)


class FastEmbedEmbedder:
    """Multilingual ONNX embedding adapter with query/passage-aware encoding."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        *,
        cache_dir: Path | None = None,
        batch_size: int = 32,
        model: Any | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if model is None:
            try:
                from fastembed import TextEmbedding  # type: ignore[import-not-found]
            except ImportError as error:
                raise RuntimeError(
                    "FastEmbed is optional; install QueryWeaver with the retrieval extra"
                ) from error
            supported_models = {item["model"] for item in TextEmbedding.list_supported_models()}
            if model_name not in supported_models:
                raise ValueError(
                    f"FastEmbed model {model_name!r} is not registered in this runtime"
                )
            options: dict[str, object] = {"model_name": model_name, "lazy_load": True}
            if cache_dir is not None:
                options["cache_dir"] = str(cache_dir)
            model = TextEmbedding(**options)
        self.model_name = model_name
        self.batch_size = batch_size
        self._model = model

    @staticmethod
    def _as_floats(vector: Iterable[Any]) -> list[float]:
        return [float(value) for value in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.passage_embed(texts, batch_size=self.batch_size)
        return [self._as_floats(vector) for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        vectors = self._model.query_embed(text, batch_size=self.batch_size)
        try:
            return self._as_floats(next(iter(vectors)))
        except StopIteration as error:
            raise ValueError("embedding model returned no vector for the query") from error


class VectorRetriever:
    def __init__(self, chunks: Iterable[Chunk], embedder: Embedder) -> None:
        self.chunks = list(chunks)
        self.embedder = embedder
        self._vectors = [
            _normalize(vector)
            for vector in embedder.embed_documents([chunk.text for chunk in self.chunks])
        ]
        dimensions = {len(vector) for vector in self._vectors}
        if len(dimensions) > 1:
            raise ValueError("embedder returned inconsistent vector dimensions")

    def search(self, query: str, *, top_k: int = 5) -> list[SearchHit]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query_vector = _normalize(self.embedder.embed_query(query))
        if self._vectors and len(query_vector) != len(self._vectors[0]):
            raise ValueError("query and document vector dimensions differ")

        hits = [
            SearchHit(
                chunk,
                sum(left * right for left, right in zip(vector, query_vector, strict=True)),
            )
            for chunk, vector in zip(self.chunks, self._vectors, strict=True)
        ]
        positive_hits = (hit for hit in hits if hit.score > 0)
        return sorted(positive_hits, key=lambda hit: (-hit.score, hit.chunk.id))[:top_k]
