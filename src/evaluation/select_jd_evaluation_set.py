#!/usr/bin/env python3
"""Select a deterministic 120-JD evaluation set outside the graph corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.processing.clean_multisource_jobs import classify_records, normalize_record, read_jsonl, status_reason


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_GRAPH_CORPUS = PROJECT_ROOT / "data" / "processed" / "relevant_jobs.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation"

# 94 target-domain records + 26 boundary/noise records. The latter are needed
# to measure false positives instead of evaluating only easy positive samples.
QUOTAS = {
    ("bytedance_dev_jobs.jsonl", "relevant"): 45,
    ("tencent_jobs.jsonl", "relevant"): 30,
    ("alibaba_jobs.jsonl", "relevant"): 15,
    ("meituan_jobs.jsonl", "relevant"): 4,
    ("bytedance_dev_jobs.jsonl", "boundary_noise"): 6,
    ("tencent_jobs.jsonl", "boundary_noise"): 8,
    ("alibaba_jobs.jsonl", "boundary_noise"): 6,
    ("meituan_jobs.jsonl", "boundary_noise"): 2,
    ("huawei_jobs.jsonl", "boundary_noise"): 4,
}


def read_objects(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    records.append(item)
    return records


def stable_key(record: dict[str, Any], seed: str) -> str:
    value = f"{seed}|{record['source_id']}|{record['content_hash']}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def select_records(raw_dir: Path, graph_corpus: Path, seed: str) -> list[dict[str, Any]]:
    graph_records = read_objects(graph_corpus)
    excluded_ids = {str(item.get("source_id", "")) for item in graph_records}
    excluded_hashes = {str(item.get("content_hash", "")) for item in graph_records}

    selected: list[dict[str, Any]] = []
    selected_hashes: set[str] = set()
    for (filename, stratum), quota in QUOTAS.items():
        raw_records, parse_rejections = read_jsonl(raw_dir / filename)
        if parse_rejections:
            raise ValueError(f"{filename} contains {len(parse_rejections)} unparsable lines")
        relevant, _, _, _ = classify_records(raw_records)
        boundary_by_id: dict[str, dict[str, Any]] = {}
        for _, _, raw_item in raw_records:
            cleaned = normalize_record(raw_item)
            reason, _ = status_reason(cleaned)
            if not reason.startswith("relevant:"):
                boundary_by_id[cleaned["source_id"]] = cleaned
        candidates = relevant if stratum == "relevant" else list(boundary_by_id.values())
        eligible = [
            item
            for item in candidates
            if item["source_id"] not in excluded_ids
            and item["content_hash"] not in excluded_hashes
            and item["content_hash"] not in selected_hashes
        ]
        eligible.sort(key=lambda item: stable_key(item, seed))
        candidates = []
        candidate_hashes: set[str] = set()
        for item in eligible:
            if item["content_hash"] in candidate_hashes:
                continue
            candidates.append(item)
            candidate_hashes.add(item["content_hash"])
        if len(candidates) < quota:
            raise ValueError(f"{filename}/{stratum}: need {quota}, only {len(candidates)} available")
        for item in candidates[:quota]:
            selected.append(
                {
                    "source_id": item["source_id"],
                    "source_file": filename,
                    "sampling_stratum": stratum,
                    "source_platform": item["source_platform"],
                    "company": item["company"],
                    "title": item["title"],
                    "content_hash": item["content_hash"],
                    "publish_time": item["publish_time"],
                    "url": item["url"],
                }
            )
            selected_hashes.add(item["content_hash"])

    selected.sort(key=lambda item: (item["source_file"], item["sampling_stratum"], stable_key(item, seed)))
    for index, item in enumerate(selected, start=1):
        item["evaluation_id"] = f"JD-EVAL-{index:03d}"
    if len(selected) != 120 or len({item["source_id"] for item in selected}) != 120:
        raise AssertionError("evaluation set must contain 120 unique source IDs")
    if excluded_ids & {item["source_id"] for item in selected}:
        raise AssertionError("graph corpus source ID leaked into evaluation set")
    if excluded_hashes & {item["content_hash"] for item in selected}:
        raise AssertionError("graph corpus content leaked into evaluation set")
    return selected


def write_outputs(records: list[dict[str, Any]], output_dir: Path, seed: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "jd_eval_120_manifest.jsonl"
    ids_path = output_dir / "jd_eval_120_ids.txt"
    summary_path = output_dir / "jd_eval_120_summary.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        for item in records:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    with ids_path.open("w", encoding="utf-8", newline="\n") as stream:
        for item in records:
            stream.write(f"{item['evaluation_id']}\t{item['source_id']}\n")
    summary = {
        "count": len(records),
        "seed": seed,
        "exclusion": "source_id and content_hash from data/processed/relevant_jobs.jsonl",
        "sourceFiles": dict(sorted(Counter(item["source_file"] for item in records).items())),
        "samplingStrata": dict(sorted(Counter(item["sampling_stratum"] for item in records).items())),
        "companies": dict(sorted(Counter(item["company"] for item in records).items())),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--graph-corpus", type=Path, default=DEFAULT_GRAPH_CORPUS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", default="career-prism-jd-eval-v1")
    args = parser.parse_args()
    records = select_records(args.raw_dir, args.graph_corpus, args.seed)
    write_outputs(records, args.output_dir, args.seed)
    print(json.dumps({"selected": len(records), "outputDir": str(args.output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
