from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.demo_data import DASHBOARD_SUMMARY, fresh
from backend.app.services.evolution_service import compute_emerging_positions, compute_evolution_changes


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _processed_jobs_path() -> Path:
    return _project_root() / "data" / "processed" / "relevant_jobs.jsonl"


def _split_report_path() -> Path:
    return _project_root() / "data" / "processed" / "splits" / "split_report.json"


def _jd_evaluation_report_path() -> Path:
    return _project_root() / "data" / "processed" / "evaluation" / "jd_evaluation_report.json"


def _cleaning_report_path() -> Path:
    return _project_root() / "data" / "processed" / "cleaning_report.json"


def _raw_jobs_paths() -> list[Path]:
    raw_dir = _project_root() / "data" / "raw"
    if not raw_dir.exists():
        return []
    return sorted(path for path in raw_dir.glob("*jobs.jsonl") if not path.name.startswith("demo_"))


def _count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def _load_cleaning_report() -> dict[str, Any]:
    path = _cleaning_report_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _load_split_report() -> dict[str, Any]:
    path = _split_report_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _load_jd_evaluation_report() -> dict[str, Any]:
    path = _jd_evaluation_report_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _raw_source_count() -> int:
    count = sum(_count_jsonl_lines(path) for path in _raw_jobs_paths())
    if count:
        return count
    report = _load_cleaning_report()
    if isinstance(report.get("input_records"), int):
        return int(report["input_records"])
    return _count_jsonl_lines(_processed_jobs_path())


def _metric_sample_counts(valid_count: int) -> dict[str, int]:
    report = _load_cleaning_report()
    split_report = _load_split_report()
    return {
        "JD 解析准确率": int(split_report.get("jdTestCount") or report.get("accepted_records") or valid_count),
        "简历提取准确率": 108,
        "人岗匹配准确率": 105,
    }


def _demo_metrics(valid_count: int) -> list[dict[str, Any]]:
    sample_counts = _metric_sample_counts(valid_count)
    jd_report = _load_jd_evaluation_report()
    metrics = []
    for metric in fresh(DASHBOARD_SUMMARY)["metrics"]:
        item = dict(metric)
        item["sampleCount"] = sample_counts.get(item["name"], item["sampleCount"])
        item["source"] = "backend_demo_metric"
        if item["name"] == "JD 解析准确率" and jd_report:
            item["value"] = round(float(jd_report.get("overallAccuracy", 0)) * 100, 1)
            item["sampleCount"] = int(jd_report.get("sampleCount") or item["sampleCount"])
            item["source"] = str(jd_report.get("metricSource") or "jd_evaluation_report")
        metrics.append(item)
    return metrics


def _pending_reviews() -> list[dict[str, Any]]:
    try:
        from backend.app.services.review_service import get_reviews

        return get_reviews(status="pending")
    except Exception:
        return []


def get_dashboard_summary() -> dict:
    summary = fresh(DASHBOARD_SUMMARY)
    valid_count = _count_jsonl_lines(_processed_jobs_path())
    split_report = _load_split_report()
    summary["sourceCount"] = _raw_source_count()
    summary["validCount"] = valid_count
    summary["graphTrainCount"] = int(split_report.get("graphTrainCount") or 0)
    summary["jdTestCount"] = int(split_report.get("jdTestCount") or 0)
    summary["holdoutCount"] = int(split_report.get("holdoutCount") or 0)
    try:
        summary["emergingCount"] = compute_emerging_positions(page=1, page_size=1)["total"]
    except Exception:
        summary["emergingCount"] = 0
    try:
        summary["changedCount"] = compute_evolution_changes(page=1, page_size=1)["total"]
    except Exception:
        summary["changedCount"] = 0
    summary["metrics"] = _demo_metrics(valid_count)
    return summary


def get_evaluation_summary() -> dict:
    summary = get_dashboard_summary()
    pending_reviews = _pending_reviews()
    return {
        "metrics": summary["metrics"],
        "pendingReviewCount": len(pending_reviews),
        "highPriorityReviewCount": sum(1 for item in pending_reviews if float(item.get("confidence", 0)) >= 0.9),
        "testedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
