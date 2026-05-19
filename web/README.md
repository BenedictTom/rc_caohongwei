# Notify Relay · Web Console

> Next.js 15 + shadcn/ui + Tailwind v4 + framer-motion + recharts。
> rc_caohongwei 项目的可视化控制台，对应 `add-frontend-console` change（capability: `admin-console`）。

## 启动

```bash
cd web
npm install        # 仅首次
npm run dev        # http://localhost:3000
```

默认 **mock 模式**：所有数据来自 `lib/api/mock.ts`，零后端依赖即可看完整 UI。
顶栏会显示 `MOCK 模式` 徽章。

切换到真实后端：

```bash
echo 'NEXT_PUBLIC_API_BASE=http://localhost:8000' > .env.local
npm run dev
```

后端需启用 CORS 允许 `http://localhost:3000`。

## 页面一览

| 路由 | 说明 |
|------|------|
| `/` | Dashboard：4 张指标卡（动画数字）、24h 趋势曲线、Provider 健康矩阵、实时活动流（5s 轮询） |
| `/notifications` | 列表 + 状态/Provider/关键字筛选（URL 同步）+ 详情抽屉（payload / 渲染预览 / 重试时间线） |
| `/notifications/new` | 三步表单：选 Provider → 编辑 payload（实时模板渲染预览）→ 确认提交 |
| `/dead-letters` | 死信队列：行内展开错误详情；模拟重投按钮 |
| `/providers` | Provider 配置卡片：URL / 鉴权 / 超时 / 熔断态（OPEN 倒计时秒级）/ 24h 成功率小图 |

## 设计要点

- **大气**：默认 zinc 中性灰底 + 语义色（emerald 成功 / amber 警告 / sky 信息 / rose 失败），Geist 字体，圆角 `rounded-xl`，hover 微交互
- **丝滑动画**：路由切换 fade+translate；指标数字从 0 滚动；列表 staggered；OPEN 状态脉冲；详情抽屉滑入 + 背景模糊
- **Mock-first**：`lib/api/index.ts` 根据 `NEXT_PUBLIC_API_BASE` 自动选 mock 或真实 client，组件代码无需改动
- **暗/亮色双主题**：next-themes 跟随系统，可手动切换；图表色阶分两套
- **键盘可达 + 骨架屏**：所有数据加载用骨架，所有交互可 Tab 聚焦

## 目录结构

```
web/
├── app/
│   ├── layout.tsx              # 根布局：Sidebar + Topbar + Providers
│   ├── page.tsx                # Dashboard
│   ├── _dashboard/             # Dashboard 子组件
│   ├── notifications/
│   │   ├── page.tsx            # 列表
│   │   ├── _components/        # FilterBar + DetailSheet
│   │   └── new/page.tsx        # 三步表单
│   ├── dead-letters/page.tsx
│   ├── providers/page.tsx
│   └── globals.css             # 主题 token + 动画
├── components/
│   ├── ui/                     # shadcn 基础组件
│   ├── providers.tsx           # ThemeProvider + QueryClient + Toaster
│   ├── sidebar.tsx · topbar.tsx · theme-toggle.tsx
│   ├── page-transition.tsx · stagger-list.tsx
│   ├── animated-number.tsx · status-badge.tsx
│   ├── code-block.tsx · empty-state.tsx · inline-error.tsx
│   ├── section.tsx · skeletons.tsx
├── lib/
│   ├── api/                    # mock + real + 自动切换
│   ├── hooks.ts                # React Query hooks
│   ├── template.ts             # 极简 Jinja 渲染（前端预览用）
│   ├── types.ts
│   └── utils.ts                # cn
└── components.json             # shadcn 配置
```

## 常用脚本

```bash
npm run dev      # 开发，含 Turbopack
npm run build    # 生产构建（已通过）
npm run start    # 本地起 production
npm run lint     # ESLint
```
