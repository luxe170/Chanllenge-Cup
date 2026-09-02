# 简历提取评测数据规范

本目录只保存脱敏后的正式评测数据。原始简历放入 `files/`，文件名使用稳定编号，不包含候选人真实姓名。

## 样本组成

- 共30份：PDF 12份、DOCX 12份、TXT 3份、扫描PDF 3份。
- 覆盖中文、英文、中英混排、表格、多栏、无技能和解析失败边界样本。
- 每个文件计算SHA-256，写入GT，防止文件被替换后继续沿用旧标签。

## Ground Truth格式

Ground Truth 的 `result` 必须与后端简历解析接口返回的 `result` 完全同构。当前10份开发样本保存在
`resume_ground_truth_10_v1.jsonl`，每行一条：

```json
{
  "resumeId": "R01",
  "file": "data/jianli/pdf/R01_示例.pdf",
  "result": {
    "candidateName": "脱敏姓名A",
    "targetPosition": "AI Agent研发工程师",
    "education": "硕士",
    "experienceYears": 0,
    "direction": "AI Agent",
    "completeness": 1.0,
    "skills": [
      {"id": "skill_python", "name": "Python", "level": 3, "source": "项目经历", "confidence": 1.0}
    ],
    "experiences": [
      {"period": "2024.01-2024.06", "title": "项目名称", "description": "项目原文摘要", "skills": ["skill_python"]}
    ]
  },
  "annotationMeta": {
    "reviewStatus": "draft_pending_human_review",
    "annotationBasis": "manual_from_resume",
    "schema": "ParsedResumeProfile.result.v1"
  }
}
```

## 标注规则

- 技能必须有简历原文证据，不根据岗位常识补充。
- 技能名称通过 `data/evaluation/ontology` 归一；表外技能先进入待审核别名/技能表，不得强行映射。
- 学历按博士、硕士、本科、大专、高中归一。
- 工作年限允许标注到0.5年；正式评分容差为0.5年。
- 目标岗位只标注简历明确写出的求职意向；没有则使用约定的“未指定”岗位ID，不根据经历猜测。
- 两位标注员独立工作，冲突经第三人裁决后才能将状态设为 `adjudicated`。
- `annotationMeta` 是评测管理信息，不参与解析结果评分；`completeness` 仅为保持接口结构一致，不作为准确率指标。

## 预测与评分

系统预测必须由上传接口所使用的正式任务链路生成：文字版简历走文本 LLM，扫描 PDF
渲染为页面图片后走多模态 LLM，PNG/JPG/JPEG/WebP 直接作为视觉输入。两条路径最终都归一为同一个
`result` 结构，因此现有 GT 的核心抽取字段可以继续使用。

先生成预测（正式评测必须加 `--require-llm`，防止规则降级结果混入模型成绩）：

```bash
python -m src.evaluation.generate_resume_predictions \
  --manifest data/evaluation/resume/resume_ground_truth_10_v1.jsonl \
  --output output/evaluation/resume_predictions_10_v1.jsonl \
  --require-llm
```

再评分：

```bash
python -m src.evaluation.evaluate_resume_predictions \
  --ground-truth data/evaluation/resume/resume_ground_truth_10_v1.jsonl \
  --predictions output/evaluation/resume_predictions_v1.jsonl \
  --ontology-dir data/evaluation/ontology \
  --output output/evaluation/resume_evaluation_report_v1.json
```

### 评分标准

- 技能先按技能表和已批准别名归一，使用集合级micro-Precision、micro-Recall和micro-F1。
- 项目/工作经历的标题归一后包含匹配或相似度不低于0.65，且期间一致，按条目计算micro-F1。
- 姓名、学历、目标岗位归一后完全匹配；工作年限允许绝对误差不超过0.5年。
- 解析失败保留为空结果并纳入全部指标的分母，同时单独报告 `parseSuccessRate`。
- 另外报告 `llmCompletionRate`、`textParseSuccessRate` 和 `visionParseSuccessRate`，用于区分模型降级、文本输入失败和多模态输入失败；这些诊断指标暂不计入综合分。
- 综合准确率 = 技能F1×35% + 经历F1×20% + 目标岗位准确率×15% + 姓名准确率×10% + 学历准确率×10% + 工作年限准确率×10%。
- `direction` 是推导展示字段，`completeness` 是资料完整度，两者不参与抽取准确率计算。
- 开发与正式通过线暂定为90%；只有达到规定样本量并完成人工复核的结果才可称为正式成绩。

当前10份样本用于开发验证，运行时需加 `--allow-draft`；正式评测仍须扩充并完成人工复核。
