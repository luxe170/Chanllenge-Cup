import { dashboardSummary, panoramaEdges, panoramaNodes, positionProfile, reviewItems, skillReverseEdges, skillReverseNodes } from '../data/mock'
import type { ApiResponse, DashboardSummary, GraphData, GraphMode, PositionProfile, ReviewItem, ReviewStatus } from '../types'

const delay = (milliseconds = 180) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

const respond = async <T>(data: T): Promise<ApiResponse<T>> => {
  await delay()
  return { data, requestId: crypto.randomUUID() }
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
