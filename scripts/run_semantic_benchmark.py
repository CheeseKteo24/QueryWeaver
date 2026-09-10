from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from queryweaver.evaluation import retrieval_metrics  # noqa: E402
from queryweaver.hybrid import HybridRetriever  # noqa: E402
from queryweaver.models import Chunk, EvaluationCase  # noqa: E402
from queryweaver.qdrant_store import QdrantRetriever  # noqa: E402
from queryweaver.retrieval import LexicalRetriever  # noqa: E402
from queryweaver.vector import FastEmbedEmbedder  # noqa: E402


def load_fixture() -> tuple[list[Chunk], list[EvaluationCase]]:
    path = ROOT / "benchmarks" / "retrieval_cases.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks = [
        Chunk(item["id"], item["document_id"], item["text"], position)
        for position, item in enumerate(payload["chunks"])
    ]
    cases = [
        EvaluationCase(item["query"], frozenset(item["relevant_chunk_ids"]))
        for item in payload["cases"]
    ]
    return chunks, cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the opt-in real semantic benchmark")
    parser.add_argument(
        "--model", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    parser.add_argument("--qdrant-location", default=str(ROOT / "data" / "local" / "qdrant"))
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--assert-minimum", type=float, default=None)
    args = parser.parse_args()

    chunks, cases = load_fixture()
    started = perf_counter()
    embedder = FastEmbedEmbedder(
        model_name=args.model,
        cache_dir=ROOT / "data" / "local" / "models",
    )
    semantic = QdrantRetriever(embedder, location=args.qdrant_location)
    indexed = semantic.rebuild(chunks)
    indexing_seconds = perf_counter() - started
    lexical = LexicalRetriever(chunks)
    hybrid = HybridRetriever(lexical, semantic)

    search_started = perf_counter()
    metrics = retrieval_metrics(
        cases,
        lambda query, top_k: hybrid.search(query, top_k=top_k),
        top_k=args.top_k,
    )
    elapsed = perf_counter() - search_started
    latency_ms = elapsed * 1000 / len(cases)
    metric_name = f"hit_rate@{args.top_k}"

    print(f"model: {args.model}")
    print(f"indexed chunks: {indexed}")
    print(f"indexing seconds: {indexing_seconds:.3f}")
    print(f"mean query latency ms: {latency_ms:.3f}")
    for name, value in metrics.items():
        print(f"{name}: {value:.3f}")

    semantic.close()
    if args.assert_minimum is not None and metrics[metric_name] < args.assert_minimum:
        print(f"quality gate failed: {metric_name} < {args.assert_minimum}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
