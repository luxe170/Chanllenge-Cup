import { ChevronDown, ExternalLink, Focus, Layers3, Maximize2, Minus, Plus, Search, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Confidence, SectionHeader } from '../components/common'
import Graph3D from '../components/graph/Graph3D'
import { panoramaEdges, panoramaNodes, skillReverseEdges, skillReverseNodes } from '../data/mock'
import type { GraphEdge, GraphNode } from '../types'

type GraphMode = 'panorama' | 'skill'

const nodeColors = { position: '#7c6df2', skill: '#45c9dc', cluster: '#58d09e', stack: '#f5b86b' }

const modeConfig: Record<GraphMode, { label: string; title: string; subtitle: string; description: string }> = {
  panorama: {
    label: '全景模式',
    title: '新一代信息技术岗位全景',
    subtitle: '岗位簇 → 岗位 → 技能点',
    description: '从岗位簇出发，逐层查看标准岗位及其直接要求的技能点。',
  },
  skill: {
    label: '技能反查',
    title: '技能需求反查图谱',
    subtitle: '技术栈 → 技能簇 → 技能点 → 岗位',
    description: '沿技能层级向下展开，反向查看每个技能点对应的需求岗位。',
  },
}

const graphData: Record<GraphMode, { nodes: GraphNode[]; edges: GraphEdge[] }> = {
  panorama: { nodes: panoramaNodes, edges: panoramaEdges },
  skill: { nodes: skillReverseNodes, edges: skillReverseEdges },
}

const modeSummary: Record<GraphMode, [string, string, string]> = {
  panorama: ['3 个岗位簇', '6 个岗位', '9 个技能点'],
  skill: ['1 个技术栈', '4 个技能点', '5 个关联岗位'],
}

const layerGuides: Record<GraphMode, Array<{ label: string; top: string }>> = {
  panorama: [
    { label: '岗位簇', top: '8%' },
    { label: '岗位', top: '43%' },
    { label: '技能点', top: '82%' },
  ],
  skill: [
    { label: '技术栈', top: '3%' },
    { label: '技能簇', top: '26%' },
    { label: '技能点', top: '52%' },
    { label: '岗位', top: '84%' },
  ],
}

const cleanName = (name: string) => name.replaceAll('\n', ' ')

export default function GraphPage() {
  const [mode, setMode] = useState<GraphMode>('panorama')
  const [selectedNode, setSelectedNode] = useState<GraphNode>(panoramaNodes[0])
  const [scale, setScale] = useState(1)
  const [resetSignal, setResetSignal] = useState(0)
  const activeGraph = graphData[mode]
  const activeConfig = modeConfig[mode]

  const changeMode = (nextMode: GraphMode) => {
    setMode(nextMode)
    setSelectedNode(graphData[nextMode].nodes[0])
    setScale(1)
    setResetSignal((value) => value + 1)
  }

  const connectedNodes = useMemo(() => {
    const ids = activeGraph.edges.flatMap((edge) => {
      if (edge.source === selectedNode.id) return [edge.target]
      if (edge.target === selectedNode.id) return [edge.source]
      return []
    })
    return activeGraph.nodes.filter((node) => ids.includes(node.id))
  }, [activeGraph, selectedNode.id])

  const adjacentSkills = useMemo(() => activeGraph.edges.flatMap((edge) => {
    if (edge.relationship !== 'REQUIRES' || edge.source !== selectedNode.id) return []
    const skill = activeGraph.nodes.find((node) => node.id === edge.target && node.type === 'skill')
    return skill ? [{ skill, requirementType: edge.requirementType ?? 'required' }] : []
  }), [activeGraph, selectedNode.id])

  const nodeTypeLabel = selectedNode.type === 'position'
    ? '岗位'
    : selectedNode.type === 'skill'
      ? '技能点'
      : selectedNode.type === 'stack'
        ? '技术栈'
        : mode === 'panorama' ? '岗位簇' : '技能簇'

  return (
    <div className="graph-workspace">
      <section className="graph-toolbar">
        <div className="view-switcher" aria-label="图谱展示模式">
          {(Object.keys(modeConfig) as GraphMode[]).map((item) => (
            <button key={item} onClick={() => changeMode(item)} className={mode === item ? 'active' : ''}>{modeConfig[item].label}</button>
          ))}
        </div>
        <div className="toolbar-group">
          <button className="filter-button"><Layers3 size={16} />{mode === 'panorama' ? '全部岗位簇' : '全部技术栈'}<ChevronDown size={15} /></button>
        </div>
        <div className="graph-summary">
          <span><i className="dot-position" />{modeSummary[mode][0]}</span>
          <span><i className="dot-skill" />{modeSummary[mode][1]}</span>
          <span><i className="dot-new" />{modeSummary[mode][2]}</span>
        </div>
      </section>

      <div className="graph-layout">
        <aside className="graph-filter-panel">
          <SectionHeader title="图谱筛选" description={activeConfig.description} />
          <label className="panel-search"><Search size={16} /><input placeholder={mode === 'skill' ? '搜索技术栈、技能或岗位' : '搜索岗位簇、岗位或技能'} /></label>
          {mode === 'skill' && (
            <div className="reverse-skill-list">
              <span>技能反查入口</span>
              <button className="active">RAG<em>4 个岗位</em></button>
              <button>大语言模型<em>12 个岗位</em></button>
              <button>云原生<em>18 个岗位</em></button>
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
              nodes={activeGraph.nodes}
              edges={activeGraph.edges}
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
                <><span><i style={{ background: nodeColors.stack }} />技术栈</span><span><i style={{ background: nodeColors.cluster }} />技能簇</span><span><i style={{ background: nodeColors.skill }} />技能点</span><span><i style={{ background: nodeColors.position }} />岗位</span></>
              )}
            </div>
          </div>
        </section>

        <aside className="node-detail-panel">
          <span className="detail-type"><Sparkles size={14} />{nodeTypeLabel}</span>
          <h2>{cleanName(selectedNode.name)}</h2>

          {selectedNode.type === 'stack' && (
            <>
              <p>技术栈是技能体系的顶层领域，向下连接技能簇、技能点及实际需求岗位。</p>
              <div className="detail-meta-grid"><div><span>技能簇</span><strong>{connectedNodes.length} 个</strong></div><div><span>技能点</span><strong>68 个</strong></div><div><span>关联岗位</span><strong>36 个</strong></div><div><span>活跃度</span><strong>持续上升</strong></div></div>
              <div className="detail-block"><span>领域活跃度</span><Confidence value={.91} /></div>
            </>
          )}

          {selectedNode.type === 'cluster' && (
            <>
              <p>{mode === 'panorama' ? '岗位簇汇聚职责和技能结构相近的标准岗位，并直接连接岗位层。' : '技能簇归属于技术栈，向下组织含义和用途相近的技能点。'}</p>
              <div className="detail-meta-grid"><div><span>{mode === 'panorama' ? '标准岗位' : '技能点'}</span><strong>{connectedNodes.length} 个</strong></div><div><span>有效样本</span><strong>218 条</strong></div><div><span>新增节点</span><strong>3 个</strong></div><div><span>近期变化</span><strong>12 项</strong></div></div>
              <div className="detail-block"><span>直接关联节点</span><div className="tag-list">{connectedNodes.slice(0, 5).map((node) => <em key={node.id}>{cleanName(node.name)}</em>)}</div></div>
              <div className="detail-block"><span>聚类可信度</span><Confidence value={.89} /></div>
            </>
          )}

          {selectedNode.type === 'position' && (
            <>
              <p>{cleanName(selectedNode.name)}的标准岗位画像，可查看所属岗位簇以及直接要求的技能点。</p>
              <div className="detail-meta-grid"><div><span>首次发现</span><strong>{selectedNode.trend === 'new' ? '2025-08-12' : '2023-01-06'}</strong></div><div><span>样本支持</span><strong>38 条</strong></div></div>
              <div className="detail-block"><span>判定可信度</span><Confidence value={selectedNode.trend === 'new' ? .88 : .93} /></div>
              <div className="detail-block adjacent-skill-groups">
                <span>相邻技能</span>
                <div><strong>必备</strong><div className="tag-list required-tags">{adjacentSkills.filter((item) => item.requirementType === 'required').map(({ skill }) => <em key={skill.id}>{cleanName(skill.name)}</em>)}</div></div>
                <div><strong>加分</strong><div className="tag-list preferred-tags">{adjacentSkills.filter((item) => item.requirementType === 'preferred').map(({ skill }) => <em key={skill.id}>{cleanName(skill.name)}</em>)}</div></div>
              </div>
            </>
          )}

          {selectedNode.type === 'skill' && (
            <>
              <p>{cleanName(selectedNode.name)}是可从 JD 和简历中识别的标准技能点，可反向查看需要该技能的岗位。</p>
              <div className="detail-meta-grid"><div><span>技能权重</span><strong>{(selectedNode.weight ?? .82).toFixed(2)}</strong></div><div><span>关联岗位</span><strong>{connectedNodes.filter((node) => node.type === 'position').length} 个</strong></div></div>
              <div className="detail-block"><span>关系可信度</span><Confidence value={.91} /></div>
              <div className="detail-block"><span>相邻岗位</span><div className="tag-list">{connectedNodes.filter((node) => node.type === 'position').slice(0, 5).map((node) => <em key={node.id}>{cleanName(node.name)}</em>)}</div></div>
            </>
          )}

          <button className="primary-button full-button">查看完整数据<ExternalLink size={15} /></button>
        </aside>
      </div>
    </div>
  )
}
