# 前后端功能闭环方案：数据处理与 LLM 接入边界

## 目标

明确当前阶段哪些用规则实现，哪些以后用 LLM 增强。原则是：先把功能闭环做好，在线页面不要依赖 LLM。

## 当前可用数据

主要数据：

- `data/processed/relevant_jobs.jsonl`
- `data/processed/relevant_jobs.csv`
- `data/processed/cleaned_job_postings.csv`
- `data/raw/*.jsonl`
- `data/raw/*.csv`

当前后端已经能基于 `relevant_jobs.jsonl` 做岗位演化和岗位画像。

## 当前阶段不用 LLM 的部分

这些先用规则实现：

- 工作台统计
- 基础岗位图谱
- 能力演化
- 新岗位发现
- 审核项生成
- 第一版匹配评分

规则来源：

- 岗位关键词：`POSITION_ALIASES`
- 技能关键词：`SKILL_ALIASES`
- JD 时间窗口
- 企业数、样本数、命中频率

## 后续适合 LLM 的部分

后续作为离线处理接入：

- JD 技能抽取
- 技能归一化
- 岗位标准化
- 岗位簇/技能簇命名
- 职责和场景摘要
- 简历解析
- 匹配解释和学习路径文案

不要在用户打开页面时实时调用 LLM。

## 推荐数据流水线

### 规则处理

建议脚本：

- `src/processing/build_graph_seed.py`
- `src/processing/build_review_candidates.py`

输出：

- `data/processed/graph_nodes.jsonl`
- `data/processed/graph_edges.jsonl`
- `data/processed/review_candidates.jsonl`

### LLM 离线增强

建议脚本：

- `src/processing/llm_extract_jd_skills.py`
- `src/processing/llm_normalize_skills.py`
- `src/processing/llm_normalize_positions.py`
- `src/processing/llm_summarize_profiles.py`

输出：

- `data/processed/llm_skill_mentions.jsonl`
- `data/processed/skill_normalization.jsonl`
- `data/processed/position_normalization.jsonl`
- `data/processed/position_profile_summaries.jsonl`

## 后端读取优先级

服务层读取数据时按这个顺序：

1. LLM 增强结果。
2. 规则处理结果。
3. 从 `relevant_jobs.jsonl` 实时计算。
4. 后端 demo 数据。

这样可以保证没有增强数据时系统也能跑。

## 对外表述边界

可以说：

- 全页面已完成前后端接口闭环。
- 岗位演化和岗位画像基于已有 JD 数据。
- 图谱接口已具备后端返回节点和关系的能力。
- LLM 可作为后续离线增强模块接入。

不要说：

- 所有节点已由 LLM 精准抽取。
- 简历解析已支持任意真实简历。
- 已接入完整图数据库。
- 匹配结果已经过完整模型评测。

## 验收

不运行任何 LLM，也能启动系统并访问所有页面：

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
cd frontend
npm run dev -- --host 127.0.0.1
```

