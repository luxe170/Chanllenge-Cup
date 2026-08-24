import { ArrowRight, BriefcaseBusiness, Database, GitBranch, Sparkles, TrendingUp } from 'lucide-react'
import { useEffect, useState } from 'react'
import { MetricCard } from '../components/common'
import { dashboardSummary } from '../data/mock'
import { AppLink } from '../router'
import { api } from '../services/api'

export default function DashboardPage() {
  const [summary, setSummary] = useState(dashboardSummary)

  useEffect(() => {
    api.getDashboard().then((res) => setSummary(res.data)).catch(() => setSummary(dashboardSummary))
  }, [])

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
    </div>
  )
}
