from __future__ import annotations

import json
from pathlib import Path

from backend.app.services.data_sources import write_jsonl
from src.evaluation.evaluate_jd_parser import evaluate_jd_parser


def _record(source_id: str, title: str, requirement: str) -> dict[str, str]:
    return {
        "source_id": source_id,
        "source_platform": "test_jobs",
        "source_job_id": source_id,
        "title": title,
        "category": "研发",
        "publish_time": "2026-01-01T00:00:00+08:00",
        "description": "负责技术系统研发",
        "requirement": requirement,
        "url": f"https://example.com/{source_id}",
    }


def test_evaluate_jd_parser_writes_metrics(tmp_path: Path) -> None:
    test_path = tmp_path / "jd_test_set_100.jsonl"
    labels_path = tmp_path / "jd_gold_labels.jsonl"
    output_path = tmp_path / "jd_evaluation_report.json"
    write_jsonl(
        test_path,
        [
            _record("job-1", "推荐算法工程师", "熟悉 Python、机器学习、推荐算法"),
            _record("job-2", "后端研发工程师", "熟悉 Go、分布式、Docker"),
        ],
    )
    write_jsonl(
        labels_path,
        [
            {
                "sourceId": "job-1",
                "expectedPositionId": "pos_algorithm_engineer",
                "expectedPositionName": "算法工程师",
                "expectedSkills": [{"id": "skill_python", "name": "Python", "type": "required"}],
            },
            {
                "sourceId": "job-2",
                "expectedPositionId": "pos_backend_engineer",
                "expectedPositionName": "后端研发工程师",
                "expectedSkills": [{"id": "skill_go", "name": "Go", "type": "required"}],
            },
        ],
    )

    report = evaluate_jd_parser(test_path, labels_path, output_path)

    assert report["sampleCount"] == 2
    assert report["positionAccuracy"] == 1.0
    assert report["skillTruePositive"] >= 2
    assert output_path.exists()


def test_dashboard_uses_jd_evaluation_report_when_present(tmp_path: Path, monkeypatch) -> None:
    import backend.app.services.dashboard_service as dashboard_service

    report_path = tmp_path / "jd_evaluation_report.json"
    report_path.write_text(
        json.dumps(
            {
                "overallAccuracy": 0.876,
                "sampleCount": 100,
                "metricSource": "deepseek_gold_evaluation",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(dashboard_service, "_jd_evaluation_report_path", lambda: report_path)

    metric = next(item for item in dashboard_service._demo_metrics(636) if item["name"] == "JD 解析准确率")

    assert metric["value"] == 87.6
    assert metric["sampleCount"] == 100
    assert metric["source"] == "deepseek_gold_evaluation"
