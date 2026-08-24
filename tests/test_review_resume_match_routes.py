import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class ReviewResumeMatchRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_reviews_are_generated_from_evolution_and_can_be_decided(self) -> None:
        response = self.client.get("/api/v1/reviews?type=能力变更")

        self.assertEqual(response.status_code, 200)
        items = response.json()["data"]
        self.assertGreater(len(items), 0)
        self.assertIn("targetId", items[0])

        review_id = items[0]["id"]
        decision = self.client.post(
            f"/api/v1/reviews/{review_id}/decision",
            json={"status": "approved", "note": "通过"},
        )
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json()["data"]["status"], "approved")

        decided = self.client.get("/api/v1/reviews?status=approved").json()["data"]
        self.assertTrue(any(item["id"] == review_id and item["note"] == "通过" for item in decided))

    def test_resume_task_supports_skill_patch(self) -> None:
        created = self.client.post("/api/v1/resume-tasks")
        self.assertEqual(created.status_code, 200)
        task = created.json()["data"]
        self.assertEqual(task["progress"], 100)

        task_id = task["taskId"]
        patched = self.client.patch(
            f"/api/v1/resume-tasks/{task_id}/skills",
            json={"skills": [{"name": "Python", "level": "精通", "source": "人工修正", "confidence": 1.0}]},
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["data"]["skills"][0]["source"], "人工修正")

        fetched = self.client.get(f"/api/v1/resume-tasks/{task_id}").json()["data"]
        self.assertEqual(fetched["result"]["skills"][0]["source"], "人工修正")

    def test_match_report_and_learning_path_are_linked(self) -> None:
        created = self.client.post(
            "/api/v1/matches",
            json={"resumeTaskId": "demo_resume_task", "positionId": "pos_ai_agent_engineer"},
        )

        self.assertEqual(created.status_code, 200)
        report = created.json()["data"]
        self.assertIn("matchId", report)
        self.assertIn("overallScore", report)

        path = self.client.get(f"/api/v1/matches/{report['matchId']}/learning-path")
        self.assertEqual(path.status_code, 200)
        self.assertEqual(path.json()["data"]["matchId"], report["matchId"])
        self.assertGreater(len(path.json()["data"]["items"]), 0)


if __name__ == "__main__":
    unittest.main()
