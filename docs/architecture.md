# Architecture decisions

## Product boundary

QueryWeaver answers analytical questions from two evidence sources: unstructured documents and read-only relational data. An explicit router chooses tools; a synthesizer must cite the returned evidence. The system never gives the model a writable database connection.

## ADR-001: keep a framework-independent core

The first milestone uses plain Python. LangGraph, FastAPI, Qdrant, and model providers will be adapters around the core rather than business logic containers. This makes routing, retrieval, evaluation, and safety behavior testable without network calls.

## ADR-002: lexical retrieval is the baseline, not the destination

BM25-style retrieval is cheap, deterministic, and explainable. M1 will add dense retrieval and reciprocal-rank fusion. The baseline stays in the benchmark so every more complex technique must prove that it improves quality.

## ADR-003: SQL execution is deny-by-default

Only one `SELECT` or read-only CTE is accepted. SQLite is switched to `query_only` mode before execution. M2 will add AST validation, row/time limits, schema allowlists, and query-plan inspection.

## Planned service boundaries

- `web`: workspace UI, streaming chat, evidence inspector, experiment dashboard
- `api`: auth, ingestion, query orchestration, rate limits
- `worker`: parsing, embeddings, benchmark jobs
- `postgres`: users, projects, metadata, traces
- `qdrant`: dense vector index
- `object-store`: uploaded source files
