from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from queryweaver.schema import SchemaCatalog  # noqa: E402
from queryweaver.sql_policy import (  # noqa: E402
    SqlPolicy,
    SqlPolicyError,
    SqlPolicyValidator,
    execute_validated_sql,
)


def build_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT)")
    connection.execute(
        "CREATE TABLE sales(id INTEGER PRIMARY KEY, customer_id INTEGER, region TEXT, amount REAL)"
    )
    connection.execute("CREATE TABLE secrets(token TEXT)")
    connection.executemany("INSERT INTO customers VALUES (?, ?)", [(1, "Ada"), (2, "Lin")])
    connection.executemany(
        "INSERT INTO sales VALUES (?, ?, ?, ?)",
        [(1, 1, "east", 10.0), (2, 1, "east", 20.0), (3, 2, "west", 30.0)],
    )
    connection.execute("INSERT INTO secrets VALUES ('never-visible')")
    return connection


def main() -> int:
    payload = json.loads(
        (ROOT / "benchmarks" / "sql_policy_cases.json").read_text(encoding="utf-8")
    )
    connection = build_database()
    catalog = SchemaCatalog.from_sqlite(
        connection, include_tables=frozenset({"customers", "sales"})
    )
    policy = SqlPolicy(max_rows=50, timeout_ms=500)
    validator = SqlPolicyValidator(catalog, policy)
    correct = 0

    print(f"{'case':<36} {'expected':<9} {'actual':<9}")
    for case in payload["cases"]:
        try:
            validated = validator.validate(case["sql"])
            execute_validated_sql(connection, validated, policy)
            actual = "allow"
        except (SqlPolicyError, sqlite3.DatabaseError):
            actual = "block"
        correct += actual == case["expected"]
        print(f"{case['name']:<36} {case['expected']:<9} {actual:<9}")

    total = len(payload["cases"])
    accuracy = correct / total
    print(f"policy accuracy: {correct}/{total} ({accuracy:.3f})")
    return 0 if correct == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
