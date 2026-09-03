import { Check, CheckCircle2, ChevronDown, CircleAlert, Filter, Search, ShieldCheck, Sparkles, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Confidence, SectionHeader } from '../components/common'
import { dashboardSummary, reviewItems as initialReviewItems } from '../data/mock'
import { api } from '../services/api'
import type { EvaluationSummary, ReviewItem, ReviewStatus } from '../types'

const fallbackEvaluation: EvaluationSummary = {
  metrics: dashboardSummary.metrics,
  pendingReviewCount: 28,
  highPriorityReviewCount: 6,
  testedAt: '2026-07-29T10:00:00+08:00',
}

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>(initialReviewItems)
  const [evaluation, setEvaluation] = useState<EvaluationSummary>(fallbackEvaluation)
  const [activeId, setActiveId] = useState(initialReviewItems[0].id)
  const [keyword, setKeyword] = useState('')
  const [note, setNote] = useState('')
  const [actionMessage, setActionMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const active = items.find((item) => item.id === activeId) ?? items[0]
  useEffect(() => {
    api.getEvaluationSummary().then((res) => setEvaluation(res.data)).catch(() => setEvaluation(fallbackEvaluation))
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api.getReviews({ status: 'pending', keyword }).then((res) => {
      setItems(res.data)
      setActiveId(res.data[0]?.id ?? '')
    }).catch(() => setItems(initialReviewItems))
    }, 250)
    return () => window.clearTimeout(timer)
  }, [keyword])

  useEffect(() => {
    setNote(active?.note ?? '')
  }, [active?.id, active?.note])

  const review = async (status: ReviewStatus) => {
    if (!active) return
    setSubmitting(true)
    setActionMessage('')
    try {
      const res = await api.decideReview(activeId, status, note)
      setItems((current) => {
        const remaining = current.filter((item) => item.id !== activeId)
        setActiveId(remaining[0]?.id ?? '')
        return remaining
      })
      setActionMessage(status === 'approved'
        ? active.type === '新岗位' ? '审核通过，岗位已更新到正式图谱' : '审核通过，结果已保存'
        : '已驳回并保存审核意见')
    } catch (error) {
      setActionMessage(error instanceof Error ? `操作失败：${error.message}` : '操作失败，请检查后端服务')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page-stack review-page">
      <section className="page-intro">
        <div><span className="section-eyebrow">QUALITY CONTROL</span><h2>让每个岗位与能力都有据可查</h2><p>对新岗位、能力变更与技能归一结果进行人工审核，并持续验证模型效果。</p></div>
      </section>

      <section className="panel review-workbench">
        <div className="review-toolbar"><div><span className="section-eyebrow">HUMAN IN THE LOOP</span><h2>人工审核工作台</h2></div><div><label><Search size={16} /><input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索审核项" /></label><button className="filter-button"><Filter size={15} />全部类型<ChevronDown size={14} /></button></div></div>
        <div className="review-layout">
          <div className="review-list">
            {items.map((item) => <button key={item.id} className={`review-list-item ${activeId === item.id ? 'active' : ''}`} onClick={() => setActiveId(item.id)}><div><span className={`review-type type-${item.type}`}>{item.type}</span>{item.status !== 'pending' && <span className={`review-status status-${item.status}`}>{item.status === 'approved' ? '已通过' : '已驳回'}</span>}<time>{item.createdAt}</time></div><h3>{item.title}</h3><p>{item.description}</p><div><span>{item.sources.length} 个数据源</span><span>可信度 {Math.round(item.confidence * 100)}%</span></div></button>)}
          </div>
          {active && <aside className="review-detail">
            <div className="review-detail-head"><span className={`review-type type-${active.type}`}>{active.type}</span><h2>{active.title}</h2><p>{active.description}</p></div>
            <div className="detail-block"><span>模型综合可信度</span><Confidence value={active.confidence} /></div>
            <div className="detail-block"><span>来源交叉验证</span><div className="source-list">{active.sources.map((source) => <div key={source}><span>{source.slice(0, 1)}</span><strong>{source}</strong><CheckCircle2 size={15} /></div>)}</div></div>
            <div className="review-reasoning"><span><Sparkles size={16} />系统判定依据</span><ul><li>岗位名称新颖度达到 0.86</li><li>技能组合与最近岗位差异度超过阈值</li><li>连续三个时间窗口稳定增长</li><li>多来源语义描述一致性达到 92%</li></ul></div>
            <label className="review-note"><span>审核备注</span><textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="补充审核意见（选填）" /></label>
            {actionMessage && <p role="status">{actionMessage}</p>}
            <div className="review-actions"><button className="reject-button" disabled={submitting} onClick={() => review('rejected')}><X size={16} />驳回修正</button><button className="approve-button" disabled={submitting} onClick={() => review('approved')}><Check size={16} />{submitting ? '处理中…' : '确认通过'}</button></div>
          </aside>}
        </div>
      </section>

      <section className="panel evaluation-table-panel">
        <SectionHeader eyebrow="TEST REPORT" title="可量化评测报告" description="赛题核心指标与测试集覆盖情况" />
        <div className="evaluation-table"><div className="evaluation-head"><span>评测任务</span><span>测试集</span><span>准确率</span><span>赛题目标</span><span>结果</span></div>{evaluation.metrics.map((metric) => <div className="evaluation-row" key={metric.name}><span><ShieldCheck size={16} /><strong>{metric.name}</strong></span><span>{metric.sampleCount} 条标注样本</span><span><b>{metric.value}%</b><i><em style={{ width: `${metric.value}%` }} /></i></span><span>≥ {metric.target}%</span><span className={metric.value >= metric.target ? 'pass-chip' : 'warn-chip'}>{metric.value >= metric.target ? <CheckCircle2 size={14} /> : <CircleAlert size={14} />}{metric.value >= metric.target ? '通过' : '待优化'}</span></div>)}</div>
      </section>
    </div>
  )
}
