from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence

READ_ONLY_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum|replace)\b",
    re.IGNORECASE,
)


class UnsafeQueryError(ValueError):
    pass


def validate_read_only_sql(statement: str) -> str:
    candidate = statement.strip().rstrip(";")
    if not READ_ONLY_START.match(candidate) or FORBIDDEN.search(candidate):
        raise UnsafeQueryError("Only a single read-only SELECT/CTE statement is allowed")
    if ";" in candidate:
        raise UnsafeQueryError("Multiple SQL statements are not allowed")
    return candidate


def execute_read_only(
    connection: sqlite3.Connection, statement: str, parameters: Sequence[object] = ()
) -> list[tuple[object, ...]]:
    safe_statement = validate_read_only_sql(statement)
    connection.execute("PRAGMA query_only = ON")
    return connection.execute(safe_statement, parameters).fetchall()
