import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class FrontendClosureRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_dashboard_and_evaluation_summary_routes(self) -> None:
        for path in ["/api/v1/dashboard", "/api/v1/dashboard/summary", "/api/v1/evaluations/summary"]:
            response = self.client.get(path)

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("data", payload)
            self.assertIn("requestId", payload)

        evaluation = self.client.get("/api/v1/evaluations/summary").json()["data"]
        self.assertIn("metrics", evaluation)
        self.assertIn("pendingReviewCount", evaluation)
        self.assertIn("highPriorityReviewCount", evaluation)
        self.assertIn("testedAt", evaluation)

    def test_graph_routes_return_valid_edges(self) -> None:
        for mode in ["panorama", "skill_reverse"]:
            response = self.client.get(f"/api/v1/graph?mode={mode}")

            self.assertEqual(response.status_code, 200)
            graph = response.json()["data"]
            node_ids = {node["id"] for node in graph["nodes"]}
            self.assertGreater(len(node_ids), 0)
            self.assertTrue(all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"]))

    def test_graph_roots_detail_and_search_routes(self) -> None:
        roots_response = self.client.get("/api/v1/graph/roots?mode=panorama")
        self.assertEqual(roots_response.status_code, 200)
        roots = roots_response.json()["data"]
        self.assertGreater(len(roots), 0)

        detail_response = self.client.get(f"/api/v1/graph/nodes/{roots[0]['id']}")
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()["data"]
        self.assertEqual(detail["id"], roots[0]["id"])
        self.assertIn("directNodes", detail)

        search_response = self.client.get("/api/v1/graph/search?keyword=RAG&mode=panorama")
        self.assertEqual(search_response.status_code, 200)
        self.assertGreater(len(search_response.json()["data"]), 0)


if __name__ == "__main__":
    unittest.main()
