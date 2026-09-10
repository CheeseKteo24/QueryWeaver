from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Sequence
from typing import Protocol

from queryweaver.models import Chunk, SearchHit
from queryweaver.retrieval import tokenize


class Embedder(Protocol):
    """Provider boundary for local, hosted, or test embedding implementations."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def _normalize(vector: Sequence[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else [0.0 for value in vector]


class HashingEmbedder:
    """Deterministic, API-free vector baseline—not a semantic embedding model."""

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be at least 8")
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        return _normalize(vector)


class VectorRetriever:
    def __init__(self, chunks: Iterable[Chunk], embedder: Embedder) -> None:
        self.chunks = list(chunks)
        self.embedder = embedder
        self._vectors = [_normalize(vector) for vector in embedder.embed(
            [chunk.text for chunk in self.chunks]
        )]
        dimensions = {len(vector) for vector in self._vectors}
        if len(dimensions) > 1:
            raise ValueError("embedder returned inconsistent vector dimensions")

    def search(self, query: str, *, top_k: int = 5) -> list[SearchHit]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query_vectors = self.embedder.embed([query])
        if len(query_vectors) != 1:
            raise ValueError("embedder must return one vector for one query")
        query_vector = _normalize(query_vectors[0])
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
