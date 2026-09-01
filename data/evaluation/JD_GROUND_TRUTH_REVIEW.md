# JD Ground Truth 复核说明

## 文件用途

- `jd_ground_truth_draft_120.jsonl`：第一标注员候选结果，包含完整原文、标签及证据。
- `jd_ground_truth_review_120.csv`：提供给第二标注员逐行复核的表格。
- `jd_ground_truth_draft_summary.json`：数量和字段完整性统计。

当前版本为 `draft-v1`，不能在未复核时直接作为正式准确率的金标准。

## 第二标注员操作

逐行检查 CSV 中以下字段：

1. `scope`：`in_scope`、`review` 或 `out_of_scope`。
2. `standard_position`：不能直接照抄包含公司、地点和业务线的原始标题。
3. `skills_json`：只能保留原文明确出现的技能；补充漏标，删除误标。
4. `requirement_type`：出现“优先、加分”等表述时为 `preferred`，否则为 `required`。
5. `responsibilities_json`：删除团队介绍、福利宣传和任职资格，只保留岗位职责。
6. `scenarios_json`：应用场景必须有原文依据，不能依靠常识臆测。

每条修改后填写：

- `review_status`：`approved` 或 `changed`。
- `reviewer`：复核人姓名或代号。
- `review_note`：说明重要修改或仍有争议的地方。

## 裁决规则

- 第二标注员完全同意：该条可进入正式金标准。
- 第二标注员做出修改：第一、第二标注员讨论；不能达成一致时由第三人裁决。
- 无法确定的能力不得强行标注，可在备注中记录并从主指标字段排除。
- 任何技能、职责和场景都必须保存可在 JD 原文中找到的 `evidence`。

复核完成后再生成 `jd_ground_truth_120.jsonl`，并冻结文件 SHA-256。正式评测脚本只能读取无 `pending` 状态的最终文件。
