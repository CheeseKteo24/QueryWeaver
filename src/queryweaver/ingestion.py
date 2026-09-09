from __future__ import annotations

import hashlib
import re

from queryweaver.models import Chunk


def chunk_document(document_id: str, text: str, *, max_words: int = 120) -> list[Chunk]:
    """Split text deterministically while retaining stable, traceable chunk IDs."""
    if max_words < 1:
        raise ValueError("max_words must be positive")

    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    sentences = re.split(r"(?<=[.!?。！？])\s*", normalized)
    groups: list[str] = []
    current: list[str] = []
    current_size = 0

    for sentence in filter(None, sentences):
        words = sentence.split()
        units = words if len(words) > max_words else [sentence]
        for unit in units:
            unit_size = len(unit.split())
            if current and current_size + unit_size > max_words:
                groups.append(" ".join(current))
                current, current_size = [], 0
            current.append(unit)
            current_size += unit_size

    if current:
        groups.append(" ".join(current))

    chunks: list[Chunk] = []
    for position, group in enumerate(groups):
        digest = hashlib.sha256(f"{document_id}:{position}:{group}".encode()).hexdigest()[:12]
        chunks.append(Chunk(f"{document_id}-{digest}", document_id, group, position))
    return chunks
