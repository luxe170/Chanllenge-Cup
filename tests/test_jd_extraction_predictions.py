from __future__ import annotations

from pathlib import Path

from backend.app.services.data_sources import read_jsonl, write_jsonl
from src.evaluation.evaluate_jd_parser import evaluate_jd_parser
from src.processing.build_graph_seed import build_graph_seed
from src.processing.extract_jd_predictions import extract_default_splits, extract_file


def _record(source_id: str, title: str, requirement: str) -> dict[str, str]:
    return {
        "source_id": source_id,
        "source_platform": "test_jobs",
        "source_job_id": source_id,
        "company": "测试公司",
        "title": title,
        "category": "研发",
        "publish_time": "2026-01-01T00:00:00+08:00",
        "description": "负责互联网技术系统研发",
        "requirement": requirement,
        "url": f"https://example.com/{source_id}",
    }


def test_extract_file_writes_per_jd_predictions(tmp_path: Path) -> None:
    input_path = tmp_path / "graph_train_200.jsonl"
    output_path = tmp_path / "extractions" / "jd_graph_train_predictions.jsonl"
    write_jsonl(
        input_path,
        [
            _record("job-1", "推荐算法工程师", "熟悉 Python、机器学习、推荐算法"),
            _record("job-2", "后端研发工程师", "熟悉 Go、分布式、Docker"),
        ],
    )

    predictions = extract_file(input_path, output_path, split="graph_train")
    stored = read_jsonl(output_path)

    assert len(predictions) == 2
    assert stored == predictions
    assert stored[0]["split"] == "graph_train"
    assert stored[0]["predictedPositionId"] == "pos_algorithm_engineer"
    assert {skill["id"] for skill in stored[0]["predictedSkills"]} >= {"skill_python", "skill_algorithm"}
    assert stored[0]["predictedSkills"][0]["evidenceText"]


def test_extract_default_splits_writes_combined_and_test_subset(tmp_path: Path, monkeypatch) -> None:
    import src.processing.extract_jd_predictions as extractor

    graph_train = tmp_path / "graph_train_200.jsonl"
    jd_test = tmp_path / "jd_test_set_100.jsonl"
    holdout = tmp_path / "jd_holdout_336.jsonl"
    write_jsonl(graph_train, [_record("train-1", "后端研发工程师", "熟悉 Go")])
    write_jsonl(jd_test, [_record("test-1", "测试开发工程师", "熟悉自动化测试")])
    write_jsonl(holdout, [_record("holdout-1", "云计算 SRE 工程师", "熟悉 Kubernetes")])
    monkeypatch.setattr(
        extractor,
        "DEFAULT_SPLITS",
        {"graph_train": graph_train, "jd_test": jd_test, "holdout": holdout},
    )

    output_path = tmp_path / "extractions" / "jd_extraction_predictions.jsonl"
    test_output_path = tmp_path / "evaluation" / "jd_test_predictions.jsonl"
    predictions = extract_default_splits(output_path, test_output_path=test_output_path)

    assert len(predictions) == 3
    assert [item["split"] for item in read_jsonl(output_path)] == ["graph_train", "jd_test", "holdout"]
    assert [item["sourceId"] for item in read_jsonl(test_output_path)] == ["test-1"]


def test_build_graph_seed_can_use_extraction_predictions(tmp_path: Path) -> None:
    input_path = tmp_path / "all_predictions.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "sourceId": "train-1",
                "split": "graph_train",
                "title": "后端研发工程师",
                "publishTime": "2026-01-01T00:00:00+08:00",
                "positionId": "pos_backend_engineer",
                "skills": [{"id": "skill_go", "name": "Go"}],
            },
            {
                "sourceId": "test-1",
                "split": "jd_test",
                "title": "测试开发工程师",
                "publishTime": "2026-01-01T00:00:00+08:00",
                "positionId": "pos_test_engineer",
                "skills": [{"id": "skill_testing", "name": "自动化测试"}],
            },
        ],
    )

    all_predictions = read_jsonl(input_path)
    train_predictions = [item for item in all_predictions if item["split"] == "graph_train"]
    nodes, _ = build_graph_seed(predictions=train_predictions)
    node_ids = {node["id"] for node in nodes}

    assert "pos_backend_engineer" in node_ids
    assert "skill_go" in node_ids
    assert "pos_test_engineer" not in node_ids


def test_evaluate_jd_parser_writes_test_predictions(tmp_path: Path) -> None:
    test_path = tmp_path / "jd_test_set_100.jsonl"
    labels_path = tmp_path / "jd_gold_labels.jsonl"
    report_path = tmp_path / "jd_evaluation_report.json"
    predictions_path = tmp_path / "jd_test_predictions.jsonl"
    write_jsonl(test_path, [_record("job-1", "推荐算法工程师", "熟悉 Python、机器学习、推荐算法")])
    write_jsonl(
        labels_path,
        [
            {
                "sourceId": "job-1",
                "expectedPositionId": "pos_algorithm_engineer",
                "expectedSkills": [{"id": "skill_python", "name": "Python", "type": "required"}],
            }
        ],
    )

    report = evaluate_jd_parser(test_path, labels_path, report_path, predictions_path)

    assert report["predictionPath"] == str(predictions_path)
    assert read_jsonl(predictions_path)[0]["sourceId"] == "job-1"
