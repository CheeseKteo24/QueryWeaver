from __future__ import annotations

from collections.abc import Callable, Sequence

from queryweaver.models import EvaluationCase, SearchHit


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
