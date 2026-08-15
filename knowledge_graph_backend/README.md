# 职涯棱镜知识图谱后端

这是从清洗 JD 到可查询、可追溯、可增量发布的正式知识图谱后端。它不是三维页面的 Mock 数据服务。

## 能力范围

- 岗位与技能标准实体、别名和人工扩展；
- 基于证据区间的岗位链接与技能抽取；
- 必备/加分要求识别；
- 重复样本折叠、时间窗口聚合、权重与置信度计算；
- 新增、上升、稳定和下降趋势；
- PostgreSQL/SQLite 保存 JD、证据、快照、变更、审核和图谱版本；
- Neo4j 保存可重建的当前图谱投影；
- 规范 API 与现有前端 V1 兼容 DTO；
- 管理 API Key、导入路径隔离、请求 ID、CORS 和健康检查；
- CLI、Alembic、Docker Compose、单元与接口测试。

## 数据边界

Neo4j 只保存五类标准节点及三类关系。原始 JD、完整证据、抽取中间结果、审核记录和历史快照保存在业务数据库。任何 `REQUIRES` 关系都能通过 `sourceIds` 回溯到 JD。

## 本地开发

推荐使用 Python 3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

环境变量可由进程或容器注入；应用不会自动解析 `.env`，避免生产环境出现隐式配置。开发环境若暂时没有 Neo4j，可设置：

```powershell
$env:GRAPH_BACKEND='memory'
$env:DATABASE_URL='sqlite:///./var/knowledge_graph.db'
$env:IMPORT_ROOT='../data/processed'
```

初始化并导入：

```powershell
career-prism-kg init-db
career-prism-kg import --source relevant_jobs.csv --window-days 180 --min-sample-count 2
career-prism-kg serve --reload
```

API 文档位于 `http://localhost:8000/docs`。

注意：memory 图后端仅供测试和本地逻辑验证，服务重启后图投影会消失。正式运行必须使用 Neo4j。

## 生产部署

先在当前目录创建 `.env`，至少提供：

```text
POSTGRES_PASSWORD=<strong-random-secret>
NEO4J_PASSWORD=<strong-random-secret>
ADMIN_API_KEY=<at-least-16-characters>
CORS_ORIGINS=https://your-frontend.example
```

然后运行：

```bash
docker compose up -d --build
```

Compose 会先由一次性 `migrate` 服务执行数据库迁移，再启动 API 和 worker。数据目录以只读方式挂载到 API 与 worker；导入 API 只允许访问 `IMPORT_ROOT` 内的 CSV，防止任意文件读取。

推荐通过 `POST /api/v1/pipeline-runs` 创建持久化导入任务，由 worker 异步执行。运维人员也可在容器内使用 `career-prism-kg import` 同步执行一次构建。

## API 契约

所有响应为：

```json
{"data": {}, "requestId": "req_xxx"}
```

核心查询：

- `GET /api/v1/graph`
- `GET /api/v1/graph/roots`
- `GET /api/v1/graph/nodes/{id}`
- `GET /api/v1/graph/search`
- `GET /api/v1/positions/{id}`
- `GET /api/v1/positions/{id}/evidence`
- `GET /api/v1/skills/{id}`
- `GET /api/v1/evolution/changes`
- `GET /api/v1/emerging-positions`
- `GET /api/v1/evaluations/extraction`

管理接口：

- `POST /api/v1/pipeline-runs`
- `GET /api/v1/pipeline-runs/{id}`
- `POST /api/v1/pipeline-runs/{id}/retry`
- `GET /api/v1/reviews`
- `POST /api/v1/reviews/{id}/decision`
- `POST /api/v1/entities`
- `POST /api/v1/gold-annotations`

生产环境的写接口必须携带 `X-Admin-Key`。

`POST /pipeline-runs` 只创建持久化队列任务；独立 `worker` 服务负责认领和执行。API 进程重启不会丢失已排队任务。CLI 的 `import` 命令用于运维人员同步执行一次完整构建。

现有前端接入时，可调用：

```text
GET /api/v1/graph?mode=panorama&contract=frontend_v1
```

规范契约使用明确的 `position_category`、`skill_cluster`、`tech_stack` 和 `IN_CATEGORY`；兼容契约会临时映射成旧前端的 `cluster`、`stack` 和 `BELONGS_TO`。

## 质量和发布规则

- 新岗位候选不会自动创建正式节点，必须审核；
- 新技能应通过管理接口或后续模型候选审核进入标准库；
- 低于 `MIN_AUTO_PUBLISH_CONFIDENCE` 的关系进入审核队列；
- 同一岗位—技能关系在图中最多一条；
- 发布使用稳定业务 ID，整次 Neo4j 投影替换在一个事务内完成；
- SQL 中的运行数据允许失败后重试，图谱投影可由任意已验收快照重建；
- 生产发布前必须准备不少于 100 条人工标注 JD，并运行覆盖率和抽取指标。

## 测试

```bash
pytest --cov=app --cov-report=term-missing
```

测试默认使用临时 SQLite 和内存图仓库，不依赖外部 Neo4j。本项目已在 Docker Desktop 中完成 PostgreSQL 17、Neo4j 5、队列恢复、失败重试和跨容器持久化集成验证；CI 仍应持续运行同类测试，并补充性能与并发测试。
