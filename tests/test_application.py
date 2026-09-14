import unittest

from queryweaver.demo import create_demo_application
from queryweaver.models import Route


class QueryWeaverApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = create_demo_application()

    def test_document_question_returns_traceable_evidence(self) -> None:
        response = self.application.ask("数字订阅可以在多少天内退款？", top_k=2)

        self.assertEqual(response.route, Route.DOCUMENTS)
        self.assertTrue(response.evidence)
        self.assertEqual(response.evidence[0].document_id, "refund-policy")
        self.assertIn(response.evidence[0].chunk_id, response.answer)
        self.assertIsNone(response.sql_result)

    def test_analytical_question_returns_guarded_sql_result(self) -> None:
        response = self.application.ask("按地区统计销售额")

        self.assertEqual(response.route, Route.SQL)
        self.assertEqual(response.sql_result.columns, ("region", "revenue"))
        self.assertEqual(response.sql_result.rows[0], ("华东", 20000.0))
        self.assertIn("SELECT", response.validated_sql or "")
        self.assertFalse(response.evidence)

    def test_empty_question_is_rejected_at_application_boundary(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            self.application.ask("   ")


if __name__ == "__main__":
    unittest.main()
