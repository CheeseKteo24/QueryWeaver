import unittest

from queryweaver.ingestion import chunk_document
from queryweaver.retrieval import LexicalRetriever, tokenize


class LexicalRetrieverTests(unittest.TestCase):
    def test_relevant_chunk_ranks_first(self) -> None:
        chunks = chunk_document(
            "policy",
            "Refund requests are accepted within 30 days. International delivery takes 10 days.",
            max_words=7,
        )
        results = LexicalRetriever(chunks).search("refund requests", top_k=2)
        self.assertIn("Refund", results[0].chunk.text)
        self.assertGreater(results[0].score, 0)

    def test_chinese_text_emits_overlapping_bigrams(self) -> None:
        tokens = tokenize("退款政策")
        self.assertIn("退款", tokens)
        self.assertIn("款政", tokens)
        self.assertIn("政策", tokens)

    def test_chinese_query_matches_a_longer_sentence(self) -> None:
        chunks = chunk_document("zh-policy", "我们支持用户在三十天内申请退款。海外配送需要十天。")
        results = LexicalRetriever(chunks).search("退款申请", top_k=1)
        self.assertEqual(results[0].chunk.document_id, "zh-policy")


if __name__ == "__main__":
    unittest.main()
