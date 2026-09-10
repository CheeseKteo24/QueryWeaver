# Semantic retrieval and Qdrant

## Provider boundary

The `Embedder` contract intentionally exposes two methods:

- `embed_documents`: build passage vectors during indexing;
- `embed_query`: build a query vector during retrieval.

Retrieval-oriented models such as E5 and BGE may apply different prompts or internal handling to queries and passages. Calling a generic embedding method for both can silently reduce quality.

`HashingEmbedder` keeps unit tests deterministic and offline. `FastEmbedEmbedder` is the production-oriented adapter and defaults to `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, a model registered by the current FastEmbed runtime for roughly 50 languages. The adapter validates the model name at startup, loads lazily, and caches model files under `data/local/models`, which is excluded from version control.

## Qdrant boundary

`QdrantRetriever` accepts an in-memory location, a local persistence directory, or an HTTP(S) Qdrant endpoint. Application code sees the same `search(query, top_k)` contract as the lexical retriever, so the hybrid layer is storage-agnostic.

Chunk IDs are converted to deterministic UUIDv5 point IDs. The original chunk ID and citation fields remain in the payload. This provides:

- repeatable identities across index rebuilds;
- a direct path from a search hit back to its source;
- simpler incremental upsert and deletion work in the next milestone.

## Offline CI versus opt-in benchmark

CI must remain fast and deterministic, so it uses fake semantic vectors and the hashing baseline. The real semantic benchmark is opt-in because the first run downloads an ONNX model and performance depends on the machine.

The benchmark reports indexing time, mean query latency, and retrieval quality. Its target is to raise `hit_rate@3` from the offline baseline of `0.800` to at least `0.900`, while retaining direct keyword cases.

## Known limitations

- `rebuild` replaces the whole collection; incremental indexing is not implemented yet.
- latency currently reports the mean; p50/p95 distributions are next.
- the fixture is intentionally small and must grow before metrics are resume-worthy.
- no reranker is applied after first-stage retrieval yet.
