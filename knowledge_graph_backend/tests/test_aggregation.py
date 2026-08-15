from datetime import date

import pytest

from app.aggregation import AggregationConfig, PositionPosting, RequirementEvidence, aggregate_requirements
from app.domain import RequirementType, Trend


def evidence(source: str, day: date, duplicate: str | None = None) -> RequirementEvidence:
    return RequirementEvidence(
        source_id=source,
        position_id="pos_ai_agent_engineer",
        skill_id="skill_rag",
        company="company_" + source[-1],
        publish_date=day,
        requirement_type=RequirementType.REQUIRED,
        extraction_confidence=0.95,
        linking_confidence=0.95,
        duplicate_group_id=duplicate,
    )


def test_aggregation_uses_all_position_postings_as_denominator_and_deduplicates():
    rows = [
        evidence("jd_1", date(2026, 8, 1), "dup_a"),
        evidence("jd_2", date(2026, 8, 2), "dup_a"),
        evidence("jd_3", date(2026, 8, 3)),
    ]
    postings = [
        PositionPosting("jd_1", "pos_ai_agent_engineer", date(2026, 8, 1), "dup_a"),
        PositionPosting("jd_2", "pos_ai_agent_engineer", date(2026, 8, 2), "dup_a"),
        PositionPosting("jd_3", "pos_ai_agent_engineer", date(2026, 8, 3)),
        PositionPosting("jd_4", "pos_ai_agent_engineer", date(2026, 8, 4)),
    ]
    result = aggregate_requirements(rows, AggregationConfig(window_days=30, min_sample_count=2), date(2026, 8, 15), postings)
    assert len(result.requirements) == 1
    requirement = result.requirements[0]
    assert requirement.sample_count == 2
    assert requirement.frequency == pytest.approx(2 / 3, abs=0.0001)
    assert requirement.trend == Trend.NEW


def test_aggregation_rejects_insufficient_support():
    result = aggregate_requirements(
        [evidence("jd_1", date(2026, 8, 1))],
        AggregationConfig(window_days=30, min_sample_count=2),
        date(2026, 8, 15),
    )
    assert result.requirements == ()
