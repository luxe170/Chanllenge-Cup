#!/usr/bin/env python3
"""Run the production resume parser for every file listed by a GT manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.services.resume_service import parse_resume_text
from backend.app.services.resume_text import extract_resume_text
from src.evaluation.evaluate_jd_predictions import read_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate resume predictions with the production parser.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output_rows = []
    for item in read_jsonl(args.manifest):
        resume_id = str(item.get("resumeId") or item.get("resume_id") or "")
        relative_path = Path(str(item.get("file") or ""))
        source = relative_path if relative_path.is_absolute() else PROJECT_ROOT / relative_path
        try:
            text = extract_resume_text(source.name, source.read_bytes())
            result = parse_resume_text(source.name, text)
            output_rows.append({"resumeId": resume_id, "file": str(relative_path), "result": result})
        except Exception as exc:
            output_rows.append({"resumeId": resume_id, "file": str(relative_path), "result": {}, "error": str(exc)})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output_rows), encoding="utf-8")
    failed = sum(1 for row in output_rows if row.get("error"))
    print(json.dumps({"records": len(output_rows), "parsed": len(output_rows) - failed, "failed": failed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
