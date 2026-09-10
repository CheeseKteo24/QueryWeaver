from __future__ import annotations

import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from queryweaver.models import Chunk, SearchHit
from queryweaver.vector import Embedder


def _point_id(chunk_id: str) -> str:
    """Qdrant accepts UUIDs; derive one deterministically from our stable chunk ID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"queryweaver:chunk:{chunk_id}"))


class QdrantRetriever:
    """Persistent dense retriever backed by local or remote Qdrant."""

    def __init__(
        self,
        embedder: Embedder,
        *,
        collection_name: str = "queryweaver_chunks",
        location: str | Path = ":memory:",
        client: Any | None = None,
        model_types: Any | None = None,
    ) -> None:
        if client is None or model_types is None:
            try:
                from qdrant_client import QdrantClient, models  # type: ignore[import-not-found]
            except ImportError as error:
                raise RuntimeError(
                    "Qdrant is optional; install QueryWeaver with the retrieval extra"
                ) from error
            location_value = str(location)
            if location_value == ":memory:":
                client = client or QdrantClient(":memory:")
            elif location_value.startswith(("http://", "https://")):
                client = client or QdrantClient(url=location_value)
            else:
                client = client or QdrantClient(path=location_value)
            model_types = model_types or models
        self.embedder = embedder
        self.collection_name = collection_name
        self._client = client
        self._models = model_types

    def rebuild(self, chunks: Iterable[Chunk]) -> int:
        """Replace a derived vector collection with a deterministic fresh index."""
        chunk_list = list(chunks)
        vectors = self.embedder.embed_documents([chunk.text for chunk in chunk_list])
        if len(vectors) != len(chunk_list):
            raise ValueError("embedder returned a different number of vectors than documents")
        if not vectors:
            return 0
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1 or not next(iter(dimensions)):
            raise ValueError("document vectors must share a non-zero dimension")

        if self._client.collection_exists(self.collection_name):
            self._client.delete_collection(self.collection_name)
        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=self._models.VectorParams(
                size=next(iter(dimensions)), distance=self._models.Distance.COSINE
            ),
        )
        points = [
            self._models.PointStruct(
                id=_point_id(chunk.id),
                vector=vector,
                payload={
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "text": chunk.text,
                    "position": chunk.position,
                },
            )
            for chunk, vector in zip(chunk_list, vectors, strict=True)
        ]
        self._client.upload_points(collection_name=self.collection_name, points=points)
        return len(points)

    def search(self, query: str, *, top_k: int = 5) -> list[SearchHit]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        response = self._client.query_points(
            collection_name=self.collection_name,
            query=self.embedder.embed_query(query),
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        hits: list[SearchHit] = []
        for point in response.points:
            if point.score <= 0:
                continue
            payload = point.payload or {}
            chunk = Chunk(
                id=str(payload["chunk_id"]),
                document_id=str(payload["document_id"]),
                text=str(payload["text"]),
                position=int(payload["position"]),
            )
            hits.append(SearchHit(chunk, float(point.score)))
        return hits

    def close(self) -> None:
        self._client.close()
