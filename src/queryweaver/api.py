from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from queryweaver.application import QueryWeaverApplication
from queryweaver.demo import create_demo_application
from queryweaver.sql_policy import SqlPolicyError, SqlTimeoutError


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=5, ge=1, le=20)


class EvidenceResponse(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    score: float


class SqlResultResponse(BaseModel):
    columns: list[str]
    rows: list[list[object]]
    elapsed_ms: float
    truncated: bool


class QueryResponseModel(BaseModel):
    question: str
    route: str
    answer: str
    evidence: list[EvidenceResponse]
    generated_sql: str | None
    validated_sql: str | None
    sql_result: SqlResultResponse | None
    latency_ms: float


def create_api(application: QueryWeaverApplication) -> FastAPI:
    api = FastAPI(
        title="QueryWeaver API",
        version="0.5.0",
        description="Verifiable document retrieval and guarded Text-to-SQL.",
    )
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "demo"}

    @api.post("/v1/query", response_model=QueryResponseModel)
    def query(request: QueryRequest) -> QueryResponseModel:
        try:
            response = application.ask(request.question, top_k=request.top_k)
        except (SqlPolicyError, SqlTimeoutError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        sql_result = None
        if response.sql_result is not None:
            sql_result = SqlResultResponse(
                columns=list(response.sql_result.columns),
                rows=[list(row) for row in response.sql_result.rows],
                elapsed_ms=response.sql_result.elapsed_ms,
                truncated=response.sql_result.truncated,
            )
        return QueryResponseModel(
            question=response.question,
            route=response.route.value,
            answer=response.answer,
            evidence=[
                EvidenceResponse(
                    chunk_id=item.chunk_id,
                    document_id=item.document_id,
                    text=item.text,
                    score=item.score,
                )
                for item in response.evidence
            ],
            generated_sql=response.generated_sql,
            validated_sql=response.validated_sql,
            sql_result=sql_result,
            latency_ms=response.latency_ms,
        )

    default_web_root = Path(__file__).resolve().parents[2] / "web"
    web_root = Path(os.environ.get("QUERYWEAVER_WEB_ROOT", default_web_root))
    if web_root.is_dir():
        api.mount("/", StaticFiles(directory=web_root, html=True), name="web")
    return api


app = create_api(create_demo_application())
