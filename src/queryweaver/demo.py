from __future__ import annotations

import sqlite3

from queryweaver.application import DeterministicSynthesizer, QueryWeaverApplication
from queryweaver.hybrid import HybridRetriever
from queryweaver.ingestion import chunk_document
from queryweaver.reranking import RerankingRetriever, TokenOverlapReranker
from queryweaver.retrieval import LexicalRetriever
from queryweaver.text_to_sql import TextToSqlService
from queryweaver.vector import HashingEmbedder, VectorRetriever


class DemoSqlGenerator:
    """Deterministic stand-in that exercises the same boundary as a production LLM."""

    def generate(self, question: str, schema_context: str) -> str:
        if "TABLE sales" not in schema_context:
            raise ValueError("demo sales schema is unavailable")
        normalized = question.casefold()
        if any(signal in normalized for signal in ("地区", "region", "各区域")):
            return (
                "SELECT region, ROUND(SUM(amount), 2) AS revenue "
                "FROM sales GROUP BY region ORDER BY revenue DESC"
            )
        if any(signal in normalized for signal in ("多少", "count", "how many")):
            return "SELECT COUNT(*) AS sale_count FROM sales"
        return "SELECT ROUND(SUM(amount), 2) AS total_revenue FROM sales"


def _demo_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.execute(
        "CREATE TABLE sales(id INTEGER PRIMARY KEY, region TEXT NOT NULL, amount REAL NOT NULL)"
    )
    connection.executemany(
        "INSERT INTO sales(region, amount) VALUES (?, ?)",
        [
            ("华东", 12800.0),
            ("华东", 7200.0),
            ("华南", 15600.0),
            ("华北", 9400.0),
        ],
    )
    connection.commit()
    return connection


def create_demo_application() -> QueryWeaverApplication:
    """Build a zero-key vertical slice for local learning and end-to-end tests."""
    documents = {
        "refund-policy": (
            "普通商品可在签收后 30 天内申请退款。数字订阅服务应在购买后 7 天内申请退款，"
            "并且账号使用时长不能超过两小时。"
        ),
        "leave-policy": (
            "正式员工每年享有 12 天带薪年假。外包人员不适用员工年假制度，"
            "休假安排依据其服务合同执行。"
        ),
        "access-policy": (
            "生产环境访问权限需要直属主管与安全团队共同审批。开发环境访问只需要项目负责人审批。"
        ),
    }
    chunks = [
        chunk
        for document_id, text in documents.items()
        for chunk in chunk_document(document_id, text, max_words=28)
    ]
    lexical = LexicalRetriever(chunks)
    vector = VectorRetriever(chunks, HashingEmbedder())
    hybrid = HybridRetriever(lexical, vector, candidate_multiplier=2)
    retriever = RerankingRetriever(hybrid, TokenOverlapReranker(), candidate_multiplier=2)

    text_to_sql = TextToSqlService(_demo_connection(), DemoSqlGenerator())
    return QueryWeaverApplication(retriever, text_to_sql, DeterministicSynthesizer())
