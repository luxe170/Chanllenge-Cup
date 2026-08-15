#!/usr/bin/env python3
"""清洗结构化招聘记录并生成可追溯的岗位数据集。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


SOURCE_FIELDS = (
    "position_id",
    "job_id",
    "title",
    "locations",
    "employment_type",
    "category",
    "publish_time",
    "description",
    "requirement",
    "url",
)

OUTPUT_FIELDS = (
    "source_id",
    *SOURCE_FIELDS,
    "content_hash",
    "duplicate_group_id",
    "quality_flags",
)

REJECTED_FIELDS = ("line_number", "reason", "raw_record")
REQUIRED_FIELDS = ("position_id", "title", "description", "requirement", "url")


def normalize_scalar(value: Any) -> str:
    """统一 Unicode、空白符和首尾空格。"""
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def normalize_multiline(value: Any) -> str:
    """清理多行文本，同时保留段落结构。"""
    text = unicodedata.normalize("NFKC", str(value or "")).replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def normalize_url(value: Any) -> str:
    """移除 URL 查询参数和片段，保留稳定的职位详情地址。"""
    url = normalize_scalar(value)
    if not url:
        return ""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def normalize_publish_time(value: Any) -> str:
    text = normalize_scalar(value)
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return parsed.isoformat(sep=" ", timespec="seconds")


def content_hash(record: dict[str, str]) -> str:
    """计算与地点和发布时间无关的岗位内容指纹。"""
    content = "\n".join(
        (record["title"], record["description"], record["requirement"])
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def clean_record(record: dict[str, Any]) -> dict[str, str]:
    cleaned = {
        "position_id": normalize_scalar(record.get("position_id")),
        "job_id": normalize_scalar(record.get("job_id")),
        "title": normalize_scalar(record.get("title")),
        "locations": normalize_scalar(record.get("locations")),
        "employment_type": normalize_scalar(record.get("employment_type")),
        "category": normalize_scalar(record.get("category")),
        "publish_time": normalize_publish_time(record.get("publish_time")),
        "description": normalize_multiline(record.get("description")),
        "requirement": normalize_multiline(record.get("requirement")),
        "url": normalize_url(record.get("url")),
    }
    cleaned["source_id"] = f"bytedance:{cleaned['position_id']}"
    cleaned["content_hash"] = content_hash(cleaned)
    cleaned["duplicate_group_id"] = ""
    cleaned["quality_flags"] = ""
    return cleaned


def rejection_reason(record: dict[str, str]) -> str:
    missing = [field for field in REQUIRED_FIELDS if not record[field]]
    if missing:
        return "missing_required_fields:" + ",".join(missing)
    if not record["url"].startswith(("http://", "https://")):
        return "invalid_url"
    return ""


def record_quality(record: dict[str, str]) -> tuple[int, int]:
    """同一来源主键冲突时，优先保留字段更完整、正文更长的记录。"""
    populated = sum(bool(record[field]) for field in SOURCE_FIELDS)
    text_length = len(record["description"]) + len(record["requirement"])
    return populated, text_length


def clean_records(
    records: Iterable[tuple[int, dict[str, Any]]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    accepted_by_source: dict[str, dict[str, str]] = {}
    rejected: list[dict[str, str]] = []
    duplicate_source_ids = 0

    for line_number, raw in records:
        cleaned = clean_record(raw)
        reason = rejection_reason(cleaned)
        if reason:
            rejected.append(
                {
                    "line_number": str(line_number),
                    "reason": reason,
                    "raw_record": json.dumps(raw, ensure_ascii=False, sort_keys=True),
                }
            )
            continue

        source_id = cleaned["source_id"]
        previous = accepted_by_source.get(source_id)
        if previous is None:
            accepted_by_source[source_id] = cleaned
            continue

        duplicate_source_ids += 1
        if record_quality(cleaned) > record_quality(previous):
            accepted_by_source[source_id] = cleaned

    accepted = list(accepted_by_source.values())
    hash_counts = Counter(record["content_hash"] for record in accepted)
    duplicate_content_records = 0
    missing_publish_time = 0

    for record in accepted:
        flags: list[str] = []
        if not record["publish_time"]:
            flags.append("missing_publish_time")
            missing_publish_time += 1
        if hash_counts[record["content_hash"]] > 1:
            flags.append("duplicate_content")
            record["duplicate_group_id"] = "dup_" + record["content_hash"][:16]
            duplicate_content_records += 1
        record["quality_flags"] = ";".join(flags)

    accepted.sort(key=lambda row: (row["position_id"], row["source_id"]))
    report = {
        "input_records": len(accepted) + len(rejected) + duplicate_source_ids,
        "accepted_records": len(accepted),
        "rejected_records": len(rejected),
        "duplicate_source_records_removed": duplicate_source_ids,
        "duplicate_content_records_retained": duplicate_content_records,
        "missing_publish_time_records": missing_publish_time,
    }
    return accepted, rejected, report


def read_jsonl(path: Path) -> tuple[list[tuple[int, dict[str, Any]]], list[dict[str, str]]]:
    records: list[tuple[int, dict[str, Any]]] = []
    rejected: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                rejected.append(
                    {
                        "line_number": str(line_number),
                        "reason": f"invalid_json:{exc.msg}",
                        "raw_record": line.rstrip("\n"),
                    }
                )
                continue
            if not isinstance(value, dict):
                rejected.append(
                    {
                        "line_number": str(line_number),
                        "reason": "record_is_not_object",
                        "raw_record": line.rstrip("\n"),
                    }
                )
                continue
            records.append((line_number, value))
    return records, rejected


def write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run(input_path: Path, output_dir: Path) -> dict[str, int]:
    records, parse_rejections = read_jsonl(input_path)
    accepted, validation_rejections, report = clean_records(records)
    rejected = parse_rejections + validation_rejections
    report["input_records"] += len(parse_rejections)
    report["rejected_records"] = len(rejected)

    write_csv(output_dir / "cleaned_job_postings.csv", OUTPUT_FIELDS, accepted)
    write_csv(output_dir / "rejected_job_postings.csv", REJECTED_FIELDS, rejected)
    with (output_dir / "cleaning_report.json").open("w", encoding="utf-8") as target:
        json.dump(report, target, ensure_ascii=False, indent=2, sort_keys=True)
        target.write("\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/bytedance_dev_jobs.jsonl"),
        help="原始 JSONL 文件",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="清洗结果目录",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run(args.input, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
