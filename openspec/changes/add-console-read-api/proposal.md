## Why

前端 console（`web/`）已实现 5 个页面，目前由 `lib/api/mock.ts` 提供数据，零后端依赖即可演示完整 UI。但**真实可用**需要：

1. **Notifications 列表页**需要查询接口——按 status / provider / 时间范围筛选，分页展示
2. **Dashboard 顶部 4 张卡片 + 24h 趋势图**需要 JSON 摘要接口
3. **Providers 页**需要列出当前生效的 provider 配置 + 实时熔断状态

后端目前只暴露了**写**（`POST /v1/notifications`）和**人工介入查询**（`GET /v1/dead-letters`），缺少给 console UI 用的**只读 query 接口**。本次新增一类只读 API 把"已落库的真实状态"暴露给前端。

## What Changes

- 新增 `GET /v1/notifications`：按 `status / provider / from / to / q` 筛选，offset 分页
- 新增 `GET /v1/providers`：列出当前 `providers.yaml` 加载的所有 provider，带**实时熔断态**
- 改造 `GET /metrics`：保持原 Prometheus 文本兼容；**新增** `GET /v1/metrics/summary` 输出 JSON 摘要给 dashboard
  - 字段：`successRate / inflight / dlqTotal / p95LatencyMs / trend[24h] / byProvider[]`
  - 取数策略：**实时 SQL 聚合**（GROUP BY status / provider）——重启不丢数据
  - p95 latency：MVP 阶段在 `notifications` 表加 `last_elapsed_ms` 字段持久化最近一次耗时
- 前端 `lib/api/real.ts` 已经为这些接口写好 stub，本次让真实 fetch 跑通；前端字段映射到后端响应（snake_case ↔ camelCase）
- 配置 CORS 允许本地 `http://localhost:3000` 访问

**显式不做**（且**前端同步移除假数据展示**——避免演示假瀑布流让评审困惑边界）：

| 不做的功能 | 后端 | 前端配套删除 | 理由 |
|------------|------|-------------|------|
| 详情接口 `GET /v1/notifications/{id}` | 不实现 | 删 `detail-sheet` 的"时间线" tab + `Notification.attemptHistory` 字段 + `AttemptRecord` 接口 | 列表已返回全部 ORM 字段；attempt 时间线在后端**未持久化**（design.md 决策："V1 只保留最后一次响应 + attempts 计数"），做接口也填不出真数据 |
| 事件流 `GET /v1/activity` | 不实现 | 删 `_dashboard/activity-feed.tsx` 整个组件 + dashboard 引用 + `ActivityEvent` 类型 | 派生方案看不到历史变迁；独立 `activity_logs` 表写入翻倍代价 vs dashboard 二级 UI 收益 |
| DLQ 重投 `POST /v1/dead-letters/{id}/retry` | 不实现 | 删 DLQ 页"模拟重投"按钮 + `simulateDlqRetry` stub | 危险动作，HTTP 暴露面缺权限 / 审计；倾向 CLI（init-mvp design.md Open Question 2 已裁决） |

> **诚实优先于热闹**：与其展示一个不真做事的按钮和瀑布流，不如让 UI 真实反映系统能力——这正是 PDF 评估重点 2、3（"识别并主动管理复杂度"+"对 AI 输出的判断与取舍"）的体现。

## Capabilities

### New Capabilities
- `console-read-api`：为前端 console 提供的只读查询接口集（list / providers / metrics summary）

### Modified Capabilities
- `notification-delivery`：dispatcher 投递结束后写入 `last_elapsed_ms` 字段（用于 p95 计算）

## Impact

- **新增代码**：`app/api/routes_console.py`（list / providers / summary 三个 endpoint），`app/api/schemas.py` 增 5 个响应模型
- **数据模型**：`notifications` 表加 `last_elapsed_ms: int | None` 列（向后兼容，新增允许 NULL）
- **配置**：`Settings` 增 `cors_allow_origins: list[str]`，默认 `["http://localhost:3000"]`
- **前端**：`web/lib/api/real.ts` 改为真实 fetch；新增字段映射工具（`snake_to_camel`）；`web/.env.local.example` 写入 `NEXT_PUBLIC_API_BASE=http://localhost:8000`
- **测试**：3 个新 endpoint 各加 1-2 个集成测试，保持 50+ 通过率
- **不影响**：现有 `POST /v1/notifications`、`GET /v1/dead-letters`、`GET /healthz` 接口契约
