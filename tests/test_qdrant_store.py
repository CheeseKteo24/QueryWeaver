import unittest
from types import SimpleNamespace

from queryweaver.models import Chunk
from queryweaver.qdrant_store import QdrantRetriever, _point_id
from queryweaver.vector import HashingEmbedder


class FakeModels:
    class Distance:
        COSINE = "cosine"

    @staticmethod
    def VectorParams(**values: object) -> dict[str, object]:
        return values

    @staticmethod
    def PointStruct(**values: object) -> SimpleNamespace:
        return SimpleNamespace(**values)


class FakeQdrantClient:
    def __init__(self) -> None:
        self.exists = True
        self.deleted = False
        self.points: list[SimpleNamespace] = []
        self.closed = False

    def collection_exists(self, _: str) -> bool:
        return self.exists

    def delete_collection(self, _: str) -> None:
        self.deleted = True

    def create_collection(self, **_: object) -> None:
        self.exists = True

    def upload_points(self, *, collection_name: str, points: list[SimpleNamespace]) -> None:
        self.points = points

    def query_points(self, **_: object) -> SimpleNamespace:
        point = self.points[0]
        return SimpleNamespace(points=[SimpleNamespace(payload=point.payload, score=0.91)])

    def close(self) -> None:
        self.closed = True


class QdrantRetrieverTests(unittest.TestCase):
    def test_rebuild_replaces_index_and_round_trips_payload(self) -> None:
        client = FakeQdrantClient()
        retriever = QdrantRetriever(
            HashingEmbedder(dimensions=16), client=client, model_types=FakeModels
        )
        chunk = Chunk("refund", "policy", "Refunds are available for 30 days.", 2)

        self.assertEqual(retriever.rebuild([chunk]), 1)
        self.assertTrue(client.deleted)
        self.assertEqual(client.points[0].id, _point_id("refund"))
        self.assertEqual(retriever.search("refund", top_k=1)[0].chunk, chunk)

        retriever.close()
        self.assertTrue(client.closed)


if __name__ == "__main__":
    unittest.main()
