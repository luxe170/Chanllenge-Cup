from __future__ import annotations

from pathlib import Path

from backend.app.demo_data import DASHBOARD_SUMMARY, fresh
from backend.app.services.evolution_service import compute_emerging_positions, compute_evolution_changes


def _processed_jobs_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "processed" / "relevant_jobs.jsonl"


def _count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def get_dashboard_summary() -> dict:
    summary = fresh(DASHBOARD_SUMMARY)
    summary["validCount"] = _count_jsonl_lines(_processed_jobs_path())
    try:
        summary["emergingCount"] = compute_emerging_positions(page=1, page_size=1)["total"]
    except Exception:
        summary["emergingCount"] = 0
    try:
        summary["changedCount"] = compute_evolution_changes(page=1, page_size=1)["total"]
    except Exception:
        summary["changedCount"] = 0
    return summary


def get_evaluation_summary() -> dict:
    summary = get_dashboard_summary()
    metrics = summary["metrics"]
    return {
        "metrics": metrics,
        "pendingReviewCount": 28,
        "highPriorityReviewCount": 6,
        "testedAt": "2026-07-29T10:00:00+08:00",
    }
