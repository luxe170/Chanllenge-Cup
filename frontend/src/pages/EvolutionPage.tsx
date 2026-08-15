import { ArrowRight, ChevronRight, Clock3, DatabaseZap, FileText, Search, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Confidence, TrendBadge } from '../components/common'
import { changes } from '../data/mock'

const emerging = [
  { name: 'AI Agent 研发工程师', description: '聚焦智能体编排、工具调用与工作流研发', growth: 168, confidence: .93, firstSeen: '2025-03', sources: 4, skills: ['LangChain', 'RAG', '多智能体'] },
  { name: '具身智能数据工程师', description: '负责机器人多模态数据采集、治理与训练管线', growth: 124, confidence: .88, firstSeen: '2025-08', sources: 3, skills: ['ROS', '多模态数据', '数据闭环'] },
  { name: '大模型安全工程师', description: '建设模型安全评测、攻击防护与合规体系', growth: 97, confidence: .91, firstSeen: '2025-06', sources: 5, skills: ['红队评测', '安全对齐', '内容安全'] },
]

export default function EvolutionPage() {
  const [tab, setTab] = useState<'changes' | 'emerging'>('changes')
  const [selectedId, setSelectedId] = useState(changes[0].id)
  const selected = changes.find((item) => item.id === selectedId)!

  return (
    <div className="page-stack evolution-page">
      <section className="panel evolution-detail-panel">
        <div className="content-tabs"><button className={tab === 'changes' ? 'active' : ''} onClick={() => setTab('changes')}>能力变更记录<span>47</span></button><button className={tab === 'emerging' ? 'active' : ''} onClick={() => setTab('emerging')}>新岗位发现<span>12</span></button><label><Search size={16} /><input placeholder="搜索岗位或技能" /></label></div>
        {tab === 'changes' ? (
          <div className="change-layout">
            <div className="change-list">
              <div className="change-table-head"><span>岗位与技能</span><span>变化</span><span>证据</span><span>可信度</span></div>
              {changes.map((change) => (
                <button key={change.id} className={`change-table-row ${selectedId === change.id ? 'selected' : ''}`} onClick={() => setSelectedId(change.id)}>
                  <span><strong>{change.position}</strong><small>{change.skill}</small></span>
                  <span><TrendBadge trend={change.changeType === '新增' ? 'new' : change.changeType === '下降' ? 'declining' : 'rising'} /><small>{change.before} → {change.after}</small></span>
                  <span>{change.evidenceCount} 条</span><span>{Math.round(change.confidence * 100)}%<ChevronRight size={15} /></span>
                </button>
              ))}
            </div>
            <aside className="evidence-panel">
              <span className="detail-type"><DatabaseZap size={14} />变化证据链</span><h3>{selected.skill}</h3><p>{selected.position}</p>
              <div className="change-comparison"><div><span>历史窗口</span><strong>{selected.before}</strong></div><ArrowRight size={18} /><div><span>当前窗口</span><strong>{selected.after}</strong></div></div>
              <div className="detail-block"><span>综合可信度</span><Confidence value={selected.confidence} /></div>
              <div className="evidence-timeline">
                <div><i /><span><strong>多源数据支持</strong><small>来自 3 家企业，共 {selected.evidenceCount} 条有效 JD</small></span></div>
                <div><i /><span><strong>跨窗口持续出现</strong><small>连续 3 个时间窗口达到阈值</small></span></div>
                <div><i /><span><strong>语义一致性校验</strong><small>技能上下文一致性 94%</small></span></div>
              </div>
              <button className="ghost-button full-button"><FileText size={15} />查看原始证据</button>
            </aside>
          </div>
        ) : (
          <div className="emerging-card-grid">
            {emerging.map((item) => (
              <article className="emerging-card" key={item.name}><div className="emerging-card-top"><span className="detail-type"><Sparkles size={13} />候选新岗位</span><strong>+{item.growth}%</strong></div><h3>{item.name}</h3><p>{item.description}</p><div className="tag-list">{item.skills.map((skill) => <em key={skill}>{skill}</em>)}</div><div className="emerging-card-meta"><span><Clock3 size={14} />首次出现 {item.firstSeen}</span><span>{item.sources} 个数据源</span></div><Confidence value={item.confidence} /><button>查看岗位定义<ArrowRight size={15} /></button></article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
