from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import perf_counter

from queryweaver.models import EvaluationCase, SearchHit


@dataclass(frozen=True, slots=True)
class LatencyStats:
    samples: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float


def _nearest_rank(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    if not 0 < percentile <= 1:
        raise ValueError("percentile must be in (0, 1]")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def measure_search_latency(
    queries: Sequence[str],
    search: Callable[[str, int], Sequence[SearchHit]],
    *,
    top_k: int = 5,
    warmup_rounds: int = 1,
    measured_rounds: int = 5,
    clock: Callable[[], float] = perf_counter,
) -> LatencyStats:
    if warmup_rounds < 0 or measured_rounds < 1:
        raise ValueError("warmup_rounds must be non-negative and measured_rounds must be positive")
    for _ in range(warmup_rounds):
        for query in queries:
            search(query, top_k)

    durations_ms: list[float] = []
    for _ in range(measured_rounds):
        for query in queries:
            started = clock()
            search(query, top_k)
            durations_ms.append((clock() - started) * 1000)

    return LatencyStats(
        samples=len(durations_ms),
        mean_ms=sum(durations_ms) / len(durations_ms) if durations_ms else 0.0,
        p50_ms=_nearest_rank(durations_ms, 0.50),
        p95_ms=_nearest_rank(durations_ms, 0.95),
        max_ms=max(durations_ms, default=0.0),
    )


def retrieval_metrics(
    cases: Sequence[EvaluationCase],
    search: Callable[[str, int], Sequence[SearchHit]],
    *,
    top_k: int = 5,
) -> dict[str, float]:
    """Compute hit rate and mean reciprocal rank for a retrieval regression suite."""
    if not cases:
        return {
            f"hit_rate@{top_k}": 0.0,
            f"mrr@{top_k}": 0.0,
            f"recall@{top_k}": 0.0,
        }

    hits = 0
    reciprocal_ranks = 0.0
    recall = 0.0
    for case in cases:
        results = search(case.query, top_k)
        retrieved_ids = {hit.chunk.id for hit in results}
        first_relevant_rank = next(
            (
                rank
                for rank, hit in enumerate(results, 1)
                if hit.chunk.id in case.relevant_chunk_ids
            ),
            None,
        )
        if first_relevant_rank is not None:
            hits += 1
            reciprocal_ranks += 1 / first_relevant_rank
        if case.relevant_chunk_ids:
            recall += len(retrieved_ids & case.relevant_chunk_ids) / len(case.relevant_chunk_ids)

    return {
        f"hit_rate@{top_k}": hits / len(cases),
        f"mrr@{top_k}": reciprocal_ranks / len(cases),
        f"recall@{top_k}": recall / len(cases),
    }
