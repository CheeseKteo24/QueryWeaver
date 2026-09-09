import unittest

from queryweaver.ingestion import chunk_document
from queryweaver.retrieval import LexicalRetriever


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


if __name__ == "__main__":
    unittest.main()
