## Context

后端 MVP 已规划完成（`init-notification-mvp`），暴露的能力是 HTTP API。但作业评审 / 运维调试场景都需要"看见"系统状态的能力。本次以一个独立的 Next.js 子项目实现可视化控制台，与后端通过 HTTP 解耦。

**约束**：
- 作业演示优先，不做 SSO / 鉴权 / 多租户
- 默认 mock 数据可独立运行，便于评审时不依赖后端环境
- 视觉上要"够看"——这是给评审者看的第一眼；动画要"够丝滑"——避免廉价感

## Goals / Non-Goals

**Goals:**
- 一条命令本地起前端，无需依赖后端即可看到全部 UI
- 5 大功能页面对应后端 5 类核心能力（提交 / 查询 / 投递追踪 / 死信 / Provider）
- 页面切换 / 数据加载 / 状态变化都有过渡动画，无突兀跳变
- 设计统一：调色板 / 圆角 / 间距 / 字体 / 阴影一套规范，整体大气而不花哨
- 服务层抽象，env 切真实 API 不需要改 UI 组件

**Non-Goals:**
- ❌ 鉴权 / 用户管理 / 权限分级
- ❌ 国际化（中文界面 + 必要英文术语足够）
- ❌ 移动端深度适配（响应式即可，但不专门做手机版）
- ❌ E2E 测试（Cypress / Playwright）— MVP 不必要
- ❌ 服务端 API Routes 转发（直接前端调后端，靠 CORS）

## Decisions

### 决策 1：Next.js 15 App Router 而非 Vite + React

**选择**：`create-next-app` + TypeScript + Tailwind + App Router。

**为什么**：
- shadcn/ui 官方首选 Next.js，新版组件直接 `npx shadcn add` 即可
- App Router 的 layout 嵌套适合"全站固定侧栏 + 主区动态切换"
- `next/font` 自带 Geist 字体，质感比 Vite 默认强
- 即使全是客户端渲染，Next 的开发体验（HMR / 错误边界 / 路由）仍优于 Vite SPA

**替代**：Vite + React Router 更轻，但 shadcn 集成步骤多、字体与构建配置都要自己写。MVP 阶段省那点启动时间不值。

### 决策 2：数据来源 = Mock-First + 环境变量切真实

**选择**：

```ts
// web/lib/api/client.ts
const BASE = process.env.NEXT_PUBLIC_API_BASE
export const api = BASE ? createRealClient(BASE) : createMockClient()
```

**为什么**：
- 评审者 clone 后 `npm i && npm run dev` 立刻看到完整 UI，零后端依赖
- 服务层接口对组件透明，UI 代码不需要写 `if (mock) ...`
- 切换真实 API 只改一个 `.env.local`

**舍**：MSW（Service Worker）拦截真实请求—— overkill；mock 数据写 JSON 文件足够。

### 决策 3：动画库 = framer-motion

**选择**：framer-motion 负责所有非平凡动画，Tailwind 的 `transition-*` 负责 hover/focus 等微交互。

**为什么**：
- React 生态最成熟、API 直观
- `AnimatePresence` 解决路由切换 / 列表元素增删的退出动画痛点
- `motion.div` 可读性高，和 Tailwind 共存友好

**关键动画清单**：
| 场景 | 动画 |
|------|------|
| 路由切换 | fade + 上移 12px，250ms |
| Dashboard 数字 | 从 0 滚动到目标值，800ms ease-out |
| 列表加载 | staggered fade-up，每项延迟 40ms |
| 详情抽屉 | 右侧滑入 + 背景模糊 |
| 状态徽章 | OPEN 熔断状态加 0.6s 脉冲 |
| 主题切换 | 全局 200ms color/background 过渡 |
| 表单提交 | 按钮 spinner + 成功 ✓ 动画 1.2s 后 toast |

### 决策 4：图表库 = recharts

**选择**：recharts 做投递趋势线 / 成功率柱状 / Provider 维度堆积柱状。

**替代**：visx（更底层）/ ECharts（更重量）/ Chart.js（DOM 不友好）。recharts 与 React 心智一致，shadcn 也提供 `Chart` 组件包装。

### 决策 5：状态管理 = React Query + URL state

**选择**：
- 服务端数据 → `@tanstack/react-query`（缓存 / 失效 / 轮询；mock 也实现成 promise，复用 hook）
- 筛选 / 分页 / Tab → URL search params（可分享、可后退）
- 全局 UI（侧栏折叠 / 主题）→ `next-themes` + 局部 zustand（如需要）

**舍**：Redux —— 这种规模没必要。

### 决策 6：信息架构 / 页面层级

```
/ (Dashboard)
├─ 概览指标（4 张大卡）  →  successRate / dlqCount / inflight / avgLatency
├─ 最近 24h 趋势曲线
├─ Provider 健康矩阵
└─ 实时活动流（最近 20 条）

/notifications              列表 + 筛选 + 详情抽屉
/notifications/new          新建（多步骤：Provider → Payload → Confirm）
/dead-letters               DLQ 列表 + 模拟重投
/providers                  Provider 配置卡片 + 熔断态
```

### 决策 7：视觉系统

- **基色**：`zinc` 中性灰为底，`emerald` 表示成功，`amber` 警告，`rose` 失败/死信，`sky` 信息
- **字体**：`Geist Sans`（Next.js 内置）+ `Geist Mono`（代码 / payload 展示）
- **圆角**：默认 `rounded-xl`，卡片之间 `gap-6`，整体留白偏大
- **阴影**：`shadow-sm` 为主，hover 时 `shadow-md` + `-translate-y-0.5`
- **暗色模式**：默认跟随系统，可手动切换

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| Mock 数据"太干净"看起来不真实 | 数据生成器引入随机性 / 偶发错误 / 突发流量峰值 |
| framer-motion 动画过密导致页面"晕" | 动画限制在过渡 / 加载 / 状态变化场景，hover 用 CSS 即可 |
| 切换真实 API 时 CORS 失败 | design.md 备忘要求后端启用 CORS（`allow_origins=["http://localhost:3000"]`） |
| Next.js 19 / React 19 与某些库不兼容 | 锁版本：next@15.x、react@19；shadcn 文档说明已兼容 |
| 暗色模式下图表配色对比度不足 | recharts 主题与 Tailwind 变量绑定，亮暗各一套 palette |

## Migration Plan

无迁移负担：新建独立子项目。

**接入真实后端步骤**：
1. 后端 FastAPI 启用 CORS：
   ```python
   app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], ...)
   ```
2. 前端 `web/.env.local` 设 `NEXT_PUBLIC_API_BASE=http://localhost:8000`
3. 重启 `npm run dev`，UI 不变，数据来自后端

## Open Questions

1. 是否需要 `/v1/notifications/{id}` 详情接口？—— 后端 spec 暂未定义；前端先用列表 row 数据 + 客户端展开
2. 是否在前端做 "重投死信" 操作？—— 倾向**只展示**，不提交动作；后端尚未提供该 endpoint，演示时用 mock 模拟即可
3. 是否需要 SSE / WebSocket 实时推送？—— V1 先 5s 轮询；如演进到大规模再换长连接
