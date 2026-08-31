from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def processed_path(filename: str) -> Path:
    return project_root() / "data" / "processed" / filename


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                items.append(item)
    return items


def write_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def data_source_status() -> dict[str, Any]:
    files = [
        "llm_skill_mentions.jsonl",
        "skill_normalization.jsonl",
        "position_normalization.jsonl",
        "position_profile_summaries.jsonl",
        "graph_nodes.jsonl",
        "graph_edges.jsonl",
        "review_candidates.jsonl",
        "relevant_jobs.jsonl",
        "splits/graph_train_200.jsonl",
        "splits/jd_test_set_100.jsonl",
        "splits/jd_holdout_336.jsonl",
        "splits/split_report.json",
        "evaluation/jd_gold_labels.jsonl",
        "evaluation/jd_evaluation_report.json",
    ]
    states = []
    for filename in files:
        path = processed_path(filename)
        states.append(
            {
                "name": filename,
                "exists": path.exists(),
                "recordCount": len(read_jsonl(path)) if path.suffix == ".jsonl" and path.exists() else 0,
            }
        )
    return {
        "llmRuntimeRequired": False,
        "onlineLlmEnabled": False,
        "readPriority": ["llm_enhanced_outputs", "rule_outputs", "realtime_relevant_jobs", "backend_demo_data"],
        "files": states,
    }
