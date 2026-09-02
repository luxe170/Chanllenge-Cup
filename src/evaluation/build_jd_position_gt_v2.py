#!/usr/bin/env python3
"""Build moderately merged position GT and vocabulary from the frozen 100 JDs."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_SET = ROOT / "data/processed/splits/jd_test_set_100.jsonl"
BASE_GT = ROOT / "data/processed/evaluation/jd_result_ground_truth_100_v1.jsonl"
POSITION_GT = ROOT / "data/processed/evaluation/jd_position_ground_truth_100_v2.jsonl"
VOCABULARY = ROOT / "data/processed/evaluation/jd_position_vocabulary_100_v2.json"
RESULT_GT = ROOT / "data/processed/evaluation/jd_result_ground_truth_100_v2.jsonl"


# One independently assigned standard name per frozen JD, in test-set order.
# Company, location, business line, seniority and internship status are ignored.
# Closely related jobs sharing a core function are merged; materially different
# algorithm/system/security functions remain separate.
LABELS = [
    "金融投资分析师", "AI模型评测工程师", "数据标注与治理工程师", "AI基础设施工程师", "数据库与检索工程师",
    "网络基础设施工程师", "安全工程师", "移动系统与多媒体开发工程师", "移动系统与多媒体开发工程师", "移动系统与多媒体开发工程师",
    "移动系统与多媒体开发工程师", "移动系统与多媒体开发工程师", "大模型系统工程师", "移动系统与多媒体开发工程师", "移动系统与多媒体开发工程师",
    "AI质量与测试工程师", "AI基础设施工程师", "AI智能体工程师", "计算机视觉与多模态算法工程师", "推荐与广告算法工程师",
    "搜索算法工程师", "机器学习平台工程师", "计算机视觉与多模态算法工程师", "计算机视觉与多模态算法工程师", "数据挖掘与分析工程师",
    "通用算法工程师", "计算机视觉与多模态算法工程师", "风控算法工程师", "推荐与广告算法工程师", "语音与自然语言处理算法工程师",
    "决策算法工程师", "风控算法工程师", "语音与自然语言处理算法工程师", "后端开发工程师", "游戏开发工程师",
    "网络基础设施工程师", "数据库与检索工程师", "网络基础设施工程师", "AI基础设施工程师", "数据开发工程师",
    "游戏开发工程师", "游戏开发工程师", "AI计算与编译优化工程师", "AI计算与编译优化工程师", "AI计算与编译优化工程师",
    "大模型算法工程师", "大模型算法工程师", "大模型算法工程师", "AI模型评测工程师", "AI应用开发工程师",
    "AI智能体工程师", "安全工程师", "安全工程师", "风控算法工程师", "安全工程师",
    "数据库与检索工程师", "数据库与检索工程师", "数据库与检索工程师", "AI质量与测试工程师", "AI质量与测试工程师",
    "AI质量与测试工程师", "AI质量与测试工程师", "AI质量与测试工程师", "AI应用开发工程师", "大模型算法工程师",
    "移动系统与多媒体开发工程师", "AI计算与编译优化工程师", "AI计算与编译优化工程师", "游戏开发工程师", "网络基础设施工程师",
    "大模型算法工程师", "网络基础设施工程师", "后端开发工程师", "AI制药算法工程师", "EHS安全管理专家",
    "AI质量与测试工程师", "游戏开发工程师", "游戏开发工程师", "语音与自然语言处理算法工程师", "机器学习平台工程师",
    "推荐与广告算法工程师", "计算机视觉与多模态算法工程师", "大模型算法工程师", "搜索算法工程师", "大模型系统工程师",
    "AI应用开发工程师", "大模型算法工程师", "推荐与广告算法工程师", "网络基础设施工程师", "大模型系统工程师",
    "推荐与广告算法工程师", "AI应用开发工程师", "数据标注与治理工程师", "推荐与广告算法工程师", "大模型系统工程师",
    "数据标注与治理工程师", "推荐与广告算法工程师", "风控算法工程师", "大模型算法工程师", "机器学习平台工程师",
]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def position_id(name: str) -> str:
    return "gt_pos_" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]


def main() -> None:
    records = read_jsonl(TEST_SET)
    base_rows = {row["sourceId"]: row for row in read_jsonl(BASE_GT)}
    if len(records) != 100 or len(LABELS) != 100:
        raise ValueError("the frozen test set and LABELS must both contain exactly 100 rows")
    position_rows, result_rows = [], []
    observed: dict[str, set[str]] = defaultdict(set)
    for record, standard_name in zip(records, LABELS):
        source_id = str(record.get("source_id") or record.get("sourceId") or "")
        raw_name = str(record.get("title") or "").strip()
        observed[standard_name].add(raw_name)
        position_rows.append({
            "sourceId": source_id,
            "rawPositionName": raw_name,
            "standardPositionId": position_id(standard_name),
            "standardPositionName": standard_name,
            "acceptableNames": sorted({raw_name, standard_name}),
            "annotationMeta": {"version": "jd-position-gt-v2", "reviewStatus": "draft_pending_human_review", "method": "independent_core-function_merge"},
        })
        base = json.loads(json.dumps(base_rows[source_id], ensure_ascii=False))
        base["result"]["position"] = {"id": position_id(standard_name), "name": standard_name, "confidence": 1.0, "source": "position_gt_v2", "evidenceText": raw_name}
        base["result"]["isNewPositionCandidate"] = False
        base["annotationMeta"].update({"version": "jd-result-gt-v2", "reviewStatus": "draft_pending_human_review", "positionAnnotationMethod": "independent_core-function_merge", "nonPositionFields": "carried from v1 draft; human review required"})
        result_rows.append(base)

    positions = [{"id": position_id(name), "name": name, "sampleCount": sum(label == name for label in LABELS), "observedNames": sorted(names)} for name, names in sorted(observed.items())]
    vocabulary = {"version": "jd-position-vocabulary-v2", "source": "standardPositionName values in jd_position_ground_truth_100_v2.jsonl", "sampleCount": 100, "positionCount": len(positions), "positions": positions}
    POSITION_GT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in position_rows), encoding="utf-8")
    RESULT_GT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result_rows), encoding="utf-8")
    VOCABULARY.write_text(json.dumps(vocabulary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"samples": 100, "positions": len(positions)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
