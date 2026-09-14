import unittest

from queryweaver.models import Route
from queryweaver.router import route_question


class RouterTests(unittest.TestCase):
    def test_routes_aggregate_to_sql(self) -> None:
        self.assertEqual(route_question("What was the average sales revenue?"), Route.SQL)

    def test_routes_policy_question_to_documents(self) -> None:
        self.assertEqual(route_question("What is our refund policy?"), Route.DOCUMENTS)

    def test_document_domain_signal_wins_over_ambiguous_count_word(self) -> None:
        self.assertEqual(route_question("数字订阅可以在多少天内退款？"), Route.DOCUMENTS)


if __name__ == "__main__":
    unittest.main()
