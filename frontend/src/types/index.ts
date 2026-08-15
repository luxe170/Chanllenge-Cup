export type Trend = 'new' | 'rising' | 'stable' | 'declining'
export type RequirementType = 'required' | 'preferred'
export type ReviewStatus = 'pending' | 'approved' | 'rejected'
export type GraphMode = 'panorama' | 'skill_reverse'

export interface DashboardSummary {
  sourceCount: number
  validCount: number
  emergingCount: number
  changedCount: number
  metrics: EvaluationMetric[]
}

export interface EvaluationMetric {
  name: string
  value: number
  target: number
  sampleCount: number
}

export interface GraphNode {
  id: string
  name: string
  type: 'position' | 'skill' | 'cluster' | 'stack'
  x?: number
  y?: number
  trend?: Trend
  weight?: number
  sampleCount?: number
  firstSeen?: string
  confidence?: number
}

export interface GraphEdge {
  source: string
  target: string
  relationship: 'REQUIRES' | 'BELONGS_TO'
  requirementType?: RequirementType
  weight?: number
  confidence?: number
}

export interface GraphData {
  mode: GraphMode
  hierarchy: GraphNode['type'][]
  nodes: GraphNode[]
  edges: GraphEdge[]
  summary: {
    positionClusterCount: number
    techStackCount: number
    skillClusterCount: number
    positionCount: number
    skillCount: number
  }
  updatedAt: string
  graphVersion: string
  truncated?: boolean
}

export interface SkillRequirement {
  id: string
  name: string
  type: RequirementType
  weight: number
  frequency: number
  confidence: number
  trend: Trend
  firstSeen: string
  evidenceCount: number
}

export interface PositionProfile {
  id: string
  name: string
  category: string
  techStack: string
  level: string
  status: 'emerging' | 'existing' | 'inactive'
  description: string
  firstSeen: string
  lastSeen: string
  confidence: number
  sampleCount: number
  aliases: string[]
  responsibilities: string[]
  scenarios: string[]
  requirements: SkillRequirement[]
}

export interface ChangeRecord {
  id: string
  position: string
  skill: string
  changeType: '新增' | '增强' | '修改' | '下降'
  before: string
  after: string
  date: string
  evidenceCount: number
  confidence: number
}

export interface ResumeSkill {
  name: string
  level: '熟悉' | '掌握' | '精通'
  source: string
  confidence: number
}

export interface MatchDimension {
  name: string
  value: number
  color: string
}

export interface LearningStep {
  stage: number
  title: string
  duration: string
  skills: string[]
  goal: string
}

export interface ReviewItem {
  id: string
  type: '新岗位' | '能力变更' | '技能归一'
  title: string
  description: string
  confidence: number
  sources: string[]
  createdAt: string
  status: ReviewStatus
}

export interface ApiResponse<T> {
  data: T
  requestId: string
}
