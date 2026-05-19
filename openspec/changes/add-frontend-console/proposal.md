## Why

当前 `init-notification-mvp` 提供了后端 HTTP API（收单、投递、DLQ、metrics），但运维 / QA / 演示场景下都需要一个**可视化界面**：（1）业务方在调用前可以试发一条；（2）运维能直观看到投递成功率、DLQ 堆积、Provider 熔断状态；（3）作业评审时能立刻"看见"系统在做什么，而不是只看 README 与 curl 日志。本次新增前端 Web Console，作为后端能力的统一可视化入口。

## What Changes

- 新增 `web/` 子项目，使用 Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui
- 提供 5 个核心页面：Dashboard、Notifications 列表、新建 Notification、Dead Letters、Providers
- 引入 Mock services 层（`web/lib/api/`），默认返回 mock 数据，通过环境变量 `NEXT_PUBLIC_API_BASE` 一键切换为调用真实 FastAPI 后端
- 引入 framer-motion 提供丝滑页面过渡 / 数字滚动 / staggered 列表动画
- 引入 recharts 做投递趋势 / 成功率 / 延迟分布的可视化
- 全站支持暗色 / 亮色主题切换
- 此前端**不引入**鉴权 / 多账号管理 / 服务端持久化（演示与作业场景下不需要）

## Capabilities

### New Capabilities
- `admin-console`: Web 端可视化控制台 — 仪表盘、通知管理、死信查看、Provider 健康度，统一通过 mock-or-real services 层与后端交互

### Modified Capabilities
（无；前端是新增能力，后端不变更）

## Impact

- **新增代码**：`web/` 目录（独立 Next.js 项目），与 `app/` 后端解耦
- **依赖**：Node 20+；`next@15`、`react@19`、`tailwindcss@3`、`shadcn/ui`、`framer-motion`、`recharts`、`lucide-react`、`@tanstack/react-query`、`zod`、`date-fns`
- **构建产物**：本地 `pnpm dev` / `npm run dev` 启动，端口 3000；`npm run build` 输出标准 Next.js production 构建
- **不影响**：后端 FastAPI 代码与 OpenSpec 已有 specs；前端默认使用 mock 数据，后端未跑也能完整体验 UI
- **CORS**：当切换到真实后端时，需要后端启用 CORS（已写入 design.md 备忘）
