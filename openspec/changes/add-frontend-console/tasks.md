## 1. 项目初始化

- [ ] 1.1 在仓库根 `web/` 下初始化 Next.js 15（TS + Tailwind + App Router + alias `@/*`）
- [ ] 1.2 安装 shadcn/ui 并配置（zinc 主题 / RSC 关）
- [ ] 1.3 安装依赖：framer-motion、recharts、lucide-react、@tanstack/react-query、zod、date-fns、next-themes、sonner
- [ ] 1.4 配置 Tailwind 主题 token（颜色、字体、阴影、圆角扩展）
- [ ] 1.5 引入 shadcn 基础组件：button、card、input、label、select、badge、separator、dialog、sheet、tabs、tooltip、skeleton、scroll-area、dropdown-menu、toast/sonner

## 2. 全局基础

- [ ] 2.1 `app/layout.tsx`：根布局 + 主题 Provider + React Query Provider + Toaster
- [ ] 2.2 `components/providers.tsx`：客户端 Provider 容器
- [ ] 2.3 `components/theme-toggle.tsx`：主题切换按钮（带图标动画）
- [ ] 2.4 `components/sidebar.tsx`：固定侧栏 + 路由高亮 + 折叠态
- [ ] 2.5 `components/topbar.tsx`：顶部条 + 环境标签（mock/real）+ 主题切换 + 占位头像
- [ ] 2.6 `components/page-transition.tsx`：路由切换 fade+translate 动画包装

## 3. 服务层与类型

- [ ] 3.1 `lib/types.ts`：Notification / Provider / DeadLetter / Metrics / BreakerState 等类型
- [ ] 3.2 `lib/api/mock.ts`：mock 数据生成器，含随机性 / 偶发错误 / 时序模拟
- [ ] 3.3 `lib/api/real.ts`：真实 HTTP 客户端（fetch 封装 + 错误归一化）
- [ ] 3.4 `lib/api/index.ts`：根据 `NEXT_PUBLIC_API_BASE` 选择 mock/real
- [ ] 3.5 `lib/hooks/`：useNotifications、useMetrics、useProviders、useDeadLetters、useSubmitNotification 等 React Query hooks

## 4. 共享 UI 组件

- [ ] 4.1 `components/animated-number.tsx`：数字滚动组件（基于 framer-motion useMotionValue）
- [ ] 4.2 `components/status-badge.tsx`：状态徽章（含 OPEN 脉冲动画）
- [ ] 4.3 `components/empty-state.tsx` / `components/inline-error.tsx`
- [ ] 4.4 `components/skeleton-card.tsx` / `components/skeleton-row.tsx`
- [ ] 4.5 `components/code-block.tsx`：JSON 展示（mono 字体 + 配色）
- [ ] 4.6 `components/stagger-list.tsx`：staggered fade-up 容器

## 5. Dashboard 页

- [ ] 5.1 `app/page.tsx`：四张指标卡（成功率 / In-Flight / DLQ / P95 延迟）
- [ ] 5.2 `app/_dashboard/trend-chart.tsx`：24h 投递趋势曲线（recharts AreaChart）
- [ ] 5.3 `app/_dashboard/provider-matrix.tsx`：Provider 健康矩阵
- [ ] 5.4 `app/_dashboard/activity-feed.tsx`：实时活动流（5s 轮询，新增/移除均带动画）

## 6. Notifications 列表 + 详情抽屉

- [ ] 6.1 `app/notifications/page.tsx`：列表 + 筛选条
- [ ] 6.2 `app/notifications/_components/filter-bar.tsx`：状态/Provider/时间/关键字筛选，URL 同步
- [ ] 6.3 `app/notifications/_components/notification-row.tsx`：表格行（含 staggered 入场）
- [ ] 6.4 `app/notifications/_components/detail-sheet.tsx`：右侧抽屉，含 payload / 渲染预览 / 重试时间线

## 7. 新建 Notification

- [ ] 7.1 `app/notifications/new/page.tsx`：分步表单容器（Tabs 风格步进器）
- [ ] 7.2 步骤 1：Provider 选择卡片（每张展示 method / url / 鉴权方式）
- [ ] 7.3 步骤 2：Monaco-lite JSON 编辑器（用 textarea + 简单语法高亮，避免重依赖）+ 渲染预览
- [ ] 7.4 步骤 3：Confirm 摘要卡 + 提交按钮（spinner → ✓ 动画 → toast → 跳转）

## 8. Dead Letters 页

- [ ] 8.1 `app/dead-letters/page.tsx`：列表 + provider/时间筛选
- [ ] 8.2 行展开渲染 last_error / last_response_summary / attempts 序列
- [ ] 8.3 "模拟重投"按钮（仅前端模拟 + toast）

## 9. Providers 页

- [ ] 9.1 `app/providers/page.tsx`：卡片网格
- [ ] 9.2 `_components/provider-card.tsx`：URL / method / 鉴权 / 超时 / 熔断态 / 24h 成功率小折线
- [ ] 9.3 OPEN 态倒计时秒级更新

## 10. 动画与打磨

- [ ] 10.1 路由切换：在 `<PageTransition>` 中以 AnimatePresence + motion.div 实现
- [ ] 10.2 列表 staggered：用 `<StaggerList>` 统一封装
- [ ] 10.3 Hover 微交互：卡片 -translate-y-0.5 + shadow-md
- [ ] 10.4 Focus ring：全局 `focus-visible:ring-2 ring-offset-2`
- [ ] 10.5 暗色主题下 recharts 配色二套
- [ ] 10.6 添加 favicon / 元信息 / OG 图（占位）

## 11. 文档与验证

- [ ] 11.1 `web/README.md`：启动方式 / mock/real 切换 / 截图占位
- [ ] 11.2 根 `README.md`：在"项目结构"加入 web/，"运行"章节加前端启动指引
- [ ] 11.3 跑 `npm run build` 确保无 TS / lint 错误
- [ ] 11.4 跑 `npm run dev`，逐页人工 smoke：路由切换 / 主题切换 / 表单提交 / 抽屉 / 筛选
