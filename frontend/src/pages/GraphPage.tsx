import { ChevronDown, Focus, Layers3, Maximize2, Minus, Plus, Search, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { SectionHeader } from '../components/common'
import Graph3D from '../components/graph/Graph3D'
import { panoramaEdges, panoramaNodes, skillReverseEdges, skillReverseNodes } from '../data/mock'
import { api } from '../services/api'
import type { GraphData, GraphEdge, GraphMode, GraphNode, GraphNodeDetail, GraphRoot, GraphSearchItem } from '../types'

const nodeColors = { position: '#7c6df2', skill: '#45c9dc', cluster: '#58d09e' }

const modeConfig: Record<GraphMode, { label: string; title: string; subtitle: string; description: string }> = {
  panorama: {
    label: '全景模式',
    title: '新一代信息技术岗位全景',
    subtitle: '岗位簇 → 岗位 → 技能点',
    description: '从岗位簇出发，逐层查看标准岗位及其直接要求的技能点。',
  },
  skill_reverse: {
    label: '技能反查',
    title: '技能需求反查图谱',
    subtitle: '技能簇 → 技能点 → 岗位',
    description: '从技能簇展开技能点，反向查看每个技能对应的需求岗位。',
  },
}

const createFallbackGraph = (mode: GraphMode, sourceNodes: GraphNode[], sourceEdges: GraphEdge[]): GraphData => {
  const nodes = mode === 'skill_reverse' ? sourceNodes.filter((node) => node.type !== 'stack') : sourceNodes
  const nodeIds = new Set(nodes.map((node) => node.id))
  const edges = sourceEdges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
  return ({
  mode,
  hierarchy: mode === 'panorama' ? ['cluster', 'position', 'skill'] : ['cluster', 'skill', 'position'],
  nodes,
  edges,
  summary: {
    positionClusterCount: nodes.filter((node) => mode === 'panorama' && node.type === 'cluster').length,
    techStackCount: nodes.filter((node) => node.type === 'stack').length,
    skillClusterCount: nodes.filter((node) => mode === 'skill_reverse' && node.type === 'cluster').length,
    positionCount: nodes.filter((node) => node.type === 'position').length,
    skillCount: nodes.filter((node) => node.type === 'skill').length,
  },
  updatedAt: '2026-07-29T10:00:00+08:00',
  graphVersion: 'mock.1',
  })
}

const fallbackGraphs: Record<GraphMode, GraphData> = {
  panorama: createFallbackGraph('panorama', panoramaNodes, panoramaEdges),
  skill_reverse: createFallbackGraph('skill_reverse', skillReverseNodes, skillReverseEdges),
}

const layerGuides: Record<GraphMode, Array<{ label: string; top: string }>> = {
  panorama: [
    { label: '岗位簇', top: '8%' },
    { label: '岗位', top: '43%' },
    { label: '技能点', top: '82%' },
  ],
  skill_reverse: [
    { label: '技能簇', top: '8%' },
    { label: '技能点', top: '45%' },
    { label: '岗位', top: '84%' },
  ],
}

const cleanName = (name: string) => name.replaceAll('\n', ' ')

export default function GraphPage() {
  const [mode, setMode] = useState<GraphMode>('panorama')
  const [activeGraph, setActiveGraph] = useState<GraphData>(fallbackGraphs.panorama)
  const [selectedNode, setSelectedNode] = useState<GraphNode>(fallbackGraphs.panorama.nodes[0])
  const [selectedDetail, setSelectedDetail] = useState<GraphNodeDetail | null>(null)
  const [roots, setRoots] = useState<GraphRoot[]>([])
  const [keyword, setKeyword] = useState('')
  const [searchItems, setSearchItems] = useState<GraphSearchItem[]>([])
  const [scale, setScale] = useState(1)
  const [resetSignal, setResetSignal] = useState(0)
  const [selectedRootId, setSelectedRootId] = useState('')
  const [rootMenuOpen, setRootMenuOpen] = useState(false)
  const activeConfig = modeConfig[mode]

  useEffect(() => {
    let active = true
    api.getGraph(mode)
      .then((res) => {
        const nextGraph = res.data.nodes.length > 0 ? res.data : fallbackGraphs[mode]
        if (!active) return
        setActiveGraph(nextGraph)
        setSelectedNode(nextGraph.nodes[0])
      })
      .catch(() => {
        if (!active) return
        setActiveGraph(fallbackGraphs[mode])
        setSelectedNode(fallbackGraphs[mode].nodes[0])
      })
    return () => { active = false }
  }, [mode])

  useEffect(() => {
    api.getGraphRoots(mode).then((res) => setRoots(res.data)).catch(() => setRoots([]))
  }, [mode])

  useEffect(() => {
    setSelectedDetail(null)
    api.getGraphNodeDetail(selectedNode.id).then((res) => setSelectedDetail(res.data)).catch(() => setSelectedDetail(null))
  }, [selectedNode.id])

  useEffect(() => {
    if (keyword.trim().length < 2) {
      setSearchItems([])
      return
    }
    const timer = window.setTimeout(() => {
      api.searchGraph(mode, keyword.trim(), 6).then((res) => setSearchItems(res.data)).catch(() => setSearchItems([]))
    }, 300)
    return () => window.clearTimeout(timer)
  }, [keyword, mode])

  const changeMode = (nextMode: GraphMode) => {
    setMode(nextMode)
    setKeyword('')
    setSearchItems([])
    setScale(1)
    setSelectedRootId('')
    setRootMenuOpen(false)
    setResetSignal((value) => value + 1)
  }

  const focusNode = (nodeId: string) => {
    const target = activeGraph.nodes.find((node) => node.id === nodeId)
    if (target) setSelectedNode(target)
  }

  const displayedGraph = useMemo<GraphData>(() => {
    if (!selectedRootId) return activeGraph
    const included = new Set<string>([selectedRootId])
    let changed = true
    while (changed) {
      changed = false
      activeGraph.edges.forEach((edge) => {
        const followsHierarchy = edge.relationship === 'BELONGS_TO' && included.has(edge.target)
        if (followsHierarchy && !included.has(edge.source)) {
          included.add(edge.source)
          changed = true
        }

        const followsPanoramaSkills = mode === 'panorama' && edge.relationship === 'REQUIRES' && included.has(edge.source)
        if (followsPanoramaSkills && !included.has(edge.target)) {
          included.add(edge.target)
          changed = true
        }

        const followsReversePositions = mode === 'skill_reverse' && edge.relationship === 'REQUIRES' && included.has(edge.target)
        if (followsReversePositions && !included.has(edge.source)) {
          included.add(edge.source)
          changed = true
        }
      })
    }
    const nodes = activeGraph.nodes.filter((node) => included.has(node.id))
    const edges = activeGraph.edges.filter((edge) => included.has(edge.source) && included.has(edge.target))
    return {
      ...activeGraph,
      nodes,
      edges,
      summary: {
        positionClusterCount: nodes.filter((node) => mode === 'panorama' && node.type === 'cluster').length,
        techStackCount: nodes.filter((node) => node.type === 'stack').length,
        skillClusterCount: nodes.filter((node) => mode === 'skill_reverse' && node.type === 'cluster').length,
        positionCount: nodes.filter((node) => node.type === 'position').length,
        skillCount: nodes.filter((node) => node.type === 'skill').length,
      },
    }
  }, [activeGraph, mode, selectedRootId])

  const connectedNodes = useMemo(() => {
    const ids = displayedGraph.edges.flatMap((edge) => {
      if (edge.source === selectedNode.id) return [edge.target]
      if (edge.target === selectedNode.id) return [edge.source]
      return []
    })
    return displayedGraph.nodes.filter((node) => ids.includes(node.id))
  }, [displayedGraph, selectedNode.id])

  const adjacentSkills = useMemo(() => displayedGraph.edges.flatMap((edge) => {
    if (edge.relationship !== 'REQUIRES' || edge.source !== selectedNode.id) return []
    const skill = displayedGraph.nodes.find((node) => node.id === edge.target && node.type === 'skill')
    return skill ? [{ skill, requirementType: edge.requirementType ?? 'required' }] : []
  }), [displayedGraph, selectedNode.id])

  const nodeTypeLabel = selectedNode.type === 'position'
    ? '岗位'
    : selectedNode.type === 'skill'
      ? '技能点'
      : mode === 'panorama' ? '岗位簇' : '技能簇'

  const modeSummary = mode === 'panorama'
    ? [`${displayedGraph.summary.positionClusterCount} 个岗位簇`, `${displayedGraph.summary.positionCount} 个岗位`, `${displayedGraph.summary.skillCount} 个技能点`]
    : [`${displayedGraph.summary.skillClusterCount} 个技能簇`, `${displayedGraph.summary.skillCount} 个技能点`, `${displayedGraph.summary.positionCount} 个关联岗位`]

  const selectedRoot = roots.find((root) => root.id === selectedRootId)
  const rootLabel = selectedRoot?.name ?? (roots.length > 0
    ? `${mode === 'panorama' ? '全部岗位簇' : '全部技能簇'} · ${roots.length}`
    : mode === 'panorama' ? '全部岗位簇' : '全部技能簇'
  )
  const detailNodes = selectedDetail?.directNodes ?? connectedNodes
  const requiredSkills = selectedDetail?.requiredSkills.map((item) => ({ skill: { id: item.skillId, name: item.name, type: 'skill' as const, weight: item.weight }, requirementType: item.requirementType })) ?? adjacentSkills.filter((item) => item.requirementType === 'required')
  const preferredSkills = selectedDetail?.preferredSkills.map((item) => ({ skill: { id: item.skillId, name: item.name, type: 'skill' as const, weight: item.weight }, requirementType: item.requirementType })) ?? adjacentSkills.filter((item) => item.requirementType === 'preferred')

  return (
    <div className="graph-workspace">
      <section className="graph-toolbar">
        <div className="view-switcher" aria-label="图谱展示模式">
          {(Object.keys(modeConfig) as GraphMode[]).map((item) => (
            <button key={item} onClick={() => changeMode(item)} className={mode === item ? 'active' : ''}>{modeConfig[item].label}</button>
          ))}
        </div>
        <div className="toolbar-group">
          <button className="filter-button" aria-expanded={rootMenuOpen} onClick={() => setRootMenuOpen((value) => !value)}><Layers3 size={16} />{rootLabel}<ChevronDown size={15} /></button>
          {rootMenuOpen && <div className="root-filter-menu">
            <button className={!selectedRootId ? 'active' : ''} onClick={() => { setSelectedRootId(''); setRootMenuOpen(false); setSelectedNode(activeGraph.nodes[0]) }}>{mode === 'panorama' ? '全部岗位簇' : '全部技能簇'}</button>
            {roots.map((root) => <button className={selectedRootId === root.id ? 'active' : ''} key={root.id} onClick={() => { setSelectedRootId(root.id); setRootMenuOpen(false); focusNode(root.id); setResetSignal((value) => value + 1) }}>{cleanName(root.name)}<span>{root.nodeCount}</span></button>)}
          </div>}
        </div>
        <div className="graph-summary">
          <span><i className="dot-position" />{modeSummary[0]}</span>
          <span><i className="dot-skill" />{modeSummary[1]}</span>
          <span><i className="dot-new" />{modeSummary[2]}</span>
        </div>
      </section>

      <div className="graph-layout">
        <aside className="graph-filter-panel">
          <SectionHeader title="图谱筛选" description={activeConfig.description} />
          <label className="panel-search"><Search size={16} /><input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder={mode === 'skill_reverse' ? '搜索技能簇、技能或岗位' : '搜索岗位簇、岗位或技能'} /></label>
          {searchItems.length > 0 && (
            <div className="reverse-skill-list">
              <span>搜索结果</span>
              {searchItems.map((item) => <button key={item.id} onClick={() => focusNode(item.id)}>{cleanName(item.name)}<em>{item.type}</em></button>)}
            </div>
          )}
          {searchItems.length === 0 && mode === 'skill_reverse' && (
            <div className="reverse-skill-list">
              <span>技能反查入口</span>
              {roots.slice(0, 3).map((root, index) => <button className={index === 0 ? 'active' : ''} key={root.id} onClick={() => focusNode(root.id)}>{cleanName(root.name)}<em>{root.nodeCount} 个节点</em></button>)}
            </div>
          )}
        </aside>

        <section className="graph-canvas">
          <div className="canvas-top">
            <div><span className="live-chip"><i /> {activeConfig.label}</span><h2>{activeConfig.title}</h2><p>{activeConfig.subtitle} · 数据更新于 2026-07-29</p></div>
            <button className="icon-button" aria-label="全屏查看"><Maximize2 size={18} /></button>
          </div>
          <div className="graph-stage">
            <div className="graph-layer-guide" aria-hidden="true">
              {layerGuides[mode].map((layer) => <span key={layer.label} style={{ top: layer.top }}>{layer.label}</span>)}
            </div>
            <Graph3D
              nodes={displayedGraph.nodes}
              edges={displayedGraph.edges}
              hierarchy={displayedGraph.hierarchy}
              selectedNodeId={selectedNode.id}
              scale={scale}
              resetSignal={resetSignal}
              onSelectNode={setSelectedNode}
            />
            <div className="graph-controls">
              <button aria-label="放大" onClick={() => setScale((value) => Math.min(1.35, value + .1))}><Plus size={17} /></button>
              <button aria-label="缩小" onClick={() => setScale((value) => Math.max(.7, value - .1))}><Minus size={17} /></button>
              <button aria-label="重置视角" onClick={() => { setScale(1); setResetSignal((value) => value + 1) }}><Focus size={17} /></button>
            </div>
            <div className="graph-legend">
              {mode === 'panorama' ? (
                <><span><i style={{ background: nodeColors.cluster }} />岗位簇</span><span><i style={{ background: nodeColors.position }} />岗位</span><span><i style={{ background: nodeColors.skill }} />技能点</span></>
              ) : (
                <><span><i style={{ background: nodeColors.cluster }} />技能簇</span><span><i style={{ background: nodeColors.skill }} />技能点</span><span><i style={{ background: nodeColors.position }} />岗位</span></>
              )}
            </div>
          </div>
        </section>

        <aside className="node-detail-panel">
          <span className="detail-type"><Sparkles size={14} />{nodeTypeLabel}</span>
          <h2>{cleanName(selectedNode.name)}</h2>

          {selectedNode.type === 'cluster' && (
            <>
              <p>{selectedDetail?.description ?? (mode === 'panorama' ? '岗位簇汇聚职责和技能结构相近的标准岗位，并直接连接岗位层。' : '技能簇是技能反查的顶层分类，向下组织含义和用途相近的技能点。')}</p>
              <div className="detail-meta-grid"><div><span>{mode === 'panorama' ? '标准岗位' : '技能点'}</span><strong>{detailNodes.length} 个</strong></div><div><span>有效样本</span><strong>{selectedDetail?.sampleCount || selectedNode.sampleCount || 218} 条</strong></div><div><span>新增节点</span><strong>3 个</strong></div><div><span>近期变化</span><strong>12 项</strong></div></div>
              <div className="detail-block"><span>直接关联节点</span><div className="tag-list">{detailNodes.slice(0, 5).map((node) => <em key={node.id}>{cleanName(node.name)}</em>)}</div></div>
            </>
          )}

          {selectedNode.type === 'position' && (
            <>
              <p>{selectedDetail?.description ?? `${cleanName(selectedNode.name)}的标准岗位画像，可查看所属岗位簇以及直接要求的技能点。`}</p>
              <div className="detail-meta-grid"><div><span>首次发现</span><strong>{selectedDetail?.firstSeen || selectedNode.firstSeen || (selectedNode.trend === 'new' ? '2025-08-12' : '2023-01-06')}</strong></div><div><span>样本支持</span><strong>{selectedDetail?.sampleCount || selectedNode.sampleCount || 38} 条</strong></div></div>
              <div className="detail-block adjacent-skill-groups">
                <span>相邻技能</span>
                <div><strong>必备</strong><div className="tag-list required-tags">{requiredSkills.map(({ skill }) => <em key={skill.id}>{cleanName(skill.name)}</em>)}</div></div>
                <div><strong>加分</strong><div className="tag-list preferred-tags">{preferredSkills.map(({ skill }) => <em key={skill.id}>{cleanName(skill.name)}</em>)}</div></div>
              </div>
            </>
          )}

          {selectedNode.type === 'skill' && (
            <>
              <p>{selectedDetail?.description ?? `${cleanName(selectedNode.name)}是可从 JD 和简历中识别的标准技能点，可反向查看需要该技能的岗位。`}</p>
              <div className="detail-meta-grid"><div><span>技能权重</span><strong>{(selectedDetail?.weight ?? selectedNode.weight ?? .82).toFixed(2)}</strong></div><div><span>关联岗位</span><strong>{selectedDetail?.relatedPositionCount ?? connectedNodes.filter((node) => node.type === 'position').length} 个</strong></div></div>
              <div className="detail-block"><span>相邻岗位</span><div className="tag-list">{detailNodes.filter((node) => node.type === 'position').slice(0, 5).map((node) => <em key={node.id}>{cleanName(node.name)}</em>)}</div></div>
            </>
          )}

        </aside>
      </div>
    </div>
  )
}
