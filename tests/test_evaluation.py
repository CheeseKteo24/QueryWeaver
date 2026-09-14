import unittest

from queryweaver.evaluation import measure_search_latency, retrieval_metrics
from queryweaver.models import Chunk, EvaluationCase, SearchHit


class EvaluationTests(unittest.TestCase):
    def test_metrics_capture_rank_and_multi_relevance_recall(self) -> None:
        chunks = [Chunk(str(index), "doc", str(index), index) for index in range(3)]
        cases = [EvaluationCase("query", frozenset({"1", "2"}))]

        def search(_: str, top_k: int) -> list[SearchHit]:
            return [SearchHit(chunks[0], 3.0), SearchHit(chunks[1], 2.0)][:top_k]

        metrics = retrieval_metrics(cases, search, top_k=2)
        self.assertEqual(metrics["hit_rate@2"], 1.0)
        self.assertEqual(metrics["mrr@2"], 0.5)
        self.assertEqual(metrics["recall@2"], 0.5)

    def test_latency_uses_nearest_rank_percentiles(self) -> None:
        clock_values = iter([0.0, 0.001, 1.0, 1.010, 2.0, 2.100, 3.0, 3.020])

        def clock() -> float:
            return next(clock_values)

        stats = measure_search_latency(
            ["a", "b", "c", "d"],
            lambda query, top_k: [],
            warmup_rounds=0,
            measured_rounds=1,
            clock=clock,
        )
        self.assertEqual(stats.samples, 4)
        self.assertAlmostEqual(stats.p50_ms, 10.0)
        self.assertAlmostEqual(stats.p95_ms, 100.0)


if __name__ == "__main__":
    unittest.main()
