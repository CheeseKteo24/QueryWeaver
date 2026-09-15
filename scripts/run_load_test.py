from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

QUESTIONS = (
    "数字订阅可以在多少天内退款？",
    "生产环境权限怎样申请？",
    "按地区统计销售额",
    "销售记录一共有多少条？",
)


@dataclass(frozen=True, slots=True)
class RequestSample:
    latency_ms: float
    status: int
    route: str | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LoadSummary:
    requests: int
    concurrency: int
    successful: int
    failed: int
    error_rate: float
    throughput_rps: float
    mean_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float
    routes: dict[str, int]


def nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def post_question(base_url: str, question: str, timeout: float) -> RequestSample:
    body = json.dumps({"question": question, "top_k": 3}).encode()
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/query",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
            return RequestSample(
                latency_ms=(time.perf_counter() - started) * 1000,
                status=response.status,
                route=str(payload.get("route")),
            )
    except urllib.error.HTTPError as error:
        return RequestSample(
            latency_ms=(time.perf_counter() - started) * 1000,
            status=error.code,
            route=None,
            error=f"HTTP {error.code}",
        )
    except Exception as error:  # noqa: BLE001 - load tests must count transport failures
        return RequestSample(
            latency_ms=(time.perf_counter() - started) * 1000,
            status=0,
            route=None,
            error=type(error).__name__,
        )


def summarize(
    samples: list[RequestSample], *, concurrency: int, elapsed_seconds: float
) -> LoadSummary:
    latencies = [sample.latency_ms for sample in samples]
    successful = sum(sample.status == 200 for sample in samples)
    routes = Counter(sample.route for sample in samples if sample.route)
    return LoadSummary(
        requests=len(samples),
        concurrency=concurrency,
        successful=successful,
        failed=len(samples) - successful,
        error_rate=(len(samples) - successful) / len(samples) if samples else 0.0,
        throughput_rps=len(samples) / elapsed_seconds if elapsed_seconds else 0.0,
        mean_ms=statistics.fmean(latencies) if latencies else 0.0,
        p50_ms=nearest_rank(latencies, 0.50),
        p95_ms=nearest_rank(latencies, 0.95),
        max_ms=max(latencies, default=0.0),
        routes=dict(sorted(routes.items())),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Concurrent QueryWeaver HTTP load test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--assert-p95-ms", type=float)
    parser.add_argument("--assert-max-error-rate", type=float, default=0.0)
    parser.add_argument("--json-output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.requests < 1 or args.concurrency < 1 or args.warmup < 0:
        raise SystemExit("requests/concurrency must be positive and warmup cannot be negative")

    for index in range(args.warmup):
        post_question(args.base_url, QUESTIONS[index % len(QUESTIONS)], args.timeout)

    started = time.perf_counter()
    samples: list[RequestSample] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(
                post_question,
                args.base_url,
                QUESTIONS[index % len(QUESTIONS)],
                args.timeout,
            )
            for index in range(args.requests)
        ]
        samples.extend(future.result() for future in as_completed(futures))
    elapsed = time.perf_counter() - started
    summary = summarize(samples, concurrency=args.concurrency, elapsed_seconds=elapsed)
    rendered = json.dumps(asdict(summary), ensure_ascii=False, indent=2)
    print(rendered)

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf8")
    if summary.error_rate > args.assert_max_error_rate:
        raise SystemExit(
            f"error rate {summary.error_rate:.3f} exceeded {args.assert_max_error_rate:.3f}"
        )
    if args.assert_p95_ms is not None and summary.p95_ms > args.assert_p95_ms:
        raise SystemExit(f"p95 {summary.p95_ms:.1f} ms exceeded {args.assert_p95_ms:.1f} ms")


if __name__ == "__main__":
    main()
