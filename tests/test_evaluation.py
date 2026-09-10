import unittest

from queryweaver.evaluation import retrieval_metrics
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


if __name__ == "__main__":
    unittest.main()
