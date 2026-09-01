from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.data_sources import project_root, read_jsonl, write_jsonl
from backend.app.services.evolution_service import (
    POSITION_NAME_MAP,
    SKILL_ALIASES,
    SKILL_NAME_MAP,
    _match_aliases,
    _position_for_record,
    _record_text,
)


PARSER_VERSION = "rule-position-skill-v1"
DEFAULT_EXTRACTION_OUTPUT = project_root() / "data" / "processed" / "extractions" / "jd_extraction_predictions.jsonl"
DEFAULT_TEST_PREDICTION_OUTPUT = project_root() / "data" / "processed" / "evaluation" / "jd_test_predictions.jsonl"
DEFAULT_SPLITS = {
    "graph_train": project_root() / "data" / "processed" / "splits" / "graph_train_200.jsonl",
    "jd_test": project_root() / "data" / "processed" / "splits" / "jd_test_set_100.jsonl",
    "holdout": project_root() / "data" / "processed" / "splits" / "jd_holdout_336.jsonl",
}


def record_id(record: dict[str, Any]) -> str:
    return str(record.get("source_id") or record.get("content_hash") or record.get("source_job_id") or "")


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _clip_evidence(text: str, alias: str, radius: int = 48) -> str:
    if not text or not alias:
        return ""
    lower_text = text.lower()
    lower_alias = alias.lower()
    index = lower_text.find(lower_alias)
    if index < 0:
        return text[: radius * 2].strip()
    start = max(0, index - radius)
    end = min(len(text), index + len(alias) + radius)
    return text[start:end].strip()


def _first_matching_alias(text: str, aliases: list[str]) -> str:
    normalized = text.lower()
    return next((alias for alias in aliases if alias.lower() in normalized), "")


def _skill_requirement_type(skill_id: str) -> str:
    required_skills = {
        "skill_llm",
        "skill_rag",
        "skill_python",
        "skill_java",
        "skill_go",
        "skill_cpp",
        "skill_sql",
    }
    return "required" if skill_id in required_skills else "preferred"


def predict_jd_label(
    record: dict[str, Any],
    *,
    split: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    text = _record_text(record)
    position_id = str(record.get("_position_id") or _position_for_record(record))
    position_name = POSITION_NAME_MAP.get(position_id, "候选新岗位")
    is_candidate = position_id.startswith("candidate_")

    skills = []
    for skill_id, aliases in SKILL_ALIASES.items():
        if not _match_aliases(text, aliases):
            continue
        matched_alias = _first_matching_alias(text, list(aliases))
        requirement_type = _skill_requirement_type(skill_id)
        skills.append(
            {
                "id": skill_id,
                "name": SKILL_NAME_MAP.get(skill_id, skill_id),
                "type": requirement_type,
                "requirementType": requirement_type,
                "confidence": 0.82,
                "source": "rule",
                "matchedAlias": matched_alias,
                "evidenceText": _clip_evidence(text, matched_alias),
            }
        )

    skills = sorted(skills, key=lambda item: item["id"])
    source_id = record_id(record)
    position = {
        "id": position_id,
        "name": position_name,
        "confidence": 0.55 if is_candidate else 0.86,
        "source": "rule",
        "evidenceText": str(record.get("title") or ""),
    }
    return {
        "schemaVersion": "1.0",
        "sourceId": source_id,
        "evaluation_id": source_id,
        "split": split,
        "sourcePlatform": record.get("source_platform") or "",
        "sourceJobId": record.get("source_job_id") or "",
        "contentHash": record.get("content_hash") or "",
        "company": record.get("company") or "",
        "title": record.get("title") or "",
        "publishTime": record.get("publish_time") or "",
        "scrapedAt": record.get("scraped_at") or "",
        "scope": "in_scope" if not is_candidate else "candidate",
        "position": position,
        "positionId": position_id,
        "positionName": position_name,
        "predictedPositionId": position_id,
        "predictedPositionName": position_name,
        "skills": skills,
        "predictedSkills": skills,
        "parserVersion": PARSER_VERSION,
        "generatedAt": generated_at or _generated_at(),
    }


def extract_predictions(
    records: list[dict[str, Any]],
    *,
    split: str = "",
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    timestamp = generated_at or _generated_at()
    return [predict_jd_label(record, split=split, generated_at=timestamp) for record in records]


def extract_file(input_path: Path, output_path: Path, *, split: str = "") -> list[dict[str, Any]]:
    predictions = extract_predictions(read_jsonl(input_path), split=split)
    write_jsonl(output_path, predictions)
    return predictions


def extract_default_splits(
    output_path: Path = DEFAULT_EXTRACTION_OUTPUT,
    *,
    test_output_path: Path | None = DEFAULT_TEST_PREDICTION_OUTPUT,
) -> list[dict[str, Any]]:
    timestamp = _generated_at()
    predictions: list[dict[str, Any]] = []
    test_predictions: list[dict[str, Any]] = []
    for split, path in DEFAULT_SPLITS.items():
        split_predictions = extract_predictions(read_jsonl(path), split=split, generated_at=timestamp)
        predictions.extend(split_predictions)
        if split == "jd_test":
            test_predictions = split_predictions
    write_jsonl(output_path, predictions)
    if test_output_path is not None:
        write_jsonl(test_output_path, test_predictions)
    return predictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Write per-JD position and skill extraction predictions.")
    parser.add_argument("--input", type=Path, default=None, help="Optional single JSONL JD input file.")
    parser.add_argument("--split", default="", help="Split label for --input records, for example graph_train or jd_test.")
    parser.add_argument("--output", type=Path, default=DEFAULT_EXTRACTION_OUTPUT)
    parser.add_argument(
        "--test-output",
        type=Path,
        default=DEFAULT_TEST_PREDICTION_OUTPUT,
        help="When extracting default splits, also write the JD test prediction subset here.",
    )
    args = parser.parse_args()

    if args.input is not None:
        predictions = extract_file(args.input, args.output, split=args.split)
    else:
        predictions = extract_default_splits(args.output, test_output_path=args.test_output)
    print(f"wrote JD extraction predictions: {len(predictions)} records -> {args.output}")


if __name__ == "__main__":
    main()
