from __future__ import annotations

from pathlib import Path

from backend.app.services.data_sources import read_jsonl, write_jsonl
from src.processing.build_graph_seed import build_graph_seed
from src.processing.split_relevant_jobs import split_relevant_jobs


def _record(index: int, title: str, source: str = "test_jobs", publish_time: str | None = None) -> dict[str, str]:
    return {
        "source_platform": source,
        "company": f"测试公司{index % 3}",
        "source_job_id": f"job-{index}",
        "source_id": f"{source}:job-{index}",
        "title": title,
        "category": "研发",
        "publish_time": publish_time or f"2026-0{index % 8 + 1}-01T00:00:00+08:00",
        "description": "负责算法、后端、测试和云原生系统建设",
        "requirement": "熟悉 Python、Go、Java、Docker、SQL 和自动化测试",
        "url": f"https://example.com/jobs/{index}",
    }


def _ids(records: list[dict]) -> set[str]:
    return {record["source_id"] for record in records}


def test_split_relevant_jobs_is_stable_and_isolates_test_set(tmp_path: Path) -> None:
    records = [
        _record(1, "推荐算法工程师", "bytedance"),
        _record(2, "后端研发工程师", "tencent"),
        _record(3, "测试开发工程师", "bytedance"),
        _record(4, "数据平台研发工程师", "tencent"),
        _record(5, "云计算 SRE 工程师", "alibaba"),
        _record(6, "安全工程师", "meituan"),
        _record(7, "硬件芯片工程师", "bytedance"),
        _record(8, "存储数据库研发工程师", "tencent"),
        {**_record(9, "未知技术岗位", "tencent"), "publish_time": "", "scraped_at": ""},
    ]
    input_path = tmp_path / "relevant_jobs.jsonl"
    write_jsonl(input_path, records)

    first = split_relevant_jobs(input_path, tmp_path / "first", train_size=4, test_size=2)
    second = split_relevant_jobs(input_path, tmp_path / "second", train_size=4, test_size=2)

    first_train = read_jsonl(Path(first["files"]["graphTrain"]))
    first_test = read_jsonl(Path(first["files"]["jdTest"]))
    first_holdout = read_jsonl(Path(first["files"]["holdout"]))
    second_train = read_jsonl(Path(second["files"]["graphTrain"]))
    second_test = read_jsonl(Path(second["files"]["jdTest"]))

    assert len(first_train) == 4
    assert len(first_test) == 2
    assert len(first_holdout) == 3
    assert _ids(first_train).isdisjoint(_ids(first_test))
    assert _ids(first_train).isdisjoint(_ids(first_holdout))
    assert _ids(first_test).isdisjoint(_ids(first_holdout))
    assert [item["source_id"] for item in first_train] == [item["source_id"] for item in second_train]
    assert [item["source_id"] for item in first_test] == [item["source_id"] for item in second_test]


def test_build_graph_seed_uses_explicit_training_input(tmp_path: Path) -> None:
    train_path = tmp_path / "graph_train_200.jsonl"
    write_jsonl(
        train_path,
        [
            _record(1, "推荐算法工程师"),
            _record(2, "后端研发工程师"),
            _record(3, "测试开发工程师"),
        ],
    )

    nodes, edges = build_graph_seed(train_path)
    node_ids = {node["id"] for node in nodes}
    position_ids = {node["id"] for node in nodes if node.get("mode") == "panorama" and node.get("type") == "position"}

    assert {"pos_algorithm_engineer", "pos_backend_engineer", "pos_test_engineer"}.issubset(position_ids)
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in edges)
