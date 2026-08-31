from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from backend.app.services.data_sources import read_jsonl, write_jsonl
from backend.app.services.evolution_service import POSITION_NAME_MAP, SKILL_NAME_MAP


DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"


def _record_id(record: dict[str, Any]) -> str:
    return str(record.get("source_id") or record.get("content_hash") or record.get("source_job_id") or "")


def _compact_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceId": _record_id(record),
        "title": record.get("title", ""),
        "category": record.get("category", ""),
        "company": record.get("company", ""),
        "description": str(record.get("description", ""))[:1200],
        "requirement": str(record.get("requirement", ""))[:1200],
    }


def _system_prompt() -> str:
    positions = [{"id": key, "name": value} for key, value in sorted(POSITION_NAME_MAP.items())]
    skills = [{"id": key, "name": value} for key, value in sorted(SKILL_NAME_MAP.items())]
    return (
        "你是招聘 JD 标注员。请只基于给定 JD 标注标准岗位和技能，不要编造不存在的证据。\n"
        "标准岗位只能从 positions 中选择；如果确实无法归入任何标准岗位，使用 candidate_other。\n"
        "技能只能从 skills 中选择，最多选择 10 个最明确的技能。\n"
        "技能 type 只能是 required 或 preferred。明确写在职责/要求核心条款里的用 required，泛化加分项用 preferred。\n"
        "每个 label 必须原样返回对应 JD 的 sourceId。\n"
        "返回严格 JSON，格式为 {\"labels\":[...]}，不要 Markdown。\n"
        f"positions={json.dumps(positions, ensure_ascii=False)}\n"
        f"skills={json.dumps(skills, ensure_ascii=False)}"
    )


def _user_prompt(records: list[dict[str, Any]]) -> str:
    return json.dumps({"jobs": [_compact_record(record) for record in records]}, ensure_ascii=False)


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end < start:
            raise
        return json.loads(cleaned[start : end + 1])


def _call_deepseek(
    records: list[dict[str, Any]],
    api_key: str,
    model: str,
    base_url: str,
    timeout: int,
    retries: int,
) -> list[dict[str, Any]]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(records)},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
            result = json.loads(raw)
            content = result["choices"][0]["message"]["content"]
            parsed = _extract_json_object(content)
            labels = parsed.get("labels")
            if not isinstance(labels, list):
                raise ValueError("DeepSeek response missing labels list")
            return labels
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"DeepSeek labeling failed after {retries + 1} attempts: {last_error}") from last_error


def _normalize_label(label: dict[str, Any], source_id: str, model: str) -> dict[str, Any]:
    expected_skills = []
    for skill in label.get("expectedSkills") or label.get("skills") or []:
        if not isinstance(skill, dict):
            continue
        skill_id = str(skill.get("id") or skill.get("skill") or skill.get("skillId") or "")
        if skill_id not in SKILL_NAME_MAP:
            continue
        skill_type = "required" if skill.get("type") == "required" else "preferred"
        expected_skills.append({"id": skill_id, "name": SKILL_NAME_MAP[skill_id], "type": skill_type})

    position_id = str(label.get("expectedPositionId") or label.get("position") or label.get("positionId") or "candidate_other")
    if position_id not in POSITION_NAME_MAP:
        position_id = "candidate_other"
    return {
        "sourceId": source_id,
        "expectedPositionId": position_id,
        "expectedPositionName": POSITION_NAME_MAP.get(position_id, "候选新岗位"),
        "expectedSkills": expected_skills,
        "confidence": float(label.get("confidence") or 0.0),
        "labeler": model,
        "notes": str(label.get("notes") or ""),
    }


def label_jd_test_set(
    input_path: Path,
    output_path: Path,
    api_key: str,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    batch_size: int = 5,
    limit: int | None = None,
    timeout: int = 90,
    retries: int = 2,
    overwrite: bool = False,
) -> list[dict[str, Any]]:
    records = read_jsonl(input_path)
    if limit is not None:
        records = records[:limit]

    existing = [] if overwrite else read_jsonl(output_path)
    labels_by_id = {str(item.get("sourceId")): item for item in existing if item.get("sourceId")}
    pending = [record for record in records if _record_id(record) not in labels_by_id]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        raw_labels = _call_deepseek(batch, api_key, model, base_url, timeout, retries)
        raw_by_id = {
            str(item.get("sourceId") or item.get("source_id") or item.get("id") or ""): item
            for item in raw_labels
            if isinstance(item, dict)
        }
        for index, record in enumerate(batch):
            source_id = _record_id(record)
            raw_label = raw_by_id.get(source_id)
            if raw_label is None and index < len(raw_labels) and isinstance(raw_labels[index], dict):
                raw_label = raw_labels[index]
            labels_by_id[source_id] = _normalize_label(raw_label or {}, source_id, model)
        ordered = [labels_by_id[_record_id(record)] for record in records if _record_id(record) in labels_by_id]
        write_jsonl(output_path, ordered)
        print(f"labeled {len(ordered)}/{len(records)} JD records")

    return [labels_by_id[_record_id(record)] for record in records if _record_id(record) in labels_by_id]


def main() -> None:
    parser = argparse.ArgumentParser(description="Label JD test set with DeepSeek-compatible chat completions.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/splits/jd_test_set_100.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/evaluation/jd_gold_labels.jsonl"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--overwrite", action="store_true", help="Ignore existing labels and regenerate the output file.")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is required")

    labels = label_jd_test_set(
        input_path=args.input,
        output_path=args.output,
        api_key=api_key,
        model=args.model,
        base_url=args.base_url,
        batch_size=args.batch_size,
        limit=args.limit,
        timeout=args.timeout,
        retries=args.retries,
        overwrite=args.overwrite,
    )
    print(f"wrote {len(labels)} labels to {args.output}")


if __name__ == "__main__":
    main()
