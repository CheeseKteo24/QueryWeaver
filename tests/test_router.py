import unittest

from queryweaver.models import Route
from queryweaver.router import route_question


class RouterTests(unittest.TestCase):
    def test_routes_aggregate_to_sql(self) -> None:
        self.assertEqual(route_question("What was the average sales revenue?"), Route.SQL)

    def test_routes_policy_question_to_documents(self) -> None:
        self.assertEqual(route_question("What is our refund policy?"), Route.DOCUMENTS)


if __name__ == "__main__":
    unittest.main()
