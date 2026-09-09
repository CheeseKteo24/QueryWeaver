# Learning roadmap

The goal is not merely to finish features. At each milestone, be ready to explain and reproduce the important part yourself.

## M0 — Foundations (current)

Learn: chunking trade-offs, inverted indexes/BM25 intuition, retrieval metrics, SQL safety, test design.

Your exercises:

1. Explain why stable chunk IDs matter for citations and incremental indexing.
2. Derive the IDF term used in `LexicalRetriever` with a small three-document example.
3. Add one Chinese retrieval test and explain the tokenizer limitation you observe.
4. Write five adversarial SQL strings and see which layer blocks each one.

Exit evidence: all tests pass; one short benchmark table is committed.

## M1 — Hybrid retrieval

Learn: embeddings, cosine similarity, BM25, reciprocal-rank fusion, reranking, recall/latency trade-offs.

Build: Qdrant adapter, local embedding provider, fusion retriever, reranker, 30-case dataset.

Exit evidence: compare lexical, dense, and hybrid results using hit-rate/MRR and p95 latency.

## M2 — Text-to-SQL

Learn: schema linking, constrained generation, AST validation, query repair, execution feedback.

Build: schema catalog, read-only Postgres role, SQLGlot validation, result table/chart response.

Exit evidence: 30 benchmark questions and a report covering execution accuracy and unsafe-query rejection.

## M3–M5 — Agent reliability

Learn: state machines, tool contracts, idempotency, retries, trace context, LLM-as-judge limitations.

Build: LangGraph orchestration, OpenTelemetry traces, golden datasets, regression gates, human review.

Exit evidence: a failed trace can be diagnosed from the dashboard, and CI blocks a known quality regression.

## M6–M7 — Shipping and open source

Learn: streaming UX, auth/multi-tenancy, containers, deployment, documentation, maintainer workflow.

Build: Next.js UI, Docker Compose, hosted demo, architecture diagram, demo video, good-first-issues.

Exit evidence: a stranger can run the project in under ten minutes and reproduce the benchmark.
