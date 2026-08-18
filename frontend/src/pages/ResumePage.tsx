import { AlertTriangle, ArrowRight, BriefcaseBusiness, CheckCircle2, FileCheck2, FileText, GraduationCap, LoaderCircle, PenLine, RotateCcw, ShieldCheck, UploadCloud, WandSparkles } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { Confidence, SectionHeader } from '../components/common'
import { resumeSkills as mockSkills } from '../data/mock'
import { AppLink } from '../router'
import { resumeApi } from '../services/api'
import type { ResumeExperience, ResumeProfile, ResumeSkill } from '../types'

type ParseState = 'idle' | 'uploading' | 'parsing' | 'done' | 'error'

const MOCK_PROFILE: ResumeProfile = {
  name: '陈小雨',
  intendedPosition: 'AI Agent 研发工程师',
  education: '硕士 · 计算机科学',
  experienceYears: 3,
  summary: '算法与 AI 应用方向 · 3 年项目经验',
  completeness: 94,
  skills: mockSkills.map((skill) => ({ ...skill, id: skill.name })),
  experiences: [
    {
      period: '2025.03 — 至今',
      title: '企业知识库智能问答系统',
      detail: '负责 RAG 链路、向量检索与模型服务化，离线评测准确率提升 18%。',
      tags: ['RAG', 'LangChain', 'FastAPI'],
    },
    {
      period: '2024.06 — 2025.01',
      title: '多轮对话助手',
      detail: '参与提示词工程、会话状态管理及工具调用模块开发。',
      tags: ['大语言模型', 'Python'],
    },
  ],
}

function bytesToHuman(bytes: number): string {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function ResumePage() {
  const [fileName, setFileName] = useState('陈小雨_AI产品研发_简历.pdf')
  const [fileSize, setFileSize] = useState<number>(0)
  const [state, setState] = useState<ParseState>('done')
  const [profile, setProfile] = useState<ResumeProfile>(MOCK_PROFILE)
  const [error, setError] = useState<string | null>(null)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [usingMock, setUsingMock] = useState(true)
  const inputRef = useRef<HTMLInputElement>(null)

  const parsing = state === 'uploading' || state === 'parsing'
  const parsed = state === 'done'

  const experienceCount = profile.experiences.length
  const parsedProgress = useMemo(() => (parsing ? '解析中' : parsed ? '解析完成' : '待处理'), [parsing, parsed])

  const handleFile = async (file: File) => {
    setFileName(file.name)
    setFileSize(file.size)
    setError(null)
    setState('uploading')
    try {
      const upload = await resumeApi.upload(file)
      setTaskId(upload.data.id)
      setState('parsing')
      const task = upload.data.status === 'succeeded' ? upload.data : (await resumeApi.get(upload.data.id)).data
      if (task.status === 'failed') {
        throw new Error(task.error || '解析失败')
      }
      if (!task.result) {
        throw new Error('未返回解析结果')
      }
      setProfile(task.result)
      setUsingMock(false)
      setState('done')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setError(`${message} — 已回退至演示数据`)
      setProfile(MOCK_PROFILE)
      setUsingMock(true)
      setState('error')
      window.setTimeout(() => setState('done'), 400)
    }
  }

  return (
    <div className="page-stack resume-page">
      <section className="page-intro">
        <div>
          <span className="section-eyebrow">AI RESUME PARSER</span>
          <h2>把经历转化为可计算的能力画像</h2>
          <p>支持 PDF、Word 简历解析，并将技能实体链接到岗位能力图谱。</p>
        </div>
        <div className="privacy-chip"><ShieldCheck size={16} />文件仅用于本次分析</div>
      </section>

      <section className="resume-layout">
        <aside className="panel upload-panel">
          <SectionHeader eyebrow="STEP 01" title="上传简历" description="单个文件不超过 10 MB，支持 PDF / DOCX / TXT" />
          <button className={`dropzone ${parsing ? 'parsing' : ''}`} onClick={() => inputRef.current?.click()}>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.doc,.docx,.txt,.md"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) void handleFile(file)
                event.target.value = ''
              }}
            />
            {parsing ? (
              <>
                <LoaderCircle size={34} className="spinner" />
                <strong>{state === 'uploading' ? '正在上传简历' : '正在解析简历'}</strong>
                <span>建立技能实体链接...</span>
              </>
            ) : (
              <>
                <span className="upload-icon"><UploadCloud size={28} /></span>
                <strong>拖拽文件到这里，或点击上传</strong>
                <span>支持 PDF / DOC / DOCX / TXT</span>
              </>
            )}
          </button>
          {fileName && (
            <div className="file-item">
              <span><FileText size={19} /></span>
              <div>
                <strong>{fileName}</strong>
                <small>{bytesToHuman(fileSize)} · {parsedProgress}</small>
              </div>
              {parsed ? <CheckCircle2 size={18} className="success-icon" /> : <LoaderCircle size={18} className="spinner" />}
            </div>
          )}
          <button className="ghost-button full-button" onClick={() => inputRef.current?.click()}>
            <RotateCcw size={15} />重新上传
          </button>
          {error && (
            <div className="parser-metric" role="alert" style={{ background: 'rgba(251, 146, 60, 0.08)' }}>
              <AlertTriangle size={18} />
              <div>
                <strong>解析失败</strong>
                <span>{error}</span>
              </div>
            </div>
          )}
          <div className="parser-metric">
            <WandSparkles size={18} />
            <div>
              <strong>{usingMock ? '92.4% 简历提取准确率' : `${profile.completeness}% 解析完整度`}</strong>
              <span>{usingMock ? '基于 108 份人工标注简历验证' : `识别技能 ${profile.skills.length} 项 · 关联经历 ${experienceCount} 段`}</span>
            </div>
          </div>
          {taskId && !usingMock && (
            <div className="parser-metric" style={{ opacity: 0.7 }}>
              <FileCheck2 size={18} />
              <div>
                <strong>任务号 {taskId.slice(0, 12)}...</strong>
                <span>可用于结果追溯与编辑修正</span>
              </div>
            </div>
          )}
        </aside>

        <section className={`panel resume-result ${parsed ? 'visible' : ''}`}>
          <div className="result-header">
            <div>
              <span className="section-eyebrow">PARSED PROFILE</span>
              <h2>{profile.name || '未识别姓名'}的能力画像</h2>
              <p>{profile.summary}</p>
            </div>
            <span className="parse-score">
              <small>解析完整度</small>
              <strong>{profile.completeness}<em>%</em></strong>
            </span>
          </div>
          <div className="profile-summary">
            <div>
              <span className="profile-avatar">{profile.name ? profile.name.slice(0, 1) : '?'}</span>
              <div>
                <strong>{profile.name || '未识别姓名'}</strong>
                <span>意向：{profile.intendedPosition || '未填写'}</span>
              </div>
            </div>
            {profile.education && (
              <span><GraduationCap size={17} />{profile.education}</span>
            )}
            {profile.experienceYears !== null && (
              <span><BriefcaseBusiness size={17} />{profile.experienceYears} 年相关经验</span>
            )}
          </div>

          <div className="result-section">
            <div className="result-section-head">
              <h3>技能要素 <span>{profile.skills.length}</span></h3>
              <button><PenLine size={14} />编辑修正</button>
            </div>
            <div className="resume-skill-list">
              {profile.skills.length === 0 && (
                <div className="empty-state">尚未识别到与岗位图谱匹配的技能。</div>
              )}
              {profile.skills.map((skill: ResumeSkill) => (
                <div className="resume-skill" key={skill.id ?? skill.name}>
                  <div>
                    <span className={`level-dot level-${skill.level}`} />
                    <strong>{skill.name}</strong>
                    <em>{skill.level}</em>
                  </div>
                  <p>{skill.source}</p>
                  <Confidence value={skill.confidence} />
                </div>
              ))}
            </div>
          </div>

          <div className="result-section experience-section">
            <div className="result-section-head">
              <h3>核心经历 <span>{experienceCount}</span></h3>
            </div>
            <div className="experience-list">
              {profile.experiences.length === 0 && (
                <div className="empty-state">未识别到时间明确的项目经历。</div>
              )}
              {profile.experiences.map((exp: ResumeExperience) => (
                <article key={`${exp.period}-${exp.title}`}>
                  <i />
                  <div>
                    <span>{exp.period}</span>
                    <h4>{exp.title || '未命名经历'}</h4>
                    <p>{exp.detail}</p>
                    {exp.tags.length > 0 && (
                      <div className="tag-list">
                        {exp.tags.map((tag) => <em key={tag}>{tag}</em>)}
                      </div>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </div>

          <div className="result-footer">
            <span><FileCheck2 size={17} />{usingMock ? '演示数据 · 上传真实简历以启用后端解析' : '已完成技能标准化与歧义消解'}</span>
            <AppLink to="/match" className="primary-button">进入匹配诊断<ArrowRight size={16} /></AppLink>
          </div>
        </section>
      </section>
    </div>
  )
}
