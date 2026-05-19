## Context

后端 MVP 已完成（`POST /v1/notifications` / `GET /v1/dead-letters` / `GET /healthz` / `GET /metrics`）。前端 console 已用 mock 实现完整 UI，但要真正"演示"必须切到真实数据。

**约束**：
- 后端只读 query 不应阻塞 worker 派发链路（投递吞吐优先级 > 查询性能）
- 前端 5 个页面 + 60+ 处 mock 调用，**不希望大改组件代码**——尽量在 `lib/api/real.ts` 内做字段映射
- 后端模型字段是 snake_case，前端类型定义是 camelCase（参考 `web/lib/types.ts` 已确定）
- MVP 量级 < 100 QPS、< 10K 行数据，SQLite GROUP BY 性能不是瓶颈

**主要利益相关者**：
- 评审者：`npm run dev` + `uvicorn` 双开就能看到完整真实数据流
- 后端：保持核心投递路径不变
- 前端：组件代码零修改，只在 API 客户端层做转换

## Goals / Non-Goals

**Goals:**
- 前端切到 `NEXT_PUBLIC_API_BASE=http://localhost:8000` 后，**Notifications / Providers / Dashboard** 三个页面看到真实数据
- 字段映射在单点（`real.ts`）完成；组件代码零改动
- 新增字段 `last_elapsed_ms` 不破坏既有 ORM / 测试
- p95 latency 真实可计算（不是 0 占位）
- CORS 配置不让生产环境裸奔（默认仅本地）

**Non-Goals:**
- ❌ 实时推送（WebSocket / SSE）—— Dashboard 用 SWR 5s 轮询足够
- ❌ 复杂查询语法（DSL / 全文检索）—— `q` 参数仅做 idempotency_key / id 前缀匹配
- ❌ 详情页接口 / 事件流 / 重投 —— 见 proposal 不做清单
- ❌ 跨域生产配置 —— MVP 默认仅 localhost；生产部署时通过环境变量覆盖

## Decisions

### 决策 1：取数策略 = 实时 SQL 聚合

**选择**：`metrics/summary` 全部通过 `SELECT ... GROUP BY` 实时算。

**为什么**：
- MVP 数据量 << 万行，SQLite GROUP BY < 10ms
- 重启不丢数据，相比"内存 counter"更可靠
- 前端 5s 轮询带来的负载可忽略
- 写实现就 ~50 行 SQL，不需要单独维护"汇总表"

**替代方案**：
- *预聚合表*（按小时桶物化）：吞吐起来后再做，YAGNI
- *从 Prometheus counter 读*：重启清零，p95 也无法从 counter 反推

### 决策 2：p95 latency 持久化 = 字段，不是直方图表

**选择**：在 `notifications` 表加 `last_elapsed_ms: int | None`，dispatcher 在 `_persist_*` 时一并写入。

**为什么**：
- p95 计算就是 `SELECT ... ORDER BY last_elapsed_ms DESC LIMIT k` —— 一行 SQL
- 不引入 histogram 桶表
- "最后一次"的耗时对 dashboard 展示已足够；如果一条多次重试，反映的是最近一次表现——这就是 dashboard 想看的

**替代方案**：
- *延迟直方图表（attempt_log）*：精度高但 schema 翻倍，MVP 过度
- *从 Prometheus histogram 反推*：重启丢、且要 scrape

### 决策 3：字段映射 = 客户端 snake → camel 单点转换

**选择**：所有后端响应保持 snake_case；`web/lib/api/real.ts` 内一个 `snakeToCamel<T>()` 工具递归转 key。

**为什么**：
- 后端 Python 习惯 snake_case；前端 TS 习惯 camelCase；双方各自舒服
- 转换在 API 层一次性做，组件代码零感知
- 后端响应 schema 在 OpenAPI 自动文档里更标准（FastAPI 直接用字段名）

**替代方案**：
- *后端 alias 改 camelCase*：FastAPI/Pydantic 支持但全局加 alias 配置侵入大
- *前端类型改 snake_case*：组件代码全改，影响面最大

### 决策 4：CORS = 配置驱动 + 默认只允许 localhost

**选择**：`Settings.cors_allow_origins: list[str] = ["http://localhost:3000"]`；`main.py` 装 FastAPI `CORSMiddleware`。

**为什么**：
- 默认安全（不裸奔）
- 部署时通过 `APP_CORS_ALLOW_ORIGINS=https://console.example.com` 覆盖
- pydantic-settings 的 list 类型直接用 JSON 字符串解析

### 决策 5：分页 = offset 简单分页（不做 cursor）

**选择**：`limit + offset`，响应携带 `total / limit / offset`。

**为什么**：
- 前端表格组件已经按这种 shape 设计
- MVP 数据量 << 1 万行，深翻页性能不是问题
- cursor 分页要求 `next_retry_at + id` 复合排序锁，复杂度不抵收益

**演进路径**：单表破 100K 行后，再换 keyset/cursor 分页；接口字段只需补 `next_cursor`，前端兼容。

### 决策 6：providers 列表 = 静态配置 + 实时熔断态合并

**选择**：response 中既包含 `providers.yaml` 加载的静态字段（url/method/headers/timeout），也包含**实时**熔断态（`breaker: CLOSED/OPEN/HALF_OPEN`）+ `breakerCooldownSeconds`。

**为什么**：
- providers 页的核心价值是"看哪个 provider 在熔断"，没熔断态等于一张废纸
- 熔断状态从 `get_breaker().snapshot()` 读，~5 行代码
- 不持久化历史成功率（前端类型有 `successRateSeries` 字段）—— 用 SQL 按小时桶聚合，与 dashboard trend 同源逻辑

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| `metrics/summary` 实时 SQL 在大数据量下变慢 | 加索引 `(status, created_at)`；超过阈值后切预聚合表 |
| `last_elapsed_ms` 是 nullable 列，老记录为 NULL | p95 SQL 用 `WHERE last_elapsed_ms IS NOT NULL`；前端兼容 NULL |
| 字段映射递归转换性能 | MVP 响应 < 100 行，递归 O(n) 可忽略；profile 后再优化 |
| CORS 配错导致前端拿不到响应 | 默认值已含 localhost:3000；启动日志打印 CORS allowlist 让 misconfiguration 立刻可见 |
| 前端切真后端后 mock 模式失效 | `lib/api/index.ts` 已有 `apiMode` 切换；保留 mock 作为 fallback |

## Migration Plan

V1 已在跑，本次纯加法（新 endpoint + 新字段 + 新中间件）：

1. 后端先实现 + 测试通过 + `uvicorn` 起来 cURL 验证 3 个 endpoint
2. 前端 `lib/api/real.ts` 替换 stub 为真 fetch + 字段映射
3. 前端 `web/.env.local` 配 `NEXT_PUBLIC_API_BASE`，`npm run dev` 验证 3 页
4. 保留 mock 作为离线演示模式（不删 `mock.ts`）

**回滚**：前端 `unset NEXT_PUBLIC_API_BASE` 即回到 mock；后端新 endpoint 移除不影响既有调用方。

## Open Questions

1. **`q` 参数的语义**：当前定义为"id / idempotency_key 前缀匹配"。如果将来要按 payload 内容搜，需要全文索引——但 MVP 不做。
2. **trend 的时间桶**：固定 24 桶（1h 一桶）还是按窗口动态？前端类型只要 `{t, succeeded, failed, inflight}` 数组，本次实现取**当前时刻往前 24 小时、每小时 1 桶 = 24 个点**。
3. **breakerCooldownSeconds 的精度**：当前从 `_VendorState.opened_at` 与 `open_duration` 计算；HALF_OPEN 态时显示 0；CLOSED 态显示 null。
