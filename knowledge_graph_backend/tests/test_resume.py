from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ocr import CallableOcrProvider, HttpOcrProvider, NullOcrProvider, OcrError, _extract_text_from_response, set_ocr_provider
from app.resume import parse_resume_text
from app.resume_service import get_resume_task_store
from app.resume_text import ResumeTextError, extract_resume_text


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


def test_extract_text_from_plain_bytes():
    text = extract_resume_text("resume.txt", SAMPLE_RESUME.encode("utf-8"))
    assert "陈小雨" in text
    assert "RAG" in text


def test_extract_text_rejects_unsupported_extension():
    with pytest.raises(ResumeTextError):
        extract_resume_text("resume.exe", b"binary")


def test_extract_text_rejects_empty_upload():
    with pytest.raises(ResumeTextError):
        extract_resume_text("resume.txt", b"")


def test_parse_resume_text_produces_structured_profile():
    profile = parse_resume_text(SAMPLE_RESUME)
    assert profile.name == "陈小雨"
    assert profile.intendedPosition.startswith("AI Agent")
    assert profile.experienceYears == 3
    assert "硕士" in profile.education
    assert profile.experiences, "expected at least one experience block"
    assert profile.experiences[0].period.startswith("2025.03")
    skill_names = {skill.name for skill in profile.skills}
    assert {"Python", "RAG", "LangChain", "FastAPI"} <= skill_names
    python_skill = next(skill for skill in profile.skills if skill.name == "Python")
    assert python_skill.level == "精通"
    assert profile.completeness >= 70


def test_parse_resume_defaults_when_no_marker():
    profile = parse_resume_text("熟悉 Docker 使用")
    docker = next(skill for skill in profile.skills if skill.name == "Docker")
    assert docker.level == "熟悉"


def test_resume_task_lifecycle_via_api():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resume-tasks",
            files={"file": ("resume.txt", SAMPLE_RESUME.encode("utf-8"), "text/plain")},
        )
        assert response.status_code == 202, response.text
        body = response.json()["data"]
        assert body["status"] == "succeeded"
        assert body["result"]["name"] == "陈小雨"
        task_id = body["id"]

        polled = client.get(f"/api/v1/resume-tasks/{task_id}")
        assert polled.status_code == 200
        assert polled.json()["data"]["status"] == "succeeded"

        patch = client.patch(
            f"/api/v1/resume-tasks/{task_id}/skills",
            json={
                "added": [{"name": "Kubernetes", "level": "熟悉", "source": "用户补充"}],
                "removed": ["skill_docker"],
                "updated": [{"id": "skill_python", "level": "掌握"}],
            },
        )
        assert patch.status_code == 200
        edited = patch.json()["data"]["result"]["skills"]
        names = {item["name"] for item in edited}
        assert "Kubernetes" in names
        assert "Docker" not in names
        python = next(item for item in edited if item["name"] == "Python")
        assert python["level"] == "掌握"


def test_resume_task_missing_returns_404():
    with TestClient(app) as client:
        assert client.get("/api/v1/resume-tasks/does_not_exist").status_code == 404
        assert (
            client.patch(
                "/api/v1/resume-tasks/does_not_exist/skills",
                json={"added": [], "removed": [], "updated": []},
            ).status_code
            == 404
        )


def test_resume_task_rejects_bad_pdf():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resume-tasks",
            files={"file": ("resume.pdf", b"not a real pdf", "application/pdf")},
        )
        # Upload succeeds but the task itself records the parse failure.
        assert response.status_code == 202
        body = response.json()["data"]
        assert body["status"] == "failed"
        assert body["error"]


def _build_scanned_pdf() -> bytes:
    """Render a PNG into a single-page PDF that has no text layer."""

    import fitz  # PyMuPDF

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    # A blank rectangle is enough — the point is there's no text layer.
    page.draw_rect(fitz.Rect(50, 50, 545, 792), color=(0.9, 0.9, 0.9), fill=(1, 1, 1))
    data = document.tobytes()
    document.close()
    return data


def test_scanned_pdf_routes_through_ocr_provider():
    calls: list[tuple[int, str]] = []

    def fake_ocr(image: bytes, mime: str) -> str:
        calls.append((len(image), mime))
        return "陈小雨\n精通 Python 与 RAG 检索链路"

    set_ocr_provider(CallableOcrProvider(fake_ocr, name="fake"))
    try:
        text = extract_resume_text("scanned.pdf", _build_scanned_pdf())
    finally:
        set_ocr_provider(None)
    assert "陈小雨" in text
    assert calls and calls[0][1] == "image/png"


def test_scanned_pdf_without_provider_reports_clear_error():
    set_ocr_provider(NullOcrProvider())
    try:
        with pytest.raises(ResumeTextError, match="OCR"):
            extract_resume_text("scanned.pdf", _build_scanned_pdf())
    finally:
        set_ocr_provider(None)


def test_null_ocr_provider_raises_on_recognize():
    provider = NullOcrProvider()
    assert provider.available is False
    with pytest.raises(OcrError):
        provider.recognize(b"x")


def test_http_ocr_provider_requires_endpoint():
    with pytest.raises(ValueError):
        HttpOcrProvider(endpoint="")


def test_ocr_response_extractor_handles_nested_shapes():
    assert _extract_text_from_response({"text": "hi"}) == "hi"
    assert _extract_text_from_response({"data": {"text": "hi"}}) == "hi"
    assert _extract_text_from_response({"result": [{"text": "a"}, {"text": "b"}]}) == "a\nb"
    assert _extract_text_from_response({"nope": 1}) == ""


def test_resume_store_singleton():
    store = get_resume_task_store()
    task = store.create("resume.txt", SAMPLE_RESUME.encode("utf-8"))
    assert store.get(task.id) is task
