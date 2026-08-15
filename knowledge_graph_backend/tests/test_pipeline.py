from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base, build_engine
from app.graph import InMemoryGraphRepository
from app.models import PipelineRun, ReviewItem
from app.pipeline import PipelineService


def settings(import_root: Path, database_url: str) -> Settings:
    return Settings(
        app_env="test",
        app_host="127.0.0.1",
        app_port=8000,
        database_url=database_url,
        graph_backend="memory",
        neo4j_uri="",
        neo4j_username="",
        neo4j_password="",
        neo4j_database="neo4j",
        import_root=import_root,
        default_window_days=90,
        min_sample_count=2,
        min_auto_publish_confidence=0.6,
        cors_origins=("http://localhost:5173",),
        admin_api_key="test-key-1234567",
    )


def write_input(path: Path) -> None:
    fields = ["source_id", "source_platform", "company", "title", "category", "locations", "publish_time", "description", "requirement", "url", "content_hash", "duplicate_group_id", "quality_flags"]
    rows = []
    for index in range(1, 5):
        rows.append({
            "source_id": f"test:{index}",
            "source_platform": "test",
            "company": f"企业{index}",
            "title": "AI Agent 研发工程师",
            "category": "人工智能",
            "locations": "北京",
            "publish_time": f"2026-08-0{index}T00:00:00+08:00",
            "description": "使用 Python 构建智能体和 RAG 服务。",
            "requirement": "要求掌握 Python、RAG 和 LangChain。",
            "url": f"https://example.test/jobs/{index}",
            "content_hash": "",
            "duplicate_group_id": "",
            "quality_flags": "",
        })
    rows.append({
        "source_id": "test:unknown",
        "source_platform": "test",
        "company": "企业X",
        "title": "量子工作流编排师",
        "category": "研发",
        "locations": "上海",
        "publish_time": "2026-08-05T00:00:00+08:00",
        "description": "探索新型工作流。",
        "requirement": "要求掌握 Python。",
        "url": "https://example.test/jobs/unknown",
        "content_hash": "",
        "duplicate_group_id": "",
        "quality_flags": "",
    })
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_end_to_end_pipeline_builds_queryable_graph(tmp_path: Path):
    input_path = tmp_path / "input.csv"
    write_input(input_path)
    database_url = f"sqlite:///{(tmp_path / 'pipeline.db').as_posix()}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    graph = InMemoryGraphRepository()
    service = PipelineService(sessions, graph, settings(tmp_path, database_url))

    run = service.run_now("input.csv", {"windowEnd": "2026-08-15", "windowDays": 90})
    assert run.status == "completed"
    assert run.statistics["importedRecords"] == 5
    assert run.statistics["publishedRelationships"] >= 3
    data = graph.graph("panorama", max_nodes=100)
    assert any(node["id"] == "pos_ai_agent_engineer" for node in data["nodes"])
    assert any(edge["relationship"] == "REQUIRES" for edge in data["edges"])

    with sessions() as session:
        stored = session.get(PipelineRun, run.id)
        assert stored.status == "completed"
        assert session.query(ReviewItem).filter_by(review_type="new_position").count() == 1


def test_import_path_cannot_escape_root(tmp_path: Path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'security.db').as_posix()}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    service = PipelineService(sessions, InMemoryGraphRepository(), settings(tmp_path, str(engine.url)))
    try:
        service.resolve_source("../outside.csv")
    except ValueError as exc:
        assert "IMPORT_ROOT" in str(exc)
    else:
        raise AssertionError("path traversal must be rejected")

