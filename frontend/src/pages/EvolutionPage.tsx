import { ArrowRight, ChevronRight, Clock3, DatabaseZap, ExternalLink, FileText, Search, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Confidence, Modal, TrendBadge } from '../components/common'
import { api } from '../services/api'
import type { ChangeEvidence, EmergingPosition, EvidenceDetail, EvolutionChange, PositionProfile } from '../types'

const toDisplay = (snapshot: { requirementType: 'required' | 'preferred'; weight: number } | null) => {
  if (!snapshot) return '首次新增'
  return `${snapshot.requirementType === 'required' ? '必备技能' : '加分技能'} · ${snapshot.weight.toFixed(2)}`
}

const statusLabel: Record<PositionProfile['status'], string> = {
  emerging: '新兴岗位',
  existing: '既有岗位',
  inactive: '已停用',
}

export default function EvolutionPage() {
  const [tab, setTab] = useState<'changes' | 'emerging'>('changes')
  const [keyword, setKeyword] = useState('')
  const [changes, setChanges] = useState<EvolutionChange[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [evidence, setEvidence] = useState<ChangeEvidence | null>(null)
  const [emerging, setEmerging] = useState<EmergingPosition[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [evidenceDetails, setEvidenceDetails] = useState<EvidenceDetail[]>([])
  const [evidenceIndex, setEvidenceIndex] = useState(0)
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [evidenceMessage, setEvidenceMessage] = useState('')

  const [positionProfile, setPositionProfile] = useState<PositionProfile | null>(null)
  const [positionOpen, setPositionOpen] = useState(false)
  const [positionLoading, setPositionLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError('')
    api.getEvolutionChanges().then((res) => {
      setChanges(res.data.items)
      if (res.data.items.length) setSelectedId(res.data.items[0].id)
    }).catch(() => {
      setChanges([])
      setSelectedId('')
      setError('岗位演化接口暂不可用。')
    }).finally(() => {
      setLoading(false)
    })
    api.getEmergingPositions().then((res) => setEmerging(res.data.items)).catch(() => {
      setEmerging([])
      setError((message) => message || '新岗位发现接口暂不可用。')
    })
  }, [])

  useEffect(() => {
    if (!selectedId) return
    api.getChangeEvidence(selectedId).then((res) => setEvidence(res.data)).catch(() => setEvidence(null))
  }, [selectedId])

  const filteredChanges = useMemo(() => {
    if (!keyword.trim()) return changes
    const text = keyword.toLowerCase()
    return changes.filter((item) => `${item.positionName} ${item.skillName}`.toLowerCase().includes(text))
  }, [changes, keyword])

  const filteredEmerging = useMemo(() => {
    if (!keyword.trim()) return emerging
    const text = keyword.toLowerCase()
    return emerging.filter((item) => `${item.name} ${item.skills.map((skill) => skill.name).join(' ')}`.toLowerCase().includes(text))
  }, [emerging, keyword])

  const selected = useMemo(() => filteredChanges.find((item) => item.id === selectedId) ?? changes[0] ?? null, [changes, filteredChanges, selectedId])

  const handleViewEvidence = async () => {
    if (!selected || !evidence) {
      setEvidenceMessage('证据链尚未加载完成，请稍后重试。')
      return
    }
    if (evidence.evidenceIds.length === 0) {
      setEvidenceMessage('当前变化记录没有可展示的原始证据。')
      return
    }
    setEvidenceMessage('')
    try {
      const results = await Promise.all(evidence.evidenceIds.map((id) => api.getEvidenceDetail(id)))
      setEvidenceDetails(results.map((res) => res.data))
      setEvidenceIndex(0)
      setEvidenceOpen(true)
    } catch {
      setEvidenceOpen(false)
      setEvidenceMessage('原始证据加载失败，请稍后重试。')
    }
  }

  const handleViewEmergingDefinition = async (item: EmergingPosition) => {
    setPositionProfile(null)
    setPositionLoading(true)
    setPositionOpen(true)
    try {
      const res = await api.getPosition(item.positionId)
      setPositionProfile(res.data)
    } catch {
      setPositionProfile(null)
    } finally {
      setPositionLoading(false)
    }
  }

  const activeEvidence = evidenceDetails[evidenceIndex] ?? null

  return (
    <div className="page-stack evolution-page">
      <section className="panel evolution-detail-panel">
        <div className="content-tabs">
          <button className={tab === 'changes' ? 'active' : ''} onClick={() => setTab('changes')}>能力变更记录<span>{changes.length}</span></button>
          <button className={tab === 'emerging' ? 'active' : ''} onClick={() => setTab('emerging')}>新岗位发现<span>{emerging.length}</span></button>
          <label>
            <Search size={16} />
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索岗位或技能" />
          </label>
        </div>

        {loading && <div className="empty-state">正在加载岗位演化数据...</div>}
        {error && !loading && <div className="empty-state">{error}</div>}

        {!loading && tab === 'changes' ? (
          <div className="change-layout">
            <div className="change-list">
              <div className="change-table-head"><span>岗位与技能</span><span>变化</span><span>证据</span><span>可信度</span></div>
              {filteredChanges.map((change) => (
                <button key={change.id} className={`change-table-row ${selectedId === change.id ? 'selected' : ''}`} onClick={() => setSelectedId(change.id)}>
                  <span><strong>{change.positionName}</strong><small>{change.skillName}</small></span>
                  <span><TrendBadge trend={change.changeType === 'new' ? 'new' : change.changeType === 'declining' ? 'declining' : 'rising'} /><small>{toDisplay(change.before)} → {toDisplay(change.after)}</small></span>
                  <span>{change.evidenceCount} 条</span><span>{Math.round(change.confidence * 100)}%<ChevronRight size={15} /></span>
                </button>
              ))}
            </div>

            <aside className="evidence-panel">
              {selected && evidence ? (
                <>
                  <span className="detail-type"><DatabaseZap size={14} />变化证据链</span>
                  <h3>{selected.skillName}</h3>
                  <p>{selected.positionName}</p>

                  <div className="change-comparison">
                    <div><span>历史窗口</span><strong>{toDisplay(selected.before)}</strong></div>
                    <ArrowRight size={18} />
                    <div><span>当前窗口</span><strong>{toDisplay(selected.after)}</strong></div>
                  </div>

                  <div className="detail-block"><span>综合可信度</span><Confidence value={evidence.confidence} /></div>

                  <div className="evidence-timeline">
                    <div><i /><span><strong>多源数据支持</strong><small>来自 {evidence.sourceSupport.companyCount} 家企业，共 {evidence.sourceSupport.jobCount} 条有效 JD</small></span></div>
                    <div><i /><span><strong>跨窗口持续出现</strong><small>连续 {evidence.windowContinuity.continuousWindowCount} 个时间窗口达到阈值</small></span></div>
                    <div><i /><span><strong>语义一致性校验</strong><small>技能上下文一致性 {Math.round(evidence.semanticConsistency * 100)}%</small></span></div>
                  </div>

                  <button className="ghost-button full-button" onClick={handleViewEvidence}><FileText size={15} />查看原始证据</button>
                  {evidenceMessage && <p className="evidence-message">{evidenceMessage}</p>}
                </>
              ) : (
                <div className="empty-state">暂无能力变更记录</div>
              )}
            </aside>
          </div>
        ) : !loading && (
          <div className="emerging-card-grid">
            {filteredEmerging.map((item) => (
              <article className="emerging-card" key={item.id}>
                <div className="emerging-card-top">
                  <span className="detail-type"><Sparkles size={13} />候选新岗位</span>
                  <strong>+{Math.round(item.growthRate * 100)}%</strong>
                </div>
                <h3>{item.name}</h3>
                <p>{item.description}</p>
                <div className="tag-list">{item.skills.map((skill) => <em key={skill.id}>{skill.name}</em>)}</div>
                <div className="emerging-card-meta">
                  <span><Clock3 size={14} />首次出现 {item.firstSeen.slice(0, 7)}</span>
                  <span>{item.sourceCount} 个数据源</span>
                </div>
                <Confidence value={item.confidence} />

                <button onClick={() => handleViewEmergingDefinition(item)}>查看岗位定义<ArrowRight size={15} /></button>
              </article>
            ))}
            {filteredEmerging.length === 0 && <div className="empty-state">暂无新岗位发现</div>}
          </div>
        )}
      </section>

      {evidenceOpen && (
        <Modal title={`原始证据 · ${selected?.skillName ?? ''}`} onClose={() => setEvidenceOpen(false)}>
          {evidenceDetails.length > 1 && (
            <div className="evidence-switcher">
              {evidenceDetails.map((detail, index) => (
                <button key={detail.evidenceId} className={index === evidenceIndex ? 'active' : ''} onClick={() => setEvidenceIndex(index)}>
                  JD {index + 1}
                </button>
              ))}
            </div>
          )}

          {activeEvidence && (
            <div className="evidence-detail">
              <div className="evidence-meta">
                <span><strong>{activeEvidence.company}</strong></span>
                <span>{activeEvidence.positionTitle}</span>
                <span>{activeEvidence.sourcePlatform}</span>
                <span>{activeEvidence.publishedAt}</span>
              </div>

              <div className="matched-skill">命中技能：{activeEvidence.matchedSkill}</div>

              {activeEvidence.url && (
                <a className="text-link" href={activeEvidence.url} target="_blank" rel="noreferrer" style={{ margin: '8px 0' }}>
                  查看来源链接<ExternalLink size={13} />
                </a>
              )}

              <div className="jd-block">
                <span>JD 原文</span>
                <pre>{activeEvidence.jdText}</pre>
              </div>
            </div>
          )}
        </Modal>
      )}

      {positionOpen && (
        <Modal title="岗位定义" onClose={() => setPositionOpen(false)}>
          {positionLoading && !positionProfile && <div className="empty-state">加载中…</div>}

          {positionProfile && (
            <div className="definition-detail">
              <div className="definition-head">
                <h4>{positionProfile.name}</h4>
                <span className={`status-badge status-${positionProfile.status}`}>{statusLabel[positionProfile.status]}</span>
              </div>

              <div className="definition-meta">
                <span>所属类别：{positionProfile.category}</span>
                {positionProfile.aliases.length > 0 && <span>别名：{positionProfile.aliases.join('、')}</span>}
                <span>首次出现：{positionProfile.firstSeen}</span>
                <span>最近出现：{positionProfile.lastSeen}</span>
                <span>支撑样本：{positionProfile.sampleCount} 条 JD</span>
              </div>

              <div className="detail-block">
                <span>岗位描述</span>
                <p className="definition-text">{positionProfile.description}</p>
              </div>

              {positionProfile.responsibilities.length > 0 && (
                <div className="detail-block">
                  <span>核心职责</span>
                  <ul className="definition-list">{positionProfile.responsibilities.map((item, index) => <li key={index}>{item}</li>)}</ul>
                </div>
              )}

              {positionProfile.scenarios.length > 0 && (
                <div className="detail-block">
                  <span>应用场景</span>
                  <ul className="definition-list">{positionProfile.scenarios.map((item, index) => <li key={index}>{item}</li>)}</ul>
                </div>
              )}

              <div className="detail-block">
                <span>技能要求</span>
                <div className="requirement-groups">
                  {(['required', 'preferred'] as const).map((type) => {
                    const items = positionProfile.requirements.filter((requirement) => requirement.type === type)
                    if (items.length === 0) return null
                    return (
                      <div key={type}>
                        <strong>{type === 'required' ? '必备技能' : '加分技能'}</strong>
                        <div className="requirement-list">
                          {items.map((requirement) => (
                            <div key={requirement.id}>
                              <span>{requirement.name}</span>
                              <span>{requirement.frequency} 次</span>
                              <Confidence value={requirement.confidence} />
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}
