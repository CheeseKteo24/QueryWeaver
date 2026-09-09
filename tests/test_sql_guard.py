import sqlite3
import unittest

from queryweaver.sql_guard import UnsafeQueryError, execute_read_only, validate_read_only_sql


class SqlGuardTests(unittest.TestCase):
    def test_allows_select(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE sales(amount INTEGER)")
        connection.executemany("INSERT INTO sales VALUES (?)", [(10,), (20,)])
        self.assertEqual(execute_read_only(connection, "SELECT SUM(amount) FROM sales"), [(30,)])

    def test_blocks_mutation_and_multiple_statements(self) -> None:
        for statement in ("DELETE FROM sales", "SELECT 1; DROP TABLE sales"):
            with self.subTest(statement=statement), self.assertRaises(UnsafeQueryError):
                validate_read_only_sql(statement)


if __name__ == "__main__":
    unittest.main()
