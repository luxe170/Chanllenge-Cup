# 职涯棱镜

多源异构数据驱动的岗位能力图谱动态构建与演化分析系统，参赛题目编号为
`XH-202621`。

## 项目目标

围绕新一代信息技术岗位，完成多源数据采集与清洗、新岗位发现、既有岗位能力
更新、能力知识图谱、简历解析、人岗匹配、差距分析和学习路径推荐的完整闭环。

## 目录结构

```text
.
├── README.md                 # 项目入口与协作说明
├── requirements.txt         # Python 依赖
├── docs/
│   ├── requirements/        # 官方赛题与评分要求
│   ├── product/             # PRD、系统方案与任务规划
│   └── data/                # 数据采集和数据规范文档
├── materials/
│   ├── registration/        # 报名与盖章材料
│   └── presentation/        # 汇报及答辩材料
├── data/
│   ├── raw/                 # 未加工的原始数据
│   └── processed/           # 清洗、标准化和标注后的数据
├── src/
│   └── crawlers/            # 数据采集程序
├── frontend/                # React + TypeScript Web 前端
├── tests/                   # 自动化测试与评测用例
├── output/                  # 临时运行结果和导出成果
└── tmp/                     # 本地检查产生的临时文件
```

## 关键文档

- 赛题要求：`docs/requirements/赛题说明.pdf`
- 产品与技术方案：`docs/product/产品与技术方案.md`
- 数据采集说明：`docs/data/字节岗位爬虫说明.md`
- 数据清洗说明：`docs/data/岗位数据清洗说明.md`
- 早期汇报稿：`materials/presentation/早期汇报稿.pptx`

## 数据现状

- `data/raw/bytedance_dev_jobs.csv`：字节跳动研发岗位结构化数据。
- `data/raw/bytedance_dev_jobs.jsonl`：支持断点续采的原始记录。
- `data/raw/多平台岗位样本.csv`：多平台早期样本，仍需清洗与质量核验。

原始数据保持只读语义。后续清洗、去重、技能标准化和标注结果统一写入
`data/processed/`，不要覆盖 `data/raw/`。

## 运行爬虫

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python src/crawlers/bytedance_jobs_spider.py --max-pages 1 --output output/test_jobs
```

完成环境验证后，可运行全量采集：

```bash
python src/crawlers/bytedance_jobs_spider.py
```

## 清洗岗位数据

原始采集完成后运行：

```bash
python src/processing/clean_job_postings.py
```

清洗结果写入 `data/processed/`，包括有效岗位、拒绝记录和质量统计报告。

## 抓取腾讯、阿里、美团和华为岗位

先用每家公司一页做连通性验证：

```bash
python src/crawlers/multi_company_jobs_spider.py --max-pages 1
```

确认后抓取所有公开职位：

```bash
python src/crawlers/multi_company_jobs_spider.py
```

可用 `--companies tencent meituan` 选择来源。数据分别写入
`data/raw/tencent_jobs.*`、`alibaba_jobs.*`、`meituan_jobs.*` 和
`huawei_jobs.*`。阿里集团当前将社会招聘分散到各业务招聘站，脚本采集其仍由集团
统一提供的校园招聘职位，并在 `recruit_type` 中保留具体批次。

## 近期重点

1. 建立多源数据清洗、去重和可信度评估流程。
2. 定义岗位、技能、技能簇和技术栈的图谱 Schema。
3. 制作不少于 100 条 JD 的人工标注测试集。
4. 建立 JD 解析、简历提取和人岗匹配三项准确率评测。
5. 完成可部署的前后端闭环与正式参赛材料。

## 运行前端

```bash
cd frontend
npm install
npm run dev
```

当前前端使用 Mock 数据提供完整演示流程，接口约定见
`docs/product/前端接口契约.md`。
