## ADDED Requirements

### Requirement: 通知列表查询接口

系统 SHALL 提供 `GET /v1/notifications` 接口，按 `status / provider / from / to / q` 过滤，offset 分页返回通知列表。响应字段 MUST 与 `web/lib/types.ts` 的 `Notification` 类型契合（snake_case，前端做映射）。

#### Scenario: 默认查询返回最近通知

- **WHEN** 调用 `GET /v1/notifications`（无参数）
- **THEN** 返回 `200 OK`，响应包含 `items / total / limit / offset` 字段，按 `created_at DESC` 排序，默认 `limit=50`、`offset=0`

#### Scenario: 按状态过滤

- **WHEN** 调用 `GET /v1/notifications?status=DEAD_LETTER`
- **THEN** `items` 中所有记录的 `status` 字段均为 `DEAD_LETTER`，`total` 为该状态记录的总数

#### Scenario: 按 provider + 时间范围过滤

- **WHEN** 调用 `GET /v1/notifications?provider=demo-crm&from=2026-05-18T00:00:00Z&to=2026-05-19T00:00:00Z`
- **THEN** 返回的 items 全部满足 `provider=demo-crm` 且 `created_at` 在指定窗口内

#### Scenario: q 参数前缀匹配

- **WHEN** 调用 `GET /v1/notifications?q=ntf_abc`
- **THEN** 返回的 items 必须满足 `id LIKE 'ntf_abc%' OR idempotency_key LIKE 'ntf_abc%'`

#### Scenario: 分页越界

- **WHEN** 调用 `GET /v1/notifications?offset=99999`
- **THEN** 返回 `200 OK`，`items: []`，`total` 仍是真实总数

### Requirement: Provider 列表与熔断态

系统 SHALL 提供 `GET /v1/providers` 接口，返回当前 `providers.yaml` 加载的所有 provider，每条记录 MUST 包含静态配置（`name / url / method / timeout_ms / headers / body_template / auth.type / auth.token_env`）和**实时**熔断态（`breaker / breaker_cooldown_seconds`）。

#### Scenario: 列出 provider

- **WHEN** 调用 `GET /v1/providers`
- **THEN** 返回 `200 OK`，items 长度等于 `providers.yaml` 中定义的条目数

#### Scenario: 含熔断态

- **WHEN** demo-crm 处于 OPEN 态、剩余 240 秒
- **THEN** 该 provider 的 `breaker` 字段为 `"OPEN"`，`breaker_cooldown_seconds` 约为 `240`（允许 ±5 秒误差）

#### Scenario: CLOSED 态时 cooldown 为 null

- **WHEN** demo-crm 处于 CLOSED 态
- **THEN** `breaker` 为 `"CLOSED"`，`breaker_cooldown_seconds` 字段为 `null`

#### Scenario: 鉴权 token 不外泄

- **WHEN** provider 配置 `auth.type=bearer, token_env=CRM_TOKEN`
- **THEN** 响应中只暴露 `auth.type` 与 `auth.token_env` 字段，**不**包含 token 本身的值

### Requirement: Dashboard 摘要接口

系统 SHALL 提供 `GET /v1/metrics/summary` 接口，返回 dashboard 顶部 4 张卡片 + 24h 趋势图所需的 JSON。响应字段集合 MUST 包含：

- `success_rate`：最近 24h 成功率（0–1）；分母 = SUCCEEDED + DEAD_LETTER
- `inflight`：当前 status ∈ {PENDING, IN_FLIGHT} 的记录数
- `dlq_total`：累计 status=DEAD_LETTER 的记录数
- `p95_latency_ms`：最近 24h `last_elapsed_ms` 的 p95（仅 SUCCEEDED 或最终 DEAD_LETTER 计入）
- `trend`：近 24 小时按 1 小时桶聚合的 `[{t, succeeded, failed, inflight}]` 数组（24 项）
- `by_provider`：每个 provider 的累计 `{provider, succeeded, failed, dlq}`

#### Scenario: 默认窗口 24h

- **WHEN** 调用 `GET /v1/metrics/summary`
- **THEN** 返回 `200 OK`，包含上述全部字段；`trend` 长度恰好 24

#### Scenario: 无数据时

- **WHEN** 数据库中尚无 notifications 记录
- **THEN** 返回 `success_rate=0.0`、`inflight=0`、`dlq_total=0`、`p95_latency_ms=0`、`trend` 含 24 个全零桶、`by_provider=[]`

#### Scenario: p95 仅计入有耗时的记录

- **WHEN** 数据库中存在 100 条投递成功的记录（每条均填了 `last_elapsed_ms`）和 50 条 PENDING 记录（`last_elapsed_ms IS NULL`）
- **THEN** `p95_latency_ms` 仅基于 100 条 SUCCEEDED 计算

### Requirement: Dispatcher 持久化最近一次耗时

`notification-delivery` capability 的 dispatcher 在每次投递结束（成功 / 失败 / 重新调度）后，MUST 将本次 HTTP 调用的实际耗时（毫秒，整数四舍五入）写入 `notifications.last_elapsed_ms` 字段。模板渲染失败 / 未知 provider 等"未发起 HTTP 请求"的场景 MUST NOT 写该字段（保持为 NULL 或保留前值）。

#### Scenario: 投递成功后落库耗时

- **WHEN** 一条通知投递成功，HTTP 实际耗时 312ms
- **THEN** 该 notification 记录的 `last_elapsed_ms = 312`

#### Scenario: 模板渲染失败不写耗时

- **WHEN** 一条通知因 payload 缺字段进入 DLQ（未发起 HTTP）
- **THEN** 该 notification 记录的 `last_elapsed_ms` 保持 `NULL`

### Requirement: CORS 配置

系统 SHALL 通过 `Settings.cors_allow_origins` 配置允许的前端 origin，默认值 MUST 为 `["http://localhost:3000"]`。FastAPI `CORSMiddleware` MUST 在创建 app 时装入；启动日志 MUST 打印当前 allowlist。

#### Scenario: 默认放通本地前端

- **WHEN** 前端从 `http://localhost:3000` 调用 `GET /v1/notifications`
- **THEN** 浏览器 preflight `OPTIONS` 返回 `200`，响应头含 `Access-Control-Allow-Origin: http://localhost:3000`

#### Scenario: 未配置 origin 拒绝

- **WHEN** 前端从 `http://other.example.com` 调用接口
- **THEN** preflight 不返回 `Access-Control-Allow-Origin` 头部，浏览器拦截请求

#### Scenario: 通过环境变量覆盖

- **WHEN** 启动前设置 `APP_CORS_ALLOW_ORIGINS='["https://console.example.com"]'`
- **THEN** 启动日志 `cors_allowlist` 字段输出 `["https://console.example.com"]`，且该 origin 的请求被放通
