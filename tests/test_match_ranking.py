from __future__ import annotations

import unittest

from backend.app.services.match_service import rank_matches


class MatchRankingTest(unittest.TestCase):
    def test_ranks_all_graph_positions_and_marks_highest_score(self) -> None:
        result = rank_matches("demo_resume_task")

        self.assertGreater(len(result["items"]), 1)
        self.assertEqual(result["bestPositionId"], result["items"][0]["positionId"])
        self.assertEqual(result["bestPositionName"], result["items"][0]["positionName"])
        self.assertEqual(result["bestScore"], result["items"][0]["score"])
        self.assertEqual(
            [item["score"] for item in result["items"]],
            sorted((item["score"] for item in result["items"]), reverse=True),
        )


if __name__ == "__main__":
    unittest.main()
