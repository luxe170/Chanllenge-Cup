from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.evaluate_match_predictions import evaluate


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class MatchPredictionEvaluatorTest(unittest.TestCase):
    def test_perfect_full_pool_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pool = [{"positionId": f"P{index}", "positionName": f"岗位{index}"} for index in range(10)]
            gt = [{"resumeId": "R1", "bestPositionId": "P0", "acceptablePositionIds": ["P0", "P1"], "level": "高", "matchedRequiredSkills": ["Python"], "missingRequiredSkills": ["Go"], "annotationMeta": {"reviewStatus": "approved"}}]
            rankings = [{"rank": index + 1, "positionId": row["positionId"], "level": "高" if index == 0 else "低", "matchedSkills": ["Python"] if index == 0 else [], "missingSkills": ["Go"] if index == 0 else []} for index, row in enumerate(pool)]
            write_jsonl(root / "pool.jsonl", pool); write_jsonl(root / "gt.jsonl", gt); write_jsonl(root / "pred.jsonl", [{"resumeId": "R1", "rankings": rankings}])
            report = evaluate(root / "gt.jsonl", root / "pred.jsonl", root / "pool.jsonl")
            self.assertEqual(report["metrics"]["top1Accuracy"], 1.0)
            self.assertEqual(report["metrics"]["missingSkillMicroF1"], 1.0)

    def test_rejects_incomplete_position_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pool = [{"positionId": f"P{index}"} for index in range(10)]
            gt = [{"resumeId": "R1", "bestPositionId": "P0", "acceptablePositionIds": ["P0"], "level": "高", "annotationMeta": {"reviewStatus": "approved"}}]
            write_jsonl(root / "pool.jsonl", pool); write_jsonl(root / "gt.jsonl", gt); write_jsonl(root / "pred.jsonl", [{"resumeId": "R1", "rankings": [{"positionId": "P0"}]}])
            with self.assertRaisesRegex(ValueError, "cover the frozen position pool"):
                evaluate(root / "gt.jsonl", root / "pred.jsonl", root / "pool.jsonl")


if __name__ == "__main__":
    unittest.main()
