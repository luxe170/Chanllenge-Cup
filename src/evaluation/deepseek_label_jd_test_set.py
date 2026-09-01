from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from backend.app.services.data_sources import read_jsonl, write_jsonl
from backend.app.services.evolution_service import POSITION_NAME_MAP, SKILL_NAME_MAP
from src.llm_client import ChatCompletionsClient, DEFAULT_BASE_URL, DEFAULT_MODEL, JsonChatClient


PROMPT_VERSION = "jd-evaluation-label-draft-v1"


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
        "你是招聘 JD 测评集初标助手。请只基于给定 JD 标注标准岗位和技能，不要编造不存在的证据。\n"
        "你的输出是待人工复核的标注草稿，不是最终金标准。\n"
        "标准岗位只能从 positions 中选择；如果确实无法归入任何标准岗位，使用 candidate_other。\n"
        "技能只能从 skills 中选择，最多选择 10 个最明确的技能。\n"
        "技能 type 只能是 required 或 preferred。明确写在职责/要求核心条款里的用 required，泛化加分项用 preferred。\n"
        "每个技能尽量给出 evidenceText；岗位也应给出 positionEvidenceText。\n"
        "请标记 scope，可选 in_scope、review、out_of_scope。\n"
        "每个 label 必须原样返回对应 JD 的 sourceId。\n"
        "返回严格 JSON，格式为 {\"labels\":[...]}，不要 Markdown。\n"
        f"positions={json.dumps(positions, ensure_ascii=False)}\n"
        f"skills={json.dumps(skills, ensure_ascii=False)}"
    )


def _user_prompt(records: list[dict[str, Any]]) -> str:
    return json.dumps({"jobs": [_compact_record(record) for record in records]}, ensure_ascii=False)


def _call_labeler(
    records: list[dict[str, Any]],
    client: JsonChatClient,
) -> list[dict[str, Any]]:
    parsed = client.complete_json(_system_prompt(), {"jobs": [_compact_record(record) for record in records]})
    labels = parsed.get("labels")
    if not isinstance(labels, list):
        raise ValueError("LLM labeling response missing labels list")
    return labels


def _clamp_confidence(value: Any) -> float:
    try:
        return round(max(0.0, min(1.0, float(value))), 3)
    except (TypeError, ValueError):
        return 0.0


def _normalize_label(label: dict[str, Any], source_id: str, model: str) -> dict[str, Any]:
    expected_skills = []
    for skill in label.get("expectedSkills") or label.get("skills") or []:
        if not isinstance(skill, dict):
            continue
        skill_id = str(skill.get("id") or skill.get("skill") or skill.get("skillId") or "")
        if skill_id not in SKILL_NAME_MAP:
            continue
        skill_type = "required" if skill.get("type") == "required" else "preferred"
        expected_skills.append(
            {
                "id": skill_id,
                "name": SKILL_NAME_MAP[skill_id],
                "type": skill_type,
                "evidenceText": str(skill.get("evidenceText") or skill.get("evidence") or "")[:300],
                "confidence": _clamp_confidence(skill.get("confidence")),
            }
        )

    position_id = str(label.get("expectedPositionId") or label.get("position") or label.get("positionId") or "candidate_other")
    if position_id not in POSITION_NAME_MAP:
        position_id = "candidate_other"
    scope = str(label.get("scope") or "in_scope")
    if scope not in {"in_scope", "review", "out_of_scope"}:
        scope = "review"
    confidence = _clamp_confidence(label.get("confidence"))
    review_reasons = []
    for value in label.get("reviewReasons") or []:
        text = str(value).strip()
        if text and text not in review_reasons:
            review_reasons.append(text[:120])
    if confidence < 0.7 and "LLM 置信度较低" not in review_reasons:
        review_reasons.append("LLM 置信度较低")
    if position_id == "candidate_other" and "候选新岗位或无法归类岗位" not in review_reasons:
        review_reasons.append("候选新岗位或无法归类岗位")
    return {
        "schemaVersion": "1.1",
        "sourceId": source_id,
        "scope": scope,
        "expectedPositionId": position_id,
        "expectedPositionName": POSITION_NAME_MAP.get(position_id, "候选新岗位"),
        "positionEvidenceText": str(label.get("positionEvidenceText") or label.get("evidenceText") or "")[:300],
        "expectedSkills": expected_skills,
        "confidence": confidence,
        "labeler": model,
        "labelSource": "llm_draft",
        "promptVersion": PROMPT_VERSION,
        "reviewStatus": "pending_human_review",
        "reviewReasons": review_reasons,
        "notes": str(label.get("notes") or ""),
    }


def label_jd_test_set(
    input_path: Path,
    output_path: Path,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    batch_size: int = 5,
    limit: int | None = None,
    timeout: int = 90,
    retries: int = 2,
    overwrite: bool = False,
    client: JsonChatClient | None = None,
) -> list[dict[str, Any]]:
    if client is None:
        if api_key is None:
            client = ChatCompletionsClient.from_env(model=model, base_url=base_url, timeout=timeout, retries=retries)
        else:
            client = ChatCompletionsClient(
                api_key=api_key,
                model=model,
                base_url=base_url,
                timeout=timeout,
                retries=retries,
            )
    records = read_jsonl(input_path)
    if limit is not None:
        records = records[:limit]

    existing = [] if overwrite else read_jsonl(output_path)
    labels_by_id = {str(item.get("sourceId")): item for item in existing if item.get("sourceId")}
    pending = [record for record in records if _record_id(record) not in labels_by_id]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    step = max(1, batch_size)
    for start in range(0, len(pending), step):
        batch = pending[start : start + step]
        raw_labels = _call_labeler(batch, client)
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
            labels_by_id[source_id] = _normalize_label(raw_label or {}, source_id, client.model)
        ordered = [labels_by_id[_record_id(record)] for record in records if _record_id(record) in labels_by_id]
        write_jsonl(output_path, ordered)
        print(f"labeled {len(ordered)}/{len(records)} JD records")

    return [labels_by_id[_record_id(record)] for record in records if _record_id(record) in labels_by_id]


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft-label JD test set with a DeepSeek/OpenAI-compatible chat API.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/splits/jd_test_set_100.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/evaluation/jd_llm_label_draft.jsonl"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--overwrite", action="store_true", help="Ignore existing labels and regenerate the output file.")
    parser.add_argument("--write-empty", action="store_true", help="Create an empty draft label file without calling an LLM.")
    args = parser.parse_args()

    if args.write_empty:
        write_jsonl(args.output, [])
        print(f"wrote empty LLM draft labels -> {args.output}")
        return

    labels = label_jd_test_set(
        input_path=args.input,
        output_path=args.output,
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
