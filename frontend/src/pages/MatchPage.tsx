import { ArrowRight, Award, BookOpenCheck, Check, CheckCircle2, ChevronDown, CircleAlert, CircleCheck, FileText, Lightbulb, Route, Search, Sparkles, Target, TrendingUp } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { SectionHeader } from '../components/common'
import { AppLink } from '../router'
import { api } from '../services/api'
import type { MatchRankingItem, MatchReport } from '../types'

export default function MatchPage() {
  const [selectedStage, setSelectedStage] = useState(1)
  const [report, setReport] = useState<MatchReport | null>(null)
  const [rankings, setRankings] = useState<MatchRankingItem[]>([])
  const [positionId, setPositionId] = useState('')
  const [positionSearch, setPositionSearch] = useState('')
  const [positionMenuOpen, setPositionMenuOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [matchError, setMatchError] = useState('')
  const storedResumeTaskId = window.sessionStorage.getItem('latestResumeTaskId') ?? ''
  const resumeTaskId = storedResumeTaskId === 'demo_resume_task' ? '' : storedResumeTaskId

  const refreshMatch = (targetPositionId = positionId, manageLoading = true) => {
    if (!targetPositionId) return
    if (manageLoading) setLoading(true)
    setMatchError('')
    return api.createMatch(resumeTaskId, targetPositionId)
      .then(async (res) => {
        const path = await api.getLearningPath(res.data.matchId)
        setReport({ ...res.data, learningPath: path.data.items })
        setSelectedStage(path.data.items[0]?.stage ?? 1)
      })
      .catch((error) => setMatchError(error instanceof Error ? error.message : '匹配计算失败'))
      .finally(() => { if (manageLoading) setLoading(false) })
  }

  const refreshRanking = () => {
    setLoading(true)
    setMatchError('')
    api.rankMatches(resumeTaskId)
      .then(async (res) => {
        setRankings(res.data.items)
        const target = res.data.bestPositionId
        setPositionId(target)
        if (target) await refreshMatch(target, false)
      })
      .catch((error) => setMatchError(error instanceof Error ? error.message : '无法完成全部岗位匹配'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (storedResumeTaskId === 'demo_resume_task') window.sessionStorage.removeItem('latestResumeTaskId')
    if (resumeTaskId) refreshRanking()
  }, [])

  const selectedRanking = rankings.find((item) => item.positionId === positionId)
  const bestRanking = rankings[0]
  const filteredRankings = useMemo(() => {
    const value = positionSearch.trim().toLowerCase()
    return value ? rankings.filter((item) => item.positionName.toLowerCase().includes(value)) : rankings
  }, [positionSearch, rankings])

  const selectPosition = (item: MatchRankingItem) => {
    setPositionId(item.positionId)
    setPositionMenuOpen(false)
    setPositionSearch('')
    refreshMatch(item.positionId)
  }

  if (!resumeTaskId) {
    return <div className="page-stack match-page"><section className="panel match-empty-state"><Target size={34} /><h2>请先上传并解析简历</h2><p>系统需要基于真实简历能力画像计算岗位排名、能力差距和学习路径，不会再展示示例评分。</p><AppLink to="/resume" className="primary-button">前往简历解析<ArrowRight size={16} /></AppLink></section></div>
  }

  if (!report) {
    return <div className="page-stack match-page"><section className="panel match-empty-state"><Target size={34} /><h2>{loading ? '正在计算真实岗位匹配' : '暂时无法生成匹配诊断'}</h2><p>{matchError || '正在读取简历并评估全部岗位，请稍候。'}</p>{!loading && <button className="primary-button" onClick={refreshRanking}>重新评估</button>}</section></div>
  }

  return (
    <div className="page-stack match-page">
      <section className="match-selector panel">
        <div className="candidate-selector"><span className="candidate-avatar">{report.candidateName.slice(0, 1)}</span><div><small>候选人</small><strong>{report.candidateName}</strong></div></div>
        <div className="matching-arrow"><span /><Target size={22} /><span /></div>
        {bestRanking && <button className="best-position-card" onClick={() => selectPosition(bestRanking)}><span className="best-position-icon"><Award size={19} /></span><span><small>系统最高匹配</small><strong>{bestRanking.positionName}</strong><em>{bestRanking.matchedSkillCount}/{bestRanking.totalSkillCount} 项技能匹配</em></span><b>{bestRanking.score}<small>分</small></b></button>}
        <div className="position-selector ranked-position-selector">
          <span className="position-icon"><Sparkles size={20} /></span>
          <button className="position-selector-trigger" onClick={() => setPositionMenuOpen((value) => !value)} aria-expanded={positionMenuOpen}>
            <span><small>{positionId === bestRanking?.positionId ? '当前岗位 · 推荐最高分' : '查看其他目标岗位'}</small><strong>{selectedRanking?.positionName ?? '选择岗位'}</strong></span>
            {selectedRanking && <em>{selectedRanking.score} 分</em>}<ChevronDown size={16} />
          </button>
          {positionMenuOpen && <div className="position-ranking-menu">
            <label><Search size={15} /><input autoFocus value={positionSearch} onChange={(event) => setPositionSearch(event.target.value)} placeholder="搜索岗位名称" /></label>
            <div className="position-ranking-list">
              {filteredRankings.map((item, index) => <button className={item.positionId === positionId ? 'active' : ''} key={item.positionId} onClick={() => selectPosition(item)}>
                <i>{rankings.indexOf(item) + 1}</i><span><strong>{item.positionName}</strong><small>{item.fitLevel} · 匹配 {item.matchedSkillCount}/{item.totalSkillCount} 项技能</small><em>{item.strengths.length ? item.strengths.join(' · ') : '暂无已匹配技能'}</em></span><b>{item.score}</b>{index === 0 && !positionSearch && <u>推荐</u>}
              </button>)}
              {filteredRankings.length === 0 && <p>没有找到相关岗位</p>}
            </div>
          </div>}
        </div>
        <button className="primary-button" disabled={loading} onClick={refreshRanking}>{loading ? '评估中…' : '重新评估全部岗位'}</button>
      </section>
      {matchError && <p role="alert">匹配失败：{matchError}</p>}

      <section className="match-overview-grid">
        <article className="panel match-score-card">
          <span className="section-eyebrow">OVERALL MATCH</span><div className="score-ring"><div><strong>{report.overallScore}</strong><span>匹配度</span></div></div><h2>{report.fitLevel}</h2><p>{report.summary}</p><div className="benchmark"><span>候选人排名</span><strong>{report.benchmarkRank}</strong><small>{report.benchmarkSampleCount ? `同方向 ${report.benchmarkSampleCount} 份画像` : '尚无真实排名样本'}</small></div>
        </article>
        <article className="panel dimension-card">
          <SectionHeader eyebrow="DIMENSION SCORE" title="多维能力匹配" description="结合要求类型、技能权重和项目证据计算" />
          <div className="dimension-list">
            {report.dimensions.map((dimension) => <div key={dimension.name}><span>{dimension.name}</span><div><i style={{ width: `${dimension.value}%`, background: dimension.color }} /></div><strong>{dimension.value}</strong></div>)}
          </div>
          <div className="match-insight"><Lightbulb size={17} /><p><strong>关键结论：</strong>{report.summary}</p></div>
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
          <div className="fit-level"><div><span>当前适配等级</span><strong>{report.overallScore >= 80 ? 'A' : report.overallScore >= 60 ? 'B' : 'C'}</strong></div><p>{report.summary}</p></div>
          <ul>{report.suggestions.map((suggestion) => <li key={suggestion}><CheckCircle2 size={16} />{suggestion}</li>)}</ul>
        </article>
      </section>

      <section className="panel learning-card">
        <SectionHeader eyebrow="PERSONALIZED ROADMAP" title="个性化学习路径" description="基于技能前置关系和差距优先级生成，预计 6–9 周完成" action={<button className="ghost-button"><BookOpenCheck size={15} />导出学习计划</button>} />
        <div className="learning-layout">
          <div className="stage-navigation">
            {report.learningPath.map((step) => <button className={selectedStage === step.stage ? 'active' : ''} onClick={() => setSelectedStage(step.stage)} key={step.stage}><i>{step.stage}</i><span><small>阶段 {step.stage} · {step.duration}</small><strong>{step.title}</strong></span><ArrowRight size={16} /></button>)}
          </div>
          {report.learningPath.filter((step) => step.stage === selectedStage).map((step) => <div className="stage-detail" key={step.stage}><span className="stage-icon"><Route size={24} /></span><span className="section-eyebrow">STAGE {step.stage}</span><h3>{step.title}</h3><p>{step.goal}</p><div><span>重点技能</span><div className="tag-list">{step.skills.map((skill) => <em key={skill}>{skill}</em>)}</div></div><div className="stage-outcome"><CircleCheck size={17} /><span><strong>阶段成果</strong>完成可展示项目并通过能力自测</span></div></div>)}
        </div>
      </section>
    </div>
  )
}
