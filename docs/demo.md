# Demo：四个核心场景的 curl 演示

仓库默认配置已经能在本机跑通完整链路，**不需要任何外部 token / 联网**。三个 demo provider 在 `providers.yaml` 里都指向 `127.0.0.1:8500/<name>` 的本地 mock。

## 0. 准备

打开三个终端：

```bash
# T1: 本地 mock provider（fail-rate 注入 5xx / 超时让链路有"非全绿"样本）
uv run python tools/mock_provider.py --port 8500 --fail-rate 0.15

# T2: 后端
uv run uvicorn app.main:app --port 8000

# T3 (可选): 前端
cd web && NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

启动后端时应看到：

```
{"event": "providers_loaded", "providers": ["demo-crm", "demo-ad-network", "demo-inventory"], ...}
{"event": "worker_started", "interval": 1.0, ...}
```

> Tip：如果想纯走"全部失败 → DLQ"的路径，把 mock 启动参数改 `--fail-rate 1.0` 即可，无需改 `providers.yaml`。

---

## 场景 1：成功投递

```bash
curl -i -X POST http://localhost:8000/v1/notifications \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-success-001" \
  -d '{
    "provider": "demo-crm",
    "payload": {"user_id": 42, "event": "subscription.paid", "metadata": {"plan": "pro"}}
  }'
# → HTTP/1.1 202 Accepted
# → {"id":"ntf_xxx","status":"PENDING","duplicated":false}
```

约 1~2 秒后查询：

```bash
curl -s "http://localhost:8000/v1/notifications?q=demo-success-001" | python3 -m json.tool
# → items[0].status == "SUCCEEDED"
# → items[0].deliveredAt 有值
# → items[0].lastResponseSummary == "HTTP 200 OK"
```

字段命名：响应是 camelCase（`deliveredAt / nextRetryAt / lastError / lastResponseSummary / idempotencyKey / createdAt`），由 Pydantic `alias_generator=to_camel` 在出口转换；Python 内部仍是 snake_case。

---

## 场景 2：5xx 触发重试

把 mock 拉到全失败：

```bash
# 停掉 T1 终端的 mock，用 fail-rate=1.0 重启
uv run python tools/mock_provider.py --port 8500 --fail-rate 1.0
```

然后发一条：

```bash
curl -X POST http://localhost:8000/v1/notifications \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-retry-001" \
  -d '{"provider":"demo-crm","payload":{"user_id":1,"event":"x","metadata":{}}}'
```

后端日志（每秒 worker 扫一次，只挑 `next_retry_at <= now` 的）：

```
{"event":"delivery_attempt","attempt":1,"outcome":"RETRY","reason":"server_error_500", ...}
# 1s 后
{"event":"delivery_attempt","attempt":2,"outcome":"RETRY","reason":"server_error_500", ...}
# 5s 后
{"event":"delivery_attempt","attempt":3,"outcome":"RETRY","reason":"server_error_500", ...}
# 25s 后
{"event":"delivery_attempt","attempt":4,"outcome":"DEAD_LETTER","reason":"max_retries", ...}
```

退避序列固定为 `1s, 5s, 25s, 2m, ...`；实际跑几次由 `MAX_RETRY_ATTEMPTS` 控制（默认 4，约 ~30s 后进 DLQ）。`.env` 设 `MAX_RETRY_ATTEMPTS=8` 可拿到原 31h 容忍度。

---

## 场景 3：4xx 立即进死信

mock 不模拟 4xx，要演示这条路径，临时把某个 provider URL 指到一个会回 4xx 的端点（如 httpbin），或在 mock 里加一个返回 400 的 path。最简验证：dispatcher 收到 400 直接判 `DEAD_LETTER`，跳过任何重试。

查询 DLQ（响应是统一的 `Page<NotificationItem>` 外壳）：

```bash
curl -s http://localhost:8000/v1/dead-letters | python3 -m json.tool
# {
#   "items": [
#     {
#       "id": "ntf_xxx",
#       "idempotencyKey": "...",
#       "provider": "demo-crm",
#       "status": "DEAD_LETTER",
#       "attempts": 1,
#       "lastError": "client_error_400",
#       "lastResponseSummary": "HTTP 400 Bad Request",
#       "payload": {...},
#       "createdAt": "...",
#       ...
#     }
#   ],
#   "total": 1, "limit": 50, "offset": 0
# }
```

---

## 场景 4：幂等

```bash
for i in 1 2; do
  curl -s -X POST http://localhost:8000/v1/notifications \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: idem-test" \
    -d '{"provider":"demo-crm","payload":{"x":1,"event":"y","metadata":{}}}' \
    | python3 -c "import json,sys;d=json.load(sys.stdin);print(f'#{$i}: id={d[\"id\"]} duplicated={d[\"duplicated\"]}')"
done
# → #1: id=ntf_xxx duplicated=False
# → #2: id=ntf_xxx duplicated=True   ← 同一 id，第二次命中幂等
```

未带 `Idempotency-Key` 时按 `sha256(provider + canonical(payload))` 兜底——见 `routes_notifications.py:_fallback_idem_key`，并打 `idempotency_key_auto_generated` 警告日志。

---

## 观察：聚合指标 & Provider 状态

```bash
# Dashboard 用的 JSON（前端 useMetrics 直接消费这个）
curl -s http://localhost:8000/v1/metrics/summary | python3 -m json.tool
# {
#   "successRate": 0.84,
#   "inflight": 2,
#   "dlqTotal": 1,
#   "p95LatencyMs": 226.56,
#   "trend": [{"t":"...Z","succeeded":N,"failed":N,"inflight":N}, ... 24 个],
#   "byProvider": [{"provider":"demo-crm","succeeded":N,"failed":N,"dlq":N}, ...]
# }

# Provider 配置 + 当前熔断 + 24h 成功率序列
curl -s http://localhost:8000/v1/providers | python3 -m json.tool
# [{"name":"demo-crm","breaker":"CLOSED","breakerCooldownSeconds":null,
#   "successRateSeries":[{"t":"...","rate":1.0}, ...]}, ...]

# Prometheus 文本（外部抓取用）
curl -s http://localhost:8000/metrics | head -20

# 健康检查
curl -s http://localhost:8000/healthz
# → {"status":"ok","db":"ok","scheduler":"ok","failed":[]}
```

---

## 列表查询的 query 参数

| 参数 | 说明 |
|---|---|
| `status` | `PENDING / IN_FLIGHT / SUCCEEDED / DEAD_LETTER` |
| `provider` | provider 名 |
| `q` | 子串搜索 id / idempotencyKey / payload |
| `fromTs / toTs` | ISO 时间戳过滤 `created_at` |
| `limit / offset` | 分页（list 默认 25，DLQ 默认 50） |

```bash
curl "http://localhost:8000/v1/notifications?status=SUCCEEDED&provider=demo-crm&limit=5"
curl "http://localhost:8000/v1/notifications?q=ntf_05af&limit=1"
curl "http://localhost:8000/v1/dead-letters?fromTs=2026-05-01T00:00:00Z"
```
