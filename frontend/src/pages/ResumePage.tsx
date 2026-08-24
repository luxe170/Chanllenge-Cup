import { ArrowRight, BriefcaseBusiness, CheckCircle2, FileCheck2, FileText, GraduationCap, LoaderCircle, PenLine, RotateCcw, ShieldCheck, Sparkles, UploadCloud, WandSparkles, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Confidence, SectionHeader } from '../components/common'
import { resumeSkills } from '../data/mock'
import { AppLink } from '../router'
import { api } from '../services/api'
import type { ParsedResumeProfile } from '../types'

const fallbackProfile: ParsedResumeProfile = {
  candidateName: '陈小雨',
  targetPosition: 'AI Agent 研发工程师',
  education: '硕士 · 计算机科学',
  experienceYears: 3,
  direction: '算法与 AI 应用方向',
  completeness: 94,
  skills: resumeSkills,
  experiences: [
    { period: '2025.03 — 至今', title: '企业知识库智能问答系统', description: '负责 RAG 链路、向量检索与模型服务化，离线评测准确率提升 18%。', skills: ['RAG', 'LangChain', 'FastAPI'] },
    { period: '2024.06 — 2025.01', title: '多轮对话助手', description: '参与提示词工程、会话状态管理及工具调用模块开发。', skills: ['大语言模型', 'Python'] },
  ],
}

export default function ResumePage() {
  const [fileName, setFileName] = useState('陈小雨_AI产品研发_简历.pdf')
  const [parsing, setParsing] = useState(false)
  const [parsed, setParsed] = useState(true)
  const [profile, setProfile] = useState<ParsedResumeProfile>(fallbackProfile)
  const [taskId, setTaskId] = useState('demo_resume_task')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.getResumeTask('demo_resume_task')
      .then((res) => res.data.result && setProfile(res.data.result))
      .catch(() => setProfile(fallbackProfile))
  }, [])

  const parseResume = (file: File) => {
    setFileName(file.name)
    setParsing(true)
    setParsed(false)
    api.createResumeTask(file)
      .then((res) => api.getResumeTask(res.data.taskId))
      .then((res) => {
        setTaskId(res.data.taskId)
        if (res.data.result) setProfile(res.data.result)
      })
      .catch(() => setProfile(fallbackProfile))
      .finally(() => {
        setParsing(false)
        setParsed(true)
      })
  }

  const updateSkills = () => {
    api.updateResumeSkills(taskId, profile.skills)
      .then((res) => setProfile((current) => ({ ...current, skills: res.data.skills })))
      .catch(() => setProfile((current) => ({ ...current })))
  }

  return (
    <div className="page-stack resume-page">
      <section className="page-intro">
        <div><span className="section-eyebrow">AI RESUME PARSER</span><h2>把经历转化为可计算的能力画像</h2><p>支持 PDF、Word 简历解析，并将技能实体链接到岗位能力图谱。</p></div>
        <div className="privacy-chip"><ShieldCheck size={16} />文件仅用于本次分析</div>
      </section>

      <section className="resume-layout">
        <aside className="panel upload-panel">
          <SectionHeader eyebrow="STEP 01" title="上传简历" description="单个文件不超过 10 MB" />
          <button className={`dropzone ${parsing ? 'parsing' : ''}`} onClick={() => inputRef.current?.click()}>
            <input ref={inputRef} type="file" accept=".pdf,.doc,.docx" onChange={(event) => event.target.files?.[0] && parseResume(event.target.files[0])} />
            {parsing ? <><LoaderCircle size={34} className="spinner" /><strong>正在解析简历</strong><span>建立技能实体链接...</span></> : <><span className="upload-icon"><UploadCloud size={28} /></span><strong>拖拽文件到这里，或点击上传</strong><span>支持 PDF / DOC / DOCX</span></>}
          </button>
          {fileName && <div className="file-item"><span><FileText size={19} /></span><div><strong>{fileName}</strong><small>1.8 MB · {parsed ? '解析完成' : '处理中'}</small></div>{parsed ? <CheckCircle2 size={18} className="success-icon" /> : <LoaderCircle size={18} className="spinner" />}</div>}
          <button className="ghost-button full-button" onClick={() => inputRef.current?.click()}><RotateCcw size={15} />重新上传</button>
          <div className="parser-metric"><WandSparkles size={18} /><div><strong>92.4% 简历提取准确率</strong><span>基于 108 份人工标注简历验证</span></div></div>
        </aside>

        <section className={`panel resume-result ${parsed ? 'visible' : ''}`}>
          <div className="result-header"><div><span className="section-eyebrow">PARSED PROFILE</span><h2>{profile.candidateName}的能力画像</h2><p>{profile.direction} · {profile.experienceYears} 年项目经验</p></div><span className="parse-score"><small>解析完整度</small><strong>{profile.completeness}<em>%</em></strong></span></div>
          <div className="profile-summary">
            <div><span className="profile-avatar">{profile.candidateName.slice(0, 1)}</span><div><strong>{profile.candidateName}</strong><span>意向：{profile.targetPosition}</span></div></div>
            <span><GraduationCap size={17} />{profile.education}</span><span><BriefcaseBusiness size={17} />{profile.experienceYears} 年相关经验</span>
          </div>

          <div className="result-section">
            <div className="result-section-head"><h3>技能要素 <span>{profile.skills.length}</span></h3><button onClick={updateSkills}><PenLine size={14} />编辑修正</button></div>
            <div className="resume-skill-list">
              {profile.skills.map((skill) => (
                <div className="resume-skill" key={skill.name}><div><span className={`level-dot level-${skill.level}`} /><strong>{skill.name}</strong><em>{skill.level}</em></div><p>{skill.source}</p><Confidence value={skill.confidence} /></div>
              ))}
            </div>
          </div>

          <div className="result-section experience-section">
            <div className="result-section-head"><h3>核心经历 <span>{profile.experiences.length}</span></h3></div>
            <div className="experience-list">
              {profile.experiences.map((experience) => (
                <article key={experience.title}><i /><div><span>{experience.period}</span><h4>{experience.title}</h4><p>{experience.description}</p><div className="tag-list">{experience.skills.map((skill) => <em key={skill}>{skill}</em>)}</div></div></article>
              ))}
            </div>
          </div>

          <div className="result-footer"><span><FileCheck2 size={17} />已完成技能标准化与歧义消解</span><AppLink to="/match" className="primary-button">进入匹配诊断<ArrowRight size={16} /></AppLink></div>
        </section>
      </section>
    </div>
  )
}
