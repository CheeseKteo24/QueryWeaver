from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable

from queryweaver.models import Chunk, SearchHit

TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


class LexicalRetriever:
    """Small BM25 retriever used as an explainable baseline and CI fixture."""

    def __init__(self, chunks: Iterable[Chunk], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = list(chunks)
        self.k1 = k1
        self.b = b
        self._tokens = [tokenize(chunk.text) for chunk in self.chunks]
        self._avg_length = (
            sum(map(len, self._tokens)) / len(self._tokens) if self._tokens else 0.0
        )
        self._document_frequency: Counter[str] = Counter()
        for tokens in self._tokens:
            self._document_frequency.update(set(tokens))

    def search(self, query: str, *, top_k: int = 5) -> list[SearchHit]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query_tokens = tokenize(query)
        scored: list[SearchHit] = []
        for chunk, tokens in zip(self.chunks, self._tokens, strict=True):
            term_frequency = Counter(tokens)
            score = sum(self._bm25(term, term_frequency[term], len(tokens)) for term in query_tokens)
            if score > 0:
                scored.append(SearchHit(chunk, score))
        return sorted(scored, key=lambda hit: (-hit.score, hit.chunk.id))[:top_k]

    def _bm25(self, term: str, frequency: int, document_length: int) -> float:
        if not frequency or not self.chunks or not self._avg_length:
            return 0.0
        document_frequency = self._document_frequency[term]
        inverse_document_frequency = math.log(
            1 + (len(self.chunks) - document_frequency + 0.5) / (document_frequency + 0.5)
        )
        normalization = frequency + self.k1 * (
            1 - self.b + self.b * document_length / self._avg_length
        )
        return inverse_document_frequency * frequency * (self.k1 + 1) / normalization
