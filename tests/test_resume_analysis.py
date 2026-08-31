from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.ocr import CallableOcrProvider, NullOcrProvider, OcrError, _extract_text_from_response, set_ocr_provider
from backend.app.services.resume_service import parse_resume_text
from backend.app.services.resume_text import ResumeTextError, extract_resume_text


SAMPLE_RESUME = """姓名：陈小雨
求职意向：AI Agent 研发工程师
硕士 · 计算机科学
3 年相关工作经验

专业技能
- 精通 Python，熟练掌握 FastAPI
- 掌握 大语言模型 与 RAG 检索链路
- 熟悉 LangChain、向量数据库、Docker

项目经历
2025.03 - 至今  企业知识库智能问答系统
负责 RAG 链路、向量检索与模型服务化，离线评测准确率提升 18%。

2024.06 - 2025.01  多轮对话助手
参与提示词工程、会话状态管理及工具调用模块开发。
"""


def test_parse_resume_text_links_skills_to_graph_catalog() -> None:
    profile = parse_resume_text("陈小雨_简历.txt", SAMPLE_RESUME)

    assert profile["candidateName"] == "陈小雨"
    assert profile["targetPosition"] == "AI Agent 研发工程师"
    assert profile["experienceYears"] == 3
    assert profile["completeness"] >= 80

    skills = {skill["name"]: skill for skill in profile["skills"]}
    assert {"Python", "RAG", "FastAPI", "LangChain", "云原生"} <= set(skills)
    assert skills["Python"]["level"] == "精通"
    assert skills["云原生"]["id"] == "skill_cloud_native"
    assert profile["experiences"]


def test_resume_task_lifecycle_supports_upload_and_delta_skill_patch() -> None:
    client = TestClient(app)

    created = client.post(
        "/api/v1/resume-tasks",
        files={"file": ("resume.txt", SAMPLE_RESUME.encode("utf-8"), "text/plain")},
    )
    assert created.status_code == 200
    task_id = created.json()["data"]["taskId"]

    fetched = client.get(f"/api/v1/resume-tasks/{task_id}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["result"]["candidateName"] == "陈小雨"

    patched = client.patch(
        f"/api/v1/resume-tasks/{task_id}/skills",
        json={
            "added": [{"name": "Kubernetes", "level": "熟悉", "source": "用户补充"}],
            "removed": ["skill_fastapi"],
            "updated": [{"id": "skill_python", "level": "掌握", "source": "人工修正"}],
        },
    )
    assert patched.status_code == 200
    edited = patched.json()["data"]["skills"]
    names = {skill["name"] for skill in edited}
    assert "Kubernetes" in names
    assert "FastAPI" not in names
    python = next(skill for skill in edited if skill["id"] == "skill_python")
    assert python["level"] == "掌握"
    assert python["source"] == "人工修正"


def test_extract_text_from_plain_bytes_supports_chinese_encodings() -> None:
    text = extract_resume_text("resume.txt", "姓名：陈小雨\n熟悉 SQL".encode("gb18030"))

    assert "陈小雨" in text
    assert "SQL" in text


def test_ocr_response_extractor_handles_common_json_shapes() -> None:
    assert _extract_text_from_response({"text": "hi"}) == "hi"
    assert _extract_text_from_response({"data": {"text": "hi"}}) == "hi"
    assert _extract_text_from_response({"result": [{"text": "a"}, {"text": "b"}]}) == "a\nb"
    assert _extract_text_from_response({"nope": 1}) == ""


def _build_scanned_pdf() -> bytes:
    fitz = pytest.importorskip("fitz")

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(50, 50, 545, 792), color=(0.9, 0.9, 0.9), fill=(1, 1, 1))
    data = document.tobytes()
    document.close()
    return data


def test_scanned_pdf_routes_through_configured_ocr_provider() -> None:
    calls: list[str] = []

    def fake_ocr(image: bytes, mime: str) -> str:
        calls.append(mime)
        return "姓名：陈小雨\n精通 Python 与 RAG 检索链路"

    set_ocr_provider(CallableOcrProvider(fake_ocr, name="fake"))
    try:
        text = extract_resume_text("scanned.pdf", _build_scanned_pdf())
    finally:
        set_ocr_provider(None)

    assert "陈小雨" in text
    assert calls == ["image/png"]


def test_scanned_pdf_without_ocr_provider_reports_clear_error() -> None:
    set_ocr_provider(NullOcrProvider())
    try:
        with pytest.raises(ResumeTextError, match="OCR"):
            extract_resume_text("scanned.pdf", _build_scanned_pdf())
    finally:
        set_ocr_provider(None)


def test_null_ocr_provider_raises_on_direct_use() -> None:
    provider = NullOcrProvider()

    assert provider.available is False
    with pytest.raises(OcrError):
        provider.recognize(b"image")
