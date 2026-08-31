from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.app.services.data_sources import read_jsonl
from backend.app.services.evolution_service import (
    POSITION_NAME_MAP,
    SKILL_ALIASES,
    SKILL_NAME_MAP,
    _match_aliases,
    _position_for_record,
    _record_text,
)


def _record_id(record: dict[str, Any]) -> str:
    return str(record.get("source_id") or record.get("content_hash") or record.get("source_job_id") or "")


def predict_jd_label(record: dict[str, Any]) -> dict[str, Any]:
    text = _record_text(record)
    skills = []
    for skill_id, aliases in SKILL_ALIASES.items():
        if _match_aliases(text, aliases):
            skills.append({"id": skill_id, "name": SKILL_NAME_MAP.get(skill_id, skill_id)})

    position_id = _position_for_record(record)
    return {
        "sourceId": _record_id(record),
        "positionId": position_id,
        "positionName": POSITION_NAME_MAP.get(position_id, "候选新岗位"),
        "skills": sorted(skills, key=lambda item: item["id"]),
    }


def _skill_ids(label: dict[str, Any]) -> set[str]:
    return {
        str(skill.get("id"))
        for skill in label.get("expectedSkills", [])
        if isinstance(skill, dict) and str(skill.get("id")) in SKILL_NAME_MAP
    }


def _position_match(predicted: str, expected: str) -> bool:
    if expected == "candidate_other":
        return predicted.startswith("candidate_")
    return predicted == expected


def evaluate_jd_parser(test_path: Path, labels_path: Path, output_path: Path) -> dict[str, Any]:
    records = read_jsonl(test_path)
    labels = read_jsonl(labels_path)
    labels_by_id = {str(label.get("sourceId")): label for label in labels if label.get("sourceId")}

    total = 0
    position_correct = 0
    skill_tp = 0
    skill_fp = 0
    skill_fn = 0
    error_cases: list[dict[str, Any]] = []
    invalid_labels: list[str] = []

    for record in records:
        source_id = _record_id(record)
        expected = labels_by_id.get(source_id)
        if expected is None:
            continue

        expected_position = str(expected.get("expectedPositionId") or "")
        if expected_position != "candidate_other" and expected_position not in POSITION_NAME_MAP:
            invalid_labels.append(source_id)
            continue

        predicted = predict_jd_label(record)
        predicted_skills = {skill["id"] for skill in predicted["skills"]}
        expected_skills = _skill_ids(expected)

        total += 1
        position_ok = _position_match(predicted["positionId"], expected_position)
        if position_ok:
            position_correct += 1

        common = predicted_skills & expected_skills
        missing = expected_skills - predicted_skills
        extra = predicted_skills - expected_skills
        skill_tp += len(common)
        skill_fp += len(extra)
        skill_fn += len(missing)

        if not position_ok or missing or extra:
            error_cases.append(
                {
                    "sourceId": source_id,
                    "title": record.get("title", ""),
                    "expectedPositionId": expected_position,
                    "predictedPositionId": predicted["positionId"],
                    "missingSkills": sorted(missing),
                    "extraSkills": sorted(extra),
                }
            )

    if total == 0:
        raise ValueError("No labeled JD records matched the test set")

    position_accuracy = position_correct / total
    skill_precision = skill_tp / max(1, skill_tp + skill_fp)
    skill_recall = skill_tp / max(1, skill_tp + skill_fn)
    skill_f1 = 0.0 if skill_precision + skill_recall == 0 else 2 * skill_precision * skill_recall / (skill_precision + skill_recall)
    overall_accuracy = (position_accuracy + skill_f1) / 2

    report = {
        "generatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "testSetPath": str(test_path),
        "labelPath": str(labels_path),
        "sampleCount": total,
        "labelCount": len(labels),
        "missingLabelCount": len(records) - total,
        "invalidLabelCount": len(invalid_labels),
        "positionAccuracy": round(position_accuracy, 4),
        "skillPrecision": round(skill_precision, 4),
        "skillRecall": round(skill_recall, 4),
        "skillF1": round(skill_f1, 4),
        "overallAccuracy": round(overall_accuracy, 4),
        "positionCorrectCount": position_correct,
        "skillTruePositive": skill_tp,
        "skillFalsePositive": skill_fp,
        "skillFalseNegative": skill_fn,
        "labeler": "deepseek-v4-flash",
        "metricSource": "deepseek_gold_evaluation",
        "errorCases": error_cases[:30],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate JD parser predictions against labeled JD test set.")
    parser.add_argument("--test-set", type=Path, default=Path("data/processed/splits/jd_test_set_100.jsonl"))
    parser.add_argument("--labels", type=Path, default=Path("data/processed/evaluation/jd_gold_labels.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/evaluation/jd_evaluation_report.json"))
    args = parser.parse_args()

    report = evaluate_jd_parser(args.test_set, args.labels, args.output)
    print(
        "evaluated JD parser: "
        f"sampleCount={report['sampleCount']} "
        f"overallAccuracy={report['overallAccuracy']:.4f} "
        f"positionAccuracy={report['positionAccuracy']:.4f} "
        f"skillF1={report['skillF1']:.4f}"
    )


if __name__ == "__main__":
    main()
