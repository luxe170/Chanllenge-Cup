#!/usr/bin/env python3
"""Evaluate production LLM JD extraction results against result-shaped GT."""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.evaluation.evaluate_jd_predictions import FINAL_REVIEW_STATUSES, file_sha256, harmonic_mean, read_jsonl, safe_ratio


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GT = PROJECT_ROOT / "data/processed/evaluation/jd_result_ground_truth_100_v2.jsonl"
DEFAULT_PREDICTIONS = PROJECT_ROOT / "output/evaluation/jd_predictions_100_v2.jsonl"
DEFAULT_TEST_SET = PROJECT_ROOT / "data/processed/splits/jd_test_set_100.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "output/evaluation/jd_evaluation_report_100_v2.json"
VALID_SCOPES = {"in_scope", "review", "out_of_scope"}
VALID_REQUIREMENT_TYPES = {"required", "preferred"}


def _text(value: Any) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"\s+|[^0-9a-z\u4e00-\u9fff]+", "", value)


def _id(item: dict[str, Any]) -> str:
    return str(item.get("sourceId") or item.get("source_id") or item.get("evaluation_id") or "")


def _result(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("result") if "result" in item else item


def _position_id(result: dict[str, Any]) -> str:
    position = result.get("position") or {}
    return str(position.get("id") or result.get("positionId") or result.get("predictedPositionId") or "")


def _position_registry(ground_truth: list[dict[str, Any]]) -> dict[str, str]:
    """Freeze the evaluation label space from GT labels, never from JD text."""
    registry: dict[str, str] = {}
    for item in ground_truth:
        result = _result(item)
        position = result.get("position") or {}
        position_id = _position_id(result)
        if position_id:
            registry[position_id] = str(position.get("name") or result.get("positionName") or position_id)
    return registry


def _normalize_position_id(position_id: str, registry: dict[str, str]) -> str:
    if position_id in registry:
        return position_id
    if position_id.startswith("candidate_") and "candidate_other" in registry:
        return "candidate_other"
    return position_id


def _skills(result: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for skill in result.get("skills") or []:
        if not isinstance(skill, dict):
            continue
        skill_id = str(skill.get("id") or "")
        if not skill_id:
            continue
        requirement_type = str(skill.get("requirementType") or skill.get("type") or "")
        values[skill_id] = requirement_type
    return values


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision, recall = safe_ratio(tp, tp + fp), safe_ratio(tp, tp + fn)
    return precision, recall, harmonic_mean(precision, recall)


def _macro_f1(expected: list[str], predicted: list[str], labels: set[str]) -> float:
    scores = []
    active_labels = labels & (set(expected) | set(predicted))
    for label in sorted(active_labels):
        tp = sum(a == label and b == label for a, b in zip(expected, predicted))
        fp = sum(a != label and b == label for a, b in zip(expected, predicted))
        fn = sum(a == label and b != label for a, b in zip(expected, predicted))
        scores.append(_prf(tp, fp, fn)[2])
    return safe_ratio(sum(scores), len(scores))


def _bigrams(value: str) -> set[str]:
    return {value[index:index + 2] for index in range(max(0, len(value) - 1))} or ({value} if value else set())


def _similarity(left: str, right: str) -> float:
    left, right = _text(left), _text(right)
    if not left or not right:
        return 0.0
    if left in right or right in left:
        return 1.0
    a, b = _bigrams(left), _bigrams(right)
    return safe_ratio(2 * len(a & b), len(a) + len(b))


def _list_prf(expected: list[Any], predicted: list[Any], threshold: float) -> tuple[int, int, int]:
    expected_text = [str(item.get("name") if isinstance(item, dict) else item) for item in expected]
    predicted_text = [str(item.get("name") if isinstance(item, dict) else item) for item in predicted]
    unmatched = set(range(len(predicted_text)))
    tp = 0
    for expected_item in expected_text:
        candidates = [(index, _similarity(expected_item, predicted_text[index])) for index in unmatched]
        if not candidates:
            continue
        index, score = max(candidates, key=lambda value: value[1])
        if score >= threshold:
            tp += 1
            unmatched.remove(index)
    return tp, len(unmatched), len(expected_text) - tp


def _evidence_items(result: dict[str, Any]) -> list[str]:
    items = [str((result.get("position") or {}).get("evidenceText") or "")]
    items.extend(str(skill.get("evidenceText") or "") for skill in result.get("skills") or [] if isinstance(skill, dict))
    items.extend(str(skill.get("evidenceText") or "") for skill in result.get("newSkillCandidates") or [] if isinstance(skill, dict))
    return items


def _new_skill_names(result: dict[str, Any]) -> set[str]:
    return {_text(item.get("name")) for item in result.get("newSkillCandidates") or [] if isinstance(item, dict) and _text(item.get("name"))}


def evaluate_llm_jd_predictions(
    ground_truth_path: Path,
    predictions_path: Path,
    test_set_path: Path,
    *,
    candidate_judgments_path: Path | None = None,
    allow_draft: bool = False,
    semantic_threshold: float = 0.80,
    core_threshold: float = 0.90,
    evidence_threshold: float = 0.95,
) -> dict[str, Any]:
    ground_truth, predictions, test_records = read_jsonl(ground_truth_path), read_jsonl(predictions_path), read_jsonl(test_set_path)
    if len(ground_truth) < 100 and not allow_draft:
        raise ValueError(f"formal LLM JD evaluation requires at least 100 records, got {len(ground_truth)}")
    gt_ids, prediction_ids = [_id(item) for item in ground_truth], [_id(item) for item in predictions]
    if any(not value for value in gt_ids + prediction_ids):
        raise ValueError("sourceId is required")
    if len(set(gt_ids)) != len(gt_ids) or len(set(prediction_ids)) != len(prediction_ids):
        raise ValueError("duplicate sourceId")
    if set(gt_ids) != set(prediction_ids):
        raise ValueError("prediction coverage mismatch")
    record_map = {_id(item): item for item in test_records}
    if set(gt_ids) != set(record_map):
        raise ValueError("test-set coverage mismatch")
    for item in ground_truth:
        status = str((item.get("annotationMeta") or {}).get("reviewStatus") or "")
        if status not in FINAL_REVIEW_STATUSES and not allow_draft:
            raise ValueError(f"{_id(item)}: ground truth is not adjudicated")

    prediction_map = {_id(item): item for item in predictions}
    candidate_judgments: dict[str, dict[str, Any]] = {}
    if candidate_judgments_path is not None:
        judgment_rows = read_jsonl(candidate_judgments_path)
        judgment_ids = [_id(item) for item in judgment_rows]
        if any(not value for value in judgment_ids) or len(judgment_ids) != len(set(judgment_ids)):
            raise ValueError("candidate judgments require unique sourceId values")
        candidate_judgments = dict(zip(judgment_ids, judgment_rows))
        expected_candidate_ids = {
            _id(item) for item in ground_truth
            if _position_id(_result(item)) == "candidate_other"
        }
        if set(candidate_judgments) != expected_candidate_ids:
            raise ValueError("candidate judgment coverage mismatch")
        for source_id, judgment in candidate_judgments.items():
            current_name = str((_result(prediction_map[source_id]).get("position") or {}).get("name") or "")
            if _text(judgment.get("predictedPositionName")) != _text(current_name):
                raise ValueError(f"{source_id}: candidate judgment does not match current prediction")
            if not isinstance(judgment.get("correct"), bool):
                raise ValueError(f"{source_id}: candidate judgment correct must be boolean")
    position_registry = _position_registry(ground_truth)
    counts = defaultdict(int)
    scope_expected: list[str] = []
    scope_predicted: list[str] = []
    requirement_expected: list[str] = []
    requirement_predicted: list[str] = []
    responsibility_totals = [0, 0, 0]
    scenario_totals = [0, 0, 0]
    new_position_expected: list[bool] = []
    new_position_predicted: list[bool] = []
    similar_hit1 = similar_hit3 = 0
    similar_reciprocal_rank = 0.0
    similar_cases = 0
    confidence_squared_error = 0.0
    errors: list[dict[str, Any]] = []

    for gt_item in ground_truth:
        source_id = _id(gt_item)
        expected, predicted = _result(gt_item), _result(prediction_map[source_id])
        expected_scope, predicted_scope = str(expected.get("scope") or ""), str(predicted.get("scope") or "")
        scope_expected.append(expected_scope)
        scope_predicted.append(predicted_scope)
        if predicted_scope not in VALID_SCOPES:
            counts["invalidScopeCount"] += 1

        expected_position = _normalize_position_id(_position_id(expected), position_registry)
        raw_predicted_position = _position_id(predicted)
        predicted_position = (
            "candidate_other"
            if bool(predicted.get("isNewPositionCandidate")) and "candidate_other" in position_registry
            else _normalize_position_id(raw_predicted_position, position_registry)
        )
        position_ok = expected_scope == "out_of_scope" or expected_position == predicted_position
        if expected_position == "candidate_other" and candidate_judgments:
            position_ok = bool(candidate_judgments[source_id]["correct"])
            counts["candidatePositionLlmJudged"] += 1
        if expected_scope != "out_of_scope":
            counts["positionEvaluated"] += 1
            counts["positionCorrect"] += int(position_ok)
            counts["positionStrictIdCorrect"] += int(expected_position == raw_predicted_position)
            if expected_position == "candidate_other":
                counts["candidatePositionEvaluated"] += 1
                counts["candidatePositionCorrect"] += int(position_ok)
            else:
                counts["registryPositionEvaluated"] += 1
                counts["registryPositionCorrect"] += int(position_ok)

        expected_skills, predicted_skills = _skills(expected), _skills(predicted)
        if expected_scope == "out_of_scope":
            expected_skills, predicted_skills = {}, {}
        expected_ids, predicted_ids_set = set(expected_skills), set(predicted_skills)
        counts["skillTP"] += len(expected_ids & predicted_ids_set)
        counts["skillFP"] += len(predicted_ids_set - expected_ids)
        counts["skillFN"] += len(expected_ids - predicted_ids_set)
        for skill_id in sorted(expected_ids & predicted_ids_set):
            requirement_expected.append(expected_skills[skill_id])
            requirement_predicted.append(predicted_skills[skill_id])
            if predicted_skills[skill_id] not in VALID_REQUIREMENT_TYPES:
                counts["invalidRequirementTypeCount"] += 1

        raw_record = record_map[source_id]
        raw_text = _text("\n".join(str(raw_record.get(key) or "") for key in ("title", "description", "requirement")))
        evidence = _evidence_items(predicted)
        counts["evidenceTotal"] += len(evidence)
        supported = sum(bool(_text(item)) and _text(item) in raw_text for item in evidence)
        counts["evidenceSupported"] += supported

        for target, values in (
            (responsibility_totals, _list_prf(expected.get("responsibilities") or [], predicted.get("responsibilities") or [], semantic_threshold)),
            (scenario_totals, _list_prf(expected.get("scenarios") or [], predicted.get("scenarios") or [], semantic_threshold)),
        ):
            for index, value in enumerate(values):
                target[index] += value

        gt_new_skills, predicted_new_skills = _new_skill_names(expected), _new_skill_names(predicted)
        counts["newSkillTP"] += len(gt_new_skills & predicted_new_skills)
        counts["newSkillFP"] += len(predicted_new_skills - gt_new_skills)
        counts["newSkillFN"] += len(gt_new_skills - predicted_new_skills)
        expected_new_position, predicted_new_position = bool(expected.get("isNewPositionCandidate")), bool(predicted.get("isNewPositionCandidate"))
        new_position_expected.append(expected_new_position)
        new_position_predicted.append(predicted_new_position)

        expected_similar = {str(item.get("id") or "") for item in expected.get("similarPositions") or [] if isinstance(item, dict) and item.get("id")}
        predicted_similar = [str(item.get("id") or "") for item in predicted.get("similarPositions") or [] if isinstance(item, dict) and item.get("id")]
        if expected_similar:
            similar_cases += 1
            similar_hit1 += int(bool(predicted_similar[:1] and predicted_similar[0] in expected_similar))
            similar_hit3 += int(bool(set(predicted_similar[:3]) & expected_similar))
            rank = next((index + 1 for index, value in enumerate(predicted_similar) if value in expected_similar), 0)
            similar_reciprocal_rank += safe_ratio(1, rank) if rank else 0

        sample_correct = expected_scope == predicted_scope and position_ok and expected_ids == predicted_ids_set
        try:
            confidence = min(1.0, max(0.0, float(predicted.get("confidence") or 0)))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence_squared_error += (confidence - float(sample_correct)) ** 2
        if not sample_correct or supported != len(evidence):
            errors.append({
                "sourceId": source_id,
                "scopeExpected": expected_scope, "scopePredicted": predicted_scope,
                "positionExpected": expected_position, "positionPredicted": raw_predicted_position,
                "positionPredictedNormalized": predicted_position,
                "missingSkills": sorted(expected_ids - predicted_ids_set), "extraSkills": sorted(predicted_ids_set - expected_ids),
                "unsupportedEvidenceCount": len(evidence) - supported,
            })

    sample_count = len(ground_truth)
    scope_f1 = _macro_f1(scope_expected, scope_predicted, VALID_SCOPES)
    position_accuracy = safe_ratio(counts["positionCorrect"], counts["positionEvaluated"])
    position_strict_accuracy = safe_ratio(counts["positionStrictIdCorrect"], counts["positionEvaluated"])
    registry_position_accuracy = safe_ratio(counts["registryPositionCorrect"], counts["registryPositionEvaluated"])
    candidate_position_accuracy = safe_ratio(counts["candidatePositionCorrect"], counts["candidatePositionEvaluated"])
    skill_precision, skill_recall, skill_f1 = _prf(counts["skillTP"], counts["skillFP"], counts["skillFN"])
    requirement_f1 = _macro_f1(requirement_expected, requirement_predicted, VALID_REQUIREMENT_TYPES)
    requirement_accuracy = safe_ratio(sum(a == b for a, b in zip(requirement_expected, requirement_predicted)), len(requirement_expected))
    core_score = scope_f1 * .10 + position_accuracy * .35 + skill_f1 * .45 + requirement_f1 * .10
    evidence_support = safe_ratio(counts["evidenceSupported"], counts["evidenceTotal"])
    responsibility = _prf(*responsibility_totals)
    scenario = _prf(*scenario_totals)
    new_skill = _prf(counts["newSkillTP"], counts["newSkillFP"], counts["newSkillFN"])
    new_position_tp = sum(a and b for a, b in zip(new_position_expected, new_position_predicted))
    new_position_fp = sum(not a and b for a, b in zip(new_position_expected, new_position_predicted))
    new_position_fn = sum(a and not b for a, b in zip(new_position_expected, new_position_predicted))
    new_position = _prf(new_position_tp, new_position_fp, new_position_fn)
    metrics = {
        "scopeMacroF1": round(scope_f1, 4), "positionAccuracy": round(position_accuracy, 4),
        "positionStrictIdAccuracy": round(position_strict_accuracy, 4),
        "registryPositionAccuracy": round(registry_position_accuracy, 4),
        "candidatePositionAccuracy": round(candidate_position_accuracy, 4),
        "skillMicroPrecision": round(skill_precision, 4), "skillMicroRecall": round(skill_recall, 4), "skillMicroF1": round(skill_f1, 4),
        "requirementTypeMacroF1": round(requirement_f1, 4), "requirementTypeAccuracyOnMatchedSkills": round(requirement_accuracy, 4),
        "coreScore": round(core_score, 4), "evidenceSupportRate": round(evidence_support, 4), "unsupportedEvidenceRate": round(1 - evidence_support, 4),
        "responsibilityPrecision": round(responsibility[0], 4), "responsibilityRecall": round(responsibility[1], 4), "responsibilityF1": round(responsibility[2], 4),
        "scenarioPrecision": round(scenario[0], 4), "scenarioRecall": round(scenario[1], 4), "scenarioF1": round(scenario[2], 4),
        "newPositionPrecision": round(new_position[0], 4), "newPositionRecall": round(new_position[1], 4), "newPositionF1": round(new_position[2], 4),
        "newSkillPrecision": round(new_skill[0], 4), "newSkillRecall": round(new_skill[1], 4), "newSkillF1": round(new_skill[2], 4),
        "similarPositionHitAt1": round(safe_ratio(similar_hit1, similar_cases), 4), "similarPositionHitAt3": round(safe_ratio(similar_hit3, similar_cases), 4), "similarPositionMRR": round(safe_ratio(similar_reciprocal_rank, similar_cases), 4),
        "confidenceBrierScore": round(safe_ratio(confidence_squared_error, sample_count), 4), "predictionCoverage": 1.0,
    }
    return {
        "evaluationType": "llm_jd_extraction", "formal": not allow_draft, "sampleCount": sample_count,
        "semanticThreshold": semantic_threshold, "groundTruthSha256": file_sha256(ground_truth_path), "predictionsSha256": file_sha256(predictions_path), "testSetSha256": file_sha256(test_set_path),
        "candidateJudgmentsSha256": file_sha256(candidate_judgments_path) if candidate_judgments_path else None,
        "candidatePositionEvaluation": "llm_judge" if candidate_judgments else "candidate_flag",
        "metrics": metrics, "counts": dict(counts),
        "positionRegistry": [{"id": key, "name": value} for key, value in sorted(position_registry.items())],
        "weights": {"scopeMacroF1": .10, "positionAccuracy": .35, "skillMicroF1": .45, "requirementTypeMacroF1": .10},
        "pass": {"coreScore": core_score >= core_threshold, "positionAccuracy": position_accuracy >= core_threshold, "skillMicroF1": skill_f1 >= core_threshold, "evidenceSupportRate": evidence_support >= evidence_threshold, "overall": core_score >= core_threshold and position_accuracy >= core_threshold and skill_f1 >= core_threshold and evidence_support >= evidence_threshold},
        "errorCases": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate production LLM JD extraction predictions.")
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GT); parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--test-set", type=Path, default=DEFAULT_TEST_SET); parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidate-judgments", type=Path)
    parser.add_argument("--allow-draft", action="store_true"); parser.add_argument("--semantic-threshold", type=float, default=.80)
    parser.add_argument("--core-threshold", type=float, default=.90); parser.add_argument("--evidence-threshold", type=float, default=.95)
    args = parser.parse_args()
    report = evaluate_llm_jd_predictions(args.ground_truth, args.predictions, args.test_set, candidate_judgments_path=args.candidate_judgments, allow_draft=args.allow_draft, semantic_threshold=args.semantic_threshold, core_threshold=args.core_threshold, evidence_threshold=args.evidence_threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
