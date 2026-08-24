import { ArrowRight, BookOpenCheck, Check, CheckCircle2, ChevronDown, CircleAlert, CircleCheck, FileText, Lightbulb, Route, Sparkles, Target, TrendingUp } from 'lucide-react'
import { useEffect, useState } from 'react'
import { SectionHeader } from '../components/common'
import { learningPath, matchDimensions, positionProfile } from '../data/mock'
import { api } from '../services/api'
import type { MatchReport } from '../types'

const fallbackReport: MatchReport = {
  matchId: 'fallback_match',
  resumeTaskId: 'demo_resume_task',
  positionId: positionProfile.id,
  positionName: positionProfile.name,
  candidateName: '陈小雨',
  overallScore: 82,
  fitLevel: '高度匹配',
  benchmarkRank: '前 18%',
  benchmarkSampleCount: 426,
  summary: '已覆盖大部分核心要求，重点补齐 2 项能力可显著提升竞争力。',
  dimensions: matchDimensions,
  strengths: ['Python', '大语言模型', '向量数据库', 'FastAPI'],
  gaps: [
  { name: 'RAG 评测', priority: '高', requirement: '必备技能', current: '未识别', weight: 84 },
  { name: '多智能体协作', priority: '高', requirement: '加分技能', current: '未识别', weight: 72 },
  { name: '工具调用', priority: '中', requirement: '必备技能', current: '基础了解', weight: 68 },
  { name: '模型安全护栏', priority: '中', requirement: '加分技能', current: '未识别', weight: 59 },
  ],
  evidence: { skillEvidenceCount: 14, projectEvidenceCount: 2, jobSampleCount: 52 },
  suggestions: ['突出企业知识库项目中的评测结果', '补充工具调用与任务规划实践', '将模型服务经验关联到工程稳定性'],
  learningPath,
}

export default function MatchPage() {
  const [selectedStage, setSelectedStage] = useState(1)
  const [report, setReport] = useState<MatchReport>(fallbackReport)

  const refreshMatch = () => {
    api.createMatch('demo_resume_task', positionProfile.id)
      .then(async (res) => {
        const path = await api.getLearningPath(res.data.matchId)
        setReport({ ...res.data, learningPath: path.data.items })
      })
      .catch(() => setReport(fallbackReport))
  }

  useEffect(() => {
    refreshMatch()
  }, [])

  return (
    <div className="page-stack match-page">
      <section className="match-selector panel">
        <div className="candidate-selector"><span className="candidate-avatar">{report.candidateName.slice(0, 1)}</span><div><small>候选人</small><strong>{report.candidateName}</strong></div><ChevronDown size={16} /></div>
        <div className="matching-arrow"><span /><Target size={22} /><span /></div>
        <div className="position-selector"><span className="position-icon"><Sparkles size={20} /></span><div><small>目标岗位</small><strong>{report.positionName}</strong></div><ChevronDown size={16} /></div>
        <button className="primary-button" onClick={refreshMatch}>重新计算匹配</button>
      </section>

      <section className="match-overview-grid">
        <article className="panel match-score-card">
          <span className="section-eyebrow">OVERALL MATCH</span><div className="score-ring"><div><strong>{report.overallScore}</strong><span>匹配度</span></div></div><h2>{report.fitLevel}</h2><p>{report.summary}</p><div className="benchmark"><span>候选人排名</span><strong>{report.benchmarkRank}</strong><small>同方向 {report.benchmarkSampleCount} 份画像</small></div>
        </article>
        <article className="panel dimension-card">
          <SectionHeader eyebrow="DIMENSION SCORE" title="多维能力匹配" description="结合要求类型、技能权重和项目证据计算" />
          <div className="dimension-list">
            {report.dimensions.map((dimension) => <div key={dimension.name}><span>{dimension.name}</span><div><i style={{ width: `${dimension.value}%`, background: dimension.color }} /></div><strong>{dimension.value}</strong></div>)}
          </div>
          <div className="match-insight"><Lightbulb size={17} /><p><strong>关键结论：</strong>项目经验与必备技能匹配较好；加分技能覆盖不足，是当前主要差距。</p></div>
        </article>
        <article className="panel evidence-card">
          <SectionHeader eyebrow="EVIDENCE" title="匹配依据" />
          <div className="evidence-score"><span><CircleCheck size={18} />可信技能证据</span><strong>{report.evidence.skillEvidenceCount}<small>项</small></strong></div>
          <div className="evidence-score"><span><FileText size={18} />相关项目经历</span><strong>{report.evidence.projectEvidenceCount}<small>段</small></strong></div>
          <div className="evidence-score"><span><TrendingUp size={18} />岗位有效样本</span><strong>{report.evidence.jobSampleCount}<small>条</small></strong></div>
          <div className="explainability"><CheckCircle2 size={16} /><span>所有结论均可追溯至简历原文与岗位证据</span></div>
        </article>
      </section>

      <section className="match-detail-grid">
        <article className="panel gap-card">
          <SectionHeader eyebrow="SKILL GAP" title="能力差距诊断" description="按岗位权重和前置关系确定补强优先级" action={<span className="gap-count">{report.gaps.length} 项待提升</span>} />
          <div className="strength-strip"><span><Check size={15} />已具备优势</span>{report.strengths.map((item) => <em key={item}>{item}</em>)}</div>
          <div className="gap-table">
            <div className="gap-table-head"><span>缺失能力</span><span>岗位要求</span><span>当前水平</span><span>重要度</span><span>优先级</span></div>
            {report.gaps.map((gap) => <div className="gap-row" key={gap.name}><span><CircleAlert size={16} /><strong>{gap.name}</strong></span><span>{gap.requirement}</span><span>{gap.current}</span><span><i><b style={{ width: `${gap.weight}%` }} /></i>{gap.weight}%</span><span className={`priority priority-${gap.priority}`}>{gap.priority}</span></div>)}
          </div>
        </article>

        <article className="panel fit-card">
          <SectionHeader eyebrow="ROLE FIT" title="岗位适配建议" />
          <div className="fit-level"><div><span>当前适配等级</span><strong>B+</strong></div><p>具备直接投递基础，建议用一个完整的 Agent 项目强化差异化竞争力。</p></div>
          <ul>{report.suggestions.map((suggestion) => <li key={suggestion}><CheckCircle2 size={16} />{suggestion}</li>)}</ul>
        </article>
      </section>

      <section className="panel learning-card">
        <SectionHeader eyebrow="PERSONALIZED ROADMAP" title="个性化学习路径" description="基于技能前置关系和差距优先级生成，预计 6–9 周完成" action={<button className="ghost-button"><BookOpenCheck size={15} />导出学习计划</button>} />
        <div className="learning-layout">
          <div className="stage-navigation">
            {report.learningPath.map((step) => <button className={selectedStage === step.stage ? 'active' : ''} onClick={() => setSelectedStage(step.stage)} key={step.stage}><i>{step.stage}</i><span><small>阶段 {step.stage} · {step.duration}</small><strong>{step.title}</strong></span><ArrowRight size={16} /></button>)}
          </div>
          {report.learningPath.filter((step) => step.stage === selectedStage).map((step) => <div className="stage-detail" key={step.stage}><span className="stage-icon"><Route size={24} /></span><span className="section-eyebrow">STAGE {step.stage}</span><h3>{step.title}</h3><p>{step.goal}</p><div><span>重点技能</span><div className="tag-list">{step.skills.map((skill) => <em key={skill}>{skill}</em>)}</div></div><div className="stage-outcome"><CircleCheck size={17} /><span><strong>阶段成果</strong>完成可展示项目并通过能力自测</span></div><button className="primary-button">查看学习任务<ArrowRight size={15} /></button></div>)}
        </div>
      </section>
    </div>
  )
}
