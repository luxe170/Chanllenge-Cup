#!/usr/bin/env python3
"""Generate full-position rankings with the production match implementation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.services.data_sources import processed_path, read_jsonl as read_processed_jsonl
from backend.app.services.match_service import _build_match_report, _position_requirements
from src.evaluation.evaluate_jd_predictions import read_jsonl


def _positions() -> list[dict]:
    return sorted(
        (node for node in read_processed_jsonl(processed_path("graph_nodes.jsonl")) if node.get("mode") == "panorama" and node.get("type") == "position"),
        key=lambda item: item["id"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate production match rankings from reviewed resume profiles.")
    parser.add_argument("--resume-ground-truth", type=Path, required=True)
    parser.add_argument("--position-pool", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    positions = _positions()
    pool_rows = []
    for position in positions:
        _, requirements = _position_requirements(position["id"])
        pool_rows.append({"positionId": position["id"], "positionName": position["name"], "requirements": requirements})
    args.position_pool.parent.mkdir(parents=True, exist_ok=True)
    args.position_pool.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in pool_rows), encoding="utf-8")

    predictions = []
    for resume in read_jsonl(args.resume_ground_truth):
        resume_id = str(resume.get("resumeId") or resume.get("resume_id"))
        profile = resume.get("result") or {}
        reports = [_build_match_report(f"evaluation_{resume_id}", profile, position["id"], persist=False) for position in positions]
        reports.sort(key=lambda report: (-report["overallScore"], -report["dimensions"][0]["value"], report["positionName"]))
        rankings = []
        for rank, report in enumerate(reports, 1):
            rankings.append({
                "rank": rank, "positionId": report["positionId"], "positionName": report["positionName"],
                "score": report["overallScore"], "level": "高" if report["overallScore"] >= 80 else "中" if report["overallScore"] >= 60 else "低",
                "matchedSkills": report["strengths"], "missingSkills": [gap["name"] for gap in report["gaps"] if gap["requirement"] == "必备技能"],
            })
        predictions.append({"resumeId": resume_id, "rankings": rankings})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions), encoding="utf-8")
    print(json.dumps({"resumes": len(predictions), "positions": len(pool_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
