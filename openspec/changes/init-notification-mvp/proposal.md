## Why

企业内部多个业务系统需要在关键事件后调用第三方 HTTP(S) API 进行通知（注册→广告系统、订阅成功→CRM、下单→库存）。当前若由各业务方自行调用，会出现两个问题：(1) 外部系统的不可用会反向影响主链路；(2) 每个业务方都要重复实现"重试 / 退避 / 协议适配"。需要一个统一的通知中转服务，把可靠投递的复杂度收敛到一处，让业务系统"提交即返回"。

## What Changes

- 新增内部服务 `rc_caohongwei`，对内提供 `POST /v1/notifications` 收单接口，对外按配置投递到多家供应商
- 投递语义明确为 **At-Least-Once**；调用方通过 `Idempotency-Key` 实现入站去重；外部供应商需自行保证下游接口幂等
- 实现持久化 outbox 模式：收单后立即落库返回 202，由后台调度器轮询、投递、按状态机推进
- 重试策略：指数退避 + jitter，最多 8 次，覆盖 ~31h 窗口；超出后进入死信
- 失败处理：4xx（除 429）立即死信；5xx / 429 / 网络错误 / 超时 → 重试；同一 vendor 连续失败触发熔断
- Provider 适配：通过 `providers.yaml` 声明 URL / method / header / body 模板（Jinja2）/ 鉴权方式，新增供应商不需改代码
- 暴露 Prometheus 文本格式指标与结构化 JSON 日志

## Capabilities

### New Capabilities
- `notification-intake`: HTTP 收单接口、幂等校验、持久化、立即返回 202 Accepted
- `notification-delivery`: outbox 轮询、Provider 适配与渲染、HTTP 投递、重试 / 熔断 / 死信状态机

### Modified Capabilities
（首版无既有 spec，留空）

## Impact

- **新增代码**：`app/api/`（FastAPI 路由）、`app/delivery/`（worker/调度/适配/熔断）、`app/models/`（ORM）、`app/core/`（配置/日志/DB）
- **数据模型**：新增 `notifications` 表（带 `idempotency_key` 唯一索引、`status` / `attempts` / `next_retry_at` 字段）；新增 `dead_letters` 表用于人工介入查询
- **依赖**：FastAPI、SQLAlchemy、APScheduler、httpx、Jinja2、structlog、pydantic-settings
- **基础设施**：MVP 阶段使用 SQLite（单文件，便于演示与测试）；演进至生产时切换 PostgreSQL，DB Schema 不变
- **运维**：单进程启动 API + Worker；后续可拆分为独立进程 / 容器
- **不影响**：业务系统现有接口契约（业务方仅需调用本服务一个接口替代直连第三方）
