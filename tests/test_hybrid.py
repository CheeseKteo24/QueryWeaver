import unittest
from collections.abc import Sequence

from queryweaver.hybrid import HybridRetriever, reciprocal_rank_fusion
from queryweaver.models import Chunk, SearchHit
from queryweaver.retrieval import LexicalRetriever
from queryweaver.vector import Embedder, VectorRetriever


class FakeSemanticEmbedder(Embedder):
    vocabulary = {
        "leave policy": [1.0, 0.0],
        "vacation rules": [1.0, 0.0],
        "quarterly revenue": [0.0, 1.0],
    }

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.vocabulary.get(text.casefold(), [0.0, 0.0]) for text in texts]


class HybridRetrieverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = Chunk("policy", "handbook", "leave policy", 0)
        self.revenue = Chunk("revenue", "finance", "quarterly revenue", 0)

    def test_vector_retrieval_can_match_a_synonym(self) -> None:
        retriever = VectorRetriever([self.policy, self.revenue], FakeSemanticEmbedder())
        self.assertEqual(retriever.search("vacation rules", top_k=1)[0].chunk.id, "policy")

    def test_rrf_rewards_a_result_found_by_both_retrievers(self) -> None:
        rankings = [
            [SearchHit(self.policy, 100.0), SearchHit(self.revenue, 1.0)],
            [SearchHit(self.revenue, 0.99), SearchHit(self.policy, 0.98)],
        ]
        fused = reciprocal_rank_fusion(rankings, top_k=2, rrf_k=60)
        self.assertEqual({hit.chunk.id for hit in fused}, {"policy", "revenue"})
        self.assertAlmostEqual(fused[0].score, fused[1].score)

    def test_hybrid_retriever_exposes_a_single_search_contract(self) -> None:
        chunks = [self.policy, self.revenue]
        hybrid = HybridRetriever(
            LexicalRetriever(chunks), VectorRetriever(chunks, FakeSemanticEmbedder())
        )
        self.assertEqual(hybrid.search("vacation rules", top_k=1)[0].chunk.id, "policy")


if __name__ == "__main__":
    unittest.main()
