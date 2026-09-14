import sqlite3
import unittest

from queryweaver.schema import SchemaCatalog


class SchemaCatalogTests(unittest.TestCase):
    def test_introspects_only_explicitly_included_tables(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE sales(id INTEGER PRIMARY KEY, amount REAL NOT NULL)")
        connection.execute("CREATE TABLE secrets(token TEXT)")

        catalog = SchemaCatalog.from_sqlite(connection, include_tables=frozenset({"sales"}))

        self.assertEqual(catalog.table_names, frozenset({"sales"}))
        self.assertEqual(catalog.columns_for("SALES"), frozenset({"id", "amount"}))
        self.assertIn(
            "TABLE sales (id INTEGER PRIMARY KEY, amount REAL)", catalog.as_prompt_context()
        )
        self.assertNotIn("secrets", catalog.as_prompt_context())


if __name__ == "__main__":
    unittest.main()
