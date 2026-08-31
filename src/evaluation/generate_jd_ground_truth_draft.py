#!/usr/bin/env python3
"""Generate a reviewable first-annotator draft for the selected 120 JDs.

This output is deliberately named ``draft``: it becomes formal ground truth only
after an independent second annotator reviews every row and resolves conflicts.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from src.processing.clean_multisource_jobs import normalize_record, read_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "evaluation" / "jd_eval_120_manifest.jsonl"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation"

PREFERRED_MARKERS = ("优先", "加分", "bonus", "preferred", "plus")

# Independent evaluation annotation vocabulary. Only explicit text mentions are
# labelled; no skill is inferred merely from a job title category.
SKILL_LEXICON: dict[str, tuple[str, ...]] = {
    "Python": ("Python",), "Java": ("Java",), "C++": ("C++", "CPP"),
    "C": ("C语言",), "Go": ("Golang", "Go语言"), "Rust": ("Rust",),
    "JavaScript": ("JavaScript",), "TypeScript": ("TypeScript",),
    "SQL": ("SQL",), "Shell": ("Shell", "Bash"), "Linux": ("Linux",),
    "Git": ("Git",), "数据结构与算法": ("数据结构", "算法基础"),
    "PyTorch": ("PyTorch",), "TensorFlow": ("TensorFlow",),
    "深度学习": ("深度学习",), "机器学习": ("机器学习",),
    "强化学习": ("强化学习", "Reinforcement Learning", "RL"),
    "自然语言处理": ("自然语言处理", "NLP"),
    "计算机视觉": ("计算机视觉", "Computer Vision", "CV"),
    "大语言模型": ("大语言模型", "大模型", "LLM"),
    "多模态": ("多模态", "VLM"), "AIGC": ("AIGC",),
    "RAG": ("RAG", "检索增强生成"), "AI Agent": ("AI Agent", "Agentic", "智能体"),
    "提示词工程": ("提示词", "Prompt Engineering"),
    "模型微调": ("模型微调", "Fine-tuning", "SFT"),
    "模型评测": ("模型评测", "模型评价", "Benchmark"),
    "模型推理": ("模型推理", "推理加速", "推理优化", "Inference"),
    "模型量化": ("模型量化", "量化压缩"), "模型蒸馏": ("模型蒸馏", "蒸馏"),
    "CUDA": ("CUDA",), "GPU": ("GPU",), "NPU": ("NPU",),
    "机器学习平台": ("机器学习平台", "ML平台", "MLOps"),
    "推荐系统": ("推荐系统", "推荐算法", "召回", "精排", "Ranking"),
    "搜索算法": ("搜索算法", "搜索系统", "搜索引擎"),
    "广告算法": ("广告算法", "广告系统", "广告投放"),
    "数据挖掘": ("数据挖掘",), "数据分析": ("数据分析",),
    "MySQL": ("MySQL",), "PostgreSQL": ("PostgreSQL",), "Redis": ("Redis",),
    "MongoDB": ("MongoDB",), "Elasticsearch": ("Elasticsearch", "ElasticSearch"),
    "Hadoop": ("Hadoop",), "Spark": ("Spark",), "Flink": ("Flink",),
    "Hive": ("Hive",), "Kafka": ("Kafka",),
    "Docker": ("Docker",), "Kubernetes": ("Kubernetes", "K8s"),
    "微服务": ("微服务",), "分布式系统": ("分布式系统", "分布式架构"),
    "数据库": ("数据库",), "云计算": ("云计算", "云原生"),
    "网络协议": ("TCP/IP", "HTTP", "QUIC", "网络协议"),
    "计算机网络": ("计算机网络",), "操作系统": ("操作系统",),
    "编译原理": ("编译原理", "编译器"), "LLVM": ("LLVM",),
    "ROS": ("ROS", "ROS2"), "物联网": ("物联网", "IoT"),
    "嵌入式系统": ("嵌入式",), "边缘计算": ("边缘计算", "边缘侧"),
    "硬件电路设计": ("硬件电路", "原理图设计", "数电模电"),
    "ARM架构": ("ARM",), "x86架构": ("X86", "x86"),
    "EMC设计": ("EMC",), "信号完整性": ("信号完整性",),
    "音视频": ("音视频",), "WebRTC": ("WebRTC",),
    "语音识别": ("语音识别", "ASR"), "语音合成": ("语音合成", "TTS"),
    "图像生成": ("图像生成",), "视频生成": ("视频生成",),
    "Unreal Engine": ("Unreal Engine", "UE4", "UE5"), "Unity": ("Unity",),
    "游戏引擎": ("游戏引擎",), "OpenGL": ("OpenGL",), "Vulkan": ("Vulkan",),
    "软件测试": ("软件测试", "测试开发", "自动化测试"),
    "性能优化": ("性能优化", "性能调优"), "信息安全": ("信息安全", "网络安全"),
    "渗透测试": ("渗透测试",), "攻防": ("攻防",), "风控": ("风控",),
    "数据治理": ("数据治理",), "数据标注": ("数据标注",),
    "概率统计": ("概率统计", "统计学"), "线性代数": ("线性代数",),
}

OUT_OF_SCOPE_TITLES = ("法务", "社群运营", "游戏运营", "宣发经理", "招聘经理", "需求计划经理")
REVIEW_SCOPE_TITLES = ("产品经理", "数据标注运营")

POSITION_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("AI产品",), "AI产品经理"), (("法务",), "法务专员"),
    (("运营",), "运营专员"), (("招聘经理",), "招聘经理"),
    (("需求计划",), "需求计划经理"), (("AI Agent", "Agentic", "智能体"), "AI Agent工程师"),
    (("多模态",), "多模态大模型工程师"), (("推荐",), "推荐算法工程师"),
    (("广告",), "广告算法工程师"), (("语音识别",), "语音识别算法工程师"),
    (("语音大模型", "TTS"), "语音算法工程师"), (("大模型推理",), "大模型推理工程师"),
    (("大模型", "LLM", "模型评测", "模型生成"), "大模型算法工程师"),
    (("强化学习",), "强化学习算法工程师"), (("算法研究", "研究科学家"), "算法研究员"),
    (("算法",), "算法工程师"), (("测试开发", "安全测试"), "测试开发工程师"),
    (("SRE", "运维"), "SRE/运维工程师"), (("数据库", "RDS"), "数据库工程师"),
    (("网络",), "网络工程师"), (("安全", "攻防", "风控"), "安全工程师"),
    (("客户端", "Gameplay"), "客户端开发工程师"), (("后台", "后端", "服务端"), "后端开发工程师"),
    (("全栈",), "全栈开发工程师"), (("平台开发",), "平台开发工程师"),
    (("引擎",), "游戏引擎工程师"), (("硬件", "芯片"), "硬件工程师"),
    (("编译",), "编译优化工程师"), (("开发工程师", "研发工程师"), "软件开发工程师"),
)

SCENARIO_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("电商", "商家", "商品"), "电商"), (("广告",), "数字广告"),
    (("搜索",), "智能搜索"), (("推荐",), "内容与商品推荐"),
    (("游戏", "UE4", "UE5", "Gameplay"), "游戏研发"),
    (("视频", "音视频", "直播"), "音视频与直播"), (("语音", "TTS", "ASR"), "智能语音"),
    (("风控", "内容安全", "安全"), "安全与风险治理"),
    (("数据库", "MySQL"), "数据库与数据基础设施"),
    (("网络",), "网络基础设施"), (("云",), "云计算"),
    (("芯片", "GPU", "NPU"), "AI计算与芯片"), (("医疗", "制药"), "智慧医疗"),
    (("法律", "法务"), "法律服务"), (("办公", "飞书", "企业微信"), "企业协同办公"),
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def reconstruct_records(raw_dir: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for path in raw_dir.glob("*_jobs.jsonl"):
        if path.name.startswith("._") or path.name == "demo_new_jobs.jsonl":
            continue
        records, _ = read_jsonl(path)
        for _, _, raw in records:
            cleaned = normalize_record(raw)
            result[cleaned["source_id"]] = cleaned
    return result


def split_evidence(text: str) -> list[str]:
    pieces = re.split(r"\n+|(?<=[。；;])", text)
    cleaned = []
    for piece in pieces:
        value = re.sub(r"^\s*(?:\d+[.、）)]|[（(]?[一二三四五六七八九十]+[)）、.]|[-•])\s*", "", piece).strip(" ;；。")
        if len(value) >= 8 and value not in cleaned:
            cleaned.append(value)
    return cleaned


def alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if alias and alias[0].isascii() and alias[0].isalnum():
        escaped = r"(?<![A-Za-z0-9])" + escaped
    if alias and alias[-1].isascii() and alias[-1].isalnum():
        escaped += r"(?![A-Za-z0-9])"
    return re.compile(escaped, re.IGNORECASE)


def extract_skills(record: dict[str, str]) -> list[dict[str, str]]:
    segments = [record["title"]] + split_evidence(record["description"] + "\n" + record["requirement"])
    results = []
    for name, aliases in SKILL_LEXICON.items():
        evidence = next((segment for segment in segments if any(alias_pattern(alias).search(segment) for alias in aliases)), None)
        if evidence is None:
            continue
        lowered = evidence.lower()
        requirement_type = "preferred" if any(marker.lower() in lowered for marker in PREFERRED_MARKERS) else "required"
        results.append({"name": name, "requirement_type": requirement_type, "evidence": evidence})
    return results


def standard_position(title: str) -> str:
    for keywords, position in POSITION_RULES:
        if any(keyword.lower() in title.lower() for keyword in keywords):
            return position
    value = re.sub(r"[（(][^）)]*(?:北京|上海|深圳|杭州|广州)[^）)]*[）)]", "", title)
    value = re.sub(r"^(?:【[^】]+】|日常实习生[-—]|阿里国际[-—])", "", value)
    return value.strip(" -—")


def scope_label(title: str) -> str:
    if any(keyword in title for keyword in OUT_OF_SCOPE_TITLES):
        return "out_of_scope"
    if any(keyword in title for keyword in REVIEW_SCOPE_TITLES):
        return "review"
    return "in_scope"


def scenarios(record: dict[str, str]) -> list[dict[str, str]]:
    blob = f"{record['title']}\n{record['description']}"
    values = []
    for keywords, name in SCENARIO_RULES:
        keyword = next((item for item in keywords if item.lower() in blob.lower()), None)
        if keyword:
            evidence = next((part for part in split_evidence(blob) if keyword.lower() in part.lower()), record["title"])
            values.append({"name": name, "evidence": evidence})
    return values[:4] or [{"name": "通用信息技术", "evidence": record["title"]}]


def build_draft(manifest: list[dict[str, Any]], records: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    output = []
    for selected in manifest:
        record = records.get(selected["source_id"])
        if record is None:
            raise KeyError(f"cannot reconstruct {selected['source_id']}")
        responsibility_segments = split_evidence(record["description"])
        output.append(
            {
                "evaluation_id": selected["evaluation_id"],
                "source_id": record["source_id"],
                "source_file": selected["source_file"],
                "content_hash": record["content_hash"],
                "raw": {
                    "company": record["company"], "title": record["title"],
                    "category": record["category"], "publish_time": record["publish_time"],
                    "description": record["description"], "requirement": record["requirement"],
                    "url": record["url"],
                },
                "annotation": {
                    "scope": scope_label(record["title"]),
                    "standard_position": standard_position(record["title"]),
                    "responsibilities": [{"text": text, "evidence": text} for text in responsibility_segments[:5]],
                    "skills": extract_skills(record),
                    "scenarios": scenarios(record),
                },
                "annotation_meta": {
                    "version": "draft-v1", "annotator": "codex-first-pass",
                    "review_status": "pending_second_annotator",
                },
            }
        )
    return output


def write_outputs(items: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "jd_ground_truth_draft_120.jsonl"
    csv_path = output_dir / "jd_ground_truth_review_120.csv"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as stream:
        for item in items:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=(
            "evaluation_id", "source_id", "company", "raw_title", "scope",
            "standard_position", "skills_json", "responsibilities_json", "scenarios_json",
            "review_status", "reviewer", "review_note",
        ))
        writer.writeheader()
        for item in items:
            annotation = item["annotation"]
            writer.writerow({
                "evaluation_id": item["evaluation_id"], "source_id": item["source_id"],
                "company": item["raw"]["company"], "raw_title": item["raw"]["title"],
                "scope": annotation["scope"], "standard_position": annotation["standard_position"],
                "skills_json": json.dumps(annotation["skills"], ensure_ascii=False),
                "responsibilities_json": json.dumps(annotation["responsibilities"], ensure_ascii=False),
                "scenarios_json": json.dumps(annotation["scenarios"], ensure_ascii=False),
                "review_status": "pending", "reviewer": "", "review_note": "",
            })
    summary = {
        "count": len(items),
        "status": "draft_requires_independent_review",
        "scope": {name: sum(x["annotation"]["scope"] == name for x in items) for name in ("in_scope", "review", "out_of_scope")},
        "records_with_skills": sum(bool(x["annotation"]["skills"]) for x in items),
        "skill_mentions": sum(len(x["annotation"]["skills"]) for x in items),
        "records_with_responsibilities": sum(bool(x["annotation"]["responsibilities"]) for x in items),
    }
    (output_dir / "jd_ground_truth_draft_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    items = build_draft(load_jsonl(args.manifest), reconstruct_records(args.raw_dir))
    if len(items) != 120:
        raise AssertionError(f"expected 120 records, got {len(items)}")
    write_outputs(items, args.output_dir)
    print(json.dumps({"generated": len(items), "outputDir": str(args.output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
