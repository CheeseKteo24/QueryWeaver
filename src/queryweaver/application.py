from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from queryweaver.hybrid import Retriever
from queryweaver.models import Route, SearchHit
from queryweaver.router import route_question
from queryweaver.sql_policy import SqlExecutionResult
from queryweaver.text_to_sql import TextToSqlAnswer, TextToSqlService


class AnswerSynthesizer(Protocol):
    """Turn trusted evidence into an answer without owning retrieval or database access."""

    def answer_documents(self, question: str, evidence: Sequence[SearchHit]) -> str: ...

    def answer_sql(self, question: str, sql_answer: TextToSqlAnswer) -> str: ...


@dataclass(frozen=True, slots=True)
class Evidence:
    chunk_id: str
    document_id: str
    text: str
    score: float


@dataclass(frozen=True, slots=True)
class QueryResponse:
    question: str
    route: Route
    answer: str
    evidence: tuple[Evidence, ...] = ()
    generated_sql: str | None = None
    validated_sql: str | None = None
    sql_result: SqlExecutionResult | None = None
    latency_ms: float = 0.0


class DeterministicSynthesizer:
    """API-free demo substitute; a model adapter can replace it through the protocol."""

    def answer_documents(self, question: str, evidence: Sequence[SearchHit]) -> str:
        del question
        if not evidence:
            return "没有检索到足够的文档证据，暂时无法回答。"
        statements = [f"[{hit.chunk.id}] {hit.chunk.text}" for hit in evidence]
        return "根据已检索到的文档：\n" + "\n".join(statements)

    def answer_sql(self, question: str, sql_answer: TextToSqlAnswer) -> str:
        del question
        result = sql_answer.result
        suffix = "，结果已按安全上限截断" if result.truncated else ""
        return f"查询成功，返回 {len(result.rows)} 行数据{suffix}。"


class QueryWeaverApplication:
    """Single application boundary shared by CLI, HTTP, tests, and future workers."""

    def __init__(
        self,
        retriever: Retriever,
        text_to_sql: TextToSqlService,
        synthesizer: AnswerSynthesizer,
        *,
        router: Callable[[str], Route] = route_question,
    ) -> None:
        self.retriever = retriever
        self.text_to_sql = text_to_sql
        self.synthesizer = synthesizer
        self.router = router

    def ask(self, question: str, *, top_k: int = 5) -> QueryResponse:
        if not question.strip():
            raise ValueError("question must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be positive")

        started = monotonic()
        route = self.router(question)
        if route is Route.DOCUMENTS:
            hits = self.retriever.search(question, top_k=top_k)
            evidence = tuple(
                Evidence(
                    chunk_id=hit.chunk.id,
                    document_id=hit.chunk.document_id,
                    text=hit.chunk.text,
                    score=hit.score,
                )
                for hit in hits
            )
            answer = self.synthesizer.answer_documents(question, hits)
            return QueryResponse(
                question=question,
                route=route,
                answer=answer,
                evidence=evidence,
                latency_ms=(monotonic() - started) * 1000,
            )

        sql_answer = self.text_to_sql.execute(question)
        answer = self.synthesizer.answer_sql(question, sql_answer)
        return QueryResponse(
            question=question,
            route=route,
            answer=answer,
            generated_sql=sql_answer.generated_sql,
            validated_sql=sql_answer.validated.sql,
            sql_result=sql_answer.result,
            latency_ms=(monotonic() - started) * 1000,
        )
