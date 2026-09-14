from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from queryweaver.hybrid import Retriever
from queryweaver.models import SearchHit
from queryweaver.retrieval import tokenize


class Reranker(Protocol):
    def rerank(self, query: str, hits: Sequence[SearchHit], *, top_k: int) -> list[SearchHit]: ...


class TokenOverlapReranker:
    """Deterministic reranking baseline used by tests and offline CI."""

    def rerank(self, query: str, hits: Sequence[SearchHit], *, top_k: int) -> list[SearchHit]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query_tokens = set(tokenize(query))
        rescored: list[SearchHit] = []
        for rank, hit in enumerate(hits, 1):
            document_tokens = set(tokenize(hit.chunk.text))
            overlap = len(query_tokens & document_tokens) / max(len(query_tokens), 1)
            tie_breaker = 1 / (10_000 + rank)
            rescored.append(SearchHit(hit.chunk, overlap + tie_breaker))
        return sorted(rescored, key=lambda item: (-item.score, item.chunk.id))[:top_k]


class FastEmbedCrossEncoderReranker:
    """Optional cross-encoder adapter; model downloads are never required by CI."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        *,
        cache_dir: Path | None = None,
        model: Any | None = None,
    ) -> None:
        if model is None:
            try:
                from fastembed.rerank.cross_encoder import (  # type: ignore[import-not-found]
                    TextCrossEncoder,
                )
            except ImportError as error:
                raise RuntimeError(
                    "FastEmbed is optional; install QueryWeaver with the retrieval extra"
                ) from error
            options: dict[str, object] = {"model_name": model_name, "lazy_load": True}
            if cache_dir is not None:
                options["cache_dir"] = str(cache_dir)
            model = TextCrossEncoder(**options)
        self.model_name = model_name
        self._model = model

    def rerank(self, query: str, hits: Sequence[SearchHit], *, top_k: int) -> list[SearchHit]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        if not hits:
            return []
        scores = list(self._model.rerank(query, [hit.chunk.text for hit in hits]))
        if len(scores) != len(hits):
            raise ValueError("reranker returned a different number of scores than candidates")
        rescored = [
            SearchHit(hit.chunk, float(score))
            for hit, score in zip(hits, scores, strict=True)
        ]
        return sorted(rescored, key=lambda item: (-item.score, item.chunk.id))[:top_k]


class RerankingRetriever:
    def __init__(
        self,
        retriever: Retriever,
        reranker: Reranker,
        *,
        candidate_multiplier: int = 4,
    ) -> None:
        if candidate_multiplier < 1:
            raise ValueError("candidate_multiplier must be positive")
        self.retriever = retriever
        self.reranker = reranker
        self.candidate_multiplier = candidate_multiplier

    def search(self, query: str, *, top_k: int = 5) -> list[SearchHit]:
        candidates = self.retriever.search(query, top_k=top_k * self.candidate_multiplier)
        return self.reranker.rerank(query, candidates, top_k=top_k)
