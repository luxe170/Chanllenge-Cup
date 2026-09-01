#!/usr/bin/env python3
"""Evaluate parsed resume profiles against independently reviewed ground truth."""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from src.evaluation.evaluate_jd_predictions import (
    FINAL_REVIEW_STATUSES,
    Ontology,
    file_sha256,
    harmonic_mean,
    read_jsonl,
    safe_ratio,
)
from backend.app.services.resume_service import _build_skill_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GROUND_TRUTH = PROJECT_ROOT / "data" / "evaluation" / "resume" / "resume_gold_v1.jsonl"
DEFAULT_PREDICTIONS = PROJECT_ROOT / "output" / "evaluation" / "resume_predictions_v1.jsonl"
DEFAULT_ONTOLOGY = PROJECT_ROOT / "data" / "evaluation" / "ontology"
DEFAULT_REPORT = PROJECT_ROOT / "output" / "evaluation" / "resume_evaluation_report_v1.json"


def _id(item: dict[str, Any]) -> str:
    return str(item.get("resume_id") or item.get("resumeId") or "")


def _profile(item: dict[str, Any], ground_truth: bool = False) -> dict[str, Any]:
    if ground_truth:
        return item.get("result") or item.get("annotation") or {}
    if "prediction" in item:
        return item.get("prediction") or {}
    if "result" in item:
        return item.get("result") or {}
    return item


def _text(value: Any) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return re.sub(r"[\s·•,，。:：;；_\-/（）()]+", "", value)


def _education(value: Any) -> str:
    text = _text(value)
    for level, aliases in (
        ("博士", ("博士", "phd", "doctor")),
        ("硕士", ("硕士", "研究生", "master")),
        ("本科", ("本科", "学士", "bachelor")),
        ("大专", ("大专", "专科", "college")),
        ("高中", ("高中", "中专")),
    ):
        if any(alias in text for alias in aliases):
            return level
    return text


def _skills(profile: dict[str, Any], ontology: Ontology, production_ids: dict[str, str], production_names: dict[str, str], *, ground_truth: bool) -> tuple[set[str], list[str]]:
    resolved: set[str] = set()
    unknown: list[str] = []
    for skill in profile.get("skills") or []:
        raw_id = str(skill.get("id") or "") if isinstance(skill, dict) else ""
        raw_name = str(skill.get("name") or "") if isinstance(skill, dict) else str(skill)
        result = ontology.resolve_skill(skill)
        if result.entity_id:
            resolved.add(result.entity_id)
            continue
        if raw_id in production_ids:
            resolved.add(f"production:{raw_id}")
            continue
        production_id = production_names.get(_text(raw_name))
        if production_id:
            resolved.add(f"production:{production_id}")
            continue
        unknown.append(result.raw_value)
    if ground_truth and unknown:
        raise ValueError(f"ground truth contains unknown skills: {unknown}")
    return resolved, unknown


def _position(profile: dict[str, Any], ontology: Ontology) -> str:
    value = profile.get("target_position") or profile.get("targetPosition") or profile.get("position") or ""
    resolved = ontology.resolve_position(value)
    return resolved.entity_id or f"raw:{_text(resolved.raw_value)}"


def _experience_match(expected: dict[str, Any], predicted: dict[str, Any]) -> bool:
    expected_title = _text(expected.get("title"))
    predicted_title = _text(predicted.get("title"))
    if not expected_title or not predicted_title:
        return False
    title_ok = (
        expected_title in predicted_title
        or predicted_title in expected_title
        or SequenceMatcher(None, expected_title, predicted_title).ratio() >= 0.65
    )
    expected_period = _text(expected.get("period"))
    predicted_period = _text(predicted.get("period"))
    period_ok = not expected_period or not predicted_period or expected_period == predicted_period
    return title_ok and period_ok


def _experience_counts(expected: dict[str, Any], predicted: dict[str, Any]) -> tuple[int, int, int]:
    expected_items = [item for item in expected.get("experiences") or [] if isinstance(item, dict)]
    predicted_items = [item for item in predicted.get("experiences") or [] if isinstance(item, dict)]
    unmatched = set(range(len(predicted_items)))
    true_positive = 0
    for expected_item in expected_items:
        match = next((index for index in unmatched if _experience_match(expected_item, predicted_items[index])), None)
        if match is not None:
            true_positive += 1
            unmatched.remove(match)
    return true_positive, len(unmatched), len(expected_items) - true_positive


def evaluate_resume_predictions(
    ground_truth_path: Path,
    predictions_path: Path,
    ontology_dir: Path,
    ontology_version: str = "v1",
    *,
    allow_draft: bool = False,
    allow_pending_aliases: bool = False,
    threshold: float = 0.90,
) -> dict[str, Any]:
    ontology = Ontology(ontology_dir, ontology_version, allow_pending_aliases)
    production_catalog = _build_skill_catalog()
    production_ids = {skill.id: skill.name for skill in production_catalog}
    production_names = {_text(skill.name): skill.id for skill in production_catalog}
    ground_truth = read_jsonl(ground_truth_path)
    predictions = read_jsonl(predictions_path)
    if len(ground_truth) < 30 and not allow_draft:
        raise ValueError(f"formal resume evaluation requires at least 30 records, got {len(ground_truth)}")

    gt_ids = [_id(item) for item in ground_truth]
    prediction_ids = [_id(item) for item in predictions]
    if any(not item for item in gt_ids + prediction_ids):
        raise ValueError("resume_id is required")
    if len(set(gt_ids)) != len(gt_ids) or len(set(prediction_ids)) != len(prediction_ids):
        raise ValueError("duplicate resume_id")
    if set(gt_ids) != set(prediction_ids):
        raise ValueError("prediction coverage mismatch")

    for item in ground_truth:
        meta = item.get("annotationMeta") or item.get("annotation_meta") or {}
        status = str(meta.get("reviewStatus") or meta.get("review_status") or "")
        if status not in FINAL_REVIEW_STATUSES and not allow_draft:
            raise ValueError(f"{_id(item)}: ground truth is not independently reviewed")

    prediction_map = {_id(item): item for item in predictions}
    counts = {
        "skillTruePositive": 0, "skillFalsePositive": 0, "skillFalseNegative": 0,
        "nameCorrect": 0, "educationCorrect": 0, "experienceYearsCorrect": 0, "targetPositionCorrect": 0,
        "unknownPredictedSkillCount": 0,
        "experienceTruePositive": 0, "experienceFalsePositive": 0, "experienceFalseNegative": 0,
        "parseSuccess": 0,
    }
    errors: list[dict[str, Any]] = []

    for gt_item in ground_truth:
        identifier = _id(gt_item)
        expected = _profile(gt_item, True)
        predicted = _profile(prediction_map[identifier])
        counts["parseSuccess"] += int(bool(predicted))
        expected_skills, _ = _skills(expected, ontology, production_ids, production_names, ground_truth=True)
        predicted_skills, unknown = _skills(predicted, ontology, production_ids, production_names, ground_truth=False)
        common = expected_skills & predicted_skills
        missing = expected_skills - predicted_skills
        extra = predicted_skills - expected_skills
        counts["skillTruePositive"] += len(common)
        counts["skillFalsePositive"] += len(extra) + len(unknown)
        counts["skillFalseNegative"] += len(missing)
        counts["unknownPredictedSkillCount"] += len(unknown)
        experience_tp, experience_fp, experience_fn = _experience_counts(expected, predicted)
        counts["experienceTruePositive"] += experience_tp
        counts["experienceFalsePositive"] += experience_fp
        counts["experienceFalseNegative"] += experience_fn

        name_ok = _text(expected.get("candidate_name") or expected.get("candidateName")) == _text(predicted.get("candidate_name") or predicted.get("candidateName"))
        education_ok = _education(expected.get("education")) == _education(predicted.get("education"))
        expected_years = float(expected.get("experience_years") if expected.get("experience_years") is not None else expected.get("experienceYears") or 0)
        predicted_years = float(predicted.get("experience_years") if predicted.get("experience_years") is not None else predicted.get("experienceYears") or 0)
        years_ok = abs(expected_years - predicted_years) <= 0.5
        position_ok = _position(expected, ontology) == _position(predicted, ontology)
        for key, ok in (("nameCorrect", name_ok), ("educationCorrect", education_ok), ("experienceYearsCorrect", years_ok), ("targetPositionCorrect", position_ok)):
            counts[key] += int(ok)

        if missing or extra or unknown or not all((name_ok, education_ok, years_ok, position_ok)):
            errors.append({
                "resumeId": identifier,
                "missingSkills": sorted(missing), "extraSkills": sorted(extra), "unknownSkills": unknown,
                "fieldErrors": [name for name, ok in (("candidateName", name_ok), ("education", education_ok), ("experienceYears", years_ok), ("targetPosition", position_ok)) if not ok],
            })

    sample_count = len(ground_truth)
    precision = safe_ratio(counts["skillTruePositive"], counts["skillTruePositive"] + counts["skillFalsePositive"])
    recall = safe_ratio(counts["skillTruePositive"], counts["skillTruePositive"] + counts["skillFalseNegative"])
    skill_f1 = harmonic_mean(precision, recall)
    experience_precision = safe_ratio(counts["experienceTruePositive"], counts["experienceTruePositive"] + counts["experienceFalsePositive"])
    experience_recall = safe_ratio(counts["experienceTruePositive"], counts["experienceTruePositive"] + counts["experienceFalseNegative"])
    experience_f1 = harmonic_mean(experience_precision, experience_recall)
    name_accuracy = safe_ratio(counts["nameCorrect"], sample_count)
    education_accuracy = safe_ratio(counts["educationCorrect"], sample_count)
    years_accuracy = safe_ratio(counts["experienceYearsCorrect"], sample_count)
    position_accuracy = safe_ratio(counts["targetPositionCorrect"], sample_count)
    overall_score = (
        skill_f1 * 0.35 + experience_f1 * 0.20 + position_accuracy * 0.15
        + name_accuracy * 0.10 + education_accuracy * 0.10 + years_accuracy * 0.10
    )
    metrics = {
        "skillMicroPrecision": round(precision, 4),
        "skillMicroRecall": round(recall, 4),
        "skillMicroF1": round(skill_f1, 4),
        "experiencePrecision": round(experience_precision, 4),
        "experienceRecall": round(experience_recall, 4),
        "experienceF1": round(experience_f1, 4),
        "candidateNameAccuracy": round(name_accuracy, 4),
        "educationAccuracy": round(education_accuracy, 4),
        "experienceYearsAccuracy": round(years_accuracy, 4),
        "targetPositionAccuracy": round(position_accuracy, 4),
        "parseSuccessRate": round(safe_ratio(counts["parseSuccess"], sample_count), 4),
        "overallScore": round(overall_score, 4),
    }
    report = {
        "evaluationType": "resume_extraction",
        "formal": not allow_draft,
        "sampleCount": sample_count,
        "groundTruthSha256": file_sha256(ground_truth_path),
        "predictionsSha256": file_sha256(predictions_path),
        "ontologyVersion": ontology_version,
        "metrics": metrics,
        "counts": counts,
        "weights": {"skillMicroF1": 0.35, "experienceF1": 0.20, "targetPositionAccuracy": 0.15, "candidateNameAccuracy": 0.10, "educationAccuracy": 0.10, "experienceYearsAccuracy": 0.10},
        "pass": {"skillMicroF1": skill_f1 >= threshold, "overallScore": overall_score >= threshold},
        "errorCases": errors,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate parsed resume predictions.")
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--ontology-dir", type=Path, default=DEFAULT_ONTOLOGY)
    parser.add_argument("--ontology-version", default="v1")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--threshold", type=float, default=0.90)
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument("--allow-pending-aliases", action="store_true")
    args = parser.parse_args()
    report = evaluate_resume_predictions(
        args.ground_truth, args.predictions, args.ontology_dir, args.ontology_version,
        allow_draft=args.allow_draft, allow_pending_aliases=args.allow_pending_aliases, threshold=args.threshold,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
