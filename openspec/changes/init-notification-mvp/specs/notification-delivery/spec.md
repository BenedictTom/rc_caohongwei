## ADDED Requirements

### Requirement: 异步可靠投递

系统 SHALL 提供后台调度器，周期性扫描 `notifications` 表中 `status=PENDING` 且 `next_retry_at <= now()` 的记录，按配置投递到目标供应商。投递语义 MUST 为 **At-Least-Once**（至少一次）。

#### Scenario: 派发待发通知

- **WHEN** 数据库中存在一条 `status=PENDING, next_retry_at=now()-1s` 的记录
- **THEN** 调度器在下一个轮询周期（≤ 2s）内将其状态改为 `IN_FLIGHT`，并发起 HTTP 请求到目标供应商

#### Scenario: 投递成功

- **WHEN** 外部供应商返回 `2xx` 响应
- **THEN** 系统将记录状态更新为 `SUCCEEDED`，记录 `delivered_at` 时间戳与最终响应摘要

### Requirement: Provider 协议适配

系统 SHALL 通过 `providers.yaml` 配置文件描述每个供应商的 URL、HTTP 方法、Header、Body 模板、鉴权方式与超时。Body 模板 MUST 使用 Jinja2 语法，可访问 `payload` 上下文变量。新增供应商 MUST NOT 需要修改 Python 代码。

#### Scenario: 渲染并发送请求

- **WHEN** 一条 `provider=demo-crm` 的通知被派发
- **THEN** 系统从 `providers.yaml` 读取 `demo-crm` 配置，使用 Jinja2 渲染 body 模板（注入 `payload`），按配置的 method/header/url 发起 HTTP 请求

#### Scenario: 模板渲染失败

- **WHEN** body 模板引用了 `payload` 中不存在的字段
- **THEN** 系统将该通知标记为 `DEAD_LETTER`，错误原因为 `"template render error: <details>"`，不进行重试

#### Scenario: 配置中的 token_env 环境变量未设置

- **WHEN** Provider 配置声明 `auth.token_env: CRM_TOKEN` 但环境中无该变量
- **THEN** 系统在启动时拒绝加载该 provider 配置，启动失败并输出明确错误信息

### Requirement: 错误分类与重试

系统 SHALL 按下表对投递失败进行分类处理：

| 错误类型 | 行为 |
|---------|------|
| `5xx` | 重试 |
| `4xx` 且非 `429` | 立即进死信 |
| `429 Too Many Requests` | 重试（视为限流） |
| 网络错误 / TCP RST / DNS 失败 | 重试 |
| TLS 握手失败 | 重试 |
| HTTP 超时（> `timeout_ms`） | 重试 |
| Body 模板渲染异常 | 立即进死信 |

#### Scenario: 5xx 触发重试

- **WHEN** 外部供应商返回 `503 Service Unavailable`
- **THEN** 系统将记录状态置为 `PENDING`，`attempts += 1`，`next_retry_at` 按退避序列计算

#### Scenario: 400 Bad Request 立即死信

- **WHEN** 外部供应商返回 `400 Bad Request`
- **THEN** 系统将记录状态置为 `DEAD_LETTER`，`attempts += 1`，**不**安排重试

#### Scenario: 429 视为可重试

- **WHEN** 外部供应商返回 `429 Too Many Requests`
- **THEN** 系统按退避序列重试，且 next_retry_at 至少为 60s 之后（避免立即再触发限流）

### Requirement: 指数退避与最大重试次数

重试退避序列 SHALL 为 `1s, 5s, 25s, 2m, 10m, 1h, 6h, 24h`（共 8 次），每次实际间隔 MUST 叠加 ±20% 随机 jitter。当 `attempts` 达到 8 次仍失败，系统 MUST 将记录置为 `DEAD_LETTER`。

#### Scenario: 第 3 次失败后的下次重试时间

- **WHEN** 一条通知第 3 次投递失败（attempts=3）
- **THEN** `next_retry_at = now + 25s × (1 ± 0.2)`

#### Scenario: 达到最大重试次数

- **WHEN** 一条通知 `attempts=8` 仍失败
- **THEN** 状态置为 `DEAD_LETTER`，记录到死信表并暴露 `dlq_total` 指标 +1

### Requirement: Vendor 维度熔断

系统 SHALL 为每个 provider 维护熔断状态。当某 provider 连续失败 ≥ **5 次**时进入 `OPEN` 态，**5 分钟**内不再向该 provider 派发新单（已入库的记录保持 `PENDING` 等待）。`OPEN` 期满后进入 `HALF_OPEN` 态，放行一单试探：成功则回到 `CLOSED`，失败则重新 `OPEN`。

#### Scenario: 触发熔断

- **WHEN** `provider=demo-crm` 在最近窗口内连续 5 次投递失败
- **THEN** 该 provider 状态变为 `OPEN`，调度器在接下来 5 分钟内**跳过**所有 `provider=demo-crm` 的待发记录

#### Scenario: 熔断期间新单仍可入库

- **WHEN** 熔断状态为 `OPEN` 期间，业务方提交新通知到该 provider
- **THEN** 入库 API 仍返回 `202 Accepted`；记录状态为 `PENDING`，等熔断恢复后再被派发

#### Scenario: 半开态试探

- **WHEN** 熔断 `OPEN` 已满 5 分钟
- **THEN** 状态变为 `HALF_OPEN`，调度器放行**一单**到该 provider；该单成功则状态变为 `CLOSED`，失败则重新进入 `OPEN`

### Requirement: 死信查询

系统 SHALL 提供 `GET /v1/dead-letters` 接口，支持按 `provider`、时间范围分页查询死信记录，用于人工介入。响应中 MUST 包含失败原因、最后一次响应摘要、`attempts` 计数。

#### Scenario: 查询某 provider 的死信

- **WHEN** 运维调用 `GET /v1/dead-letters?provider=demo-crm&limit=20`
- **THEN** 系统返回该 provider 最近的 20 条死信记录，每条包含 `id`/`payload`/`last_error`/`attempts`/`failed_at`

### Requirement: 投递并发控制

系统 SHALL 限制单进程内并发投递数为可配置值（默认 32），防止单一供应商响应慢拖死整个 worker。每次 HTTP 请求 MUST 设置由 provider 配置指定的超时（默认 5s）。

#### Scenario: 达到并发上限

- **WHEN** 当前 in-flight 投递数已达上限 32
- **THEN** 调度器**不**派发新单，等待已有投递完成；本周期跳过

### Requirement: 可观测性

系统 SHALL 输出结构化 JSON 日志，每条日志 MUST 至少包含 `notification_id`、`provider`、`attempt`、`status`、`elapsed_ms` 字段。系统 SHALL 暴露 `GET /metrics`（Prometheus 文本格式），至少包含：

- `notifications_received_total{provider}`：counter
- `notifications_delivered_total{provider, status}`：counter
- `notification_delivery_duration_seconds{provider}`：histogram
- `notifications_dlq_total{provider}`：counter
- `circuit_breaker_state{provider}`：gauge（0=closed, 1=half_open, 2=open）

#### Scenario: 一次投递失败的日志

- **WHEN** 一条通知第 2 次投递失败（5xx）
- **THEN** 日志输出至少包含：`notification_id`、`provider`、`attempt=2`、`status=PENDING`、`error=upstream_5xx`、`elapsed_ms=<n>`、`next_retry_at=<ts>`

#### Scenario: 抓取 metrics

- **WHEN** Prometheus 抓取 `GET /metrics`
- **THEN** 响应是合法的 Prometheus 文本格式，包含上述全部 metric 名
