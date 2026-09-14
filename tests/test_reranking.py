import unittest
from collections.abc import Sequence

from queryweaver.models import Chunk, SearchHit
from queryweaver.reranking import (
    FastEmbedCrossEncoderReranker,
    RerankingRetriever,
    TokenOverlapReranker,
)


class StaticRetriever:
    def __init__(self, hits: Sequence[SearchHit]) -> None:
        self.hits = list(hits)
        self.requested_top_k = 0

    def search(self, query: str, *, top_k: int = 5) -> list[SearchHit]:
        self.requested_top_k = top_k
        return self.hits[:top_k]


class FakeCrossEncoder:
    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        return [0.1, 0.9]


class RerankingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.wrong = SearchHit(Chunk("wrong", "doc", "shipping policy", 0), 9.0)
        self.right = SearchHit(Chunk("right", "doc", "refund policy is thirty days", 1), 1.0)

    def test_overlap_reranker_moves_more_relevant_candidate_first(self) -> None:
        reranked = TokenOverlapReranker().rerank(
            "refund policy", [self.wrong, self.right], top_k=1
        )
        self.assertEqual(reranked[0].chunk.id, "right")

    def test_cross_encoder_scores_are_attached_to_original_chunks(self) -> None:
        reranker = FastEmbedCrossEncoderReranker(model=FakeCrossEncoder())
        reranked = reranker.rerank("refund", [self.wrong, self.right], top_k=2)
        self.assertEqual(reranked[0].chunk.id, "right")
        self.assertEqual(reranked[0].score, 0.9)

    def test_wrapper_fetches_more_candidates_than_final_top_k(self) -> None:
        base = StaticRetriever([self.wrong, self.right])
        retriever = RerankingRetriever(base, TokenOverlapReranker(), candidate_multiplier=3)
        self.assertEqual(retriever.search("refund policy", top_k=1)[0].chunk.id, "right")
        self.assertEqual(base.requested_top_k, 3)


if __name__ == "__main__":
    unittest.main()
