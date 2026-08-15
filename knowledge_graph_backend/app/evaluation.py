from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import GoldAnnotation, PipelineRun, PositionMention, SkillMention


def extraction_metrics(session: Session, run_id: str | None = None) -> dict[str, object]:
    if run_id is None:
        latest = session.scalar(
            select(PipelineRun).where(PipelineRun.status == "completed").order_by(PipelineRun.completed_at.desc()).limit(1)
        )
        run_id = latest.id if latest else None
    gold = session.scalars(select(GoldAnnotation)).all()
    if not gold or run_id is None:
        return {
            "runId": run_id,
            "sampleCount": len({row.source_id for row in gold}),
            "goldAnnotationCount": len(gold),
            "precision": None,
            "recall": None,
            "f1": None,
            "status": "insufficient_gold_data",
        }
    predicted: set[tuple[str, str, str]] = set()
    for row in session.scalars(select(PositionMention).where(PositionMention.pipeline_run_id == run_id)).all():
        if row.status == "linked" and row.canonical_position_id:
            predicted.add((row.source_id, "position", row.canonical_position_id))
    for row in session.scalars(select(SkillMention).where(SkillMention.pipeline_run_id == run_id)).all():
        predicted.add((row.source_id, "skill", row.canonical_skill_id))
    expected = {(row.source_id, row.annotation_type, row.canonical_id) for row in gold}
    true_positive = len(predicted & expected)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "runId": run_id,
        "sampleCount": len({row.source_id for row in gold}),
        "goldAnnotationCount": len(gold),
        "predictedAnnotationCount": len(predicted),
        "truePositive": true_positive,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "status": "ready",
    }

