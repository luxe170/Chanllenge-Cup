from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.services.data_sources import read_jsonl, write_jsonl
from src.evaluation.deepseek_label_jd_test_set import label_jd_test_set
from src.llm_client import extract_json_object
from src.processing.llm_extract_jd_skills import extract_default_splits_with_llm, extract_file_with_llm


class FakeJsonClient:
    model = "fake-llm"

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def complete_json(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((system_prompt, user_payload))
        return self.response


def _record(source_id: str = "job-1") -> dict[str, str]:
    return {
        "source_id": source_id,
        "source_platform": "test_jobs",
        "source_job_id": source_id,
        "company": "测试公司",
        "title": "AI Agent 应用开发工程师",
        "category": "研发",
        "publish_time": "2026-01-01T00:00:00+08:00",
        "description": "负责智能体应用和 RAG 系统建设",
        "requirement": "熟悉 Python、大语言模型、检索增强生成，LangChain 经验优先",
        "url": f"https://example.com/{source_id}",
    }


def test_extract_json_object_accepts_markdown_fenced_json() -> None:
    parsed = extract_json_object('```json\n{"ok": true, "count": 2}\n```')

    assert parsed == {"ok": True, "count": 2}


def test_llm_jd_extraction_writes_graph_compatible_predictions(tmp_path: Path) -> None:
    input_path = tmp_path / "jobs.jsonl"
    output_path = tmp_path / "llm_jd_extraction_predictions.jsonl"
    write_jsonl(input_path, [_record()])
    client = FakeJsonClient(
        {
            "items": [
                {
                    "sourceId": "job-1",
                    "scope": "in_scope",
                    "position": {
                        "id": "pos_ai_agent_engineer",
                        "name": "AI Agent 研发工程师",
                        "confidence": 0.91,
                        "evidenceText": "AI Agent 应用开发工程师",
                    },
                    "skills": [
                        {
                            "id": "skill_python",
                            "type": "required",
                            "evidenceText": "熟悉 Python",
                            "confidence": 0.9,
                        },
                        {
                            "id": "skill_rag",
                            "type": "required",
                            "evidenceText": "RAG 系统建设",
                            "confidence": 0.88,
                        },
                    ],
                    "responsibilities": ["负责智能体应用和 RAG 系统建设"],
                    "scenarios": ["智能体应用"],
                    "confidence": 0.9,
                }
            ]
        }
    )

    predictions = extract_file_with_llm(input_path, output_path, client, split="graph_train")
    stored = read_jsonl(output_path)

    assert stored == predictions
    assert stored[0]["parserVersion"] == "llm-jd-extraction-v1"
    assert stored[0]["positionId"] == "pos_ai_agent_engineer"
    assert {skill["id"] for skill in stored[0]["skills"]} == {"skill_python", "skill_rag"}
    assert stored[0]["predictedSkills"] == stored[0]["skills"]
    assert stored[0]["reviewReasons"] == []


def test_llm_jd_labeling_marks_output_as_human_review_draft(tmp_path: Path) -> None:
    input_path = tmp_path / "jd_test_set_100.jsonl"
    output_path = tmp_path / "jd_llm_label_draft.jsonl"
    write_jsonl(input_path, [_record()])
    client = FakeJsonClient(
        {
            "labels": [
                {
                    "sourceId": "job-1",
                    "scope": "in_scope",
                    "expectedPositionId": "pos_ai_agent_engineer",
                    "positionEvidenceText": "AI Agent 应用开发工程师",
                    "expectedSkills": [
                        {
                            "id": "skill_python",
                            "type": "required",
                            "evidenceText": "熟悉 Python",
                            "confidence": 0.86,
                        }
                    ],
                    "confidence": 0.82,
                }
            ]
        }
    )

    labels = label_jd_test_set(input_path, output_path, client=client)
    stored = read_jsonl(output_path)

    assert stored == labels
    assert stored[0]["labelSource"] == "llm_draft"
    assert stored[0]["reviewStatus"] == "pending_human_review"
    assert stored[0]["expectedPositionId"] == "pos_ai_agent_engineer"
    assert stored[0]["expectedSkills"][0]["evidenceText"] == "熟悉 Python"


def test_llm_default_splits_write_combined_and_test_subset(tmp_path: Path, monkeypatch) -> None:
    import src.processing.llm_extract_jd_skills as extractor

    graph_train = tmp_path / "graph_train_200.jsonl"
    jd_test = tmp_path / "jd_test_set_100.jsonl"
    holdout = tmp_path / "jd_holdout_336.jsonl"
    write_jsonl(graph_train, [_record("train-1")])
    write_jsonl(jd_test, [_record("test-1")])
    write_jsonl(holdout, [_record("holdout-1")])
    monkeypatch.setattr(
        extractor,
        "DEFAULT_SPLITS",
        {"graph_train": graph_train, "jd_test": jd_test, "holdout": holdout},
    )
    client = FakeJsonClient(
        {
            "items": [
                {
                    "position": {"id": "pos_ai_agent_engineer"},
                    "skills": [{"id": "skill_python", "type": "required", "evidenceText": "Python"}],
                    "confidence": 0.8,
                }
            ]
        }
    )
    output_path = tmp_path / "llm_jd_extraction_predictions.jsonl"
    test_output_path = tmp_path / "llm_jd_test_predictions.jsonl"

    predictions = extract_default_splits_with_llm(
        output_path,
        client,
        test_output_path=test_output_path,
        batch_size=1,
    )

    assert len(predictions) == 3
    assert [item["split"] for item in read_jsonl(output_path)] == ["graph_train", "jd_test", "holdout"]
    assert [item["sourceId"] for item in read_jsonl(test_output_path)] == ["test-1"]


def test_llm_jd_extraction_accepts_string_position_payload(tmp_path: Path) -> None:
    input_path = tmp_path / "jobs.jsonl"
    output_path = tmp_path / "llm_jd_extraction_predictions.jsonl"
    write_jsonl(input_path, [_record()])
    client = FakeJsonClient(
        {
            "items": [
                {
                    "sourceId": "job-1",
                    "position": "pos_ai_agent_engineer",
                    "similarPositions": ["pos_llm_engineer"],
                    "skills": [{"id": "skill_rag", "type": "required", "evidenceText": "RAG"}],
                    "confidence": 0.8,
                }
            ]
        }
    )

    predictions = extract_file_with_llm(input_path, output_path, client, split="graph_train")

    assert predictions[0]["positionId"] == "pos_ai_agent_engineer"
    assert predictions[0]["similarPositions"][0]["id"] == "pos_llm_engineer"
