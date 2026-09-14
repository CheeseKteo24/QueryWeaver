import sqlite3
import unittest

from queryweaver.schema import SchemaCatalog
from queryweaver.sql_policy import (
    SqlPolicy,
    SqlPolicyError,
    SqlPolicyValidator,
    execute_validated_sql,
)


class SqlPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute(
            "CREATE TABLE sales(id INTEGER PRIMARY KEY, region TEXT, amount REAL)"
        )
        self.connection.executemany(
            "INSERT INTO sales(region, amount) VALUES (?, ?)",
            [("east", 10.0), ("west", 20.0), ("north", 30.0)],
        )
        self.connection.execute("CREATE TABLE secrets(token TEXT)")
        self.catalog = SchemaCatalog.from_sqlite(
            self.connection, include_tables=frozenset({"sales"})
        )
        self.policy = SqlPolicy(max_rows=2, timeout_ms=500)
        self.validator = SqlPolicyValidator(self.catalog, self.policy)

    def test_allows_aggregate_alias_and_cte(self) -> None:
        statement = (
            "WITH totals AS (SELECT region, SUM(amount) AS total FROM sales GROUP BY region) "
            "SELECT region, total FROM totals ORDER BY total DESC"
        )
        validated = self.validator.validate(statement)
        self.assertEqual(validated.tables, ("sales",))
        self.assertIn("amount", validated.columns)

    def test_blocks_non_query_multiple_statements_and_comments(self) -> None:
        unsafe = [
            "DELETE FROM sales",
            "SELECT amount FROM sales; DROP TABLE sales",
            "/* harmless looking */ UPDATE sales SET amount = 0",
        ]
        for statement in unsafe:
            with self.subTest(statement=statement), self.assertRaises(SqlPolicyError):
                self.validator.validate(statement)

    def test_blocks_unknown_table_column_star_and_function(self) -> None:
        unsafe = [
            "SELECT token FROM secrets",
            "SELECT password FROM sales",
            "SELECT * FROM sales",
            "SELECT load_extension('malicious')",
        ]
        for statement in unsafe:
            with self.subTest(statement=statement), self.assertRaises(SqlPolicyError):
                self.validator.validate(statement)

    def test_count_star_is_allowed(self) -> None:
        validated = self.validator.validate("SELECT COUNT(*) AS records FROM sales")
        result = execute_validated_sql(self.connection, validated, self.policy)
        self.assertEqual(result.rows, ((3,),))

    def test_execution_enforces_row_limit_and_reports_truncation(self) -> None:
        validated = self.validator.validate("SELECT id, amount FROM sales ORDER BY id")
        result = execute_validated_sql(self.connection, validated, self.policy)
        self.assertEqual(result.columns, ("id", "amount"))
        self.assertEqual(len(result.rows), 2)
        self.assertTrue(result.truncated)
        self.assertGreaterEqual(result.elapsed_ms, 0)


if __name__ == "__main__":
    unittest.main()
