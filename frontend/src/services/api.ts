import { dashboardSummary, panoramaEdges, panoramaNodes, positionProfile, reviewItems, skillReverseEdges, skillReverseNodes } from '../data/mock'
import type { ApiResponse, DashboardSummary, GraphData, GraphMode, PositionProfile, ResumeSkillPatch, ResumeTask, ReviewItem, ReviewStatus } from '../types'

const delay = (milliseconds = 180) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

const respond = async <T>(data: T): Promise<ApiResponse<T>> => {
  await delay()
  return { data, requestId: crypto.randomUUID() }
}

const API_BASE = (import.meta.env.VITE_API_BASE ?? '/api/v1').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<ApiResponse<T>> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      /* body is not JSON — keep statusText */
    }
    throw new Error(detail || `Request failed (${response.status})`)
  }
  return response.json() as Promise<ApiResponse<T>>
}

export const resumeApi = {
  upload: (file: File): Promise<ApiResponse<ResumeTask>> => {
    const form = new FormData()
    form.append('file', file)
    return request<ResumeTask>('/resume-tasks', { method: 'POST', body: form })
  },
  get: (taskId: string): Promise<ApiResponse<ResumeTask>> => request<ResumeTask>(`/resume-tasks/${taskId}`),
  patchSkills: (taskId: string, patch: ResumeSkillPatch): Promise<ApiResponse<ResumeTask>> =>
    request<ResumeTask>(`/resume-tasks/${taskId}/skills`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }),
}

export const api = {
  getDashboard: (): Promise<ApiResponse<DashboardSummary>> => respond(dashboardSummary),
  getGraph: (mode: GraphMode = 'panorama'): Promise<ApiResponse<GraphData>> => {
    const nodes = mode === 'panorama' ? panoramaNodes : skillReverseNodes
    const edges = mode === 'panorama' ? panoramaEdges : skillReverseEdges
    return respond({
      mode,
      hierarchy: mode === 'panorama' ? ['cluster', 'position', 'skill'] : ['stack', 'cluster', 'skill', 'position'],
      nodes,
      edges,
      summary: {
        positionClusterCount: mode === 'panorama' ? nodes.filter((node) => node.type === 'cluster').length : 0,
        techStackCount: nodes.filter((node) => node.type === 'stack').length,
        skillClusterCount: mode === 'skill_reverse' ? nodes.filter((node) => node.type === 'cluster').length : 0,
        positionCount: nodes.filter((node) => node.type === 'position').length,
        skillCount: nodes.filter((node) => node.type === 'skill').length,
      },
      updatedAt: '2026-08-03T10:00:00+08:00',
      graphVersion: '2026-08-03.1',
    })
  },
  getPosition: (id: string): Promise<ApiResponse<PositionProfile>> => respond({ ...positionProfile, id }),
  getReviews: (): Promise<ApiResponse<ReviewItem[]>> => respond(reviewItems),
  review: (id: string, status: ReviewStatus): Promise<ApiResponse<{ id: string; status: ReviewStatus }>> => respond({ id, status }),
}
