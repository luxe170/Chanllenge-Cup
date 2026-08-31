#!/usr/bin/env python3
"""Evaluate JD parser predictions against frozen, ontology-linked ground truth."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GROUND_TRUTH = PROJECT_ROOT / "data" / "evaluation" / "jd_ground_truth_normalized_120_v1.jsonl"
DEFAULT_ONTOLOGY = PROJECT_ROOT / "data" / "evaluation" / "ontology"
DEFAULT_PREDICTIONS = PROJECT_ROOT / "output" / "evaluation" / "jd_predictions_120.jsonl"
DEFAULT_REPORT = PROJECT_ROOT / "output" / "evaluation" / "jd_evaluation_report.json"
FINAL_REVIEW_STATUSES = {"approved", "reviewed", "final", "adjudicated"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    items = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"{path}:{line_number}: each line must be an object")
        items.append(item)
    return items


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return re.sub(r"[\s\-—_/（）()【】]+", "", text)


def harmonic_mean(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def safe_ratio(numerator: int | float, denominator: int | float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


@dataclass(frozen=True)
class Resolution:
    entity_id: str | None
    raw_value: str
    method: str


class Ontology:
    def __init__(self, directory: Path, version: str, allow_pending_aliases: bool = False) -> None:
        self.directory = directory
        self.version = version
        self.allow_pending_aliases = allow_pending_aliases
        self.positions = self._registry("position")
        self.skills = self._registry("skill")
        self.position_names = {normalize_name(row["name"]): row["id"] for row in self.positions.values()}
        self.skill_names = {normalize_name(row["name"]): row["id"] for row in self.skills.values()}
        self.position_aliases = self._aliases("position", self.positions)
        self.skill_aliases = self._aliases("skill", self.skills)
        self.skill_parents = {
            row["id"]: row.get("parent_skill_id") for row in self.skills.values() if row.get("parent_skill_id")
        }

    def _registry(self, entity: str) -> dict[str, dict[str, Any]]:
        rows = read_jsonl(self.directory / f"{entity}_registry_{self.version}.jsonl")
        result = {str(row.get("id")): row for row in rows}
        if not rows or "" in result or len(result) != len(rows):
            raise ValueError(f"invalid {entity} registry")
        return result

    def _aliases(self, entity: str, registry: dict[str, dict[str, Any]]) -> dict[str, str]:
        rows = read_jsonl(self.directory / f"{entity}_aliases_{self.version}.jsonl")
        pending = [row for row in rows if row.get("review_status") not in FINAL_REVIEW_STATUSES]
        if pending and not self.allow_pending_aliases:
            raise ValueError(
                f"{entity} aliases contain {len(pending)} unapproved rows; "
                "finish review or use --allow-pending-aliases for development only"
            )
        result: dict[str, str] = {}
        for row in rows:
            if row.get("review_status") not in FINAL_REVIEW_STATUSES and not self.allow_pending_aliases:
                continue
            entity_id = str(row.get(f"{entity}_id") or "")
            if entity_id not in registry:
                raise ValueError(f"alias references unknown {entity}: {entity_id}")
            alias = normalize_name(row.get("alias"))
            if not alias:
                continue
            previous = result.get(alias)
            if previous and previous != entity_id:
                raise ValueError(f"ambiguous {entity} alias: {row.get('alias')}")
            result[alias] = entity_id
        return result

    @staticmethod
    def _value(payload: Any, id_fields: tuple[str, ...], name_fields: tuple[str, ...]) -> tuple[str, str]:
        if isinstance(payload, str):
            return "", payload
        if not isinstance(payload, dict):
            return "", ""
        entity_id = next((str(payload[field]) for field in id_fields if payload.get(field)), "")
        name = next((str(payload[field]) for field in name_fields if payload.get(field)), "")
        return entity_id, name

    def resolve_position(self, payload: Any) -> Resolution:
        entity_id, name = self._value(
            payload, ("position_id", "positionId", "id"),
            ("name", "raw_name", "position_name", "positionName", "standard_position"),
        )
        if entity_id in self.positions:
            return Resolution(entity_id, name or entity_id, "id")
        key = normalize_name(name or entity_id)
        if key in self.position_names:
            return Resolution(self.position_names[key], name or entity_id, "canonical_name")
        if key in self.position_aliases:
            return Resolution(self.position_aliases[key], name or entity_id, "alias")
        return Resolution(None, name or entity_id, "unknown")

    def resolve_skill(self, payload: Any) -> Resolution:
        entity_id, name = self._value(
            payload, ("skill_id", "skillId", "id"),
            ("name", "raw_name", "skill_name", "skillName"),
        )
        if entity_id in self.skills:
            return Resolution(entity_id, name or entity_id, "id")
        key = normalize_name(name or entity_id)
        if key in self.skill_names:
            return Resolution(self.skill_names[key], name or entity_id, "canonical_name")
        if key in self.skill_aliases:
            return Resolution(self.skill_aliases[key], name or entity_id, "alias")
        return Resolution(None, name or entity_id, "unknown")


def record_id(item: dict[str, Any]) -> str:
    return str(item.get("evaluation_id") or item.get("evaluationId") or item.get("source_id") or item.get("sourceId") or "")


def prediction_position(item: dict[str, Any]) -> Any:
    if "position" in item:
        return item["position"]
    return {
        "position_id": item.get("position_id") or item.get("positionId"),
        "name": item.get("position_name") or item.get("positionName"),
    }


def prediction_skills(item: dict[str, Any]) -> list[Any]:
    value = item.get("skills") or item.get("predicted_skills") or item.get("predictedSkills") or []
    if not isinstance(value, list):
        raise ValueError(f"{record_id(item)}: skills must be a list")
    return value


def requirement_type(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    value = str(payload.get("requirement_type") or payload.get("requirementType") or payload.get("type") or "").lower()
    mapping = {"required": "required", "preferred": "preferred", "必备": "required", "加分": "preferred"}
    return mapping.get(value, value)


def validate_ground_truth(items: list[dict[str, Any]], ontology: Ontology, allow_draft: bool) -> None:
    if len(items) < 100 and not allow_draft:
        raise ValueError(f"formal evaluation requires at least 100 JD records, got {len(items)}")
    for item in items:
        identifier = record_id(item)
        if not identifier:
            raise ValueError("ground truth record missing evaluation_id")
        status = str(item.get("annotation_meta", {}).get("review_status") or "")
        if status not in FINAL_REVIEW_STATUSES and not allow_draft:
            raise ValueError(f"{identifier}: ground truth is not independently reviewed ({status or 'missing'})")
        annotation = item.get("annotation") or {}
        if annotation.get("position_id") not in ontology.positions:
            raise ValueError(f"{identifier}: unknown ground-truth position ID")
        for skill in annotation.get("skills") or []:
            if skill.get("skill_id") not in ontology.skills:
                raise ValueError(f"{identifier}: unknown ground-truth skill ID")


def hierarchical_matches(missing: set[str], extra: set[str], ontology: Ontology) -> list[dict[str, str]]:
    matches = []
    unused_extra = set(extra)
    for expected in sorted(missing):
        related = next(
            (
                predicted for predicted in sorted(unused_extra)
                if ontology.skill_parents.get(expected) == predicted
                or ontology.skill_parents.get(predicted) == expected
            ),
            None,
        )
        if related:
            matches.append({"expectedSkillId": expected, "predictedSkillId": related, "credit": 0.5})
            unused_extra.remove(related)
    return matches


def evaluate(
    ground_truth_path: Path,
    predictions_path: Path,
    ontology_dir: Path,
    ontology_version: str = "v1",
    *,
    allow_draft: bool = False,
    allow_pending_aliases: bool = False,
    allow_partial_predictions: bool = False,
    threshold: float = 0.90,
) -> dict[str, Any]:
    ontology = Ontology(ontology_dir, ontology_version, allow_pending_aliases)
    ground_truth = read_jsonl(ground_truth_path)
    predictions = read_jsonl(predictions_path)
    validate_ground_truth(ground_truth, ontology, allow_draft)

    gt_by_id = {record_id(item): item for item in ground_truth}
    prediction_ids = [record_id(item) for item in predictions]
    if any(not item for item in prediction_ids):
        raise ValueError("prediction record missing evaluation_id")
    if len(set(prediction_ids)) != len(prediction_ids):
        raise ValueError("duplicate prediction IDs")
    pred_by_id = dict(zip(prediction_ids, predictions))
    missing_predictions = sorted(set(gt_by_id) - set(pred_by_id))
    extra_predictions = sorted(set(pred_by_id) - set(gt_by_id))
    if (missing_predictions or extra_predictions) and not allow_partial_predictions:
        raise ValueError(
            f"prediction coverage mismatch: {len(missing_predictions)} missing, {len(extra_predictions)} extra"
        )

    position_correct = 0
    position_total = 0
    skill_tp = skill_fp = skill_fn = 0
    requirement_correct = requirement_total = 0
    scope_correct = scope_total = 0
    hierarchy_credit = 0.0
    unknown_positions: Counter[str] = Counter()
    unknown_skills: Counter[str] = Counter()
    method_counts: Counter[str] = Counter()
    errors = []

    for identifier, expected_item in gt_by_id.items():
        annotation = expected_item["annotation"]
        predicted_item = pred_by_id.get(identifier, {})
        expected_position = annotation["position_id"]
        position_resolution = ontology.resolve_position(prediction_position(predicted_item))
        method_counts[f"position:{position_resolution.method}"] += 1
        position_total += 1
        position_ok = position_resolution.entity_id == expected_position
        position_correct += int(position_ok)
        if position_resolution.method == "unknown" and position_resolution.raw_value:
            unknown_positions[position_resolution.raw_value] += 1

        expected_skills = {skill["skill_id"]: skill for skill in annotation.get("skills") or []}
        predicted_skills: dict[str, Any] = {}
        predicted_unknown = []
        duplicate_predicted_skills = []
        for payload in prediction_skills(predicted_item):
            resolution = ontology.resolve_skill(payload)
            method_counts[f"skill:{resolution.method}"] += 1
            if resolution.entity_id is None:
                raw_key = resolution.raw_value or "<empty>"
                normalized = normalize_name(raw_key) or raw_key
                if normalized not in predicted_unknown:
                    predicted_unknown.append(normalized)
                    unknown_skills[raw_key] += 1
                continue
            if resolution.entity_id in predicted_skills:
                duplicate_predicted_skills.append(resolution.entity_id)
                continue
            predicted_skills[resolution.entity_id] = payload

        expected_ids = set(expected_skills)
        predicted_ids_set = set(predicted_skills)
        common = expected_ids & predicted_ids_set
        missing = expected_ids - predicted_ids_set
        extra = predicted_ids_set - expected_ids
        skill_tp += len(common)
        skill_fp += len(extra) + len(predicted_unknown)
        skill_fn += len(missing)
        partial = hierarchical_matches(missing, extra, ontology)
        hierarchy_credit += sum(item["credit"] for item in partial)

        requirement_mismatches = []
        for skill_id in common:
            expected_type = requirement_type(expected_skills[skill_id])
            predicted_type = requirement_type(predicted_skills[skill_id])
            if expected_type:
                requirement_total += 1
                if predicted_type == expected_type:
                    requirement_correct += 1
                else:
                    requirement_mismatches.append({
                        "skillId": skill_id, "expected": expected_type,
                        "predicted": predicted_type or "missing",
                    })

        predicted_scope = str(predicted_item.get("scope") or "")
        if predicted_scope:
            scope_total += 1
            scope_correct += int(predicted_scope == annotation.get("scope"))

        if not position_ok or missing or extra or predicted_unknown or requirement_mismatches or duplicate_predicted_skills:
            errors.append({
                "evaluationId": identifier,
                "title": expected_item.get("raw", {}).get("title", ""),
                "expectedPositionId": expected_position,
                "predictedPositionId": position_resolution.entity_id,
                "predictedPositionRaw": position_resolution.raw_value,
                "missingSkillIds": sorted(missing),
                "extraSkillIds": sorted(extra),
                "unknownPredictedSkills": sorted(predicted_unknown),
                "hierarchicalPartialMatches": partial,
                "requirementTypeMismatches": requirement_mismatches,
                "duplicatePredictedSkillIds": sorted(set(duplicate_predicted_skills)),
            })

    position_accuracy = safe_ratio(position_correct, position_total)
    skill_precision = safe_ratio(skill_tp, skill_tp + skill_fp)
    skill_recall = safe_ratio(skill_tp, skill_tp + skill_fn)
    skill_f1 = harmonic_mean(skill_precision, skill_recall)
    requirement_accuracy = safe_ratio(requirement_correct, requirement_total)

    combined_tp = position_correct + skill_tp
    combined_fp = (position_total - position_correct) + skill_fp
    combined_fn = (position_total - position_correct) + skill_fn
    combined_precision = safe_ratio(combined_tp, combined_tp + combined_fp)
    combined_recall = safe_ratio(combined_tp, combined_tp + combined_fn)
    combined_f1 = harmonic_mean(combined_precision, combined_recall)
    hierarchy_adjusted_skill_recall = safe_ratio(skill_tp + hierarchy_credit, skill_tp + skill_fn)

    report = {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "development" if allow_draft or allow_pending_aliases else "formal",
        "ontologyVersion": ontology_version,
        "inputs": {
            "groundTruth": str(ground_truth_path),
            "groundTruthSha256": file_sha256(ground_truth_path),
            "predictions": str(predictions_path),
            "predictionsSha256": file_sha256(predictions_path),
            "ontologyDirectory": str(ontology_dir),
        },
        "coverage": {
            "groundTruthCount": len(ground_truth), "predictionCount": len(predictions),
            "evaluatedCount": len(ground_truth), "missingPredictionIds": missing_predictions,
            "extraPredictionIds": extra_predictions,
        },
        "metrics": {
            "positionAccuracy": round(position_accuracy, 6),
            "skillPrecision": round(skill_precision, 6),
            "skillRecall": round(skill_recall, 6),
            "skillMicroF1": round(skill_f1, 6),
            "requirementTypeAccuracy": round(requirement_accuracy, 6),
            "requirementTypeEvaluatedCount": requirement_total,
            "scopeAccuracy": round(safe_ratio(scope_correct, scope_total), 6) if scope_total else None,
            "scopeEvaluatedCount": scope_total,
            "combinedEntityPrecision": round(combined_precision, 6),
            "combinedEntityRecall": round(combined_recall, 6),
            "combinedEntityMicroF1": round(combined_f1, 6),
            "hierarchyAdjustedSkillRecall": round(hierarchy_adjusted_skill_recall, 6),
        },
        "counts": {
            "positionCorrect": position_correct, "positionTotal": position_total,
            "skillTruePositive": skill_tp, "skillFalsePositive": skill_fp, "skillFalseNegative": skill_fn,
            "unknownPositionCount": sum(unknown_positions.values()),
            "unknownSkillCount": sum(unknown_skills.values()),
            "errorRecordCount": len(errors),
        },
        "threshold": threshold,
        "pass": {
            "positionAccuracy": position_accuracy >= threshold,
            "skillMicroF1": skill_f1 >= threshold,
            "combinedEntityMicroF1": combined_f1 >= threshold,
            "allRequiredMetrics": min(position_accuracy, skill_f1, combined_f1) >= threshold,
        },
        "resolutionMethodCounts": dict(sorted(method_counts.items())),
        "unknownPositions": [{"value": key, "count": value} for key, value in unknown_positions.most_common()],
        "unknownSkills": [{"value": key, "count": value} for key, value in unknown_skills.most_common()],
        "errorCases": errors,
    }
    return report


def markdown_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    counts = report["counts"]
    passed = report["pass"]
    lines = [
        "# JD解析正式评测报告", "",
        f"- 模式：`{report['mode']}`",
        f"- 本体版本：`{report['ontologyVersion']}`",
        f"- 样本数：{report['coverage']['evaluatedCount']}",
        f"- 门槛：{report['threshold']:.0%}", "",
        "| 指标 | 结果 | 是否达标 |", "|---|---:|---|",
        f"| 岗位准确率 | {metrics['positionAccuracy']:.2%} | {'是' if passed['positionAccuracy'] else '否'} |",
        f"| 技能Precision | {metrics['skillPrecision']:.2%} | - |",
        f"| 技能Recall | {metrics['skillRecall']:.2%} | - |",
        f"| 技能micro-F1 | {metrics['skillMicroF1']:.2%} | {'是' if passed['skillMicroF1'] else '否'} |",
        f"| 必备/加分准确率 | {metrics['requirementTypeAccuracy']:.2%} | - |",
        f"| 综合实体micro-F1 | {metrics['combinedEntityMicroF1']:.2%} | {'是' if passed['combinedEntityMicroF1'] else '否'} |",
        "", "## 计数", "",
        f"- 技能TP/FP/FN：{counts['skillTruePositive']}/{counts['skillFalsePositive']}/{counts['skillFalseNegative']}",
        f"- 未知岗位：{counts['unknownPositionCount']}",
        f"- 未知技能：{counts['unknownSkillCount']}",
        f"- 含错误样本：{counts['errorRecordCount']}",
        "", "严格主指标不计入上下位概念的部分分；层级感知结果仅作诊断。", "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--ontology-dir", type=Path, default=DEFAULT_ONTOLOGY)
    parser.add_argument("--ontology-version", default="v1")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--threshold", type=float, default=0.90)
    parser.add_argument("--allow-draft", action="store_true", help="Development only: accept unreviewed ground truth.")
    parser.add_argument("--allow-pending-aliases", action="store_true", help="Development only: use pending aliases.")
    parser.add_argument("--allow-partial-predictions", action="store_true", help="Development only: accept incomplete prediction coverage.")
    parser.add_argument("--no-fail", action="store_true", help="Do not exit non-zero when metrics miss the threshold.")
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")
    report = evaluate(
        args.ground_truth, args.predictions, args.ontology_dir, args.ontology_version,
        allow_draft=args.allow_draft,
        allow_pending_aliases=args.allow_pending_aliases,
        allow_partial_predictions=args.allow_partial_predictions,
        threshold=args.threshold,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown_report(report), encoding="utf-8")
    print(json.dumps({"metrics": report["metrics"], "pass": report["pass"]}, ensure_ascii=False))
    if not args.no_fail and not report["pass"]["allRequiredMetrics"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
