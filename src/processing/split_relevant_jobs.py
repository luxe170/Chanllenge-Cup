from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.app.services.data_sources import read_jsonl, write_jsonl
from backend.app.services.evolution_service import _parse_datetime, _position_for_record, _record_time_value


DEFAULT_TRAIN_SIZE = 200
DEFAULT_TEST_SIZE = 100


def _stable_id(record: dict[str, Any]) -> str:
    explicit = record.get("source_id") or record.get("content_hash")
    if explicit:
        return str(explicit)
    payload = "|".join(
        str(record.get(field, ""))
        for field in ("source_platform", "source_job_id", "title", "url", "publish_time")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_sort_key(record: dict[str, Any]) -> str:
    return hashlib.sha256(_stable_id(record).encode("utf-8")).hexdigest()


def _quarter(record: dict[str, Any]) -> str:
    try:
        parsed = _parse_datetime(_record_time_value(record))
    except (TypeError, ValueError):
        return "missing_time"
    return f"{parsed.year}-Q{((parsed.month - 1) // 3) + 1}"


def _has_usable_time(record: dict[str, Any]) -> bool:
    if not _record_time_value(record):
        return False
    try:
        _parse_datetime(_record_time_value(record))
    except (TypeError, ValueError):
        return False
    return True


def _bucket_key(record: dict[str, Any]) -> tuple[str, str, str]:
    position_id = _position_for_record(record)
    position_bucket = position_id if not position_id.startswith("candidate_") else "candidate"
    return (position_bucket, str(record.get("source_platform") or "unknown"), _quarter(record))


def _take_balanced(records: list[dict[str, Any]], target_size: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        buckets[_bucket_key(record)].append(record)
    for bucket in buckets.values():
        bucket.sort(key=_stable_sort_key)

    selected: list[dict[str, Any]] = []
    while len(selected) < target_size and buckets:
        progressed = False
        for key in sorted(list(buckets)):
            bucket = buckets[key]
            if not bucket:
                del buckets[key]
                continue
            selected.append(bucket.pop(0))
            progressed = True
            if len(selected) == target_size:
                break
        if not progressed:
            break

    selected_ids = {_stable_id(record) for record in selected}
    remaining = [record for record in records if _stable_id(record) not in selected_ids]
    return selected, remaining


def _distribution(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get(field) or "unknown") for record in records).items()))


def _position_distribution(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(_position_for_record(record) for record in records).items()))


def split_relevant_jobs(
    input_path: Path,
    output_dir: Path,
    train_size: int = DEFAULT_TRAIN_SIZE,
    test_size: int = DEFAULT_TEST_SIZE,
) -> dict[str, Any]:
    records = read_jsonl(input_path)
    if len(records) < train_size + test_size:
        raise ValueError(f"Need at least {train_size + test_size} records, got {len(records)}")

    seen: set[str] = set()
    unique_records: list[dict[str, Any]] = []
    duplicate_ids: list[str] = []
    for record in records:
        identity = _stable_id(record)
        if identity in seen:
            duplicate_ids.append(identity)
            continue
        seen.add(identity)
        unique_records.append(record)

    missing_time = [record for record in unique_records if not _has_usable_time(record)]
    eligible = [record for record in unique_records if _has_usable_time(record)]
    eligible.sort(key=_stable_sort_key)

    known_eligible = [record for record in eligible if not _position_for_record(record).startswith("candidate_")]
    candidate_eligible = [record for record in eligible if _position_for_record(record).startswith("candidate_")]
    if len(known_eligible) < train_size:
        raise ValueError(f"Need at least {train_size} standard-position records for graph training, got {len(known_eligible)}")

    graph_train, known_remaining = _take_balanced(known_eligible, train_size)
    remaining = sorted([*known_remaining, *candidate_eligible], key=_stable_sort_key)
    jd_test, remaining = _take_balanced(remaining, test_size)
    holdout = remaining + sorted(missing_time, key=_stable_sort_key)

    if len(graph_train) != train_size or len(jd_test) != test_size:
        raise ValueError("Unable to produce requested split sizes from eligible records")

    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / f"graph_train_{train_size}.jsonl"
    test_path = output_dir / f"jd_test_set_{test_size}.jsonl"
    holdout_path = output_dir / f"jd_holdout_{len(holdout)}.jsonl"
    report_path = output_dir / "split_report.json"

    write_jsonl(train_path, graph_train)
    write_jsonl(test_path, jd_test)
    write_jsonl(holdout_path, holdout)

    report = {
        "generatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "inputPath": str(input_path),
        "totalRecords": len(records),
        "uniqueRecords": len(unique_records),
        "duplicateRecordsSkipped": len(duplicate_ids),
        "missingTimeRecords": len(missing_time),
        "graphTrainCount": len(graph_train),
        "jdTestCount": len(jd_test),
        "holdoutCount": len(holdout),
        "files": {
            "graphTrain": str(train_path),
            "jdTest": str(test_path),
            "holdout": str(holdout_path),
        },
        "distributions": {
            "graphTrainBySource": _distribution(graph_train, "source_platform"),
            "jdTestBySource": _distribution(jd_test, "source_platform"),
            "holdoutBySource": _distribution(holdout, "source_platform"),
            "graphTrainByPosition": _position_distribution(graph_train),
            "jdTestByPosition": _position_distribution(jd_test),
            "holdoutByPosition": _position_distribution(holdout),
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Split relevant JD records into graph training, test and holdout sets.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/relevant_jobs.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/splits"))
    parser.add_argument("--train-size", type=int, default=DEFAULT_TRAIN_SIZE)
    parser.add_argument("--test-size", type=int, default=DEFAULT_TEST_SIZE)
    args = parser.parse_args()

    report = split_relevant_jobs(args.input, args.output_dir, args.train_size, args.test_size)
    print(
        "split relevant jobs: "
        f"{report['graphTrainCount']} train, {report['jdTestCount']} test, {report['holdoutCount']} holdout"
    )


if __name__ == "__main__":
    main()
