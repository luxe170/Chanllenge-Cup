import { Activity, ArrowRight, Check, CheckCircle2, ChevronDown, CircleAlert, Clock3, Database, FileCheck2, Filter, FlaskConical, History, Search, ShieldCheck, Sparkles, X } from 'lucide-react'
import { useState } from 'react'
import { Confidence, SectionHeader } from '../components/common'
import { dashboardSummary, reviewItems as initialReviewItems } from '../data/mock'
import type { ReviewItem, ReviewStatus } from '../types'

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>(initialReviewItems)
  const [activeId, setActiveId] = useState(initialReviewItems[0].id)
  const active = items.find((item) => item.id === activeId) ?? items[0]

  const review = (status: ReviewStatus) => {
    setItems((current) => current.map((item) => item.id === activeId ? { ...item, status } : item))
  }

  return (
    <div className="page-stack review-page">
      <section className="page-intro">
        <div><span className="section-eyebrow">QUALITY CONTROL</span><h2>让每个岗位与能力都有据可查</h2><p>对新岗位、能力变更与技能归一结果进行人工审核，并持续验证模型效果。</p></div>
        <button className="ghost-button"><History size={16} />审核历史</button>
      </section>

      <section className="quality-metrics">
        {dashboardSummary.metrics.map((metric, index) => <article className="panel quality-metric" key={metric.name}><div className={`quality-icon quality-${index}`}>{index === 0 ? <Database size={19} /> : index === 1 ? <FileCheck2 size={19} /> : <FlaskConical size={19} />}</div><div><span>{metric.name}</span><strong>{metric.value}<small>%</small></strong><p><CheckCircle2 size={13} />超过目标 {metric.target}% · {metric.sampleCount} 条样本</p></div><div className="mini-ring" style={{ '--accuracy': `${metric.value * 3.6}deg` } as React.CSSProperties} /></article>)}
        <article className="panel quality-metric pending-metric"><div className="quality-icon quality-3"><Clock3 size={19} /></div><div><span>待审核事项</span><strong>28<small>项</small></strong><p><CircleAlert size={13} />其中 6 项为高优先级</p></div><ArrowRight size={20} /></article>
      </section>

      <section className="panel review-workbench">
        <div className="review-toolbar"><div><span className="section-eyebrow">HUMAN IN THE LOOP</span><h2>人工审核工作台</h2></div><div><label><Search size={16} /><input placeholder="搜索审核项" /></label><button className="filter-button"><Filter size={15} />全部类型<ChevronDown size={14} /></button></div></div>
        <div className="review-layout">
          <div className="review-list">
            {items.map((item) => <button key={item.id} className={`review-list-item ${activeId === item.id ? 'active' : ''}`} onClick={() => setActiveId(item.id)}><div><span className={`review-type type-${item.type}`}>{item.type}</span>{item.status !== 'pending' && <span className={`review-status status-${item.status}`}>{item.status === 'approved' ? '已通过' : '已驳回'}</span>}<time>{item.createdAt}</time></div><h3>{item.title}</h3><p>{item.description}</p><div><span>{item.sources.length} 个数据源</span><span>可信度 {Math.round(item.confidence * 100)}%</span></div></button>)}
          </div>
          {active && <aside className="review-detail">
            <div className="review-detail-head"><span className={`review-type type-${active.type}`}>{active.type}</span><h2>{active.title}</h2><p>{active.description}</p></div>
            <div className="detail-block"><span>模型综合可信度</span><Confidence value={active.confidence} /></div>
            <div className="detail-block"><span>来源交叉验证</span><div className="source-list">{active.sources.map((source) => <div key={source}><span>{source.slice(0, 1)}</span><strong>{source}</strong><CheckCircle2 size={15} /></div>)}</div></div>
            <div className="review-reasoning"><span><Sparkles size={16} />系统判定依据</span><ul><li>岗位名称新颖度达到 0.86</li><li>技能组合与最近岗位差异度超过阈值</li><li>连续三个时间窗口稳定增长</li><li>多来源语义描述一致性达到 92%</li></ul></div>
            <label className="review-note"><span>审核备注</span><textarea placeholder="补充审核意见（选填）" /></label>
            <div className="review-actions"><button className="reject-button" onClick={() => review('rejected')}><X size={16} />驳回修正</button><button className="approve-button" onClick={() => review('approved')}><Check size={16} />确认通过</button></div>
          </aside>}
        </div>
      </section>

      <section className="panel evaluation-table-panel">
        <SectionHeader eyebrow="TEST REPORT" title="可量化评测报告" description="赛题核心指标与测试集覆盖情况" action={<button className="ghost-button"><FileCheck2 size={15} />导出完整报告</button>} />
        <div className="evaluation-table"><div className="evaluation-head"><span>评测任务</span><span>测试集</span><span>准确率</span><span>赛题目标</span><span>结果</span></div>{dashboardSummary.metrics.map((metric) => <div className="evaluation-row" key={metric.name}><span><ShieldCheck size={16} /><strong>{metric.name}</strong></span><span>{metric.sampleCount} 条人工标注样本</span><span><b>{metric.value}%</b><i><em style={{ width: `${metric.value}%` }} /></i></span><span>≥ {metric.target}%</span><span className="pass-chip"><CheckCircle2 size={14} />通过</span></div>)}</div>
      </section>
    </div>
  )
}
