from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from time import monotonic

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from queryweaver.schema import SchemaCatalog


class SqlPolicyError(ValueError):
    pass


class SqlTimeoutError(TimeoutError):
    pass


DEFAULT_ALLOWED_FUNCTIONS = frozenset(
    {
        "AVG",
        "COALESCE",
        "COUNT",
        "DATE",
        "JULIAN_DAY",
        "LOWER",
        "MAX",
        "MIN",
        "NULLIF",
        "ROUND",
        "STRFTIME",
        "SUM",
        "TIME_TO_STR",
        "TS_OR_DS_TO_TIMESTAMP",
        "UPPER",
    }
)


@dataclass(frozen=True, slots=True)
class SqlPolicy:
    dialect: str = "sqlite"
    max_rows: int = 100
    timeout_ms: int = 1_000
    allow_select_star: bool = False
    allowed_functions: frozenset[str] = field(default_factory=lambda: DEFAULT_ALLOWED_FUNCTIONS)

    def __post_init__(self) -> None:
        if self.max_rows < 1 or self.timeout_ms < 1:
            raise ValueError("max_rows and timeout_ms must be positive")


@dataclass(frozen=True, slots=True)
class ValidatedSql:
    sql: str
    tables: tuple[str, ...]
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SqlExecutionResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    elapsed_ms: float
    truncated: bool


class SqlPolicyValidator:
    def __init__(self, catalog: SchemaCatalog, policy: SqlPolicy | None = None) -> None:
        self.catalog = catalog
        self.policy = policy or SqlPolicy()

    def validate(self, statement: str) -> ValidatedSql:
        try:
            parsed = [
                item for item in sqlglot.parse(statement, dialect=self.policy.dialect) if item
            ]
        except ParseError as error:
            raise SqlPolicyError(f"SQL parse failed: {error}") from error
        if len(parsed) != 1:
            raise SqlPolicyError("exactly one SQL statement is required")
        root = parsed[0]
        if not isinstance(root, exp.Query):
            raise SqlPolicyError("only read-only SELECT, UNION, or CTE queries are allowed")

        cte_names = {cte.alias_or_name.casefold() for cte in root.find_all(exp.CTE)}
        table_nodes = [
            table for table in root.find_all(exp.Table) if table.name.casefold() not in cte_names
        ]
        tables = tuple(sorted({table.name.casefold() for table in table_nodes}))
        unknown_tables = set(tables) - set(self.catalog.table_names)
        if unknown_tables:
            raise SqlPolicyError(f"tables are outside the allowlist: {sorted(unknown_tables)}")

        aliases = {table.alias_or_name.casefold(): table.name.casefold() for table in table_nodes}
        physical_columns = set().union(
            *(self.catalog.columns_for(table_name) for table_name in tables)
        )
        projection_aliases = {
            projection.alias_or_name.casefold()
            for select in root.find_all(exp.Select)
            for projection in select.expressions
            if isinstance(projection, exp.Alias) and projection.alias_or_name
        }
        columns: set[str] = set()
        for column in root.find_all(exp.Column):
            name = column.name.casefold()
            qualifier = column.table.casefold()
            columns.add(f"{qualifier}.{name}" if qualifier else name)
            if qualifier:
                source_table = aliases.get(qualifier, qualifier)
                if source_table in cte_names:
                    continue
                if name not in self.catalog.columns_for(source_table):
                    raise SqlPolicyError(f"column is outside the schema: {column.sql()}")
            elif name not in physical_columns and name not in projection_aliases and not cte_names:
                raise SqlPolicyError(f"column is outside the schema: {column.sql()}")

        if not self.policy.allow_select_star:
            for star in root.find_all(exp.Star):
                if not isinstance(star.parent, exp.Count):
                    raise SqlPolicyError("SELECT * is disabled; request explicit columns")

        for function in root.find_all(exp.Func):
            if isinstance(function, exp.Anonymous):
                name = function.name.upper()
            else:
                name = str(function.sql_name())  # type: ignore[no-untyped-call]
            if name not in self.policy.allowed_functions:
                raise SqlPolicyError(f"function is outside the allowlist: {name}")

        return ValidatedSql(
            sql=root.sql(dialect=self.policy.dialect),
            tables=tables,
            columns=tuple(sorted(columns)),
        )


def execute_validated_sql(
    connection: sqlite3.Connection, validated: ValidatedSql, policy: SqlPolicy
) -> SqlExecutionResult:
    """Execute behind row, time, and database-level read-only boundaries."""
    deadline = monotonic() + policy.timeout_ms / 1000

    def should_abort() -> int:
        return int(monotonic() >= deadline)

    wrapped = (
        f"SELECT * FROM ({validated.sql}) AS _queryweaver_result "
        f"LIMIT {policy.max_rows + 1}"
    )
    connection.execute("PRAGMA query_only = ON")
    connection.set_progress_handler(should_abort, 1_000)
    started = monotonic()
    try:
        cursor = connection.execute(wrapped)
        fetched = cursor.fetchall()
    except sqlite3.OperationalError as error:
        if "interrupted" in str(error).casefold():
            raise SqlTimeoutError(f"query exceeded {policy.timeout_ms} ms") from error
        raise
    finally:
        connection.set_progress_handler(None, 0)
    elapsed_ms = (monotonic() - started) * 1000
    truncated = len(fetched) > policy.max_rows
    rows = tuple(tuple(row) for row in fetched[: policy.max_rows])
    columns = tuple(str(item[0]) for item in (cursor.description or ()))
    return SqlExecutionResult(columns, rows, elapsed_ms, truncated)
