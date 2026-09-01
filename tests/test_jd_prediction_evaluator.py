from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.evaluate_jd_predictions import evaluate


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items), encoding="utf-8")


class JdPredictionEvaluatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ontology = self.root / "ontology"
        write_jsonl(self.ontology / "position_registry_v1.jsonl", [
            {"id": "pos_llm", "name": "大模型算法工程师", "normalized_name": "大模型算法工程师"},
            {"id": "pos_java", "name": "Java开发工程师", "normalized_name": "java开发工程师"},
        ])
        write_jsonl(self.ontology / "position_aliases_v1.jsonl", [
            {"position_id": "pos_llm", "alias": "LLM算法工程师", "review_status": "approved"},
        ])
        write_jsonl(self.ontology / "skill_registry_v1.jsonl", [
            {"id": "skill_llm", "name": "大语言模型", "normalized_name": "大语言模型", "parent_skill_id": None},
            {"id": "skill_rag", "name": "RAG", "normalized_name": "rag", "parent_skill_id": "skill_llm"},
            {"id": "skill_java", "name": "Java", "normalized_name": "java", "parent_skill_id": None},
        ])
        write_jsonl(self.ontology / "skill_aliases_v1.jsonl", [
            {"skill_id": "skill_llm", "alias": "LLM", "review_status": "approved"},
            {"skill_id": "skill_rag", "alias": "检索增强生成", "review_status": "approved"},
        ])

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def gt(identifier: str, position_id: str, skills: list[tuple[str, str]]) -> dict:
        return {
            "evaluation_id": identifier,
            "raw": {"title": "测试岗位"},
            "annotation": {
                "scope": "in_scope", "position_id": position_id,
                "skills": [{"skill_id": skill_id, "requirement_type": kind} for skill_id, kind in skills],
            },
            "annotation_meta": {"review_status": "approved"},
        }

    def test_resolves_approved_aliases_and_scores_perfect_prediction(self) -> None:
        ground_truth = self.root / "gt.jsonl"
        predictions = self.root / "pred.jsonl"
        write_jsonl(ground_truth, [self.gt("JD-1", "pos_llm", [("skill_llm", "required"), ("skill_rag", "preferred")])])
        write_jsonl(predictions, [{
            "evaluation_id": "JD-1", "position": {"name": "LLM算法工程师"}, "scope": "in_scope",
            "skills": [
                {"name": "LLM", "requirement_type": "required"},
                {"name": "检索增强生成", "requirement_type": "preferred"},
            ],
        }])
        report = evaluate(ground_truth, predictions, self.ontology, allow_draft=True)
        self.assertEqual(report["metrics"]["positionAccuracy"], 1.0)
        self.assertEqual(report["metrics"]["skillMicroF1"], 1.0)
        self.assertEqual(report["metrics"]["requirementTypeAccuracy"], 1.0)
        self.assertTrue(report["pass"]["allRequiredMetrics"])

    def test_counts_unknown_extra_missing_and_requirement_errors(self) -> None:
        ground_truth = self.root / "gt.jsonl"
        predictions = self.root / "pred.jsonl"
        write_jsonl(ground_truth, [self.gt("JD-1", "pos_llm", [("skill_llm", "required"), ("skill_rag", "preferred")])])
        write_jsonl(predictions, [{
            "evaluation_id": "JD-1", "position": {"id": "pos_java"},
            "skills": [
                {"id": "skill_llm", "requirement_type": "preferred"},
                {"name": "不存在的技能", "requirement_type": "required"},
            ],
        }])
        report = evaluate(ground_truth, predictions, self.ontology, allow_draft=True)
        self.assertEqual(report["counts"]["positionCorrect"], 0)
        self.assertEqual(report["counts"]["skillTruePositive"], 1)
        self.assertEqual(report["counts"]["skillFalsePositive"], 1)
        self.assertEqual(report["counts"]["skillFalseNegative"], 1)
        self.assertEqual(report["counts"]["unknownSkillCount"], 1)
        self.assertEqual(report["metrics"]["requirementTypeAccuracy"], 0.0)
        self.assertFalse(report["pass"]["allRequiredMetrics"])

    def test_formal_mode_rejects_pending_ground_truth(self) -> None:
        ground_truth = self.root / "gt.jsonl"
        predictions = self.root / "pred.jsonl"
        item = self.gt("JD-1", "pos_llm", [])
        item["annotation_meta"]["review_status"] = "pending"
        write_jsonl(ground_truth, [item] * 100)
        write_jsonl(predictions, [])
        with self.assertRaisesRegex(ValueError, "not independently reviewed"):
            evaluate(ground_truth, predictions, self.ontology)

    def test_rejects_prediction_coverage_mismatch(self) -> None:
        ground_truth = self.root / "gt.jsonl"
        predictions = self.root / "pred.jsonl"
        write_jsonl(ground_truth, [self.gt("JD-1", "pos_llm", [])])
        write_jsonl(predictions, [])
        with self.assertRaisesRegex(ValueError, "coverage mismatch"):
            evaluate(ground_truth, predictions, self.ontology, allow_draft=True)


if __name__ == "__main__":
    unittest.main()
