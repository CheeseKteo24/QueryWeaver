from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Route(str, Enum):
    DOCUMENTS = "documents"
    SQL = "sql"


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    document_id: str
    text: str
    position: int


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk: Chunk
    score: float


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    query: str
    relevant_chunk_ids: frozenset[str]
