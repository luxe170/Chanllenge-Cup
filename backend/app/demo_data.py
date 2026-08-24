from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


DASHBOARD_SUMMARY: dict[str, Any] = {
    "sourceCount": 8099,
    "validCount": 636,
    "emergingCount": 12,
    "changedCount": 47,
    "metrics": [
        {"name": "JD 解析准确率", "value": 93.6, "target": 90, "sampleCount": 120},
        {"name": "简历提取准确率", "value": 92.4, "target": 90, "sampleCount": 108},
        {"name": "人岗匹配准确率", "value": 91.8, "target": 90, "sampleCount": 105},
    ],
}

PANORAMA_NODES: list[dict[str, Any]] = [
    {"id": "position_cluster_ai", "name": "人工智能研发岗位簇", "type": "cluster", "sampleCount": 124, "confidence": 0.91},
    {"id": "position_cluster_software", "name": "软件研发岗位簇", "type": "cluster", "sampleCount": 286, "confidence": 0.9},
    {"id": "position_cluster_data", "name": "数据技术岗位簇", "type": "cluster", "sampleCount": 226, "confidence": 0.88},
    {"id": "pos_agent", "name": "AI Agent 研发工程师", "type": "position", "trend": "new", "sampleCount": 52, "firstSeen": "2025-03-01", "confidence": 0.93},
    {"id": "pos_llm", "name": "大模型应用工程师", "type": "position", "trend": "rising", "sampleCount": 87, "firstSeen": "2024-08-12", "confidence": 0.91},
    {"id": "pos_multimodal", "name": "多模态应用工程师", "type": "position", "trend": "new", "sampleCount": 34, "firstSeen": "2025-05-18", "confidence": 0.86},
    {"id": "pos_java", "name": "Java 开发工程师", "type": "position", "trend": "stable", "sampleCount": 161, "firstSeen": "2023-01-06", "confidence": 0.94},
    {"id": "pos_frontend", "name": "前端研发工程师", "type": "position", "trend": "stable", "sampleCount": 125, "firstSeen": "2023-02-15", "confidence": 0.92},
    {"id": "pos_data", "name": "数据研发工程师", "type": "position", "trend": "rising", "sampleCount": 96, "firstSeen": "2023-03-22", "confidence": 0.9},
    {"id": "pos_analyst", "name": "数据分析工程师", "type": "position", "trend": "stable", "sampleCount": 76, "firstSeen": "2023-04-01", "confidence": 0.88},
    {"id": "skill_python_panorama", "name": "Python", "type": "skill", "trend": "stable", "weight": 0.92},
    {"id": "skill_rag_panorama", "name": "RAG", "type": "skill", "trend": "rising", "weight": 0.84},
    {"id": "skill_langchain_panorama", "name": "LangChain", "type": "skill", "trend": "rising", "weight": 0.81},
    {"id": "skill_vlm_panorama", "name": "视觉语言模型", "type": "skill", "trend": "new", "weight": 0.76},
    {"id": "skill_java_panorama", "name": "Java", "type": "skill", "trend": "stable", "weight": 0.91},
    {"id": "skill_react_panorama", "name": "React", "type": "skill", "trend": "stable", "weight": 0.87},
    {"id": "skill_typescript_panorama", "name": "TypeScript", "type": "skill", "trend": "rising", "weight": 0.74},
    {"id": "skill_sql_panorama", "name": "SQL", "type": "skill", "trend": "stable", "weight": 0.89},
    {"id": "skill_spark_panorama", "name": "Spark", "type": "skill", "trend": "stable", "weight": 0.78},
    {"id": "skill_bi_panorama", "name": "BI 分析", "type": "skill", "trend": "declining", "weight": 0.62},
]

PANORAMA_EDGES: list[dict[str, Any]] = [
    {"source": "pos_agent", "target": "position_cluster_ai", "relationship": "BELONGS_TO"},
    {"source": "pos_llm", "target": "position_cluster_ai", "relationship": "BELONGS_TO"},
    {"source": "pos_multimodal", "target": "position_cluster_ai", "relationship": "BELONGS_TO"},
    {"source": "pos_java", "target": "position_cluster_software", "relationship": "BELONGS_TO"},
    {"source": "pos_frontend", "target": "position_cluster_software", "relationship": "BELONGS_TO"},
    {"source": "pos_data", "target": "position_cluster_data", "relationship": "BELONGS_TO"},
    {"source": "pos_analyst", "target": "position_cluster_data", "relationship": "BELONGS_TO"},
    {"source": "pos_agent", "target": "skill_python_panorama", "relationship": "REQUIRES", "requirementType": "required", "weight": 0.92, "confidence": 0.94},
    {"source": "pos_agent", "target": "skill_rag_panorama", "relationship": "REQUIRES", "requirementType": "preferred", "weight": 0.84, "confidence": 0.93},
    {"source": "pos_llm", "target": "skill_rag_panorama", "relationship": "REQUIRES", "requirementType": "required", "weight": 0.88, "confidence": 0.92},
    {"source": "pos_llm", "target": "skill_langchain_panorama", "relationship": "REQUIRES", "requirementType": "preferred", "weight": 0.81, "confidence": 0.9},
    {"source": "pos_multimodal", "target": "skill_vlm_panorama", "relationship": "REQUIRES", "requirementType": "required", "weight": 0.76, "confidence": 0.86},
    {"source": "pos_java", "target": "skill_java_panorama", "relationship": "REQUIRES", "requirementType": "required", "weight": 0.91, "confidence": 0.95},
    {"source": "pos_frontend", "target": "skill_react_panorama", "relationship": "REQUIRES", "requirementType": "required", "weight": 0.87, "confidence": 0.93},
    {"source": "pos_frontend", "target": "skill_typescript_panorama", "relationship": "REQUIRES", "requirementType": "preferred", "weight": 0.74, "confidence": 0.87},
    {"source": "pos_data", "target": "skill_sql_panorama", "relationship": "REQUIRES", "requirementType": "required", "weight": 0.89, "confidence": 0.94},
    {"source": "pos_data", "target": "skill_spark_panorama", "relationship": "REQUIRES", "requirementType": "preferred", "weight": 0.78, "confidence": 0.88},
    {"source": "pos_analyst", "target": "skill_sql_panorama", "relationship": "REQUIRES", "requirementType": "required", "weight": 0.82, "confidence": 0.9},
    {"source": "pos_analyst", "target": "skill_bi_panorama", "relationship": "REQUIRES", "requirementType": "preferred", "weight": 0.62, "confidence": 0.82},
]

SKILL_REVERSE_NODES: list[dict[str, Any]] = [
    {"id": "reverse_stack_ai", "name": "人工智能技术栈", "type": "stack", "sampleCount": 318, "confidence": 0.92},
    {"id": "reverse_cluster_llm", "name": "大模型应用开发技能簇", "type": "cluster", "sampleCount": 166, "confidence": 0.9},
    {"id": "reverse_cluster_knowledge", "name": "知识检索与工程技能簇", "type": "cluster", "sampleCount": 152, "confidence": 0.89},
    {"id": "reverse_langchain", "name": "LangChain", "type": "skill", "trend": "rising", "weight": 0.81},
    {"id": "reverse_agent_skill", "name": "工具调用", "type": "skill", "trend": "new", "weight": 0.76},
    {"id": "reverse_rag", "name": "RAG", "type": "skill", "trend": "rising", "weight": 0.84},
    {"id": "reverse_vector", "name": "向量数据库", "type": "skill", "trend": "stable", "weight": 0.73},
    {"id": "reverse_agent", "name": "AI Agent 研发工程师", "type": "position", "trend": "new", "weight": 0.84, "sampleCount": 52},
    {"id": "reverse_llm", "name": "大模型应用工程师", "type": "position", "trend": "rising", "weight": 0.91, "sampleCount": 87},
    {"id": "reverse_knowledge", "name": "知识工程工程师", "type": "position", "trend": "rising", "weight": 0.88, "sampleCount": 46},
    {"id": "reverse_search", "name": "搜索算法工程师", "type": "position", "trend": "stable", "weight": 0.76, "sampleCount": 61},
    {"id": "reverse_product", "name": "AI 产品工程师", "type": "position", "trend": "new", "weight": 0.63, "sampleCount": 29},
]

SKILL_REVERSE_EDGES: list[dict[str, Any]] = [
    {"source": "reverse_cluster_llm", "target": "reverse_stack_ai", "relationship": "BELONGS_TO"},
    {"source": "reverse_cluster_knowledge", "target": "reverse_stack_ai", "relationship": "BELONGS_TO"},
    {"source": "reverse_langchain", "target": "reverse_cluster_llm", "relationship": "BELONGS_TO"},
    {"source": "reverse_agent_skill", "target": "reverse_cluster_llm", "relationship": "BELONGS_TO"},
    {"source": "reverse_rag", "target": "reverse_cluster_knowledge", "relationship": "BELONGS_TO"},
    {"source": "reverse_vector", "target": "reverse_cluster_knowledge", "relationship": "BELONGS_TO"},
    {"source": "reverse_agent", "target": "reverse_langchain", "relationship": "REQUIRES", "requirementType": "required", "weight": 0.84, "confidence": 0.91},
    {"source": "reverse_agent", "target": "reverse_agent_skill", "relationship": "REQUIRES", "requirementType": "preferred", "weight": 0.78, "confidence": 0.89},
    {"source": "reverse_llm", "target": "reverse_langchain", "relationship": "REQUIRES", "requirementType": "required", "weight": 0.91, "confidence": 0.93},
    {"source": "reverse_llm", "target": "reverse_rag", "relationship": "REQUIRES", "requirementType": "preferred", "weight": 0.88, "confidence": 0.92},
    {"source": "reverse_knowledge", "target": "reverse_rag", "relationship": "REQUIRES", "requirementType": "required", "weight": 0.88, "confidence": 0.9},
    {"source": "reverse_knowledge", "target": "reverse_vector", "relationship": "REQUIRES", "requirementType": "preferred", "weight": 0.82, "confidence": 0.88},
    {"source": "reverse_search", "target": "reverse_rag", "relationship": "REQUIRES", "requirementType": "required", "weight": 0.76, "confidence": 0.86},
    {"source": "reverse_product", "target": "reverse_agent_skill", "relationship": "REQUIRES", "requirementType": "preferred", "weight": 0.63, "confidence": 0.82},
]

REVIEW_ITEMS: list[dict[str, Any]] = [
    {
        "id": "r1",
        "type": "新岗位",
        "title": "具身智能数据工程师",
        "description": "技能组合与机器人数据工程岗位差异度 43%，连续三个时间窗口增长。",
        "confidence": 0.88,
        "sources": ["字节跳动", "华为", "阿里巴巴"],
        "createdAt": "10 分钟前",
        "status": "pending",
    },
    {
        "id": "r2",
        "type": "能力变更",
        "title": "大模型应用工程师新增“上下文工程”",
        "description": "近两个月出现频率由 8% 上升至 36%，建议标记为加分技能。",
        "confidence": 0.91,
        "sources": ["腾讯", "字节跳动", "美团"],
        "createdAt": "35 分钟前",
        "status": "pending",
    },
    {
        "id": "r3",
        "type": "技能归一",
        "title": "Agentic Workflow → 智能体工作流",
        "description": "发现 4 种中英文别名，建议合并至现有标准技能节点。",
        "confidence": 0.96,
        "sources": ["技能词典", "JD 语料"],
        "createdAt": "1 小时前",
        "status": "pending",
    },
]

RESUME_TASK: dict[str, Any] = {
    "taskId": "demo_resume_task",
    "status": "completed",
    "progress": 100,
    "error": "",
    "result": {
        "candidateName": "陈小雨",
        "targetPosition": "AI Agent 研发工程师",
        "education": "硕士 · 计算机科学",
        "experienceYears": 3,
        "direction": "算法与 AI 应用方向",
        "completeness": 94,
        "skills": [
            {"name": "Python", "level": "精通", "source": "项目经历：智能问答系统", "confidence": 0.98},
            {"name": "大语言模型", "level": "掌握", "source": "专业技能", "confidence": 0.94},
            {"name": "LangChain", "level": "熟悉", "source": "实习经历：智能助手", "confidence": 0.93},
            {"name": "向量数据库", "level": "掌握", "source": "项目经历：企业知识库", "confidence": 0.91},
            {"name": "Docker", "level": "熟悉", "source": "专业技能", "confidence": 0.89},
            {"name": "FastAPI", "level": "掌握", "source": "项目经历：模型服务化", "confidence": 0.95},
        ],
        "experiences": [
            {
                "period": "2025.03 — 至今",
                "title": "企业知识库智能问答系统",
                "description": "负责 RAG 链路、向量检索与模型服务化，离线评测准确率提升 18%。",
                "skills": ["RAG", "LangChain", "FastAPI"],
            },
            {
                "period": "2024.06 — 2025.01",
                "title": "多轮对话助手",
                "description": "参与提示词工程、会话状态管理及工具调用模块开发。",
                "skills": ["大语言模型", "Python"],
            },
        ],
    },
}

MATCH_REPORT: dict[str, Any] = {
    "matchId": "demo_match",
    "resumeTaskId": "demo_resume_task",
    "positionId": "pos_ai_agent_engineer",
    "positionName": "AI Agent 研发工程师",
    "candidateName": "陈小雨",
    "overallScore": 82,
    "fitLevel": "高度匹配",
    "benchmarkRank": "前 18%",
    "benchmarkSampleCount": 426,
    "summary": "已覆盖大部分核心要求，重点补齐 2 项能力可显著提升竞争力。",
    "dimensions": [
        {"name": "必备技能", "value": 88, "color": "#6ee7f9"},
        {"name": "加分技能", "value": 61, "color": "#a78bfa"},
        {"name": "项目经验", "value": 82, "color": "#5ee7a8"},
        {"name": "技能深度", "value": 76, "color": "#fbbf73"},
    ],
    "strengths": ["Python", "大语言模型", "向量数据库", "FastAPI"],
    "gaps": [
        {"name": "RAG 评测", "priority": "高", "requirement": "必备技能", "current": "未识别", "weight": 84},
        {"name": "多智能体协作", "priority": "高", "requirement": "加分技能", "current": "未识别", "weight": 72},
        {"name": "工具调用", "priority": "中", "requirement": "必备技能", "current": "基础了解", "weight": 68},
        {"name": "模型安全护栏", "priority": "中", "requirement": "加分技能", "current": "未识别", "weight": 59},
    ],
    "evidence": {"skillEvidenceCount": 14, "projectEvidenceCount": 2, "jobSampleCount": 52},
    "suggestions": [
        "突出企业知识库项目中的评测结果",
        "补充工具调用与任务规划实践",
        "将模型服务经验关联到工程稳定性",
    ],
    "learningPath": [
        {"stage": 1, "title": "补齐核心方法", "duration": "1–2 周", "skills": ["RAG 评测", "检索质量分析"], "goal": "能够建立可量化的检索与生成评测集"},
        {"stage": 2, "title": "掌握智能体编排", "duration": "2–3 周", "skills": ["工具调用", "任务规划", "状态管理"], "goal": "独立完成具备工具调用能力的单智能体应用"},
        {"stage": 3, "title": "进阶多智能体系统", "duration": "3–4 周", "skills": ["多智能体协作", "记忆机制", "安全护栏"], "goal": "完成可观测、可评测的多智能体工作流项目"},
    ],
}


def fresh(value: Any) -> Any:
    return deepcopy(value)


def graph_version() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d.1")
