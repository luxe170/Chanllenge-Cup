# JD正式LLM流程评测方案

## 1. 评测目标

本方案只评测项目正式使用的LLM JD解析流程，不再把规则解析器成绩作为正式JD准确率。规则解析器及旧报告只用于回归对照。

正式被测链路为：

```text
原始JD
→ src.processing.llm_extract_jd_skills
→ llm-jd-extraction-v1结构化result
→ 与人工Ground Truth比较
→ 输出核心准确率、内容质量和候选发现诊断
```

## 2. 冻结评测资产

| 资产 | 文件 | 说明 |
|---|---|---|
| 原始评测集 | `data/processed/splits/jd_test_set_100.jsonl` | 去除17条构图泄漏后的100条JD |
| 正式结构GT | `data/processed/evaluation/jd_result_ground_truth_100_v1.jsonl` | `result`与正式LLM输出同构 |
| 岗位/技能本体 | `backend.app.services.evolution_service`中的标准表 | 评测前冻结版本和SHA-256 |
| LLM预测 | `output/evaluation/jd_predictions_100_v1.jsonl` | 正式流程一次性生成 |
| 评测报告 | `output/evaluation/llm_jd_evaluation_report_100_v1.json` | 指标、哈希及逐条错误 |

测试集与200条构图集按 `source_id`、`content_hash` 和规范化全文均为零重合。评测期间不得替换单条样本、按错误结果修改GT或将预测回写为标签。

## 3. Ground Truth要求

### 3.1 结构

每条GT由 `evaluationId`、`sourceId`、`result` 和 `annotationMeta` 组成。`result`与 `llm-jd-extraction-v1` 输出字段一致；`annotationMeta`只管理标注状态，不参与准确率。

### 3.2 人工复核

当前100条为自动迁移草稿，不能直接作为正式金标准。正式复核流程：

1. 标注员A、B只查看原始JD、冻结岗位表和技能表，独立标注。
2. 两人分别确认 `scope`、标准岗位、技能、必备/加分、证据、职责、场景及候选实体。
3. 冲突由第三人裁决；无法形成共识的记录不能进入正式集。
4. 最终 `reviewStatus` 统一改为 `adjudicated`，记录标注员、裁决人和复核时间。
5. 冻结GT并保存SHA-256；之后的任何修改必须提升版本号。

岗位名称或技能名称略有差异时，仅允许通过冻结的标准ID和已批准别名归一。表外技能必须标为 `newSkillCandidates`，不能强行映射到相近技能。

## 4. 计分范围

### 4.1 核心JD解析准确率

| 输出字段 | 指标 | 权重 |
|---|---|---:|
| `scope` | Macro-F1 | 10% |
| `position.id` | Accuracy | 35% |
| `skills[].id` | micro-Precision、Recall、F1 | 45% |
| `skills[].requirementType` | Macro-F1 | 10% |

```text
CoreScore =
  0.10 × ScopeMacroF1
+ 0.35 × PositionAccuracy
+ 0.45 × SkillMicroF1
+ 0.10 × RequirementTypeMacroF1
```

具体规则：

- `scope` 只接受 `in_scope`、`review`、`out_of_scope`。
- 岗位按标准岗位ID完全匹配；GT为 `out_of_scope` 时不计算岗位和技能内容，但保留scope计分。
- GT岗位为 `candidate_other` 时改由LLM根据原始JD判断预测岗位名是否准确；空泛占位名称判错。裁判结果必须完整落盘并冻结，评分器会校验覆盖范围、对应预测名称和文件SHA-256。
- 技能按去重后的标准技能ID集合计算micro指标。
- 要求类型只接受 `required`、`preferred`，以 `(skillId, requirementType)` 为比较单位；同时报告在正确命中技能上的条件准确率，便于区分“技能漏提”和“类型判错”。
- 空预测和解析失败保留在总体分母中。

### 4.2 原文证据真实性

对以下字段检查证据：

- `position.evidenceText`
- `skills[].evidenceText`
- `newSkillCandidates[].evidenceText`

证据文本经NFKC、大小写、空白和标点归一后，必须能够在原始JD标题、职责或要求中找到。报告：

```text
EvidenceSupportRate = 有原文依据的证据项 / 全部证据项
UnsupportedEvidenceRate = 1 - EvidenceSupportRate
```

证据支持率作为正式门槛，不并入CoreScore，避免模型通过少输出证据获得更高核心分。

### 4.3 职责和场景

`responsibilities` 和 `scenarios` 是开放文本，单独报告，不并入赛题核心准确率。

匹配采用一对一最大匹配，禁止一个预测要点重复匹配多个GT要点：

1. 归一化后完全一致或互为包含，直接判匹配。
2. 其余条目使用冻结的语义模型和固定阈值计算；阈值必须在独立开发集上确定，不能用这100条测试集调参。
3. 位于阈值灰区的条目由两名不知道系统版本的评审裁决，并保存裁决清单。

分别报告职责Precision/Recall/F1、场景Precision/Recall/F1以及无原文依据内容比例。不得使用待测LLM自己充当裁判。

### 4.4 候选发现

以下字段作为诊断指标：

| 字段 | 指标 |
|---|---|
| `isNewPositionCandidate` | Precision、Recall、F1 |
| `newSkillCandidates` | 归一名称后的micro-Precision、Recall、F1 |
| `similarPositions` | Hit@1、Hit@3、MRR |

单条JD这里只评测“是否应进入候选审核”，不能证明岗位已经成为正式新岗位。跨企业、跨时间窗口的新岗位确认应在岗位演化专项评测中完成，不能混入JD核心准确率。

## 5. 不重复计分的字段

以下字段只用于结构、追踪或运行审计：

- 身份字段：`sourceId`、`evaluation_id`、`contentHash`、`sourcePlatform`、`sourceJobId`。
- 原始元数据：`company`、`title`、`publishTime`、`scrapedAt`、`split`。
- 冗余字段：`positionId`、`positionName`、`predictedPositionId`、`predictedPositionName`、`predictedSkills`。
- 运行字段：`schemaVersion`、`parserVersion`、`promptVersion`、`model`、`generatedAt`。
- 审核辅助：`reviewReasons`、`confidence`。

冗余字段必须与主字段一致，否则报告结构错误，但不得重复增加权重。`confidence`单独报告Brier Score或ECE校准结果，不直接判断解析对错。

## 6. 正式通过标准

必须同时满足：

| 指标 | 门槛 |
|---|---:|
| CoreScore | ≥90% |
| PositionAccuracy | ≥90% |
| SkillMicroF1 | ≥90% |
| EvidenceSupportRate | ≥95% |
| 预测覆盖率 | 100% |
| GT复核状态 | 100% adjudicated |

职责、场景和候选发现指标必须披露真实结果，但当前不设为赛题核心通过门槛。任何一个硬门槛未达到，都不能只凭CoreScore宣称JD解析通过。

## 7. 执行步骤

### 7.1 生成正式LLM预测

先配置项目统一LLM环境变量，再运行：

```bash
python -m src.processing.llm_extract_jd_skills \
  --input data/processed/splits/jd_test_set_100.jsonl \
  --output output/evaluation/jd_predictions_100_v1.jsonl \
  --split jd_test \
  --batch-size 5 \
  --no-resume \
  --verbose
```

正式运行使用 `--no-resume`，确保100条预测来自同一次冻结模型、提示词和参数配置。运行前记录Git commit、模型、base URL、prompt版本、Python版本和开始时间。

### 7.2 评分

先生成候选岗位裁判记录：

```bash
python -m src.evaluation.judge_candidate_positions \
  --ground-truth data/processed/evaluation/jd_result_ground_truth_100_v1.jsonl \
  --predictions output/evaluation/jd_predictions_100_v1.jsonl \
  --test-set data/processed/splits/jd_test_set_100.jsonl \
  --output output/evaluation/jd_candidate_position_judgments_100_v1.jsonl \
  --no-resume
```

再运行评分入口：

```bash
python -m src.evaluation.evaluate_llm_jd_predictions \
  --ground-truth data/processed/evaluation/jd_result_ground_truth_100_v1.jsonl \
  --predictions output/evaluation/jd_predictions_100_v1.jsonl \
  --test-set data/processed/splits/jd_test_set_100.jsonl \
  --candidate-judgments output/evaluation/jd_candidate_position_judgments_100_v1.jsonl \
  --output output/evaluation/llm_jd_evaluation_report_100_v1.json \
  --allow-draft
```

人工复核前只能加 `--allow-draft` 联调；正式运行必须删除该参数。评分器会拒绝重复ID、覆盖不完整、测试集不一致以及正式模式下未完成裁决的GT。`evaluate_jd_parser.py` 输出仍只作为旧规则基线。

## 8. 报告内容

正式报告至少包含：

- 样本数、成功数、失败数和预测覆盖率。
- CoreScore及四项组成指标。
- 岗位混淆矩阵、技能TP/FP/FN和未知实体清单。
- 职责、场景、候选发现和证据支持指标。
- 按公司、来源平台、岗位类别分组的结果；小组只报告样本量，不单独宣称通过。
- 每条错误的GT、预测、原文证据和错误类型。
- 代码、GT、测试集、预测、本体文件哈希及完整运行配置。
