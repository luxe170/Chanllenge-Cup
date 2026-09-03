#!/usr/bin/env python3
"""Replace content-leaked records in the first-version JD evaluation set."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.data_sources import read_jsonl, write_jsonl
from backend.app.services.evolution_service import POSITION_NAME_MAP, SKILL_NAME_MAP


TEST_PATH = Path("data/processed/splits/jd_test_set_100.jsonl")
TRAIN_PATH = Path("data/processed/splits/graph_train_200.jsonl")
HOLDOUT_PATH = Path("data/processed/splits/jd_holdout_336.jsonl")
LABEL_PATH = Path("data/processed/evaluation/jd_gold_labels.jsonl")
MANIFEST_PATH = Path("data/processed/evaluation/jd_test_replacement_manifest_v1.json")

# These labels were produced from the original JD text without consulting the
# parser prediction. They remain drafts until the normal human review step.
REPLACEMENTS: list[tuple[str, str, list[str]]] = [
    ("bytedance:7623304135925090565", "pos_algorithm_engineer", ["skill_llm", "skill_python", "skill_go", "skill_algorithm", "skill_nlp", "skill_multimodal"]),
    ("tencent_careers:2037101976877170688", "pos_llm_engineer", ["skill_llm", "skill_python", "skill_cpp", "skill_distributed", "skill_multimodal", "skill_hardware"]),
    ("alibaba_campus:199906700003", "pos_ai_agent_engineer", ["skill_llm", "skill_rag", "skill_prompt", "skill_ai_codegen", "skill_frontend", "skill_database"]),
    ("meituan_careers:4530913541", "pos_algorithm_engineer", ["skill_llm", "skill_python", "skill_cpp", "skill_algorithm"]),
    ("bytedance:7621535059103303989", "pos_algorithm_engineer", ["skill_llm", "skill_rag", "skill_multi_agent", "skill_python", "skill_cpp", "skill_java", "skill_algorithm"]),
    ("tencent_careers:1932983235067904000", "pos_cloud_infra_engineer", ["skill_cloud_native", "skill_distributed", "skill_testing"]),
    ("alibaba_campus:199907880001", "pos_llm_engineer", ["skill_llm", "skill_python", "skill_cpp", "skill_algorithm", "skill_hardware"]),
    ("bytedance:7491665085673720071", "pos_algorithm_engineer", ["skill_python", "skill_cpp", "skill_algorithm", "skill_nlp"]),
    ("tencent_careers:2076924809798922240", "pos_ai_agent_engineer", ["skill_llm", "skill_rag", "skill_multi_agent"]),
    ("alibaba_campus:199904260008", "candidate_other", ["skill_database"]),
    ("bytedance:7525465167627782408", "pos_algorithm_engineer", ["skill_algorithm"]),
    ("tencent_careers:1902190189934100480", "pos_llm_engineer", ["skill_llm", "skill_python", "skill_go", "skill_cpp", "skill_distributed", "skill_hardware"]),
    ("alibaba_campus:199905160003", "pos_data_engineer", ["skill_llm", "skill_python"]),
    ("bytedance:7514636368456599826", "pos_algorithm_engineer", ["skill_llm", "skill_python", "skill_go", "skill_cpp", "skill_java", "skill_distributed", "skill_algorithm"]),
    ("tencent_careers:2054521545946214400", "pos_security_engineer", ["skill_python", "skill_java", "skill_cpp", "skill_sql", "skill_distributed", "skill_algorithm", "skill_security"]),
    ("alibaba_campus:199907980002", "pos_llm_engineer", ["skill_llm", "skill_distributed", "skill_algorithm"]),
    ("bytedance:7628921421481232645", "pos_hardware_engineer", ["skill_cpp", "skill_distributed", "skill_algorithm", "skill_hardware"]),
]


def _source_id(record: dict[str, Any]) -> str:
    return str(record.get("source_id") or record.get("sourceId") or record.get("evaluation_id") or "")


def _normalized_text(record: dict[str, Any]) -> str:
    text = "\n".join(str(record.get(key) or "") for key in ("title", "description", "requirement"))
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+|[^0-9a-z\u4e00-\u9fff]+", "", text)


def _text_hash(record: dict[str, Any]) -> str:
    return hashlib.sha256(_normalized_text(record).encode("utf-8")).hexdigest()


def _label(record: dict[str, Any], position_id: str, skill_ids: list[str]) -> dict[str, Any]:
    return {
        "sourceId": _source_id(record),
        "expectedPositionId": position_id,
        "expectedPositionName": POSITION_NAME_MAP.get(position_id, "候选新岗位"),
        "expectedSkills": [{"id": skill_id, "name": SKILL_NAME_MAP[skill_id]} for skill_id in skill_ids],
        "confidence": 0.8,
        "labeler": "manual-draft-replacement-v1",
        "reviewStatus": "pending_human_review",
        "notes": "用于替换与构图集内容重复的第一版评测样本；待第二标注员复核。",
    }


def main() -> None:
    test, train, holdout, labels = map(read_jsonl, (TEST_PATH, TRAIN_PATH, HOLDOUT_PATH, LABEL_PATH))
    train_content_hashes = {str(row.get("content_hash") or "") for row in train}
    train_text_hashes = {_text_hash(row) for row in train}
    leaked = [row for row in test if str(row.get("content_hash") or "") in train_content_hashes or _text_hash(row) in train_text_hashes]
    replacement_ids = {source_id for source_id, _, _ in REPLACEMENTS}
    if not leaked and replacement_ids.issubset({_source_id(row) for row in test}):
        print(json.dumps({"status": "already_applied", "testCount": len(test)}, ensure_ascii=False))
        return
    if len(leaked) != len(REPLACEMENTS):
        raise ValueError(f"expected {len(REPLACEMENTS)} leaked records, found {len(leaked)}")

    holdout_by_id = {_source_id(row): row for row in holdout}
    replacement_rows = []
    replacement_labels = []
    for source_id, position_id, skill_ids in REPLACEMENTS:
        record = holdout_by_id[source_id]
        if str(record.get("content_hash") or "") in train_content_hashes or _text_hash(record) in train_text_hashes:
            raise ValueError(f"replacement still overlaps graph training data: {source_id}")
        replacement_rows.append(record)
        replacement_labels.append(_label(record, position_id, skill_ids))

    leaked_ids = {_source_id(row) for row in leaked}
    retained = [row for row in test if _source_id(row) not in leaked_ids]
    updated_test = retained + replacement_rows
    if len(updated_test) != 100 or len({_source_id(row) for row in updated_test}) != 100:
        raise ValueError("replacement did not produce 100 unique source IDs")
    internal_duplicate_count = len(updated_test) - len({_text_hash(row) for row in updated_test})

    retained_labels = [row for row in labels if str(row.get("sourceId") or "") not in leaked_ids]
    updated_labels = retained_labels + replacement_labels
    if {_source_id(row) for row in updated_test} != {str(row.get("sourceId") or "") for row in updated_labels}:
        raise ValueError("updated GT does not exactly cover the updated test set")

    write_jsonl(TEST_PATH, updated_test)
    write_jsonl(LABEL_PATH, updated_labels)
    manifest = {
        "version": "first-version-test-v2-no-graph-overlap",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "testCount": len(updated_test),
        "removed": [{"sourceId": _source_id(row), "title": row.get("title", "")} for row in leaked],
        "added": [{"sourceId": _source_id(row), "title": row.get("title", "")} for row in replacement_rows],
        "validation": {"sourceIdOverlap": 0, "contentHashOverlap": 0, "normalizedTextOverlap": 0, "internalNormalizedTextDuplicates": internal_duplicate_count},
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"removed": len(leaked), "added": len(replacement_rows), "testCount": len(updated_test)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
