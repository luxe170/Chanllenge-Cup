import unittest

from fastapi.testclient import TestClient

from backend.app.main import app
from src.processing.build_graph_seed import build_graph_seed, merge_graph_data
from src.processing.build_review_candidates import build_review_candidates


class DataLlmBoundaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_data_source_status_declares_no_online_llm_dependency(self) -> None:
        response = self.client.get("/api/v1/data-sources/status")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertFalse(data["llmRuntimeRequired"])
        self.assertIn("configured", data["llmConfig"])
        self.assertNotIn("apiKey", data["llmConfig"])
        self.assertNotIn("secret", str(data["llmConfig"]).lower())
        self.assertIn("rule_outputs", data["readPriority"])

    def test_llm_config_status_does_not_return_secret(self) -> None:
        response = self.client.get("/api/v1/llm/config/status")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("configured", data)
        self.assertIn("model", data)
        self.assertNotIn("key", data)

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

    def test_graph_batch_merges_by_identity_without_duplicate_position(self) -> None:
        existing_nodes = [
            {"mode": "panorama", "id": "demo_pos_java", "name": "Java 后端工程师", "type": "position", "sampleCount": 50},
            {"mode": "panorama", "id": "demo_skill_java", "name": "Java", "type": "skill"},
        ]
        existing_edges = [
            {"mode": "panorama", "source": "demo_pos_java", "target": "demo_skill_java", "relationship": "REQUIRES"}
        ]
        incoming_nodes = [
            {"mode": "panorama", "id": "pos_java_engineer", "name": "Java 开发工程师", "type": "position", "sampleCount": 8},
            {"mode": "panorama", "id": "skill_cloud", "name": "云原生", "type": "skill"},
        ]
        incoming_edges = [
            {"mode": "panorama", "source": "pos_java_engineer", "target": "skill_cloud", "relationship": "REQUIRES"}
        ]

        nodes, edges = merge_graph_data(existing_nodes, existing_edges, incoming_nodes, incoming_edges)

        self.assertEqual(sum(node["type"] == "position" for node in nodes), 1)
        self.assertTrue(any(edge["source"] == "demo_pos_java" and edge["target"] == "skill_cloud" for edge in edges))


if __name__ == "__main__":
    unittest.main()
