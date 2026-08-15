from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class NodeType(StrEnum):
    POSITION = "position"
    POSITION_CATEGORY = "position_category"
    SKILL = "skill"
    SKILL_CLUSTER = "skill_cluster"
    TECH_STACK = "tech_stack"


class RelationshipType(StrEnum):
    IN_CATEGORY = "IN_CATEGORY"
    REQUIRES = "REQUIRES"
    BELONGS_TO = "BELONGS_TO"


class RequirementType(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class Trend(StrEnum):
    NEW = "new"
    RISING = "rising"
    STABLE = "stable"
    DECLINING = "declining"


@dataclass(slots=True)
class GraphNode:
    id: str
    type: NodeType
    name: str
    properties: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type.value, "name": self.name, **self.properties}


@dataclass(slots=True)
class GraphEdge:
    source: str
    target: str
    relationship: RelationshipType
    properties: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relationship": self.relationship.value,
            **self.properties,
        }


@dataclass(slots=True)
class GraphProjection:
    version: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    created_at: datetime


@dataclass(slots=True)
class ExtractedSkill:
    skill_id: str
    surface: str
    evidence_text: str
    requirement_type: RequirementType
    start_offset: int
    end_offset: int
    extraction_confidence: float
    linking_confidence: float
    extractor: str = "catalog_rule_v1"


@dataclass(slots=True)
class LinkedPosition:
    surface: str
    normalized_title: str
    position_id: str | None
    confidence: float
    status: str


@dataclass(slots=True)
class AggregatedRequirement:
    position_id: str
    skill_id: str
    requirement_type: RequirementType
    weight: float
    frequency: float
    confidence: float
    sample_count: int
    source_ids: list[str]
    first_seen: date
    last_seen: date
    trend: Trend

