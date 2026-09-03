from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.judge_candidate_positions import generate_judgments


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class FakeJudge:
    model = "fake-judge"

    def complete_json(self, system_prompt: str, user_payload: dict) -> dict:
        assert "核心职能" in system_prompt
        assert user_payload["predictedPosition"]["name"] == "投资分析师"
        return {"correct": True, "confidence": .9, "reason": "与投资分析职责一致"}


class CandidatePositionJudgeTest(unittest.TestCase):
    def test_only_candidate_gt_rows_are_judged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gt = [
                {"sourceId": "J1", "result": {"position": {"id": "candidate_other"}}},
                {"sourceId": "J2", "result": {"position": {"id": "pos_backend"}}},
            ]
            predictions = [
                {"sourceId": "J1", "position": {"id": "candidate_x", "name": "投资分析师"}},
                {"sourceId": "J2", "position": {"id": "pos_backend", "name": "后端开发工程师"}},
            ]
            records = [
                {"source_id": "J1", "title": "投资实习生", "description": "负责投资分析", "requirement": ""},
                {"source_id": "J2", "title": "后端开发", "description": "", "requirement": ""},
            ]
            write_jsonl(root / "gt.jsonl", gt)
            write_jsonl(root / "pred.jsonl", predictions)
            write_jsonl(root / "test.jsonl", records)

            rows = generate_judgments(root / "gt.jsonl", root / "pred.jsonl", root / "test.jsonl", root / "out.jsonl", resume=False, client=FakeJudge())

            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["correct"])
            self.assertEqual(rows[0]["sourceId"], "J1")


if __name__ == "__main__":
    unittest.main()
