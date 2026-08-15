from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from .domain import AggregatedRequirement, RequirementType, Trend


@dataclass(frozen=True, slots=True)
class RequirementEvidence:
    source_id: str
    position_id: str
    skill_id: str
    company: str
    publish_date: date
    requirement_type: RequirementType
    extraction_confidence: float
    linking_confidence: float
    duplicate_group_id: str | None = None


@dataclass(frozen=True, slots=True)
class PositionPosting:
    source_id: str
    position_id: str
    publish_date: date
    duplicate_group_id: str | None = None


@dataclass(frozen=True, slots=True)
class AggregationConfig:
    window_days: int = 90
    min_sample_count: int = 2
    rising_delta: float = 0.12
    declining_delta: float = -0.12


@dataclass(frozen=True, slots=True)
class AggregationResult:
    requirements: tuple[AggregatedRequirement, ...]
    window_start: date
    window_end: date


def _deduplicate(evidence: list[RequirementEvidence]) -> list[RequirementEvidence]:
    seen: set[tuple[str, str, str]] = set()
    result: list[RequirementEvidence] = []
    for item in sorted(evidence, key=lambda row: (row.source_id, row.skill_id)):
        evidence_identity = item.duplicate_group_id or item.source_id
        key = (item.position_id, item.skill_id, evidence_identity)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _support_score(sample_count: int, minimum: int) -> float:
    return min(1.0, sample_count / max(minimum * 3, 1))


def _source_diversity(companies: set[str]) -> float:
    return min(1.0, len(companies) / 4)


def _aggregate_window(
    evidence: list[RequirementEvidence],
    postings: list[PositionPosting],
    start: date,
    end: date,
    minimum: int,
) -> tuple[dict[tuple[str, str], dict[str, object]], dict[str, int]]:
    window_rows = [row for row in evidence if start <= row.publish_date <= end]
    unique_postings: dict[str, set[str]] = defaultdict(set)
    for posting in postings:
        if start <= posting.publish_date <= end:
            unique_postings[posting.position_id].add(posting.duplicate_group_id or posting.source_id)
    grouped: dict[tuple[str, str], list[RequirementEvidence]] = defaultdict(list)
    for row in window_rows:
        grouped[(row.position_id, row.skill_id)].append(row)

    output: dict[tuple[str, str], dict[str, object]] = {}
    denominators = {position_id: len(ids) for position_id, ids in unique_postings.items()}
    for key, raw_items in grouped.items():
        items = _deduplicate(raw_items)
        position_id, _ = key
        sample_count = len(items)
        frequency = sample_count / max(denominators.get(position_id, sample_count), 1)
        types = Counter(item.requirement_type for item in items)
        requirement_type = (
            RequirementType.REQUIRED
            if types[RequirementType.REQUIRED] >= types[RequirementType.PREFERRED]
            else RequirementType.PREFERRED
        )
        mean_extraction = sum(item.extraction_confidence * item.linking_confidence for item in items) / sample_count
        companies = {item.company for item in items if item.company}
        consistency = max(types.values()) / sample_count
        confidence = (
            0.35 * mean_extraction
            + 0.25 * _support_score(sample_count, minimum)
            + 0.20 * _source_diversity(companies)
            + 0.20 * consistency
        )
        required_ratio = types[RequirementType.REQUIRED] / sample_count
        weight = min(1.0, 0.55 * frequency + 0.30 * required_ratio + 0.15 * mean_extraction)
        output[key] = {
            "requirement_type": requirement_type,
            "weight": round(weight, 4),
            "frequency": round(frequency, 4),
            "confidence": round(min(1.0, confidence), 4),
            "sample_count": sample_count,
            "source_ids": sorted(item.source_id for item in items),
            "first_seen": min(item.publish_date for item in items),
            "last_seen": max(item.publish_date for item in items),
        }
    return output, denominators


def aggregate_requirements(
    evidence: list[RequirementEvidence],
    config: AggregationConfig,
    window_end: date | None = None,
    postings: list[PositionPosting] | None = None,
) -> AggregationResult:
    if config.window_days < 1:
        raise ValueError("window_days must be positive")
    if config.min_sample_count < 1:
        raise ValueError("min_sample_count must be positive")
    if not evidence:
        end = window_end or date.today()
        return AggregationResult((), end - timedelta(days=config.window_days - 1), end)

    posting_rows = postings or [
        PositionPosting(row.source_id, row.position_id, row.publish_date, row.duplicate_group_id)
        for row in evidence
    ]
    end = window_end or max(item.publish_date for item in evidence)
    current_start = end - timedelta(days=config.window_days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=config.window_days - 1)
    current, _ = _aggregate_window(evidence, posting_rows, current_start, end, config.min_sample_count)
    previous, _ = _aggregate_window(evidence, posting_rows, previous_start, previous_end, config.min_sample_count)

    requirements: list[AggregatedRequirement] = []
    for (position_id, skill_id), values in current.items():
        sample_count = int(values["sample_count"])
        if sample_count < config.min_sample_count:
            continue
        older = previous.get((position_id, skill_id))
        if older is None:
            trend = Trend.NEW
        else:
            delta = float(values["frequency"]) - float(older["frequency"])
            if delta >= config.rising_delta:
                trend = Trend.RISING
            elif delta <= config.declining_delta:
                trend = Trend.DECLINING
            else:
                trend = Trend.STABLE
        requirements.append(
            AggregatedRequirement(
                position_id=position_id,
                skill_id=skill_id,
                requirement_type=values["requirement_type"],  # type: ignore[arg-type]
                weight=float(values["weight"]),
                frequency=float(values["frequency"]),
                confidence=float(values["confidence"]),
                sample_count=sample_count,
                source_ids=list(values["source_ids"]),  # type: ignore[arg-type]
                first_seen=values["first_seen"],  # type: ignore[arg-type]
                last_seen=values["last_seen"],  # type: ignore[arg-type]
                trend=trend,
            )
        )
    requirements.sort(key=lambda row: (row.position_id, -row.weight, row.skill_id))
    return AggregationResult(tuple(requirements), current_start, end)
