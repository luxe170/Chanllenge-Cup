#!/usr/bin/env python3
"""Run the same production resume pipeline used by the upload API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.services.resume_service import create_resume_task, get_resume_task
from src.evaluation.evaluate_jd_predictions import read_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate resume predictions with the production parser.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="mark rule/degraded results as failures; use this for multimodal evaluation",
    )
    args = parser.parse_args()

    output_rows = []
    for item in read_jsonl(args.manifest):
        resume_id = str(item.get("resumeId") or item.get("resume_id") or "")
        relative_path = Path(str(item.get("file") or ""))
        source = relative_path if relative_path.is_absolute() else PROJECT_ROOT / relative_path
        try:
            created = create_resume_task(source.name, source.read_bytes())
            task = get_resume_task(created["taskId"])
            result = task.get("result") or {}
            analysis = result.get("llmAnalysis") or {}
            if args.require_llm and (
                result.get("analysisSource") != "llm" or analysis.get("status") != "completed"
            ):
                raise RuntimeError(
                    "未得到正式 LLM 结果；请配置 LLM_RESUME_ENABLED=true、API key 和支持图片的 LLM_VISION_MODEL"
                )
            output_rows.append(
                {
                    "resumeId": resume_id,
                    "file": str(relative_path),
                    "result": result,
                    "predictionMeta": {
                        "analysisSource": result.get("analysisSource", "unknown"),
                        "inputMode": analysis.get("inputMode", "text"),
                        "model": result.get("model") or analysis.get("model", ""),
                        "analyzerVersion": result.get("analyzerVersion", ""),
                        "promptVersion": result.get("promptVersion", ""),
                    },
                }
            )
        except Exception as exc:
            output_rows.append({"resumeId": resume_id, "file": str(relative_path), "result": {}, "error": str(exc)})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output_rows), encoding="utf-8")
    failed = sum(1 for row in output_rows if row.get("error"))
    print(json.dumps({"records": len(output_rows), "parsed": len(output_rows) - failed, "failed": failed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
