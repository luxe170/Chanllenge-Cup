from __future__ import annotations

import io
import re
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from backend.app.demo_data import RESUME_TASK, fresh


_resume_tasks: dict[str, dict] = {}


SKILL_TERMS = {
    "Python": ["python"], "Java": ["java"], "C++": ["c++"], "SQL": ["sql", "mysql"],
    "大语言模型": ["大语言模型", "大模型", "llm"], "RAG": ["rag", "检索增强"],
    "LangChain": ["langchain"], "PyTorch": ["pytorch"], "TensorFlow": ["tensorflow"],
    "FastAPI": ["fastapi"], "React": ["react"], "TypeScript": ["typescript"],
    "Docker": ["docker"], "Kubernetes": ["kubernetes", "k8s"], "Spring Boot": ["spring boot", "springboot"],
    "Spark": ["spark"], "Flink": ["flink"], "Linux": ["linux"], "Git": ["git"],
    "多智能体协作": ["多智能体", "multi-agent"], "Prompt 工程": ["prompt", "提示词"],
}


def _extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages).strip()
        except Exception as exc:
            raise ValueError("PDF 无法解析，可能是扫描件或文件已损坏") from exc
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            return "\n".join("".join(node.itertext()) for node in root.iter() if node.tag.endswith("}p")).strip()
        except Exception as exc:
            raise ValueError("Word 文件无法解析或已经损坏") from exc
    if suffix in {".txt", ".md"}:
        return content.decode("utf-8", errors="replace").strip()
    if suffix == ".doc":
        raise ValueError("暂不支持旧版 .doc，请另存为 .docx 或 PDF")
    raise ValueError("仅支持 PDF、DOCX、TXT 简历")


def _profile_from_text(filename: str, text: str) -> dict:
    if len(text.strip()) < 20:
        raise ValueError("没有从简历中提取到足够文本；扫描版 PDF 请先进行 OCR")
    lowered = text.lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    filename_name = re.sub(r"(?:简历|resume|求职|[_-].*)", "", Path(filename).stem, flags=re.I).strip()
    name_match = re.search(r"(?:姓名|name)\s*[:：]\s*([\u4e00-\u9fff]{2,4}|[A-Za-z ]{2,30})", text, re.I)
    candidate_name = (name_match.group(1).strip() if name_match else filename_name) or "未识别姓名"
    education = next((degree for degree in ("博士", "硕士", "本科", "大专") if degree in text), "未识别学历")
    years = [int(value) for value in re.findall(r"(\d{1,2})\s*年(?:工作|项目|开发|相关)?经验", text)]
    experience_years = max(years, default=0)
    target_match = re.search(r"(?:求职意向|目标岗位|意向岗位)\s*[:：]\s*([^\n]{2,30})", text)
    target = target_match.group(1).strip() if target_match else "待选择目标岗位"

    skills = []
    for name, aliases in SKILL_TERMS.items():
        hits = [alias for alias in aliases if alias.lower() in lowered]
        if not hits:
            continue
        first_line = next((line for line in lines if any(alias.lower() in line.lower() for alias in aliases)), "简历技能描述")
        frequency = sum(lowered.count(alias.lower()) for alias in aliases)
        level = "精通" if any(word in first_line for word in ("精通", "主导", "深入")) else "掌握" if frequency >= 2 else "熟悉"
        skills.append({"name": name, "level": level, "source": first_line[:80], "confidence": round(min(0.98, 0.78 + frequency * 0.05), 2)})

    experience_lines = [line for line in lines if any(word in line for word in ("项目", "实习", "工作经历", "负责"))][:3]
    experiences = [
        {"period": "简历原文", "title": line[:28], "description": line[:160],
         "skills": [skill["name"] for skill in skills if skill["name"].lower() in line.lower()][:5]}
        for line in experience_lines
    ]
    completeness = min(98, 45 + min(35, len(skills) * 5) + (10 if candidate_name != "未识别姓名" else 0) + (8 if education != "未识别学历" else 0))
    direction = "AI 与算法方向" if any(name in {"大语言模型", "RAG", "PyTorch", "TensorFlow"} for name in [s["name"] for s in skills]) else "软件与数据工程方向"
    return {"candidateName": candidate_name, "targetPosition": target, "education": education,
            "experienceYears": experience_years, "direction": direction, "completeness": completeness,
            "skills": skills, "experiences": experiences}


def create_resume_task(filename: str = "", content: bytes = b"") -> dict:
    task_id = f"resume_{uuid.uuid4().hex[:10]}"
    result = _profile_from_text(filename, _extract_text(filename, content))
    task = {"taskId": task_id, "filename": filename, "status": "completed", "progress": 100, "error": "", "result": result}
    _resume_tasks[task["taskId"]] = task
    return {"taskId": task["taskId"], "status": task["status"], "progress": task["progress"]}


def get_resume_task(task_id: str) -> dict:
    if task_id in _resume_tasks:
        return fresh(_resume_tasks[task_id])
    if task_id == "demo_resume_task":
        return fresh(RESUME_TASK)
    raise KeyError(f"unknown resume task: {task_id}")


def update_resume_skills(task_id: str, skills: list[dict]) -> dict:
    task = get_resume_task(task_id)
    task.setdefault("result", {})
    task["result"]["skills"] = skills
    task["status"] = "completed"
    task["progress"] = 100
    _resume_tasks[task["taskId"]] = task
    return {"taskId": task["taskId"], "skills": fresh(skills)}
