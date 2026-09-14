import unittest

from fastapi.testclient import TestClient

from queryweaver.api import create_api
from queryweaver.demo import create_demo_application


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_api(create_demo_application()))

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "mode": "demo"})

    def test_browser_shell_is_served_by_the_same_application(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("QueryWeaver", response.text)
        self.assertIn("/app.js", response.text)

    def test_document_query_contract(self) -> None:
        response = self.client.post(
            "/v1/query", json={"question": "生产环境权限怎样申请？", "top_k": 2}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["route"], "documents")
        self.assertEqual(body["evidence"][0]["document_id"], "access-policy")
        self.assertIsNone(body["sql_result"])

    def test_sql_query_contract(self) -> None:
        response = self.client.post("/v1/query", json={"question": "各地区销售额"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["route"], "sql")
        self.assertEqual(body["sql_result"]["columns"], ["region", "revenue"])
        self.assertTrue(body["validated_sql"].startswith("SELECT"))

    def test_request_validation_rejects_empty_question(self) -> None:
        response = self.client.post("/v1/query", json={"question": ""})

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
