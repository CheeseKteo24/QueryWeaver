from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from queryweaver.models import SearchHit


class Retriever(Protocol):
    def search(self, query: str, *, top_k: int = 5) -> list[SearchHit]: ...


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[SearchHit]], *, top_k: int, rrf_k: int = 60
) -> list[SearchHit]:
    """Fuse rankings without assuming their raw scores share a scale."""
    if top_k < 1 or rrf_k < 1:
        raise ValueError("top_k and rrf_k must be positive")

    scores: dict[str, float] = {}
    hits_by_id: dict[str, SearchHit] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, 1):
            chunk_id = hit.chunk.id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (rrf_k + rank)
            hits_by_id[chunk_id] = hit

    fused = [SearchHit(hits_by_id[chunk_id].chunk, score) for chunk_id, score in scores.items()]
    return sorted(fused, key=lambda hit: (-hit.score, hit.chunk.id))[:top_k]


class HybridRetriever:
    def __init__(
        self, lexical: Retriever, vector: Retriever, *, candidate_multiplier: int = 4, rrf_k: int = 60
    ) -> None:
        if candidate_multiplier < 1:
            raise ValueError("candidate_multiplier must be positive")
        self.lexical = lexical
        self.vector = vector
        self.candidate_multiplier = candidate_multiplier
        self.rrf_k = rrf_k

    def search(self, query: str, *, top_k: int = 5) -> list[SearchHit]:
        candidate_count = top_k * self.candidate_multiplier
        rankings = [
            self.lexical.search(query, top_k=candidate_count),
            self.vector.search(query, top_k=candidate_count),
        ]
        return reciprocal_rank_fusion(rankings, top_k=top_k, rrf_k=self.rrf_k)
