from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("run"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", index=True)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    statistics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobPosting(Base):
    __tablename__ = "job_postings"

    source_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    pipeline_run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=False, index=True)
    source_platform: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    locations: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    publish_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirement: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    duplicate_group_id: Mapped[str | None] = mapped_column(String(80), index=True)
    quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class StandardEntity(Base):
    __tablename__ = "standard_entities"
    __table_args__ = (UniqueConstraint("entity_type", "name", name="uq_standard_entity_type_name"),)

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (UniqueConstraint("entity_type", "normalized_alias", name="uq_entity_alias_type_alias"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("alias"))
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("standard_entities.id"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="manual")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class PositionMention(Base):
    __tablename__ = "position_mentions"
    __table_args__ = (UniqueConstraint("pipeline_run_id", "source_id", name="uq_position_mention_run_source"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("pm"))
    pipeline_run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("job_postings.source_id"), nullable=False, index=True)
    surface: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_position_id: Mapped[str | None] = mapped_column(String(100), index=True)
    linking_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="linked")


class SkillMention(Base):
    __tablename__ = "skill_mentions"
    __table_args__ = (
        UniqueConstraint("pipeline_run_id", "source_id", "canonical_skill_id", "start_offset", name="uq_skill_mention"),
        Index("ix_skill_mention_position_skill", "canonical_position_id", "canonical_skill_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("sm"))
    pipeline_run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("job_postings.source_id"), nullable=False, index=True)
    canonical_position_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    canonical_skill_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    surface: Mapped[str] = mapped_column(String(500), nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    extractor: Mapped[str] = mapped_column(String(80), nullable=False)
    extraction_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    linking_confidence: Mapped[float] = mapped_column(Float, nullable=False)


class RequirementSnapshot(Base):
    __tablename__ = "requirement_snapshots"
    __table_args__ = (
        UniqueConstraint("pipeline_run_id", "position_id", "skill_id", "window_start", "window_end", name="uq_snapshot"),
        Index("ix_snapshot_position_window", "position_id", "window_end"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("snap"))
    pipeline_run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=False, index=True)
    position_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    frequency: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    first_seen: Mapped[date] = mapped_column(Date, nullable=False)
    last_seen: Mapped[date] = mapped_column(Date, nullable=False)
    trend: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ChangeEvent(Base):
    __tablename__ = "change_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("change"))
    pipeline_run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=False, index=True)
    position_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ReviewItem(Base):
    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("review"))
    pipeline_run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=False, index=True)
    review_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GoldAnnotation(Base):
    __tablename__ = "gold_annotations"
    __table_args__ = (UniqueConstraint("source_id", "annotation_type", "canonical_id", name="uq_gold_annotation"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("gold"))
    source_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    annotation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    canonical_id: Mapped[str] = mapped_column(String(100), nullable=False)
    requirement_type: Mapped[str | None] = mapped_column(String(24))
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    annotator: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class GraphVersion(Base):
    __tablename__ = "graph_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pipeline_run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", index=True)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
