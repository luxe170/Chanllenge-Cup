import type {
  ChangeRecord,
  DashboardSummary,
  GraphEdge,
  GraphNode,
  LearningStep,
  MatchDimension,
  PositionProfile,
  ResumeSkill,
  ReviewItem,
} from '../types'

export const dashboardSummary: DashboardSummary = {
  sourceCount: 8099,
  validCount: 636,
  emergingCount: 12,
  changedCount: 47,
  metrics: [
    { name: 'JD 解析准确率', value: 93.6, target: 90, sampleCount: 120 },
    { name: '简历提取准确率', value: 92.4, target: 90, sampleCount: 108 },
    { name: '人岗匹配准确率', value: 91.8, target: 90, sampleCount: 105 },
  ],
}

export const positionProfile: PositionProfile = {
  id: 'pos_ai_agent_engineer',
  name: 'AI Agent 研发工程师',
  category: '人工智能研发',
  techStack: '人工智能',
  level: '中高级',
  status: 'emerging',
  description: '负责智能体应用、工具调用、知识检索与多智能体工作流系统的设计和研发。',
  firstSeen: '2025-03-01',
  lastSeen: '2026-07-29',
  confidence: 0.93,
  sampleCount: 52,
  aliases: ['智能体研发工程师', 'Agent 开发工程师'],
  responsibilities: ['设计智能体编排与任务规划能力', '建设工具调用和知识检索链路', '优化智能体评测与安全机制'],
  scenarios: ['企业智能助手', '智能客服', '研发效能', '数据分析'],
  requirements: [
    { id: 'skill_python', name: 'Python', type: 'required', weight: 0.94, frequency: 0.88, confidence: 0.97, trend: 'stable', firstSeen: '2025-03-01', evidenceCount: 48 },
    { id: 'skill_llm', name: '大语言模型', type: 'required', weight: 0.92, frequency: 0.83, confidence: 0.95, trend: 'rising', firstSeen: '2025-03-01', evidenceCount: 45 },
    { id: 'skill_langchain', name: 'LangChain', type: 'required', weight: 0.86, frequency: 0.72, confidence: 0.91, trend: 'rising', firstSeen: '2025-06-10', evidenceCount: 43 },
    { id: 'skill_rag', name: 'RAG', type: 'required', weight: 0.84, frequency: 0.68, confidence: 0.93, trend: 'rising', firstSeen: '2025-04-12', evidenceCount: 39 },
    { id: 'skill_multi_agent', name: '多智能体协作', type: 'preferred', weight: 0.72, frequency: 0.46, confidence: 0.87, trend: 'new', firstSeen: '2026-01-18', evidenceCount: 25 },
    { id: 'skill_eval', name: '模型评测', type: 'preferred', weight: 0.64, frequency: 0.41, confidence: 0.84, trend: 'new', firstSeen: '2026-02-03', evidenceCount: 21 },
  ],
}

export const graphNodes: GraphNode[] = [
  { id: 'position', name: 'AI Agent\n研发工程师', type: 'position', x: 390, y: 250, trend: 'new' },
  { id: 'python', name: 'Python', type: 'skill', x: 190, y: 105, trend: 'stable', weight: 0.94 },
  { id: 'llm', name: '大语言模型', type: 'skill', x: 380, y: 70, trend: 'rising', weight: 0.92 },
  { id: 'langchain', name: 'LangChain', type: 'skill', x: 595, y: 115, trend: 'rising', weight: 0.86 },
  { id: 'rag', name: 'RAG', type: 'skill', x: 625, y: 335, trend: 'rising', weight: 0.84 },
  { id: 'multiagent', name: '多智能体协作', type: 'skill', x: 420, y: 445, trend: 'new', weight: 0.72 },
  { id: 'evaluation', name: '模型评测', type: 'skill', x: 175, y: 370, trend: 'new', weight: 0.64 },
  { id: 'cluster', name: '大模型应用开发', type: 'cluster', x: 780, y: 215 },
  { id: 'stack', name: '人工智能', type: 'stack', x: 940, y: 215 },
]

export const graphEdges: GraphEdge[] = [
  ...['python', 'llm', 'langchain', 'rag', 'multiagent', 'evaluation'].map((target) => ({ source: 'position', target, relationship: 'REQUIRES' as const })),
  { source: 'langchain', target: 'cluster', relationship: 'BELONGS_TO' },
  { source: 'rag', target: 'cluster', relationship: 'BELONGS_TO' },
  { source: 'multiagent', target: 'cluster', relationship: 'BELONGS_TO' },
  { source: 'cluster', target: 'stack', relationship: 'BELONGS_TO' },
]

export const panoramaNodes: GraphNode[] = [
  { id: 'position_cluster_ai', name: '人工智能研发\n岗位簇', type: 'cluster', x: 210, y: 65 },
  { id: 'position_cluster_software', name: '软件研发\n岗位簇', type: 'cluster', x: 520, y: 65 },
  { id: 'position_cluster_data', name: '数据技术\n岗位簇', type: 'cluster', x: 830, y: 65 },
  { id: 'pos_agent', name: 'AI Agent\n研发工程师', type: 'position', x: 105, y: 245, trend: 'new' },
  { id: 'pos_llm', name: '大模型应用\n工程师', type: 'position', x: 275, y: 245, trend: 'rising' },
  { id: 'pos_multimodal', name: '多模态应用\n工程师', type: 'position', x: 355, y: 245, trend: 'new' },
  { id: 'pos_java', name: 'Java 开发\n工程师', type: 'position', x: 440, y: 245, trend: 'stable' },
  { id: 'pos_frontend', name: '前端研发\n工程师', type: 'position', x: 600, y: 245, trend: 'stable' },
  { id: 'pos_data', name: '数据研发\n工程师', type: 'position', x: 765, y: 245, trend: 'rising' },
  { id: 'pos_analyst', name: '数据分析\n工程师', type: 'position', x: 930, y: 245, trend: 'stable' },
  { id: 'skill_python_panorama', name: 'Python', type: 'skill', x: 65, y: 445, trend: 'stable', weight: 0.92 },
  { id: 'skill_rag_panorama', name: 'RAG', type: 'skill', x: 180, y: 445, trend: 'rising', weight: 0.84 },
  { id: 'skill_langchain_panorama', name: 'LangChain', type: 'skill', x: 295, y: 445, trend: 'rising', weight: 0.81 },
  { id: 'skill_vlm_panorama', name: '视觉语言模型', type: 'skill', x: 350, y: 445, trend: 'new', weight: 0.76 },
  { id: 'skill_java_panorama', name: 'Java', type: 'skill', x: 410, y: 445, trend: 'stable', weight: 0.91 },
  { id: 'skill_react_panorama', name: 'React', type: 'skill', x: 525, y: 445, trend: 'stable', weight: 0.87 },
  { id: 'skill_typescript_panorama', name: 'TypeScript', type: 'skill', x: 640, y: 445, trend: 'rising', weight: 0.74 },
  { id: 'skill_sql_panorama', name: 'SQL', type: 'skill', x: 755, y: 445, trend: 'stable', weight: 0.89 },
  { id: 'skill_spark_panorama', name: 'Spark', type: 'skill', x: 865, y: 445, trend: 'stable', weight: 0.78 },
  { id: 'skill_bi_panorama', name: 'BI 分析', type: 'skill', x: 970, y: 445, trend: 'declining', weight: 0.62 },
]

export const panoramaEdges: GraphEdge[] = [
  { source: 'pos_agent', target: 'position_cluster_ai', relationship: 'BELONGS_TO' },
  { source: 'pos_llm', target: 'position_cluster_ai', relationship: 'BELONGS_TO' },
  { source: 'pos_multimodal', target: 'position_cluster_ai', relationship: 'BELONGS_TO' },
  { source: 'pos_java', target: 'position_cluster_software', relationship: 'BELONGS_TO' },
  { source: 'pos_frontend', target: 'position_cluster_software', relationship: 'BELONGS_TO' },
  { source: 'pos_data', target: 'position_cluster_data', relationship: 'BELONGS_TO' },
  { source: 'pos_analyst', target: 'position_cluster_data', relationship: 'BELONGS_TO' },
  { source: 'pos_agent', target: 'skill_python_panorama', relationship: 'REQUIRES', requirementType: 'required', weight: 0.92 },
  { source: 'pos_agent', target: 'skill_rag_panorama', relationship: 'REQUIRES', requirementType: 'preferred', weight: 0.84 },
  { source: 'pos_llm', target: 'skill_rag_panorama', relationship: 'REQUIRES', requirementType: 'required', weight: 0.88 },
  { source: 'pos_llm', target: 'skill_langchain_panorama', relationship: 'REQUIRES', requirementType: 'preferred', weight: 0.81 },
  { source: 'pos_multimodal', target: 'skill_vlm_panorama', relationship: 'REQUIRES', requirementType: 'required', weight: 0.76 },
  { source: 'pos_java', target: 'skill_java_panorama', relationship: 'REQUIRES', requirementType: 'required', weight: 0.91 },
  { source: 'pos_frontend', target: 'skill_react_panorama', relationship: 'REQUIRES', requirementType: 'required', weight: 0.87 },
  { source: 'pos_frontend', target: 'skill_typescript_panorama', relationship: 'REQUIRES', requirementType: 'preferred', weight: 0.74 },
  { source: 'pos_data', target: 'skill_sql_panorama', relationship: 'REQUIRES', requirementType: 'required', weight: 0.89 },
  { source: 'pos_data', target: 'skill_spark_panorama', relationship: 'REQUIRES', requirementType: 'preferred', weight: 0.78 },
  { source: 'pos_analyst', target: 'skill_sql_panorama', relationship: 'REQUIRES', requirementType: 'required', weight: 0.82 },
  { source: 'pos_analyst', target: 'skill_bi_panorama', relationship: 'REQUIRES', requirementType: 'preferred', weight: 0.62 },
]

export const skillReverseNodes: GraphNode[] = [
  { id: 'reverse_stack_ai', name: '人工智能\n技术栈', type: 'stack', x: 520, y: 45 },
  { id: 'reverse_cluster_llm', name: '大模型应用开发\n技能簇', type: 'cluster', x: 345, y: 160 },
  { id: 'reverse_cluster_knowledge', name: '知识检索与工程\n技能簇', type: 'cluster', x: 700, y: 160 },
  { id: 'reverse_langchain', name: 'LangChain', type: 'skill', x: 245, y: 295, trend: 'rising', weight: 0.81 },
  { id: 'reverse_agent_skill', name: '工具调用', type: 'skill', x: 410, y: 295, trend: 'new', weight: 0.76 },
  { id: 'reverse_rag', name: 'RAG', type: 'skill', x: 620, y: 295, trend: 'rising', weight: 0.84 },
  { id: 'reverse_vector', name: '向量数据库', type: 'skill', x: 795, y: 295, trend: 'stable', weight: 0.73 },
  { id: 'reverse_agent', name: 'AI Agent\n研发工程师', type: 'position', x: 125, y: 460, trend: 'new', weight: 0.84 },
  { id: 'reverse_llm', name: '大模型应用\n工程师', type: 'position', x: 330, y: 460, trend: 'rising', weight: 0.91 },
  { id: 'reverse_knowledge', name: '知识工程\n工程师', type: 'position', x: 535, y: 460, trend: 'rising', weight: 0.88 },
  { id: 'reverse_search', name: '搜索算法\n工程师', type: 'position', x: 735, y: 460, trend: 'stable', weight: 0.76 },
  { id: 'reverse_product', name: 'AI 产品\n工程师', type: 'position', x: 925, y: 460, trend: 'new', weight: 0.63 },
]

export const skillReverseEdges: GraphEdge[] = [
  { source: 'reverse_cluster_llm', target: 'reverse_stack_ai', relationship: 'BELONGS_TO' },
  { source: 'reverse_cluster_knowledge', target: 'reverse_stack_ai', relationship: 'BELONGS_TO' },
  { source: 'reverse_langchain', target: 'reverse_cluster_llm', relationship: 'BELONGS_TO' },
  { source: 'reverse_agent_skill', target: 'reverse_cluster_llm', relationship: 'BELONGS_TO' },
  { source: 'reverse_rag', target: 'reverse_cluster_knowledge', relationship: 'BELONGS_TO' },
  { source: 'reverse_vector', target: 'reverse_cluster_knowledge', relationship: 'BELONGS_TO' },
  { source: 'reverse_agent', target: 'reverse_langchain', relationship: 'REQUIRES', requirementType: 'required', weight: 0.84 },
  { source: 'reverse_agent', target: 'reverse_agent_skill', relationship: 'REQUIRES', requirementType: 'preferred', weight: 0.78 },
  { source: 'reverse_llm', target: 'reverse_langchain', relationship: 'REQUIRES', requirementType: 'required', weight: 0.91 },
  { source: 'reverse_llm', target: 'reverse_rag', relationship: 'REQUIRES', requirementType: 'preferred', weight: 0.88 },
  { source: 'reverse_knowledge', target: 'reverse_rag', relationship: 'REQUIRES', requirementType: 'required', weight: 0.88 },
  { source: 'reverse_knowledge', target: 'reverse_vector', relationship: 'REQUIRES', requirementType: 'preferred', weight: 0.82 },
  { source: 'reverse_search', target: 'reverse_rag', relationship: 'REQUIRES', requirementType: 'required', weight: 0.76 },
  { source: 'reverse_product', target: 'reverse_agent_skill', relationship: 'REQUIRES', requirementType: 'preferred', weight: 0.63 },
]

export const changes: ChangeRecord[] = [
  { id: 'c1', position: 'AI Agent 研发工程师', skill: '多智能体协作', changeType: '新增', before: '—', after: '加分技能 · 0.72', date: '2026-07-29', evidenceCount: 25, confidence: 0.87 },
  { id: 'c2', position: '大模型应用工程师', skill: 'RAG 评测', changeType: '增强', before: '加分技能 · 0.45', after: '必备技能 · 0.81', date: '2026-07-27', evidenceCount: 39, confidence: 0.92 },
  { id: 'c3', position: 'Java 开发工程师', skill: '云原生', changeType: '增强', before: '加分技能 · 0.52', after: '必备技能 · 0.76', date: '2026-07-26', evidenceCount: 116, confidence: 0.95 },
  { id: 'c4', position: '数据分析师', skill: '传统报表工具', changeType: '下降', before: '必备技能 · 0.74', after: '加分技能 · 0.39', date: '2026-07-24', evidenceCount: 61, confidence: 0.89 },
  { id: 'c5', position: '前端研发工程师', skill: 'AI 辅助开发', changeType: '新增', before: '—', after: '加分技能 · 0.58', date: '2026-07-22', evidenceCount: 42, confidence: 0.86 },
]

export const resumeSkills: ResumeSkill[] = [
  { name: 'Python', level: '精通', source: '项目经历：智能问答系统', confidence: 0.98 },
  { name: '大语言模型', level: '掌握', source: '专业技能', confidence: 0.94 },
  { name: 'LangChain', level: '熟悉', source: '实习经历：智能助手', confidence: 0.93 },
  { name: '向量数据库', level: '掌握', source: '项目经历：企业知识库', confidence: 0.91 },
  { name: 'Docker', level: '熟悉', source: '专业技能', confidence: 0.89 },
  { name: 'FastAPI', level: '掌握', source: '项目经历：模型服务化', confidence: 0.95 },
]

export const matchDimensions: MatchDimension[] = [
  { name: '必备技能', value: 88, color: '#6ee7f9' },
  { name: '加分技能', value: 61, color: '#a78bfa' },
  { name: '项目经验', value: 82, color: '#5ee7a8' },
  { name: '技能深度', value: 76, color: '#fbbf73' },
]

export const learningPath: LearningStep[] = [
  { stage: 1, title: '补齐核心方法', duration: '1–2 周', skills: ['RAG 评测', '检索质量分析'], goal: '能够建立可量化的检索与生成评测集' },
  { stage: 2, title: '掌握智能体编排', duration: '2–3 周', skills: ['工具调用', '任务规划', '状态管理'], goal: '独立完成具备工具调用能力的单智能体应用' },
  { stage: 3, title: '进阶多智能体系统', duration: '3–4 周', skills: ['多智能体协作', '记忆机制', '安全护栏'], goal: '完成可观测、可评测的多智能体工作流项目' },
]

export const reviewItems: ReviewItem[] = [
  { id: 'r1', type: '新岗位', title: '具身智能数据工程师', description: '技能组合与机器人数据工程岗位差异度 43%，连续三个时间窗口增长。', confidence: 0.88, sources: ['字节跳动', '华为', '阿里巴巴'], createdAt: '10 分钟前', status: 'pending' },
  { id: 'r2', type: '能力变更', title: '大模型应用工程师新增“上下文工程”', description: '近两个月出现频率由 8% 上升至 36%，建议标记为加分技能。', confidence: 0.91, sources: ['腾讯', '字节跳动', '美团'], createdAt: '35 分钟前', status: 'pending' },
  { id: 'r3', type: '技能归一', title: 'Agentic Workflow → 智能体工作流', description: '发现 4 种中英文别名，建议合并至现有标准技能节点。', confidence: 0.96, sources: ['技能词典', 'JD 语料'], createdAt: '1 小时前', status: 'pending' },
]
