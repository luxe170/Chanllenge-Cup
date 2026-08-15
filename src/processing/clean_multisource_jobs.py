#!/usr/bin/env python3
"""清洗多源招聘记录并按岗位类型分流。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


CHINA_TIMEZONE = timezone(timedelta(hours=8))

SOURCE_FIELDS = (
    "source_platform",
    "company",
    "recruit_type",
    "source_job_id",
    "job_id",
    "title",
    "locations",
    "employment_type",
    "category",
    "publish_time",
    "description",
    "requirement",
    "url",
    "scraped_at",
)

OUTPUT_FIELDS = (
    "source_id",
    "source_status",
    "source_status_reason",
    "source_status_hits",
    *SOURCE_FIELDS,
    "content_hash",
    "duplicate_group_id",
    "quality_flags",
)

REVIEW_FIELDS = (
    "source_id",
    "source_status",
    "source_status_reason",
    "source_status_hits",
    "source_platform",
    "company",
    "recruit_type",
    "source_job_id",
    "title",
    "category",
    "url",
)

REJECTED_FIELDS = (
    "line_number",
    "source_path",
    "reason",
    "source_id",
    "raw_record",
)

REQUIRED_FIELDS = ("source_platform", "source_job_id", "title", "description", "requirement", "url")

RELEVANT_HINTS = (
    "人工智能",
    "算法",
    "大模型",
    "机器学习",
    "深度学习",
    "nlp",
    "llm",
    "agent",
    "agentic",
    "python",
    "java",
    "go",
    "golang",
    "c++",
    "后端",
    "前端",
    "客户端",
    "数据",
    "大数据",
    "云计算",
    "分布式",
    "运维",
    "测试",
    "安全",
    "物联网",
    "嵌入式",
    "硬件",
    "芯片",
    "npu",
    "cuda",
)

REVIEW_HINTS = (
    "产品",
    "解决方案",
    "架构师",
    "产品经理",
    "项目管理",
    "技术运营",
    "售前",
    "客户成功",
    "ai产品",
    "pm",
    "交互",
    "视觉",
    "设计",
)

REJECT_HINTS = (
    "销售",
    "市场",
    "公关",
    "客服",
    "财务",
    "法务",
    "人力",
    "行政",
    "采购",
    "商务",
    "运营",
    "hr",
    "法务与合规",
)

TECH_CATEGORY_HINTS = (
    "技术",
    "研发",
    "算法",
    "后端",
    "前端",
    "客户端",
    "大数据",
    "人工智能",
    "云",
    "运维",
    "安全",
    "测试",
    "硬件",
    "嵌入式",
    "物联网",
)

CHINESE_TEXT_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def normalize_scalar(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def normalize_multiline(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def normalize_url(value: Any) -> str:
    url = normalize_scalar(value)
    if not url:
        return ""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def normalize_publish_time(value: Any) -> str:
    text = normalize_scalar(value)
    if not text:
        return ""
    for parser in (
        lambda raw: datetime.fromisoformat(raw.replace("Z", "+00:00")),
        lambda raw: datetime.strptime(raw, "%Y年%m月%d日").replace(tzinfo=CHINA_TIMEZONE),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d %H:%M:%S%z"),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CHINA_TIMEZONE),
    ):
        try:
            parsed = parser(text)
        except ValueError:
            continue
        return parsed.astimezone(CHINA_TIMEZONE).isoformat(sep=" ", timespec="seconds")
    return text


def extract_source_id(record: dict[str, str]) -> str:
    return f"{record['source_platform']}:{record['source_job_id']}"


def content_hash(record: dict[str, str]) -> str:
    payload = "\n".join((record["title"], record["description"], record["requirement"]))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_record(record: dict[str, Any]) -> dict[str, str]:
    position_id = normalize_scalar(record.get("position_id"))
    source_platform = normalize_scalar(record.get("source_platform"))
    company = normalize_scalar(record.get("company"))
    recruit_type = normalize_scalar(record.get("recruit_type"))
    source_job_id = normalize_scalar(record.get("source_job_id"))

    if not source_platform and position_id:
        source_platform = "bytedance"
    if not company and source_platform == "bytedance":
        company = "字节跳动"
    if not recruit_type and source_platform == "bytedance":
        recruit_type = "社会招聘"
    if not source_job_id and position_id:
        source_job_id = position_id

    cleaned = {
        "source_platform": source_platform,
        "company": company,
        "recruit_type": recruit_type,
        "source_job_id": source_job_id,
        "job_id": normalize_scalar(record.get("job_id")),
        "title": normalize_scalar(record.get("title")),
        "locations": normalize_scalar(record.get("locations")),
        "employment_type": normalize_scalar(record.get("employment_type")),
        "category": normalize_scalar(record.get("category")),
        "publish_time": normalize_publish_time(record.get("publish_time")),
        "description": normalize_multiline(record.get("description")),
        "requirement": normalize_multiline(record.get("requirement")),
        "url": normalize_url(record.get("url")),
        "scraped_at": normalize_publish_time(record.get("scraped_at")),
    }
    cleaned["source_id"] = extract_source_id(cleaned)
    cleaned["content_hash"] = content_hash(cleaned)
    cleaned["duplicate_group_id"] = ""
    cleaned["quality_flags"] = ""
    cleaned["source_status"] = ""
    cleaned["source_status_reason"] = ""
    cleaned["source_status_hits"] = ""
    return cleaned


def text_blob(record: dict[str, str]) -> str:
    return " ".join(
        filter(
            None,
            (
                record["title"],
                record["category"],
                record["description"],
                record["requirement"],
                record["company"],
                record["recruit_type"],
            ),
        )
    ).lower()


def has_chinese_jd_text(record: dict[str, str]) -> bool:
    jd_text = "\n".join((record["title"], record["description"], record["requirement"]))
    return bool(CHINESE_TEXT_PATTERN.search(jd_text))


def status_reason(record: dict[str, str]) -> tuple[str, list[str]]:
    missing = [field for field in REQUIRED_FIELDS if not record[field]]
    if missing:
        return f"missing_required_fields:{','.join(missing)}", []
    if not record["url"].startswith(("http://", "https://")):
        return "invalid_url", []
    if not has_chinese_jd_text(record):
        return "rejected:non_chinese_jd", ["reject:non_chinese_jd"]

    blob = text_blob(record)
    title_category_blob = f"{record['title']} {record['category']}".lower()
    hits: list[str] = []

    for keyword in REJECT_HINTS:
        if keyword.lower() in blob:
            hits.append(f"reject:{keyword}")

    for keyword in REVIEW_HINTS:
        if keyword.lower() in blob:
            hits.append(f"review:{keyword}")

    for keyword in RELEVANT_HINTS:
        if keyword.lower() in blob:
            hits.append(f"relevant:{keyword}")

    category_hit = any(keyword in record["category"] for keyword in TECH_CATEGORY_HINTS)
    title_hit = any(keyword in record["title"].lower() for keyword in RELEVANT_HINTS)
    relevant_hit = any(hit.startswith("relevant:") for hit in hits) or category_hit or title_hit
    review_hit = any(hit.startswith("review:") for hit in hits)
    reject_hit = any(hit.startswith("reject:") for hit in hits)
    reject_in_title = any(keyword.lower() in title_category_blob for keyword in REJECT_HINTS)

    if reject_in_title and not (title_hit or category_hit):
        return "rejected:non_target_role", hits
    if reject_hit and not relevant_hit and not review_hit:
        return "rejected:non_target_role", hits
    if review_hit and not relevant_hit:
        return "review:ambiguous_or_boundary_role", hits
    if review_hit and relevant_hit:
        return "review:boundary_role_with_tech_signals", hits
    if relevant_hit:
        return "relevant:target_tech_role", hits
    return "review:insufficient_signal", hits


def record_quality(record: dict[str, str]) -> tuple[int, int, int]:
    populated = sum(bool(record[field]) for field in SOURCE_FIELDS)
    text_length = len(record["description"]) + len(record["requirement"])
    return populated, text_length, len(record["title"])


def read_jsonl(path: Path) -> tuple[list[tuple[int, str, dict[str, Any]]], list[dict[str, str]]]:
    records: list[tuple[int, str, dict[str, Any]]] = []
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
                        "source_path": path.name,
                        "reason": f"invalid_json:{exc.msg}",
                        "source_id": "",
                        "raw_record": line.rstrip("\n"),
                    }
                )
                continue
            if not isinstance(value, dict):
                rejected.append(
                    {
                        "line_number": str(line_number),
                        "source_path": path.name,
                        "reason": "record_is_not_object",
                        "source_id": "",
                        "raw_record": line.rstrip("\n"),
                    }
                )
                continue
            records.append((line_number, path.name, value))
    return records, rejected


def read_inputs(paths: Iterable[Path]) -> tuple[list[tuple[int, str, dict[str, Any]]], list[dict[str, str]]]:
    records: list[tuple[int, str, dict[str, Any]]] = []
    rejected: list[dict[str, str]] = []
    for path in paths:
        file_records, file_rejected = read_jsonl(path)
        records.extend(file_records)
        rejected.extend(file_rejected)
    return records, rejected


def classify_records(
    records: Iterable[tuple[int, str, dict[str, Any]]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    accepted_by_source: dict[str, dict[str, str]] = {}
    rejected: list[dict[str, str]] = []
    review: list[dict[str, str]] = []
    status_counts = Counter()
    duplicate_source_records = 0

    for line_number, source_path, raw in records:
        cleaned = normalize_record(raw)
        reason, hits = status_reason(cleaned)
        cleaned["source_status_reason"] = reason
        cleaned["source_status_hits"] = ";".join(hits)

        if reason.startswith("missing_required_fields") or reason == "invalid_url":
            rejected.append(
                {
                    "line_number": str(line_number),
                    "source_path": source_path,
                    "reason": reason,
                    "source_id": cleaned["source_id"],
                    "raw_record": json.dumps(raw, ensure_ascii=False, sort_keys=True),
                }
            )
            status_counts["rejected"] += 1
            continue

        if reason.startswith("rejected:"):
            rejected.append(
                {
                    "line_number": str(line_number),
                    "source_path": source_path,
                    "reason": reason,
                    "source_id": cleaned["source_id"],
                    "raw_record": json.dumps(raw, ensure_ascii=False, sort_keys=True),
                }
            )
            status_counts["rejected"] += 1
            continue

        cleaned["source_status"] = reason.split(":", 1)[0]

        previous = accepted_by_source.get(cleaned["source_id"])
        if previous is None:
            accepted_by_source[cleaned["source_id"]] = cleaned
        else:
            duplicate_source_records += 1
            if record_quality(cleaned) > record_quality(previous):
                accepted_by_source[cleaned["source_id"]] = cleaned

        status_counts[cleaned["source_status"]] += 1

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

    accepted.sort(key=lambda row: (row["company"], row["title"], row["source_id"]))
    rejected.sort(key=lambda row: (row["source_path"], int(row["line_number"])))

    report = {
        "input_records": len(accepted) + len(rejected) + duplicate_source_records,
        "accepted_records": len([row for row in accepted if row["source_status"] == "relevant"]),
        "review_records": len([row for row in accepted if row["source_status"] == "review"]),
        "rejected_records": len(rejected),
        "duplicate_source_records_removed": duplicate_source_records,
        "duplicate_content_records_retained": duplicate_content_records,
        "missing_publish_time_records": missing_publish_time,
        "status_relevant_records": status_counts["relevant"],
        "status_review_records": status_counts["review"],
        "status_rejected_records": status_counts["rejected"],
    }
    for record in accepted:
        if record["source_status"] == "review":
            review.append(
                {
                    "source_id": record["source_id"],
                    "source_status": record["source_status"],
                    "source_status_reason": record["source_status_reason"],
                    "source_status_hits": record["source_status_hits"],
                    "source_platform": record["source_platform"],
                    "company": record["company"],
                    "recruit_type": record["recruit_type"],
                    "source_job_id": record["source_job_id"],
                    "title": record["title"],
                    "category": record["category"],
                    "url": record["url"],
                }
            )

    review.sort(key=lambda row: (row["company"], row["title"], row["source_id"]))

    return (
        [row for row in accepted if row["source_status"] == "relevant"],
        review,
        rejected,
        report,
    )


def write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            target.write("\n")


def run(input_paths: list[Path], output_dir: Path) -> dict[str, int]:
    records, parse_rejections = read_inputs(input_paths)
    relevant, review, rejected, report = classify_records(records)
    rejected = parse_rejections + rejected
    report["input_records"] += len(parse_rejections)
    report["rejected_records"] = len(rejected)

    write_csv(output_dir / "relevant_jobs.csv", OUTPUT_FIELDS, relevant)
    write_jsonl(output_dir / "relevant_jobs.jsonl", relevant)
    write_csv(output_dir / "review_jobs.csv", REVIEW_FIELDS, review)
    write_csv(output_dir / "rejected_jobs.csv", REJECTED_FIELDS, rejected)
    with (output_dir / "cleaning_report.json").open("w", encoding="utf-8") as target:
        json.dump(report, target, ensure_ascii=False, indent=2, sort_keys=True)
        target.write("\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        nargs="*",
        default=sorted(Path("data/raw").glob("*jobs.jsonl")),
        help="原始 JSONL 文件，默认读取 data/raw 下所有 jobs.jsonl",
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
    report = run([Path(path) for path in args.input], args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
