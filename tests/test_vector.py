import unittest

from queryweaver.vector import FastEmbedEmbedder, HashingEmbedder


class FakeFastEmbedModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def passage_embed(self, texts: object, *, batch_size: int) -> list[list[float]]:
        self.calls.append(("passage", texts))
        return [[1.0, 0.0], [0.0, 1.0]]

    def query_embed(self, text: object, *, batch_size: int) -> list[list[float]]:
        self.calls.append(("query", text))
        return [[0.5, 0.5]]


class EmbeddingAdapterTests(unittest.TestCase):
    def test_hashing_embedder_has_separate_query_and_document_contracts(self) -> None:
        embedder = HashingEmbedder(dimensions=16)
        self.assertEqual(embedder.embed_query("refund"), embedder.embed_documents(["refund"])[0])

    def test_fastembed_uses_passage_and_query_specific_methods(self) -> None:
        model = FakeFastEmbedModel()
        embedder = FastEmbedEmbedder(model=model)
        self.assertEqual(embedder.embed_documents(["a", "b"]), [[1.0, 0.0], [0.0, 1.0]])
        self.assertEqual(embedder.embed_query("question"), [0.5, 0.5])
        self.assertEqual([call[0] for call in model.calls], ["passage", "query"])


if __name__ == "__main__":
    unittest.main()
