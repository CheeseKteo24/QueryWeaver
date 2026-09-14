import sqlite3
import unittest

from queryweaver.text_to_sql import TextToSqlService


class RecordingGenerator:
    def __init__(self, sql: str) -> None:
        self.sql = sql
        self.schema_context = ""

    def generate(self, question: str, schema_context: str) -> str:
        self.schema_context = schema_context
        return self.sql


class TextToSqlServiceTests(unittest.TestCase):
    def test_generation_is_validated_and_executed_with_schema_context(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE sales(region TEXT, amount REAL)")
        connection.executemany(
            "INSERT INTO sales VALUES (?, ?)", [("east", 10.0), ("east", 15.0)]
        )
        generator = RecordingGenerator(
            "SELECT region, SUM(amount) AS revenue FROM sales GROUP BY region"
        )

        answer = TextToSqlService(connection, generator).execute("Revenue by region?")

        self.assertIn("TABLE sales", generator.schema_context)
        self.assertEqual(answer.validated.tables, ("sales",))
        self.assertEqual(answer.result.rows, (("east", 25.0),))


if __name__ == "__main__":
    unittest.main()
