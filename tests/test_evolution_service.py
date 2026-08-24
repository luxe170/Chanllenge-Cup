import unittest

from backend.app.services.evolution_service import compute_evolution_changes, compute_evidence_detail, compute_emerging_positions


class EvolutionServiceTest(unittest.TestCase):
    def test_returns_realistic_change_set_from_processed_jobs(self):
        payload = compute_evolution_changes(page=1, page_size=20)

        self.assertGreater(payload["total"], 10)
        self.assertGreater(len(payload["items"]), 0)
        self.assertTrue(all(item.evidenceCount > 0 for item in payload["items"]))

    def test_returns_evidence_detail_for_real_jd_record(self):
        payload = compute_evidence_detail("jd_0001")

        self.assertIn("evidenceId", payload)
        self.assertIn("company", payload)
        self.assertIn("positionTitle", payload)
        self.assertIn("jdText", payload)

    def test_returns_emerging_positions_without_datetime_type_error(self):
        payload = compute_emerging_positions(page=1, page_size=10)

        self.assertIn("items", payload)
        self.assertIn("total", payload)
        self.assertIn("page", payload)
        self.assertIn("pageSize", payload)


if __name__ == "__main__":
    unittest.main()
