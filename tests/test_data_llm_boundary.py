import unittest

from fastapi.testclient import TestClient

from backend.app.main import app
from src.processing.build_graph_seed import build_graph_seed
from src.processing.build_review_candidates import build_review_candidates


class DataLlmBoundaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_data_source_status_declares_no_online_llm_dependency(self) -> None:
        response = self.client.get("/api/v1/data-sources/status")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertFalse(data["llmRuntimeRequired"])
        self.assertFalse(data["onlineLlmEnabled"])
        self.assertIn("rule_outputs", data["readPriority"])

    def test_rule_graph_seed_has_valid_edges(self) -> None:
        nodes, edges = build_graph_seed()

        node_ids = {node["id"] for node in nodes}
        self.assertGreater(len(node_ids), 0)
        self.assertTrue(all(edge["source"] in node_ids and edge["target"] in node_ids for edge in edges))
        self.assertTrue(any(node["mode"] == "panorama" for node in nodes))
        self.assertTrue(any(node["mode"] == "skill_reverse" for node in nodes))

    def test_rule_review_candidates_include_evolution_targets(self) -> None:
        items = build_review_candidates()

        self.assertGreater(len(items), 0)
        self.assertTrue(any(item["type"] == "能力变更" and item.get("targetId") for item in items))
        self.assertTrue(any(item["type"] == "新岗位" and item.get("targetId") for item in items))


if __name__ == "__main__":
    unittest.main()
