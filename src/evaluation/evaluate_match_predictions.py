#!/usr/bin/env python3
"""Evaluate full-pool human-job matching rankings and skill-gap diagnosis."""

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


def _text(value: Any) -> str:
    return re.sub(r"[\s·•,，。:：;；_\-/（）()]+", "", unicodedata.normalize("NFKC", str(value or "")).lower())


def _skill_set(values: list[Any]) -> set[str]:
    return {_text(value.get("name") if isinstance(value, dict) else value) for value in values if _text(value.get("name") if isinstance(value, dict) else value)}


def _set_counts(expected: set[str], predicted: set[str]) -> tuple[int, int, int]:
    return len(expected & predicted), len(predicted - expected), len(expected - predicted)


def _macro_f1(labels: list[str], predictions: list[str]) -> float:
    scores = []
    observed_labels = sorted(set(labels) | set(predictions))
    for label in observed_labels:
        tp = sum(a == label and b == label for a, b in zip(labels, predictions))
        fp = sum(a != label and b == label for a, b in zip(labels, predictions))
        fn = sum(a == label and b != label for a, b in zip(labels, predictions))
        precision, recall = safe_ratio(tp, tp + fp), safe_ratio(tp, tp + fn)
        scores.append(harmonic_mean(precision, recall))
    return safe_ratio(sum(scores), len(scores))


def evaluate(ground_truth_path: Path, predictions_path: Path, position_pool_path: Path, *, allow_draft: bool = False) -> dict:
    ground_truth, predictions, pool = read_jsonl(ground_truth_path), read_jsonl(predictions_path), read_jsonl(position_pool_path)
    pool_ids = {row["positionId"] for row in pool}
    prediction_map = {row["resumeId"]: row for row in predictions}
    if {row["resumeId"] for row in ground_truth} != set(prediction_map):
        raise ValueError("prediction coverage mismatch")
    if len(pool_ids) < 10:
        raise ValueError("position pool must contain at least 10 positions")

    counts = defaultdict(int)
    reciprocal_rank = ndcg_sum = 0.0
    expected_levels, predicted_levels, errors = [], [], []
    for gt in ground_truth:
        status = (gt.get("annotationMeta") or {}).get("reviewStatus", "")
        if status not in FINAL_REVIEW_STATUSES and not allow_draft:
            raise ValueError(f"{gt['resumeId']}: ground truth is not independently reviewed")
        rankings = prediction_map[gt["resumeId"]].get("rankings") or []
        ranked_ids = [row.get("positionId") for row in rankings]
        if set(ranked_ids) != pool_ids or len(ranked_ids) != len(pool_ids):
            raise ValueError(f"{gt['resumeId']}: ranking must cover the frozen position pool exactly once")
        best, acceptable = gt["bestPositionId"], set(gt["acceptablePositionIds"])
        counts["top1Correct"] += int(ranked_ids[0] == best)
        counts["top3Correct"] += int(bool(set(ranked_ids[:3]) & acceptable))
        best_rank = ranked_ids.index(best) + 1
        reciprocal_rank += 1 / best_rank
        relevance = [2 if position_id == best else 1 if position_id in acceptable else 0 for position_id in ranked_ids[:3]]
        dcg = sum((2**rel - 1) / math.log2(index + 2) for index, rel in enumerate(relevance))
        ideal = sorted([2] + [1] * (len(acceptable - {best})), reverse=True)[:3]
        idcg = sum((2**rel - 1) / math.log2(index + 2) for index, rel in enumerate(ideal))
        ndcg_sum += safe_ratio(dcg, idcg)

        best_prediction = rankings[ranked_ids.index(best)]
        expected_levels.append(gt["level"])
        predicted_levels.append(best_prediction["level"])
        matched = _set_counts(_skill_set(gt.get("matchedRequiredSkills") or []), _skill_set(best_prediction.get("matchedSkills") or []))
        missing = _set_counts(_skill_set(gt.get("missingRequiredSkills") or []), _skill_set(best_prediction.get("missingSkills") or []))
        for prefix, values in (("matched", matched), ("missing", missing)):
            counts[f"{prefix}TP"] += values[0]; counts[f"{prefix}FP"] += values[1]; counts[f"{prefix}FN"] += values[2]
        if ranked_ids[0] != best or best_prediction["level"] != gt["level"] or missing[1] or missing[2]:
            errors.append({"resumeId": gt["resumeId"], "expectedBest": best, "predictedBest": ranked_ids[0], "bestRank": best_rank, "expectedLevel": gt["level"], "predictedLevel": best_prediction["level"], "missingSkillFP": missing[1], "missingSkillFN": missing[2]})

    sample_count = len(ground_truth)
    def f1(prefix: str) -> float:
        precision = safe_ratio(counts[f"{prefix}TP"], counts[f"{prefix}TP"] + counts[f"{prefix}FP"])
        recall = safe_ratio(counts[f"{prefix}TP"], counts[f"{prefix}TP"] + counts[f"{prefix}FN"])
        return harmonic_mean(precision, recall)
    top1, top3 = safe_ratio(counts["top1Correct"], sample_count), safe_ratio(counts["top3Correct"], sample_count)
    ndcg, level_f1, missing_f1, matched_f1 = ndcg_sum / sample_count, _macro_f1(expected_levels, predicted_levels), f1("missing"), f1("matched")
    overall = top1 * .30 + top3 * .15 + ndcg * .10 + level_f1 * .15 + missing_f1 * .20 + matched_f1 * .10
    return {
        "evaluationType": "human_job_match", "formal": not allow_draft, "sampleCount": sample_count, "positionPoolSize": len(pool_ids),
        "groundTruthSha256": file_sha256(ground_truth_path), "predictionsSha256": file_sha256(predictions_path), "positionPoolSha256": file_sha256(position_pool_path),
        "metrics": {"top1Accuracy": round(top1, 4), "top3Accuracy": round(top3, 4), "mrr": round(reciprocal_rank / sample_count, 4), "ndcgAt3": round(ndcg, 4), "levelMacroF1": round(level_f1, 4), "missingSkillMicroF1": round(missing_f1, 4), "matchedSkillMicroF1": round(matched_f1, 4), "overallScore": round(overall, 4)},
        "weights": {"top1Accuracy": .30, "top3Accuracy": .15, "ndcgAt3": .10, "levelMacroF1": .15, "missingSkillMicroF1": .20, "matchedSkillMicroF1": .10},
        "pass": {"overallScore": overall >= .80, "top1Accuracy": top1 >= .80, "top3Accuracy": top3 >= .90}, "errorCases": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate human-job match predictions.")
    parser.add_argument("--ground-truth", type=Path, required=True); parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--position-pool", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--allow-draft", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.ground_truth, args.predictions, args.position_pool, allow_draft=args.allow_draft)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
