from typing import Literal, Optional

from pydantic import BaseModel, Field


RequirementType = Literal["required", "preferred"]
ChangeType = Literal["new", "rising", "declining"]


class RequirementSnapshot(BaseModel):
    requirementType: RequirementType
    weight: float = Field(ge=0.0, le=1.0)


class EvolutionChangeItem(BaseModel):
    id: str
    positionId: str
    positionName: str
    skillId: str
    skillName: str
    changeType: ChangeType
    before: Optional[RequirementSnapshot] = None
    after: RequirementSnapshot
    evidenceCount: int
    confidence: float = Field(ge=0.0, le=1.0)
    detectedAt: str


class EvolutionChangesResponse(BaseModel):
    items: list[EvolutionChangeItem]
    total: int
    page: int
    pageSize: int


class SourceSupport(BaseModel):
    companyCount: int
    jobCount: int


class WindowContinuity(BaseModel):
    continuousWindowCount: int
    passed: bool


class ChangeEvidence(BaseModel):
    changeId: str
    positionId: str
    positionName: str
    skillId: str
    skillName: str
    before: Optional[RequirementSnapshot] = None
    after: RequirementSnapshot
    confidence: float = Field(ge=0.0, le=1.0)
    sourceSupport: SourceSupport
    windowContinuity: WindowContinuity
    semanticConsistency: float = Field(ge=0.0, le=1.0)
    evidenceIds: list[str]


class EmergingSkill(BaseModel):
    id: str
    name: str


class EmergingPositionItem(BaseModel):
    id: str
    positionId: str
    name: str
    description: str
    growthRate: float
    confidence: float = Field(ge=0.0, le=1.0)
    firstSeen: str
    sourceCount: int
    sampleCount: int
    skills: list[EmergingSkill]


class EmergingPositionsResponse(BaseModel):
    items: list[EmergingPositionItem]
    total: int
    page: int
    pageSize: int


class SkillRequirement(BaseModel):
    id: str
    name: str
    type: RequirementType
    weight: float = Field(ge=0.0, le=1.0)
    frequency: int
    confidence: float = Field(ge=0.0, le=1.0)
    trend: Literal["new", "rising", "stable", "declining"] = "stable"
    firstSeen: str
    evidenceCount: int


class PositionProfile(BaseModel):
    id: str
    name: str
    category: str
    techStack: str
    level: str
    status: Literal["emerging", "existing", "inactive"]
    description: str
    firstSeen: str
    lastSeen: str
    confidence: float = Field(ge=0.0, le=1.0)
    sampleCount: int
    aliases: list[str]
    responsibilities: list[str]
    scenarios: list[str]
    requirements: list[SkillRequirement]


class ApiResponse(BaseModel):
    data: dict
    requestId: str
