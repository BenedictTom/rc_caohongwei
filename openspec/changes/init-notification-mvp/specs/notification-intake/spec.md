## ADDED Requirements

### Requirement: 提交通知接口

系统 SHALL 提供 `POST /v1/notifications` 接口供内部业务系统提交通知请求。接口 MUST 在通知**已落库**后立即返回 `202 Accepted`，并返回服务端生成的 `notification_id`。接口 MUST NOT 在响应中等待外部供应商的实际投递结果。

#### Scenario: 成功提交一条通知

- **WHEN** 业务系统发送 `POST /v1/notifications`，请求体包含合法的 `provider` 与 `payload`
- **THEN** 系统在 `notifications` 表写入一行 `status=PENDING` 的记录，并返回 `202 Accepted`，响应体包含 `{"id": "ntf_<uuid>", "status": "PENDING"}`

#### Scenario: 缺少必填字段

- **WHEN** 请求体缺少 `provider` 或 `payload` 字段
- **THEN** 系统返回 `400 Bad Request`，响应体包含错误说明，且不在数据库写入任何记录

#### Scenario: provider 名称在配置中不存在

- **WHEN** 请求中的 `provider` 在 `providers.yaml` 中未定义
- **THEN** 系统返回 `400 Bad Request`，错误信息为 `"unknown provider: <name>"`，不入库

### Requirement: 幂等键去重

系统 SHALL 支持调用方通过 `Idempotency-Key` HTTP Header 提交幂等键。对于相同 `Idempotency-Key` 的重复请求，系统 MUST 返回首次提交时的 `notification_id`，且 MUST NOT 创建新的记录。幂等键的有效期 MUST 至少为 24 小时。

#### Scenario: 首次提交带幂等键

- **WHEN** 业务系统首次提交请求并携带 `Idempotency-Key: abc-123`
- **THEN** 系统正常落库并返回 `202 Accepted`，记录该 `idempotency_key` 与新生成的 `notification_id` 的映射

#### Scenario: 相同幂等键重复提交

- **WHEN** 业务系统在 24 小时内再次提交完全相同 `Idempotency-Key: abc-123` 的请求
- **THEN** 系统返回 `202 Accepted`，响应体中的 `notification_id` 与首次提交时**相同**，且数据库中只有一条记录

#### Scenario: 未携带幂等键

- **WHEN** 业务系统未携带 `Idempotency-Key` Header
- **THEN** 系统按 `(provider, sha256(payload))` 计算兜底幂等键，并在响应日志中记录 `warning: idempotency_key auto-generated`

### Requirement: 持久化优先于响应

系统 MUST 在数据库事务**提交完成**后再返回 `202`。如果数据库写入失败，系统 MUST 返回 `5xx` 错误，让调用方重试。

#### Scenario: 数据库写入成功

- **WHEN** 落库事务成功提交
- **THEN** 系统才向调用方返回 `202 Accepted`

#### Scenario: 数据库写入失败

- **WHEN** 数据库连接异常或落库事务回滚
- **THEN** 系统返回 `503 Service Unavailable`，由调用方依据自身策略重试；本服务不假装成功

### Requirement: 请求大小限制

系统 SHALL 限制 `payload` 字段的最大序列化字节数为 **64 KB**，超过限制 MUST 返回 `413 Payload Too Large`。

#### Scenario: payload 超过 64KB

- **WHEN** 业务系统提交的 `payload` 序列化后 > 64 KB
- **THEN** 系统返回 `413 Payload Too Large`，且不入库

### Requirement: 健康检查接口

系统 SHALL 提供 `GET /healthz` 接口，用于运维探活。接口 MUST 在数据库可达且调度器在线时返回 `200 OK`。

#### Scenario: 系统健康

- **WHEN** 调用 `GET /healthz` 且数据库可读 + 调度器线程存活
- **THEN** 返回 `200 OK`，响应体为 `{"status": "ok"}`

#### Scenario: 系统不健康

- **WHEN** 数据库不可达或调度器线程已退出
- **THEN** 返回 `503 Service Unavailable`，响应体包含具体不健康的子系统名
