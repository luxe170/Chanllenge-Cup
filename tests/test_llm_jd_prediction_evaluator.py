from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.evaluate_llm_jd_predictions import evaluate_llm_jd_predictions


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class LlmJdPredictionEvaluatorTest(unittest.TestCase):
    def test_perfect_result_scores_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = {"sourceId": "J1", "scope": "in_scope", "position": {"id": "pos_ai", "evidenceText": "AI工程师"}, "skills": [{"id": "skill_python", "requirementType": "required", "evidenceText": "熟悉Python"}], "responsibilities": ["开发AI系统"], "scenarios": ["智能客服"], "newSkillCandidates": [], "isNewPositionCandidate": False, "similarPositions": [], "confidence": 1.0}
            gt = {"sourceId": "J1", "result": result, "annotationMeta": {"reviewStatus": "approved"}}
            record = {"source_id": "J1", "title": "AI工程师", "description": "开发AI系统，用于智能客服", "requirement": "熟悉Python"}
            write_jsonl(root / "gt.jsonl", [gt]); write_jsonl(root / "pred.jsonl", [result]); write_jsonl(root / "test.jsonl", [record])
            report = evaluate_llm_jd_predictions(root / "gt.jsonl", root / "pred.jsonl", root / "test.jsonl", allow_draft=True)
            self.assertEqual(report["metrics"]["coreScore"], 1.0)
            self.assertEqual(report["metrics"]["evidenceSupportRate"], 1.0)
            self.assertTrue(report["pass"]["overall"])

    def test_missing_skill_and_unsupported_evidence_are_penalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gt_result = {"sourceId": "J1", "scope": "in_scope", "position": {"id": "pos_ai", "evidenceText": "AI工程师"}, "skills": [{"id": "skill_python", "requirementType": "required", "evidenceText": "Python"}], "responsibilities": [], "scenarios": [], "newSkillCandidates": [], "isNewPositionCandidate": False, "similarPositions": []}
            prediction = {**gt_result, "skills": [], "position": {"id": "pos_wrong", "evidenceText": "并不存在的证据"}, "confidence": .9}
            write_jsonl(root / "gt.jsonl", [{"sourceId": "J1", "result": gt_result, "annotationMeta": {"reviewStatus": "approved"}}]); write_jsonl(root / "pred.jsonl", [prediction]); write_jsonl(root / "test.jsonl", [{"source_id": "J1", "title": "AI工程师", "description": "", "requirement": "Python"}])
            report = evaluate_llm_jd_predictions(root / "gt.jsonl", root / "pred.jsonl", root / "test.jsonl", allow_draft=True)
            self.assertEqual(report["metrics"]["positionAccuracy"], 0.0)
            self.assertEqual(report["metrics"]["skillMicroRecall"], 0.0)
            self.assertEqual(report["metrics"]["evidenceSupportRate"], 0.0)

    def test_dynamic_candidate_id_maps_to_gt_candidate_label(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gt_result = {"sourceId": "J1", "scope": "review", "position": {"id": "candidate_other", "name": "候选新岗位", "evidenceText": "推理优化工程师"}, "skills": [], "responsibilities": [], "scenarios": [], "newSkillCandidates": [], "isNewPositionCandidate": True, "similarPositions": [], "confidence": 1.0}
            prediction = {**gt_result, "position": {"id": "candidate_abc123", "name": "推理优化工程师", "evidenceText": "推理优化工程师"}}
            write_jsonl(root / "gt.jsonl", [{"sourceId": "J1", "result": gt_result, "annotationMeta": {"reviewStatus": "approved"}}])
            write_jsonl(root / "pred.jsonl", [prediction])
            write_jsonl(root / "test.jsonl", [{"source_id": "J1", "title": "推理优化工程师", "description": "", "requirement": ""}])

            report = evaluate_llm_jd_predictions(root / "gt.jsonl", root / "pred.jsonl", root / "test.jsonl", allow_draft=True)

            self.assertEqual(report["metrics"]["positionAccuracy"], 1.0)
            self.assertEqual(report["metrics"]["positionStrictIdAccuracy"], 0.0)
            self.assertEqual(report["metrics"]["candidatePositionAccuracy"], 1.0)
            self.assertEqual(report["positionRegistry"], [{"id": "candidate_other", "name": "候选新岗位"}])

    def test_candidate_position_can_be_scored_by_frozen_llm_judgment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gt_result = {"sourceId": "J1", "scope": "review", "position": {"id": "candidate_other", "name": "候选新岗位", "evidenceText": "投资实习生"}, "skills": [], "responsibilities": [], "scenarios": [], "newSkillCandidates": [], "isNewPositionCandidate": True, "similarPositions": [], "confidence": 1.0}
            prediction = {**gt_result, "isNewPositionCandidate": False, "position": {"id": "pos_finance", "name": "投资分析师", "evidenceText": "投资实习生"}}
            write_jsonl(root / "gt.jsonl", [{"sourceId": "J1", "result": gt_result, "annotationMeta": {"reviewStatus": "approved"}}])
            write_jsonl(root / "pred.jsonl", [prediction])
            write_jsonl(root / "test.jsonl", [{"source_id": "J1", "title": "投资实习生", "description": "负责投资分析", "requirement": ""}])
            write_jsonl(root / "judgments.jsonl", [{"sourceId": "J1", "predictedPositionName": "投资分析师", "correct": True, "confidence": .95, "reason": "核心职能一致"}])

            report = evaluate_llm_jd_predictions(root / "gt.jsonl", root / "pred.jsonl", root / "test.jsonl", candidate_judgments_path=root / "judgments.jsonl", allow_draft=True)

            self.assertEqual(report["metrics"]["positionAccuracy"], 1.0)
            self.assertEqual(report["counts"]["candidatePositionLlmJudged"], 1)
            self.assertEqual(report["candidatePositionEvaluation"], "llm_judge")

    def test_formal_mode_rejects_draft_gt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gt = [{"sourceId": f"J{i}", "result": {}, "annotationMeta": {"reviewStatus": "draft_pending_human_review"}} for i in range(100)]
            predictions = [{"sourceId": f"J{i}"} for i in range(100)]
            records = [{"source_id": f"J{i}"} for i in range(100)]
            write_jsonl(root / "gt.jsonl", gt); write_jsonl(root / "pred.jsonl", predictions); write_jsonl(root / "test.jsonl", records)
            with self.assertRaisesRegex(ValueError, "not adjudicated"):
                evaluate_llm_jd_predictions(root / "gt.jsonl", root / "pred.jsonl", root / "test.jsonl")


if __name__ == "__main__":
    unittest.main()
