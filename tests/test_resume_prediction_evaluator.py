from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.evaluate_resume_predictions import evaluate_resume_predictions


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class ResumePredictionEvaluatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ontology = self.root / "ontology"
        write_jsonl(self.ontology / "position_registry_v1.jsonl", [{"id": "pos_ai", "name": "AI工程师"}])
        write_jsonl(self.ontology / "position_aliases_v1.jsonl", [{"position_id": "pos_ai", "alias": "人工智能工程师", "review_status": "approved"}])
        write_jsonl(self.ontology / "skill_registry_v1.jsonl", [{"id": "skill_python", "name": "Python"}, {"id": "skill_rag", "name": "RAG"}])
        write_jsonl(self.ontology / "skill_aliases_v1.jsonl", [{"skill_id": "skill_rag", "alias": "检索增强生成", "review_status": "approved"}])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_perfect_alias_normalized_prediction(self) -> None:
        gt = self.root / "gt.jsonl"
        predictions = self.root / "predictions.jsonl"
        write_jsonl(gt, [{"resumeId": "R-1", "result": {"candidateName": "张三", "education": "硕士", "experienceYears": 3, "targetPosition": {"id": "pos_ai"}, "skills": [{"id": "skill_python"}, {"id": "skill_rag"}]}, "annotationMeta": {"reviewStatus": "approved"}}])
        write_jsonl(predictions, [{"resumeId": "R-1", "candidateName": "张 三", "education": "计算机硕士研究生", "experienceYears": 3.5, "targetPosition": "人工智能工程师", "skills": [{"name": "Python"}, {"name": "检索增强生成"}]}])
        report = evaluate_resume_predictions(gt, predictions, self.ontology, allow_draft=True)
        self.assertEqual(report["metrics"]["skillMicroF1"], 1.0)
        self.assertEqual(report["metrics"]["candidateNameAccuracy"], 1.0)
        self.assertEqual(report["metrics"]["targetPositionAccuracy"], 1.0)

    def test_unknown_skill_counts_as_false_positive(self) -> None:
        gt = self.root / "gt.jsonl"
        predictions = self.root / "predictions.jsonl"
        write_jsonl(gt, [{"resume_id": "R-1", "annotation": {"candidate_name": "张三", "education": "本科", "experience_years": 1, "target_position": {"id": "pos_ai"}, "skills": [{"id": "skill_python"}]}, "annotation_meta": {"review_status": "approved"}}])
        write_jsonl(predictions, [{"resume_id": "R-1", "candidateName": "张三", "education": "本科", "experienceYears": 1, "targetPosition": {"id": "pos_ai"}, "skills": [{"name": "Python"}, {"name": "未知技能"}]}])
        report = evaluate_resume_predictions(gt, predictions, self.ontology, allow_draft=True)
        self.assertEqual(report["counts"]["unknownPredictedSkillCount"], 1)
        self.assertEqual(report["metrics"]["skillMicroPrecision"], 0.5)

    def test_accepts_multimodal_api_envelope_and_reports_input_mode(self) -> None:
        gt = self.root / "gt.jsonl"
        predictions = self.root / "predictions.jsonl"
        profile = {
            "candidateName": "张三",
            "education": "硕士",
            "experienceYears": 3,
            "targetPosition": {"id": "pos_ai"},
            "skills": [{"id": "skill_python"}],
        }
        write_jsonl(
            gt,
            [{"resumeId": "R-1", "result": profile, "annotationMeta": {"reviewStatus": "approved"}}],
        )
        write_jsonl(
            predictions,
            [{
                "resumeId": "R-1",
                "data": {"result": {**profile, "analysisSource": "llm", "llmAnalysis": {"status": "completed", "inputMode": "vision"}}},
            }],
        )

        report = evaluate_resume_predictions(gt, predictions, self.ontology, allow_draft=True)

        self.assertEqual(report["metrics"]["skillMicroF1"], 1.0)
        self.assertEqual(report["metrics"]["llmCompletionRate"], 1.0)
        self.assertEqual(report["metrics"]["visionParseSuccessRate"], 1.0)
        self.assertEqual(report["counts"]["visionSamples"], 1)

    def test_formal_mode_rejects_small_or_unreviewed_ground_truth(self) -> None:
        gt = self.root / "gt.jsonl"
        predictions = self.root / "predictions.jsonl"
        write_jsonl(gt, [{"resume_id": "R-1", "annotation": {"skills": []}, "annotation_meta": {"review_status": "pending"}}])
        write_jsonl(predictions, [{"resume_id": "R-1", "skills": []}])
        with self.assertRaisesRegex(ValueError, "at least 30"):
            evaluate_resume_predictions(gt, predictions, self.ontology)


if __name__ == "__main__":
    unittest.main()
