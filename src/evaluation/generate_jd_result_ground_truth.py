#!/usr/bin/env python3
"""Build result-shaped JD Ground Truth drafts from the frozen first-version set."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.data_sources import read_jsonl, write_jsonl
from backend.app.services.evolution_service import POSITION_NAME_MAP, SKILL_ALIASES, SKILL_NAME_MAP
from src.evaluation.generate_jd_ground_truth_draft import scenarios, scope_label, split_evidence


PREFERRED_MARKERS = ("优先", "加分", "了解", "熟悉者", "preferred", "plus")


def _source_id(record: dict[str, Any]) -> str:
    return str(record.get("source_id") or record.get("sourceId") or "")


def _skill_evidence(record: dict[str, Any], skill_id: str) -> tuple[str, str]:
    segments = split_evidence(f"{record.get('title', '')}\n{record.get('description', '')}\n{record.get('requirement', '')}")
    aliases = list(SKILL_ALIASES.get(skill_id, ())) + [SKILL_NAME_MAP.get(skill_id, "")]
    evidence = next((segment for segment in segments if any(alias and alias.lower() in segment.lower() for alias in aliases)), "")
    requirement_type = "preferred" if evidence and any(marker.lower() in evidence.lower() for marker in PREFERRED_MARKERS) else "required"
    return evidence[:300], requirement_type


def _result(record: dict[str, Any], label: dict[str, Any]) -> dict[str, Any]:
    position_id = str(label.get("expectedPositionId") or "candidate_other")
    position_name = str(label.get("expectedPositionName") or POSITION_NAME_MAP.get(position_id, "候选新岗位"))
    skills = []
    for source_skill in label.get("expectedSkills") or []:
        if not isinstance(source_skill, dict):
            continue
        skill_id = str(source_skill.get("id") or "")
        if skill_id not in SKILL_NAME_MAP:
            continue
        evidence, requirement_type = _skill_evidence(record, skill_id)
        skills.append({
            "id": skill_id,
            "name": SKILL_NAME_MAP[skill_id],
            "type": requirement_type,
            "requirementType": requirement_type,
            "confidence": 1.0,
            "source": "ground_truth_draft",
            "matchedAlias": "",
            "evidenceText": evidence,
            "importance": 1.0 if requirement_type == "required" else 0.6,
        })
    responsibilities = split_evidence(str(record.get("description") or ""))[:6]
    scenario_names = [item["name"] for item in scenarios({
        "title": str(record.get("title") or ""),
        "description": str(record.get("description") or ""),
        "requirement": str(record.get("requirement") or ""),
    })]
    scope = scope_label(str(record.get("title") or ""))
    candidate = position_id.startswith("candidate_") and scope != "out_of_scope"
    return {
        "schemaVersion": "1.1",
        "sourceId": _source_id(record),
        "evaluation_id": _source_id(record),
        "split": "jd_test",
        "sourcePlatform": str(record.get("source_platform") or ""),
        "sourceJobId": str(record.get("source_job_id") or ""),
        "contentHash": str(record.get("content_hash") or ""),
        "company": str(record.get("company") or ""),
        "title": str(record.get("title") or ""),
        "publishTime": str(record.get("publish_time") or ""),
        "scrapedAt": str(record.get("scraped_at") or ""),
        "scope": "review" if candidate else scope,
        "position": {"id": position_id, "name": position_name, "confidence": 1.0, "source": "ground_truth_draft", "evidenceText": str(record.get("title") or "")[:300]},
        "positionId": position_id,
        "positionName": position_name,
        "predictedPositionId": position_id,
        "predictedPositionName": position_name,
        "similarPositions": [],
        "skills": skills,
        "predictedSkills": skills,
        "responsibilities": responsibilities,
        "scenarios": scenario_names,
        "newSkillCandidates": [],
        "isNewPositionCandidate": candidate,
        "reviewReasons": ["新岗位候选"] if candidate else [],
        "confidence": 1.0,
        "parserVersion": "llm-jd-extraction-v1",
        "promptVersion": "jd-extraction-v1",
        "model": "ground-truth",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate result-shaped JD GT drafts.")
    parser.add_argument("--test-set", type=Path, default=Path("data/processed/splits/jd_test_set_100.jsonl"))
    parser.add_argument("--seed-labels", type=Path, default=Path("data/processed/evaluation/jd_gold_labels.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/evaluation/jd_result_ground_truth_100_v1.jsonl"))
    args = parser.parse_args()
    records = read_jsonl(args.test_set)
    labels = {str(item.get("sourceId") or ""): item for item in read_jsonl(args.seed_labels)}
    rows = []
    for index, record in enumerate(records, 1):
        source_id = _source_id(record)
        if source_id not in labels:
            raise ValueError(f"missing seed label: {source_id}")
        rows.append({
            "evaluationId": f"JD-FIRST-{index:03d}",
            "sourceId": source_id,
            "result": _result(record, labels[source_id]),
            "annotationMeta": {
                "schema": "llm-jd-extraction-v1.result.v1",
                "reviewStatus": "draft_pending_human_review",
                "annotationBasis": "legacy_position_skill_seed_plus_original_jd",
                "scoredFields": ["scope", "position", "skills", "requirementType", "responsibilities", "scenarios", "newSkillCandidates", "isNewPositionCandidate"],
                "notes": "自动迁移草稿；岗位、技能、要求类型、职责、场景及新实体候选均须人工逐条复核。",
            },
        })
    if len(rows) != 100:
        raise ValueError(f"expected 100 records, got {len(rows)}")
    write_jsonl(args.output, rows)
    print(json.dumps({"records": len(rows), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
