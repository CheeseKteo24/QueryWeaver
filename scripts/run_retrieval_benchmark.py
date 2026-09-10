from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from queryweaver.evaluation import retrieval_metrics  # noqa: E402
from queryweaver.hybrid import HybridRetriever  # noqa: E402
from queryweaver.models import Chunk, EvaluationCase  # noqa: E402
from queryweaver.retrieval import LexicalRetriever  # noqa: E402
from queryweaver.vector import HashingEmbedder, VectorRetriever  # noqa: E402


def load_fixture(path: Path) -> tuple[list[Chunk], list[EvaluationCase]]:
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
    parser = argparse.ArgumentParser(description="Compare QueryWeaver retrieval baselines")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--assert-minimum", type=float, default=None)
    args = parser.parse_args()

    chunks, cases = load_fixture(ROOT / "benchmarks" / "retrieval_cases.json")
    lexical = LexicalRetriever(chunks)
    vector = VectorRetriever(chunks, HashingEmbedder())
    retrievers = {
        "lexical": lexical,
        "hashing-vector": vector,
        "hybrid-rrf": HybridRetriever(lexical, vector),
    }

    metric_name = f"hit_rate@{args.top_k}"
    results: dict[str, dict[str, float]] = {}
    print(f"{'retriever':<18} {'hit_rate':>10} {'mrr':>10} {'recall':>10}")
    for name, retriever in retrievers.items():
        metrics = retrieval_metrics(
            cases, lambda query, top_k, r=retriever: r.search(query, top_k=top_k), top_k=args.top_k
        )
        results[name] = metrics
        print(
            f"{name:<18} {metrics[metric_name]:>10.3f} "
            f"{metrics[f'mrr@{args.top_k}']:>10.3f} "
            f"{metrics[f'recall@{args.top_k}']:>10.3f}"
        )

    if args.assert_minimum is not None and results["hybrid-rrf"][metric_name] < args.assert_minimum:
        print(f"quality gate failed: hybrid {metric_name} < {args.assert_minimum}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
