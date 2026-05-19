## ADDED Requirements

### Requirement: 全局布局与导航

控制台 SHALL 提供统一的全局布局：左侧固定侧边栏（含 Logo、5 个主导航入口）、顶部条（含主题切换 / 当前环境标签 / 账号占位）、主内容区。侧边栏在桌面端常驻展开，在窄视口（≤ 1024px）自动折叠为图标。

#### Scenario: 桌面访问首页

- **WHEN** 用户在 ≥ 1280px 视口打开 `/`
- **THEN** 左侧呈现 240px 宽的展开侧栏，5 个导航项全部可见且与当前路由高亮联动

#### Scenario: 切换主题

- **WHEN** 用户点击顶部条的主题切换按钮
- **THEN** 全局 background / surface / 文本颜色在 200ms 内平滑过渡到目标主题，无 flash 与组件错位

#### Scenario: 路由切换动画

- **WHEN** 用户从 `/` 点击进入 `/notifications`
- **THEN** 主内容区先 fade-out + 上移 12px，再以 fade-in 渲染新页面，总时长 ≤ 350ms

### Requirement: Dashboard 概览

`/` SHALL 展示 4 张关键指标卡片（成功率、In-Flight 数、DLQ 总量、平均投递耗时）、24h 投递趋势曲线、Provider 健康度矩阵、最近活动流（最多 20 条）。指标卡片的数值 MUST 使用从 0 滚动到目标值的入场动画（≤ 800ms）。

#### Scenario: 首屏加载

- **WHEN** 用户首次访问 `/`
- **THEN** 4 张指标卡先以骨架屏占位，数据到达后数字从 0 滚动至目标值，时长 600–800ms 之间

#### Scenario: Provider 健康矩阵

- **WHEN** mock 数据中存在 ≥ 2 个 provider，其中一个状态为 `OPEN`
- **THEN** 矩阵中该 provider 卡片显示橙色脉冲徽章（每 0.6s 一次缓慢呼吸效果），文本"熔断中 · 剩余 X 分钟"

#### Scenario: 实时活动流

- **WHEN** 页面停留 ≥ 5 秒
- **THEN** 顶部新增一条最新活动并以"上移 + 淡入"动画进入；底部最早一条以"下沉 + 淡出"动画移除

### Requirement: Notifications 列表与详情

`/notifications` SHALL 提供分页列表，列：`ID`、`Provider`、`Status`、`Attempts`、`Created`、`Last Error`。SHALL 提供按 `provider` / `status` / 时间范围 / 关键字筛选，筛选条件 MUST 持久化到 URL 查询串。点击行 MUST 弹出右侧详情抽屉，展示完整 payload、HTTP 请求渲染结果、每次重试的时间线。

#### Scenario: 状态筛选

- **WHEN** 用户点击 `状态: DEAD_LETTER` 筛选
- **THEN** URL 更新为 `?status=DEAD_LETTER`，列表重新渲染只含死信记录，列表项以 staggered（每项 40ms 延迟）淡入

#### Scenario: 打开详情抽屉

- **WHEN** 用户点击列表中某行
- **THEN** 右侧抽屉以 250ms 滑入，主区背景应用 `backdrop-blur-sm`；ESC 或点击遮罩可关闭

#### Scenario: 重试时间线

- **WHEN** 详情抽屉打开一条 `attempts >= 2` 的记录
- **THEN** 抽屉中渲染一条垂直时间线，每个节点显示尝试序号 / 时间戳 / 状态码 / 错误摘要，节点以 staggered 动画依次浮现

### Requirement: 新建 Notification 表单

`/notifications/new` SHALL 提供分步表单：(1) 选择 provider；(2) 编辑 payload（含与 provider body_template 的预览联动）；(3) 确认与提交。提交 MUST 调用 services 层 `submitNotification`，成功后 toast 提示并跳转列表。

#### Scenario: Provider 选择联动

- **WHEN** 用户在第一步选择 `demo-crm`
- **THEN** 第二步右侧出现该 provider 的"必填字段"提示与渲染预览（用当前编辑中的 payload 实时渲染 body_template）

#### Scenario: 提交成功

- **WHEN** 用户在第三步点击"提交"
- **THEN** 按钮显示 spinner，成功后变为绿色 ✓ 1 秒；显示 toast `已受理 · ntf_xxx`，1.2s 后跳转 `/notifications` 并将该新通知高亮 2 秒

#### Scenario: 提交失败

- **WHEN** services 层抛出错误
- **THEN** 按钮回到可点击态；表单顶部出现 inline 错误提示卡片，详细错误展示在折叠面板中

#### Scenario: payload 校验

- **WHEN** 用户输入的 JSON 不合法
- **THEN** 编辑器下方红色文字给出具体行号与原因；"下一步"按钮禁用

### Requirement: Dead Letters 视图

`/dead-letters` SHALL 列出所有 `status=DEAD_LETTER` 的记录，支持按 provider 与时间筛选。每条记录可展开查看 `last_error` 与最后响应摘要。MAY 提供"模拟重投"按钮——MVP 阶段仅在前端模拟（不真实写后端）并以 toast 提示"已模拟，需后端支持"。

#### Scenario: 死信筛选

- **WHEN** 用户选择 `provider=demo-crm` 且 `时间=最近 7 天`
- **THEN** 列表只显示符合条件的死信记录，并在顶部展示"共 N 条 · 跨 M 个 provider"摘要

#### Scenario: 展开错误详情

- **WHEN** 用户点击某条死信的"展开"
- **THEN** 该行下方以 200ms 高度过渡展开错误详情区，包含 `last_error` 全文、`last_response_summary`、`attempts` 时间序列

### Requirement: Providers 视图

`/providers` SHALL 展示从 `providers.yaml` 解析的全部 provider，每个 provider 显示卡片：URL / method / 鉴权方式 / 超时 / 当前熔断态 / 近 24h 投递成功率小折线图。卡片 MUST 区分 `CLOSED` / `HALF_OPEN` / `OPEN` 三态视觉。

#### Scenario: 健康 provider

- **WHEN** 某 provider 当前 `CLOSED`
- **THEN** 卡片左侧 4px 绿色边、状态徽章 `运行中`、折线图为 emerald 色

#### Scenario: 熔断中 provider

- **WHEN** 某 provider 当前 `OPEN`
- **THEN** 卡片左侧 4px 橙色边、徽章 `熔断中` 带脉冲、显示"剩余 X 分钟自动恢复"倒计时（每秒更新）

### Requirement: Mock-or-Real Services 层

控制台 SHALL 通过统一的 `lib/api/` 服务层访问数据。当环境变量 `NEXT_PUBLIC_API_BASE` 未设置时，服务层 MUST 返回 mock 数据；设置后 MUST 转发到真实后端。组件代码 MUST NOT 直接构造 `fetch` 调用。

#### Scenario: 默认 mock 模式

- **WHEN** 用户在未设 `NEXT_PUBLIC_API_BASE` 的情况下运行 `npm run dev`
- **THEN** 全部页面均能正常展示 mock 数据，控制台输出 `[api] mock mode` 一次性提示

#### Scenario: 切换真实后端

- **WHEN** 用户在 `.env.local` 设置 `NEXT_PUBLIC_API_BASE=http://localhost:8000` 并重启
- **THEN** 服务层全部方法转为对该 base URL 的真实 HTTP 调用，UI 组件无需修改

### Requirement: 错误与加载态

所有数据加载 MUST 使用骨架屏（不使用整页 spinner）；所有失败 MUST 在对应区域内联展示，并提供"重试"按钮；不得出现整页报错或空白。

#### Scenario: 数据加载中

- **WHEN** 任意页面首次加载数据
- **THEN** 对应区域以贴近最终布局的骨架元素（同尺寸灰块）占位，不抖动

#### Scenario: 数据加载失败

- **WHEN** 服务层抛出错误
- **THEN** 该区域显示 inline 错误卡（图标 + 简短文案 + Retry 按钮），点击 Retry 重新触发加载并恢复骨架屏

### Requirement: 主题与可访问性

控制台 SHALL 支持暗色 / 亮色双主题，默认跟随系统偏好。色彩对比度在两套主题下都 MUST 满足 WCAG AA（正文 4.5:1，大字 3:1）。所有交互元素 MUST 可键盘聚焦并有可见 focus ring。

#### Scenario: 跟随系统主题

- **WHEN** 用户操作系统设置为深色
- **THEN** 首次访问时控制台默认采用暗色主题

#### Scenario: 键盘导航

- **WHEN** 用户用 `Tab` 键穿越主导航
- **THEN** 每个可聚焦元素显示明显 focus ring（≥ 2px outline，对比度满足 AA）
