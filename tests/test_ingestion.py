import unittest

from queryweaver.ingestion import chunk_document


class ChunkDocumentTests(unittest.TestCase):
    def test_chunk_ids_are_deterministic(self) -> None:
        text = "Returns last 30 days. Shipping takes 2 days."
        first = chunk_document("policy", text, max_words=5)
        second = chunk_document("policy", text, max_words=5)
        self.assertEqual(first, second)
        self.assertEqual([chunk.position for chunk in first], [0, 1])

    def test_empty_input_returns_no_chunks(self) -> None:
        self.assertEqual(chunk_document("empty", "   "), [])


if __name__ == "__main__":
    unittest.main()
