#!/usr/bin/env python3
"""Use an LLM judge for GT rows whose position label is candidate_other."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.evaluation.evaluate_jd_predictions import read_jsonl
from src.llm_client import ChatCompletionsClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GT = PROJECT_ROOT / "data/processed/evaluation/jd_result_ground_truth_100_v1.jsonl"
DEFAULT_PREDICTIONS = PROJECT_ROOT / "output/evaluation/jd_predictions_100_v1.jsonl"
DEFAULT_TEST_SET = PROJECT_ROOT / "data/processed/splits/jd_test_set_100.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "output/evaluation/jd_candidate_position_judgments_100_v1.jsonl"


SYSTEM_PROMPT = """你是独立的岗位名称评测裁判。你只判断模型提取的岗位名称是否准确描述该JD的核心工作职能。

判定为 correct=true 必须同时满足：
1. 岗位名称与JD标题、职责和要求所表达的核心职能一致；
2. 名称足够具体，能够作为岗位类别使用；
3. 不能只是“其他岗位”“候选岗位”“待评估”“工程师”等空泛占位词；
4. 不因公司、地点、职级、业务线等修饰差异判错；同义表达可以判对；
5. 不评价技能抽取，也不因为预测岗位不在已有岗位表中判错。

只能返回JSON对象：
{"correct": true或false, "confidence": 0到1, "reason": "简短且具体的理由"}
"""


def _id(item: dict[str, Any]) -> str:
    return str(item.get("sourceId") or item.get("source_id") or item.get("evaluation_id") or "")


def _result(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("result") if "result" in item else item


def _position_id(result: dict[str, Any]) -> str:
    position = result.get("position") or {}
    return str(position.get("id") or result.get("positionId") or "")


def _position_name(result: dict[str, Any]) -> str:
    position = result.get("position") or {}
    return str(position.get("name") or result.get("positionName") or "")


def _load_existing(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {_id(row): row for row in read_jsonl(path)}


def generate_judgments(
    ground_truth_path: Path,
    predictions_path: Path,
    test_set_path: Path,
    output_path: Path,
    *,
    resume: bool = True,
    client: ChatCompletionsClient | None = None,
) -> list[dict[str, Any]]:
    ground_truth = read_jsonl(ground_truth_path)
    predictions = {_id(row): row for row in read_jsonl(predictions_path)}
    test_records = {_id(row): row for row in read_jsonl(test_set_path)}
    candidate_ids = [
        _id(row) for row in ground_truth
        if _position_id(_result(row)) == "candidate_other"
    ]
    if not candidate_ids:
        raise ValueError("ground truth contains no candidate_other position rows")
    missing = set(candidate_ids) - set(predictions) | (set(candidate_ids) - set(test_records))
    if missing:
        raise ValueError(f"candidate prediction/test coverage mismatch: {sorted(missing)}")

    existing = _load_existing(output_path) if resume else {}
    judge = client or ChatCompletionsClient.from_env()
    rows: list[dict[str, Any]] = []
    for index, source_id in enumerate(candidate_ids, 1):
        predicted = _result(predictions[source_id])
        position_name = _position_name(predicted)
        cached_name = str(existing.get(source_id, {}).get("predictedPositionName") or "")
        if source_id in existing and cached_name.strip().casefold() == position_name.strip().casefold():
            rows.append(existing[source_id])
            print(f"[{index}/{len(candidate_ids)}] cached {source_id}", flush=True)
            continue
        record = test_records[source_id]
        response = judge.complete_json(SYSTEM_PROMPT, {
            "sourceId": source_id,
            "jd": {
                "title": str(record.get("title") or ""),
                "description": str(record.get("description") or ""),
                "requirement": str(record.get("requirement") or ""),
            },
            "predictedPosition": {
                "id": _position_id(predicted),
                "name": position_name,
                "evidenceText": str((predicted.get("position") or {}).get("evidenceText") or ""),
            },
        })
        if not isinstance(response.get("correct"), bool):
            raise ValueError(f"{source_id}: judge response must contain boolean correct")
        try:
            confidence = min(1.0, max(0.0, float(response.get("confidence"))))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{source_id}: invalid judge confidence") from exc
        row = {
            "sourceId": source_id,
            "predictedPositionName": position_name,
            "correct": response["correct"],
            "confidence": confidence,
            "reason": str(response.get("reason") or ""),
            "judgeModel": judge.model,
            "promptVersion": "candidate-position-judge-v1",
        }
        rows.append(row)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows), encoding="utf-8")
        print(f"[{index}/{len(candidate_ids)}] judged {source_id}: {row['correct']}", flush=True)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge candidate JD position names with the configured LLM.")
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GT)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--test-set", type=Path, default=DEFAULT_TEST_SET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    rows = generate_judgments(
        args.ground_truth, args.predictions, args.test_set, args.output,
        resume=not args.no_resume,
    )
    print(json.dumps({"records": len(rows), "correct": sum(bool(row["correct"]) for row in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
