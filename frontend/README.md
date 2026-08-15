# 职涯棱镜前端

岗位能力图谱动态构建与演化分析系统的 Web 前端。当前版本提供完整的评审演示闭环，使用本地 Mock 数据运行，后端接口准备完成后可在 `src/services/api.ts` 中统一替换。

## 技术栈

- React + TypeScript
- Vite
- History API 轻量客户端路由
- Lucide Icons
- Three.js + React Three Fiber 三维图谱
- 原生 SVG 趋势图

## 页面路由

| 路由 | 页面 | 主要能力 |
|---|---|---|
| `/dashboard` | 全局工作台 | 数据概览、构建流水线、新岗位信号、评测指标 |
| `/graph` | 岗位图谱 | 可旋转缩放的三维全景模式（岗位簇→岗位→技能点）与技能反查（技术栈→技能簇→技能点→岗位） |
| `/evolution` | 岗位演化 | 新岗位发现、能力新增/增强/下降、证据链 |
| `/resume` | 简历解析 | 文件上传、解析进度、技能实体链接、人工修正入口 |
| `/match` | 匹配诊断 | 多维匹配、能力差距、适配建议、学习路径 |
| `/review` | 审核评测 | 人工审核、来源交叉验证、准确率评测报告 |

## 本地运行

```bash
cd frontend
npm install
npm run dev
```

构建生产版本：

```bash
npm run build
```

## 数据接入

前端业务类型定义位于 `src/types/index.ts`，Mock 数据位于 `src/data/mock.ts`，服务入口位于 `src/services/api.ts`。后端联调时保持页面只依赖服务层，避免组件直接拼接接口地址。

岗位级别暂作为业务接口字段保留。它是赛题明确要求的图谱筛选维度，但目前未进入图谱 Schema V1，需要后端从业务数据库或聚合服务提供。
