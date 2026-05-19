## Context

业务系统当前若直接调用第三方 API，会带来三重耦合：(1) 主流程被外部 SLA 拖累；(2) 重试 / 退避 / 协议适配代码在每个业务系统重复；(3) 整体可观测性散落各处。本次改动引入一个内部"通知中转网关"，把可靠投递的复杂度收敛到单点。

**约束**：
- 作业要求 MVP 即可，目标是体现工程判断，不追求功能齐全
- 业务系统**不关心**外部 API 返回值，只要"稳定送达"
- 外部供应商的协议异构（URL/Header/Body/鉴权各不相同）
- 单人单进程演示规模（< 100 QPS）

**主要利益相关者**：
- 调用方：内部业务系统（注册 / 订阅 / 订单等）
- 被调方：第三方 SaaS（广告平台 / CRM / 库存系统）
- 运维：通过日志 / 指标 / DLQ 接口介入异常

## Goals / Non-Goals

**Goals:**
- 调用方提交通知后**立即返回 202**，不阻塞主链路
- 即使外部供应商抖动 / 短期不可用，**最终也能送达**（覆盖 ~31h 窗口）
- 同一 `Idempotency-Key` 仅入库一次，调用方重试安全
- 新增供应商不需改代码（YAML + Jinja2 模板足够）
- 失败可见、可查询、可人工介入

**Non-Goals:**
- ❌ Exactly-Once 语义（物理不可达，承认它）
- ❌ 投递回执回调给业务方（业务方已声明不关心返回值）
- ❌ 多协议投递（gRPC / Kafka 投递目标）
- ❌ 可视化模板配置后台 / 多租户配额
- ❌ 自动告警接入（PagerDuty / 飞书等）—— V2+
- ❌ 跨机房 / 高可用部署 —— 单进程足够 MVP

## Decisions

### 决策 1：投递语义 = At-Least-Once

**选择**：明确承诺"至少一次"，不假装做到 Exactly-Once。

**为什么**：跨系统场景下，外部已收到请求但响应丢失/超时是常态，调用方无法区分"未送达"与"送达但响应丢失"。强行追求 Exactly-Once 会引入两阶段提交 / 全局事务，复杂度爆炸却仍不能 100% 保证。

**替代方案**：
- *Exactly-Once*：需要外部供应商配合实现（如 dedup key 协议），不可控
- *At-Most-Once*：失败即丢，违背"稳定送达"目标

**幂等责任分两段**：
1. 调用方 → 本系统：`Idempotency-Key` + 数据库唯一索引去重
2. 本系统 → 外部供应商：在文档中**显式声明**业务方需保证下游接口幂等

### 决策 2：队列 = DB 作为队列（首版不引入 MQ）

**选择**：用 SQLite 表作 outbox，调度器轮询。

**为什么**：
- MVP 量级 < 100 QPS，DB 轮询完全够用
- 引入 Kafka / RabbitMQ = 多一个有状态依赖 + 故障域 + 运维成本
- 收单与持久化在**同一事务**内完成，天然防止"返回 202 后丢消息"
- 状态机推进就是 SQL UPDATE，调试与回放成本极低

**替代方案**：
- *Kafka / Redis Stream*：吞吐高但 MVP 用不上，且消息中间件本身的可靠性问题（消费位点 / 重平衡）会偷走时间
- *Celery + Redis*：抽象层多一层，对单机演示是过度

**演进路径**：当稳态写入 > 1k QPS 或需多消费者组，把 outbox 表替换为 Kafka topic，业务接口与状态机不变。

### 决策 3：重试策略 = 指数退避 + jitter + 上限

**选择**：退避序列 `1s, 5s, 25s, 2m, 10m, 1h, 6h, 24h`（共 8 次，覆盖 ~31h），每次 ±20% jitter。

**为什么**：
- 指数退避避免对刚恢复的供应商造成"惊群"
- jitter 打散多个 worker 的重试节拍
- 上限避免无限堆积；31h 覆盖了一个工作日 + 一晚，足够运维介入

**错误分类**：
- `5xx / 网络错误 / 超时 / 429` → 重试
- `4xx（除 429）` → 立即进 DLQ，不重试（业务错误，重试无意义）
- `DNS 解析失败 / TLS 握手失败` → 重试（视为网络抖动）

### 决策 4：熔断 = Vendor 维度的简单计数器

**选择**：每个 vendor 维护"连续失败计数 + 上次失败时间"，连续失败 ≥ 5 次进入 OPEN 态，5 分钟内不派发新单（仍接收入库）。OPEN 态结束后进入 HALF_OPEN 试探一单，成功则 CLOSED。

**为什么**：避免单一供应商挂掉拖死 worker pool；不用 Sentinel / Resilience4j 这类全功能库——`dict[str, BreakerState]` 就够。

### 决策 5：Provider 适配 = 配置驱动 + Jinja2 模板

**选择**：

```yaml
# providers.yaml
demo-crm:
  url: "https://crm.example.com/api/contacts"
  method: POST
  auth:
    type: bearer
    token_env: CRM_TOKEN
  headers:
    Content-Type: application/json
  body_template: |
    {
      "contact_id": "{{ payload.user_id }}",
      "status": "{{ payload.event }}"
    }
  timeout_ms: 5000
```

**为什么**：
- 新增供应商无需改 Python 代码
- 模板可读、易调试、可单元测试
- 比"每个 provider 一个 class"少一层抽象

**舍弃**：插件化 SPI / 动态加载——MVP 阶段是过度设计。

### 决策 6：调度器 = APScheduler 单进程

**选择**：APScheduler 的 `IntervalTrigger` 每 1s 拉一批 PENDING 单。

**为什么**：
- 比 Celery 少一层依赖（无需 Redis broker）
- 与 FastAPI 同进程内启动，演示一行命令搞定
- 多实例部署时再切换为 PostgreSQL + `FOR UPDATE SKIP LOCKED`

### 决策 7：可观测 = 结构化日志 + Prometheus 文本指标

**选择**：`structlog` 输出 JSON 日志（每条日志带 `notification_id` / `provider` / `attempt`）；`/metrics` 暴露 Prometheus 文本格式。

**为什么**：
- 90% 的排障靠日志即可串起来
- Prometheus 文本格式不需引入 SDK，最简
- 不接 OpenTelemetry / Jaeger —— 收益不抵复杂度

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| SQLite 单写者，并发写入吞吐受限 | MVP 量级足够；演进至 Postgres 时 schema 不变 |
| 单进程 worker 是单点 | 演进路径明确：水平扩展时改用 `SKIP LOCKED` |
| 模板渲染失败（如 payload 缺字段） | 渲染异常 → 直接进 DLQ + 详细日志，不重试 |
| 供应商响应慢导致 worker 堵塞 | 每次投递设置 `timeout_ms`；worker pool 限制并发 |
| 重试期间业务方下线了某通知 | MVP 不做"取消"接口；通过设置 max_attempts 自然终止 |
| 业务方未传 `Idempotency-Key` | 服务端按 `(business_id + payload_hash)` 兜底生成；记录 warning |
| 4xx vs 5xx 边界判定误差 | 4xx 默认死信；保留运维"手动重投" DLQ 的接口（V1.5） |

## Migration Plan

V1 是新建系统，无遗留迁移负担。**接入步骤**：
1. 业务方将原本直连第三方的代码改为调用 `POST /v1/notifications`
2. 在 `providers.yaml` 配置目标供应商
3. 灰度：先 1% 流量走新系统，验证投递成功率与延迟，再切全量

**回滚**：业务方保留直连旧路径开关，异常时秒级切回。

## Open Questions

1. 是否需要为业务方提供"按 idempotency_key 查询投递状态"的接口？—— 倾向不做，业务方"不关心返回值"
2. DLQ 的人工重投是 CLI 还是 HTTP？—— 倾向 CLI，安全且不暴露给业务方
3. 是否要持久化每次重试的 HTTP 响应（用于事后审计）？—— V1 只保留最后一次响应 + attempts 计数，节省存储
