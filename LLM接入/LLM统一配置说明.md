# LLM 统一配置说明

## 目标

项目内所有 LLM 能力统一通过同一个配置入口读取模型、接口地址和 API Key，避免 JD 解析、简历分析、测评标注各自维护一套配置。

当前默认配置：

- 模型：`deepseek-v4-flash`
- 接口地址：`https://api.deepseek.com`
- 接口类型：OpenAI/DeepSeek 兼容的 `chat/completions`

## 本地配置方式

推荐在项目根目录生成 `.env` 文件。`.env` 已加入 `.gitignore`，不会被提交。

```powershell
.\scripts\configure_llm.ps1 -ApiKey "你的 DeepSeek API Key"
```

生成内容包括：

```text
LLM_API_KEY=...
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_RESUME_ENABLED=true
```

也可以复制 `.env.example` 为 `.env` 后手动填写。

## 配置读取优先级

统一客户端会按以下顺序读取：

1. 系统环境变量。
2. 项目根目录 `.env`。
3. 项目根目录 `.env.local`。
4. 默认值。

API Key 支持以下变量名：

- `LLM_API_KEY`
- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY`

推荐统一使用 `LLM_API_KEY`。

## 已接入模块

- JD 提取解析：`src.processing.llm_extract_jd_skills`
- 简历分析与学习建议：`backend.app.services.resume_llm_service`
- 测评标注初稿：`src.evaluation.deepseek_label_jd_test_set`

这些模块都通过 `src.llm_client.ChatCompletionsClient.from_env()` 或 `src.llm_client.load_llm_config()` 获取统一配置。

## 状态检查

后端状态接口会返回 LLM 配置状态，但不会返回 API Key：

```http
GET /api/v1/data-sources/status
```

也可以通过本地后端 API 一键写入 `.env`：

```http
POST /api/v1/llm/config
Content-Type: application/json
```

请求体：

```json
{
  "apiKey": "你的 DeepSeek API Key",
  "model": "deepseek-v4-flash",
  "baseUrl": "https://api.deepseek.com",
  "resumeEnabled": true
}
```

状态查询：

```http
GET /api/v1/llm/config/status
```

关注字段：

- `onlineLlmEnabled`
- `llmConfig.configured`
- `llmConfig.model`
- `llmConfig.baseUrl`
- `llmConfig.resumeEnabled`

## 安全边界

不要把真实 API Key 写进代码、Markdown 文档、测试文件或提交历史。只放在本机 `.env` 或系统环境变量中。
