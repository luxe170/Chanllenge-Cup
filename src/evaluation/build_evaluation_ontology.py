#!/usr/bin/env python3
"""Build versioned position/skill registries for JD evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.evaluation.generate_jd_ground_truth_draft import SKILL_LEXICON


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DRAFT = PROJECT_ROOT / "data" / "evaluation" / "jd_ground_truth_draft_120.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "ontology"
VERSION = "v1"


POSITION_CANONICALIZATION = {
    "AI产品经理": "AI产品经理",
    "法务专员": "法务专员",
    "运营专员": "运营专员",
    "招聘经理": "招聘经理",
    "需求计划经理": "需求计划经理",
    "AI Agent工程师": "AI Agent工程师",
    "多模态大模型工程师": "多模态大模型工程师",
    "推荐算法工程师": "推荐算法工程师",
    "广告算法工程师": "广告算法工程师",
    "语音识别算法工程师": "语音算法工程师",
    "语音算法工程师": "语音算法工程师",
    "大模型推理工程师": "大模型推理工程师",
    "大模型算法工程师": "大模型算法工程师",
    "强化学习算法工程师": "强化学习算法工程师",
    "算法研究员": "算法研究员",
    "算法工程师": "算法工程师",
    "测试开发工程师": "测试开发工程师",
    "SRE/运维工程师": "SRE/运维工程师",
    "数据库工程师": "数据库工程师",
    "网络工程师": "网络工程师",
    "安全工程师": "安全工程师",
    "客户端开发工程师": "客户端开发工程师",
    "后端开发工程师": "后端开发工程师",
    "全栈开发工程师": "全栈开发工程师",
    "平台开发工程师": "平台开发工程师",
    "游戏引擎工程师": "游戏引擎工程师",
    "硬件工程师": "硬件工程师",
    "编译优化工程师": "编译优化工程师",
    "软件开发工程师": "软件开发工程师",
    "数据智多星-法律方向": "法律数据工程师",
    "数据生成实习生": "数据工程师",
    "后训练合版/OPD方向-Qwen基础模型": "大模型算法工程师",
    "RISC-V生态建设工程师-基础库与工具链": "编译与工具链工程师",
    "数据挖掘工程师-今日头条": "数据挖掘工程师",
    "系统性能交付工程师-豆包手机助手": "系统性能工程师",
    "AI质量效能负责人 - 飞书": "AI质量效能工程师",
    "服务器交付专家-基础设施": "基础设施工程师",
    "自动化系统工程师-AI制药": "自动化系统工程师",
    "UE5游戏AI高级研究员-主机射击": "游戏AI研究员",
    "AI算子性能优化专家": "AI编译优化工程师",
    "CodeAgent后训练方向研究员(数据分析与ToSQL方向)": "AI Agent研究员",
    "KPL王者荣耀职业联赛电竞宣发经理": "市场宣发经理",
    "多媒体实验室-多媒体标准专家": "多媒体技术专家",
    "Multimodal Reinforcement Learning Algorithm Researcher 107777": "多模态强化学习研究员",
    "腾讯云 EdgeOne-推理平台高级工程师": "大模型推理工程师",
    "高级GPU推理工程师": "大模型推理工程师",
    "高性能计算专家": "高性能计算工程师",
    "机器学习平台调度工程师\u200b\u200b": "机器学习平台工程师",
}

POSITION_CATEGORY_RULES = (
    (("法务", "法律"), "non_target_legal", "法务与法律"),
    (("运营", "宣发", "招聘", "需求计划"), "non_target_business", "非技术业务岗位"),
    (("产品经理",), "ai_product", "AI产品"),
    (("游戏",), "game_graphics", "游戏与图形"),
    (("硬件",), "hardware_system", "硬件与智能系统"),
    (("安全", "风控"), "security", "安全与风控"),
    (("网络", "基础设施", "SRE", "性能", "高性能计算"), "cloud_infra", "云计算与基础设施"),
    (("数据", "数据库"), "data", "数据技术"),
    (("后端", "客户端", "全栈", "软件", "平台", "编译", "自动化", "质量", "测试"), "software", "软件工程"),
    (("AI", "大模型", "算法", "多模态", "语音", "推荐", "广告", "强化学习", "机器学习"), "ai", "人工智能"),
)

SKILL_CATEGORIES = {
    "programming": {"Python", "Java", "C++", "C", "Go", "Rust", "JavaScript", "TypeScript", "SQL", "Shell", "Git", "数据结构与算法"},
    "ai_model": {"PyTorch", "TensorFlow", "深度学习", "机器学习", "强化学习", "自然语言处理", "计算机视觉", "大语言模型", "多模态", "AIGC", "RAG", "AI Agent", "提示词工程", "模型微调", "模型评测", "模型推理", "模型量化", "模型蒸馏", "推荐系统", "搜索算法", "广告算法", "语音识别", "语音合成", "图像生成", "视频生成"},
    "ai_infra": {"CUDA", "GPU", "NPU", "机器学习平台", "性能优化"},
    "data": {"数据挖掘", "数据分析", "MySQL", "PostgreSQL", "Redis", "MongoDB", "Elasticsearch", "Hadoop", "Spark", "Flink", "Hive", "Kafka", "数据库", "数据治理", "数据标注", "概率统计", "线性代数"},
    "cloud_backend": {"Linux", "Docker", "Kubernetes", "微服务", "分布式系统", "云计算", "网络协议", "计算机网络", "操作系统"},
    "system_hardware": {"编译原理", "LLVM", "ROS", "物联网", "嵌入式系统", "边缘计算", "硬件电路设计", "ARM架构", "x86架构", "EMC设计", "信号完整性"},
    "media_game": {"音视频", "WebRTC", "Unreal Engine", "Unity", "游戏引擎", "OpenGL", "Vulkan"},
    "quality_security": {"软件测试", "信息安全", "渗透测试", "攻防", "风控"},
}

CATEGORY_NAMES = {
    "programming": "编程与工程基础", "ai_model": "人工智能模型与算法",
    "ai_infra": "AI基础设施", "data": "数据技术",
    "cloud_backend": "云计算与后端系统", "system_hardware": "系统与硬件",
    "media_game": "多媒体与游戏", "quality_security": "质量与安全",
}

PARENT_SKILLS = {
    "MySQL": "数据库", "PostgreSQL": "数据库", "MongoDB": "数据库",
    "模型量化": "模型推理", "模型蒸馏": "机器学习",
    "语音识别": "自然语言处理", "语音合成": "自然语言处理",
    "图像生成": "AIGC", "视频生成": "AIGC",
}


def entity_id(prefix: str, name: str) -> str:
    digest = hashlib.sha256(name.strip().lower().encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def normalized_alias(value: str) -> str:
    return re.sub(r"[\s\-—_/（）()【】]+", "", value).lower()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def position_category(name: str) -> tuple[str, str]:
    for keywords, category_id, category_name in POSITION_CATEGORY_RULES:
        if any(keyword.lower() in name.lower() for keyword in keywords):
            return category_id, category_name
    return "other", "其他岗位"


def build(draft: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    draft_positions = {item["annotation"]["standard_position"] for item in draft}
    missing = draft_positions - set(POSITION_CANONICALIZATION)
    if missing:
        raise ValueError(f"unmapped positions: {sorted(missing)}")

    canonical_positions = sorted({POSITION_CANONICALIZATION[name] for name in draft_positions})
    position_ids = {name: entity_id("position", name) for name in canonical_positions}
    position_registry = []
    for name in canonical_positions:
        category_id, category_name = position_category(name)
        scopes = [
            item["annotation"]["scope"] for item in draft
            if POSITION_CANONICALIZATION[item["annotation"]["standard_position"]] == name
        ]
        scope = Counter(scopes).most_common(1)[0][0]
        position_registry.append({
            "id": position_ids[name], "name": name, "normalized_name": normalized_alias(name),
            "category_id": category_id, "category_name": category_name,
            "scope": scope, "status": "active", "version": VERSION,
        })

    position_alias_candidates: dict[str, set[str]] = defaultdict(set)
    for item in draft:
        draft_name = item["annotation"]["standard_position"]
        canonical_name = POSITION_CANONICALIZATION[draft_name]
        position_alias_candidates[canonical_name].update((canonical_name, draft_name, item["raw"]["title"]))
    position_aliases = []
    seen_position_aliases: set[str] = set()
    for canonical_name in sorted(position_alias_candidates):
        for alias in sorted(position_alias_candidates[canonical_name]):
            key = normalized_alias(alias)
            if not key or key in seen_position_aliases:
                continue
            seen_position_aliases.add(key)
            position_aliases.append({
                "position_id": position_ids[canonical_name], "alias": alias,
                "normalized_alias": key, "source": "jd_ground_truth_draft",
                "review_status": "pending", "version": VERSION,
            })

    skill_names = sorted({skill["name"] for item in draft for skill in item["annotation"]["skills"]})
    skill_ids = {name: entity_id("skill", name) for name in skill_names}
    skill_category_by_name = {
        name: category for category, names in SKILL_CATEGORIES.items() for name in names
    }
    uncategorized = set(skill_names) - set(skill_category_by_name)
    if uncategorized:
        raise ValueError(f"uncategorized skills: {sorted(uncategorized)}")
    skill_registry = []
    for name in skill_names:
        category_id = skill_category_by_name[name]
        parent = PARENT_SKILLS.get(name)
        skill_registry.append({
            "id": skill_ids[name], "name": name, "normalized_name": normalized_alias(name),
            "category_id": category_id, "category_name": CATEGORY_NAMES[category_id],
            "parent_skill_id": skill_ids.get(parent), "status": "active", "version": VERSION,
        })

    skill_aliases = []
    seen_skill_aliases: set[str] = set()
    for name in skill_names:
        aliases = {name, *SKILL_LEXICON.get(name, ())}
        for alias in sorted(aliases):
            key = normalized_alias(alias)
            if not key or key in seen_skill_aliases:
                continue
            seen_skill_aliases.add(key)
            skill_aliases.append({
                "skill_id": skill_ids[name], "alias": alias, "normalized_alias": key,
                "source": "evaluation_annotation_lexicon", "review_status": "pending", "version": VERSION,
            })

    normalized_ground_truth = []
    for item in draft:
        normalized = json.loads(json.dumps(item, ensure_ascii=False))
        draft_name = item["annotation"]["standard_position"]
        canonical_name = POSITION_CANONICALIZATION[draft_name]
        normalized["annotation"]["position_id"] = position_ids[canonical_name]
        normalized["annotation"]["standard_position"] = canonical_name
        for skill in normalized["annotation"]["skills"]:
            skill["skill_id"] = skill_ids[skill["name"]]
        normalized["annotation_meta"]["ontology_version"] = VERSION
        normalized_ground_truth.append(normalized)

    return {
        "position_registry": position_registry, "position_aliases": position_aliases,
        "skill_registry": skill_registry, "skill_aliases": skill_aliases,
        "normalized_ground_truth": normalized_ground_truth,
    }


def write_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for item in items:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")


def write_outputs(result: dict[str, list[dict[str, Any]]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for key in ("position_registry", "position_aliases", "skill_registry", "skill_aliases"):
        write_jsonl(output_dir / f"{key}_{VERSION}.jsonl", result[key])
    write_jsonl(
        output_dir.parent / f"jd_ground_truth_normalized_120_{VERSION}.jsonl",
        result["normalized_ground_truth"],
    )
    metadata = {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "draft_pending_human_review",
        "position_count": len(result["position_registry"]),
        "position_alias_count": len(result["position_aliases"]),
        "skill_count": len(result["skill_registry"]),
        "skill_alias_count": len(result["skill_aliases"]),
        "ground_truth_count": len(result["normalized_ground_truth"]),
    }
    (output_dir / f"ontology_metadata_{VERSION}.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = build(load_jsonl(args.draft))
    write_outputs(result, args.output_dir)
    print(json.dumps({key: len(value) for key, value in result.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
