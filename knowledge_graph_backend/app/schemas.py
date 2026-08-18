from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PipelineRunCreate(BaseModel):
    sourceFile: str = "relevant_jobs.csv"
    parameters: dict[str, Any] = Field(default_factory=dict)


class ReviewDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = ""
    modifications: dict[str, Any] = Field(default_factory=dict)


class GoldAnnotationCreate(BaseModel):
    sourceId: str
    annotationType: Literal["position", "skill"]
    canonicalId: str
    requirementType: Literal["required", "preferred"] | None = None
    startOffset: int | None = Field(default=None, ge=0)
    endOffset: int | None = Field(default=None, ge=0)
    annotator: str = Field(min_length=1, max_length=100)


class EntityCreate(BaseModel):
    id: str = Field(pattern=r"^(pos|category|skill|cluster|stack)_[a-z0-9_]+$")
    entityType: Literal["position", "position_category", "skill", "skill_cluster", "tech_stack"]
    name: str = Field(min_length=1, max_length=500)
    description: str = ""
    status: str = "active"
    properties: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)


class ResumeSkillAdd(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    level: Literal["熟悉", "掌握", "精通"] = "掌握"
    source: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ResumeSkillUpdate(BaseModel):
    id: str | None = None
    name: str | None = Field(default=None, max_length=120)
    level: Literal["熟悉", "掌握", "精通"] | None = None
    source: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ResumeSkillPatch(BaseModel):
    added: list[ResumeSkillAdd] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    updated: list[ResumeSkillUpdate] = Field(default_factory=list)


class RunView(BaseModel):
    id: str
    status: str
    sourcePath: str
    parameters: dict[str, Any]
    statistics: dict[str, Any]
    error: str | None
    createdAt: datetime
    startedAt: datetime | None
    completedAt: datetime | None

