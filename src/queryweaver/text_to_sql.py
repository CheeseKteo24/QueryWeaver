from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from queryweaver.schema import SchemaCatalog
from queryweaver.sql_policy import (
    SqlExecutionResult,
    SqlPolicy,
    SqlPolicyValidator,
    ValidatedSql,
    execute_validated_sql,
)


class SqlGenerator(Protocol):
    def generate(self, question: str, schema_context: str) -> str: ...


@dataclass(frozen=True, slots=True)
class TextToSqlAnswer:
    question: str
    generated_sql: str
    validated: ValidatedSql
    result: SqlExecutionResult


class TextToSqlService:
    """Orchestrate generation, policy validation, and guarded execution."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        generator: SqlGenerator,
        *,
        catalog: SchemaCatalog | None = None,
        policy: SqlPolicy | None = None,
    ) -> None:
        self.connection = connection
        self.generator = generator
        self.catalog = catalog or SchemaCatalog.from_sqlite(connection)
        self.policy = policy or SqlPolicy()
        self.validator = SqlPolicyValidator(self.catalog, self.policy)
        # A sqlite connection owns mutable progress-handler/query-only state. The local
        # demo shares one connection across FastAPI worker threads, so serialize its use.
        # Production replaces this with a per-request connection from a read-only pool.
        self._execution_lock = Lock()

    def execute(self, question: str) -> TextToSqlAnswer:
        with self._execution_lock:
            generated_sql = self.generator.generate(question, self.catalog.as_prompt_context())
            validated = self.validator.validate(generated_sql)
            result = execute_validated_sql(self.connection, validated, self.policy)
        return TextToSqlAnswer(question, generated_sql, validated, result)
