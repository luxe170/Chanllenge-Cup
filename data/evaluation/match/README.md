# 人岗匹配评测规范

当前开发集包含10份简历和从真实图谱冻结的14个岗位。核心匹配评测直接使用人工确认的结构化简历作为匹配输入，避免把OCR及简历解析误差混入匹配算法成绩；端到端评测另行使用系统解析结果。

Ground Truth标注每份简历的唯一最佳岗位、可接受岗位集合、最佳岗位匹配等级、已具备必备技能和缺失必备技能。GT只能依据原始简历和冻结岗位定义制作，不得查看系统排名；当前标签状态为 `draft_pending_human_review`。

综合分权重：Top-1 30%、Top-3 15%、NDCG@3 10%、等级Macro-F1 15%、缺失技能micro-F1 20%、已匹配技能micro-F1 10%。开发通过线为综合分80%、Top-1 80%、Top-3 90%。

```bash
python -m src.evaluation.generate_match_predictions \
  --resume-ground-truth data/evaluation/resume/resume_ground_truth_10_v1.jsonl \
  --position-pool data/evaluation/match/position_pool_v1.jsonl \
  --output output/evaluation/match_predictions_10_v1.jsonl

python -m src.evaluation.evaluate_match_predictions \
  --ground-truth data/evaluation/match/match_ground_truth_10_v1.jsonl \
  --predictions output/evaluation/match_predictions_10_v1.jsonl \
  --position-pool data/evaluation/match/position_pool_v1.jsonl \
  --output output/evaluation/match_evaluation_report_10_v1.json \
  --allow-draft
```
