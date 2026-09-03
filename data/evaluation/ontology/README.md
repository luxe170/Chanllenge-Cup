# 评测岗位表与技能表

## 文件

- `position_registry_v1.jsonl`：岗位主表。
- `position_aliases_v1.jsonl`：岗位别名表。
- `skill_registry_v1.jsonl`：技能主表。
- `skill_aliases_v1.jsonl`：技能别名表。
- `ontology_metadata_v1.json`：版本与数量信息。
- `../jd_ground_truth_normalized_120_v1.jsonl`：第二版120条标准化标注，现仅作为历史材料保留；当前JD评测采用 `data/processed/splits/jd_test_set_100.jsonl` 与对应第一版标签。

## 岗位主表字段

| 字段 | 说明 |
|---|---|
| `id` | 基于标准名称生成的稳定岗位ID |
| `name` | 标准岗位名称 |
| `normalized_name` | 用于精确归一化的名称 |
| `category_id/category_name` | 岗位类别 |
| `scope` | `in_scope`、`review`或`out_of_scope` |
| `status` | 实体是否启用 |
| `version` | 本体版本 |

## 技能主表字段

| 字段 | 说明 |
|---|---|
| `id` | 基于标准名称生成的稳定技能ID |
| `name` | 标准技能名称 |
| `normalized_name` | 用于精确归一化的名称 |
| `category_id/category_name` | 技能类别 |
| `parent_skill_id` | 明确存在上下位关系时指向父技能 |
| `status` | 实体是否启用 |
| `version` | 本体版本 |

## 评测使用顺序

1. 对系统输出做大小写、空格、全半角和连接符归一化。
2. 先查标准名称，再查对应别名表。
3. 命中后转换成标准实体ID，与Ground Truth的ID比较。
4. 未命中的词进入未知实体盲审，不能直接判错或自动判对。
5. `parent_skill_id`只用于计算辅助的层级感知指标，严格micro-F1仍要求标准技能ID一致。

## 冻结要求

当前所有别名的`review_status`均为`pending`。第二标注员逐项确认后改为`approved`或`rejected`；正式评测只能使用已批准别名。冻结后计算全部文件SHA-256，任何修改都必须提升版本号并保留变更记录。

## 系统预测格式

```json
{
  "evaluation_id": "JD-EVAL-001",
  "position": {
    "position_id": "position_xxx",
    "name": "大模型算法工程师"
  },
  "scope": "in_scope",
  "skills": [
    {
      "skill_id": "skill_xxx",
      "name": "大语言模型",
      "requirement_type": "required",
      "evidence": "熟悉大语言模型训练与应用"
    }
  ]
}
```

岗位和技能可以只提交ID，也可以只提交名称；评测器会依次使用ID、标准名称和已批准别名解析。无法解析的预测岗位记为岗位错误，无法解析的预测技能记为FP并进入未知技能清单。
