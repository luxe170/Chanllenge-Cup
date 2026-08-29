import { ArrowRight, BriefcaseBusiness, CheckCircle2, Database, GitBranch, LoaderCircle, Sparkles, TrendingUp, UploadCloud } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { MetricCard } from '../components/common'
import { dashboardSummary } from '../data/mock'
import { AppLink } from '../router'
import { api } from '../services/api'
import type { JdBatch } from '../types'

export default function DashboardPage() {
  const [summary, setSummary] = useState(dashboardSummary)
  const [batches, setBatches] = useState<JdBatch[]>([])
  const [uploading, setUploading] = useState(false)
  const [batchError, setBatchError] = useState('')
  const batchInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.getDashboard().then((res) => setSummary(res.data)).catch(() => setSummary(dashboardSummary))
    api.getJdBatches().then((res) => setBatches(res.data)).catch(() => setBatches([]))
  }, [])

  const uploadBatch = (file: File) => {
    setUploading(true)
    setBatchError('')
    api.createJdBatch(file)
      .then((res) => setBatches((current) => [res.data, ...current.filter((batch) => batch.id !== res.data.id)]))
      .catch((error) => setBatchError(error instanceof Error ? error.message : '批次处理失败'))
      .finally(() => setUploading(false))
  }

  return (
    <div className="page-stack dashboard-page">
      <section className="welcome-banner">
        <div className="welcome-content">
          <span className="live-chip"><i /> 数据已同步至 2026-07-29</span>
          <h2>看见岗位变化，找到能力方向</h2>
          <p>多源异构数据驱动的岗位能力图谱动态构建与演化分析系统</p>
          <div className="welcome-actions">
            <AppLink to="/graph" className="primary-button"><GitBranch size={17} />探索岗位图谱<ArrowRight size={16} /></AppLink>
            <AppLink to="/resume" className="ghost-button">开始匹配诊断</AppLink>
          </div>
        </div>
        <div className="prism-visual" aria-hidden="true">
          <span className="prism-orbit orbit-one" /><span className="prism-orbit orbit-two" />
          <div className="prism-core"><Sparkles size={38} /></div>
          <span className="float-node node-one">AI Agent</span>
          <span className="float-node node-two">RAG</span>
          <span className="float-node node-three">云原生</span>
        </div>
      </section>

      <section className="metric-grid">
        <MetricCard icon={Database} label="有效岗位样本" value={summary.validCount} change="+12.4%" tone="cyan" />
        <MetricCard icon={BriefcaseBusiness} label="新兴岗位" value={summary.emergingCount} change="+3" tone="violet" />
        <MetricCard icon={TrendingUp} label="能力变更" value={summary.changedCount} change="+8.6%" tone="green" />
      </section>

      <section className="panel batch-panel">
        <div className="batch-panel-head"><div><span className="section-eyebrow">JD PIPELINE</span><h2>新 JD 批次处理</h2><p>上传 JSONL 后自动完成清洗、去重、岗位技能提取和三路分类。</p></div><button className="primary-button" disabled={uploading} onClick={() => batchInputRef.current?.click()}>{uploading ? <LoaderCircle className="spinner" size={16} /> : <UploadCloud size={16} />}{uploading ? '处理中…' : '上传 JD 批次'}</button><input hidden ref={batchInputRef} type="file" accept=".jsonl,.json" onChange={(event) => event.target.files?.[0] && uploadBatch(event.target.files[0])} /></div>
        {batchError && <p role="alert">处理失败：{batchError}</p>}
        <div className="batch-list">
          {batches.length === 0 && <p>暂无处理批次</p>}
          {batches.map((batch) => <article key={batch.id}><div><strong>{batch.filename}</strong><small>{batch.id} · {new Date(batch.createdAt).toLocaleString()}</small></div><span>有效 {batch.validCount}</span><span>新岗位 {batch.newPositionCount}</span><span>能力变更 {batch.changeCount}</span><span>无变化 {batch.noChangeCount}</span><span>待审核 {batch.pendingReviewCount}</span><em className={`batch-status status-${batch.status}`}><CheckCircle2 size={13} />{batch.status === 'applied' ? '已入图' : batch.status === 'reviewing' ? '待审核' : '已分类'}</em></article>)}
        </div>
      </section>
    </div>
  )
}
