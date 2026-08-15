import { ArrowRight, BriefcaseBusiness, CheckCircle2, FileCheck2, FileText, GraduationCap, LoaderCircle, PenLine, RotateCcw, ShieldCheck, Sparkles, UploadCloud, WandSparkles, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { Confidence, SectionHeader } from '../components/common'
import { resumeSkills } from '../data/mock'
import { AppLink } from '../router'

export default function ResumePage() {
  const [fileName, setFileName] = useState('陈小雨_AI产品研发_简历.pdf')
  const [parsing, setParsing] = useState(false)
  const [parsed, setParsed] = useState(true)
  const inputRef = useRef<HTMLInputElement>(null)

  const parseResume = (name: string) => {
    setFileName(name)
    setParsing(true)
    setParsed(false)
    window.setTimeout(() => { setParsing(false); setParsed(true) }, 1400)
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
            <input ref={inputRef} type="file" accept=".pdf,.doc,.docx" onChange={(event) => event.target.files?.[0] && parseResume(event.target.files[0].name)} />
            {parsing ? <><LoaderCircle size={34} className="spinner" /><strong>正在解析简历</strong><span>建立技能实体链接...</span></> : <><span className="upload-icon"><UploadCloud size={28} /></span><strong>拖拽文件到这里，或点击上传</strong><span>支持 PDF / DOC / DOCX</span></>}
          </button>
          {fileName && <div className="file-item"><span><FileText size={19} /></span><div><strong>{fileName}</strong><small>1.8 MB · {parsed ? '解析完成' : '处理中'}</small></div>{parsed ? <CheckCircle2 size={18} className="success-icon" /> : <LoaderCircle size={18} className="spinner" />}</div>}
          <button className="ghost-button full-button" onClick={() => inputRef.current?.click()}><RotateCcw size={15} />重新上传</button>
          <div className="parser-metric"><WandSparkles size={18} /><div><strong>92.4% 简历提取准确率</strong><span>基于 108 份人工标注简历验证</span></div></div>
        </aside>

        <section className={`panel resume-result ${parsed ? 'visible' : ''}`}>
          <div className="result-header"><div><span className="section-eyebrow">PARSED PROFILE</span><h2>陈小雨的能力画像</h2><p>算法与 AI 应用方向 · 3 年项目经验</p></div><span className="parse-score"><small>解析完整度</small><strong>94<em>%</em></strong></span></div>
          <div className="profile-summary">
            <div><span className="profile-avatar">陈</span><div><strong>陈小雨</strong><span>意向：AI Agent 研发工程师</span></div></div>
            <span><GraduationCap size={17} />硕士 · 计算机科学</span><span><BriefcaseBusiness size={17} />3 年相关经验</span>
          </div>

          <div className="result-section">
            <div className="result-section-head"><h3>技能要素 <span>{resumeSkills.length}</span></h3><button><PenLine size={14} />编辑修正</button></div>
            <div className="resume-skill-list">
              {resumeSkills.map((skill) => (
                <div className="resume-skill" key={skill.name}><div><span className={`level-dot level-${skill.level}`} /><strong>{skill.name}</strong><em>{skill.level}</em></div><p>{skill.source}</p><Confidence value={skill.confidence} /></div>
              ))}
            </div>
          </div>

          <div className="result-section experience-section">
            <div className="result-section-head"><h3>核心经历 <span>2</span></h3></div>
            <div className="experience-list">
              <article><i /><div><span>2025.03 — 至今</span><h4>企业知识库智能问答系统</h4><p>负责 RAG 链路、向量检索与模型服务化，离线评测准确率提升 18%。</p><div className="tag-list"><em>RAG</em><em>LangChain</em><em>FastAPI</em></div></div></article>
              <article><i /><div><span>2024.06 — 2025.01</span><h4>多轮对话助手</h4><p>参与提示词工程、会话状态管理及工具调用模块开发。</p><div className="tag-list"><em>大语言模型</em><em>Python</em></div></div></article>
            </div>
          </div>

          <div className="result-footer"><span><FileCheck2 size={17} />已完成技能标准化与歧义消解</span><AppLink to="/match" className="primary-button">进入匹配诊断<ArrowRight size={16} /></AppLink></div>
        </section>
      </section>
    </div>
  )
}
