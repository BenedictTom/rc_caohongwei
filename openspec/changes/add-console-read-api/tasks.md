## 1. 数据模型 & 迁移

- [ ] 1.1 `app/models/notification.py`：在 `Notification` 上加 `last_elapsed_ms: Mapped[int | None]`（nullable，默认 NULL）
- [ ] 1.2 SQLite 表已 `create_all` 自动建——但已有 db 文件需手工 `ALTER`；MVP 简化处理：测试 fixture 自动重建表，本地开发 `rm notifications.db` 即可
- [ ] 1.3 dispatcher 在 `_persist_success / _persist_dead_letter / _persist_retry` 写入 `last_elapsed_ms`（仅 HTTP 真发起时）
- [ ] 1.4 `_apply_outcome` 的签名增加 `elapsed_ms: int` 参数；`dispatch()` 调用处传入 `int(elapsed * 1000)`

## 2. 配置 & CORS

- [ ] 2.1 `app/core/config.py`：`Settings.cors_allow_origins: list[str] = ["http://localhost:3000"]`，pydantic 自动从 JSON 字符串解析
- [ ] 2.2 `app/main.py`：装 `fastapi.middleware.cors.CORSMiddleware`，方法 / header 全放通（仅控制 origin）
- [ ] 2.3 lifespan 启动日志加一行 `cors_allowlist=...`

## 3. 响应 schema（pydantic）

- [ ] 3.1 `app/api/schemas.py` 增 `NotificationListItem`（id / idempotency_key / provider / status / attempts / payload / created_at / delivered_at / next_retry_at / last_error / last_response_summary / last_elapsed_ms）
- [ ] 3.2 增 `NotificationListResponse(items, total, limit, offset)`
- [ ] 3.3 增 `ProviderItem`（name / url / method / timeout_ms / headers / body_template / auth_type / auth_token_env / breaker / breaker_cooldown_seconds）+ `ProviderListResponse(items)`
- [ ] 3.4 增 `MetricsSummary`（success_rate / inflight / dlq_total / p95_latency_ms / trend / by_provider）+ 内部子模型 `TrendPoint / ByProvider`

## 4. 路由实现

- [ ] 4.1 `app/api/routes_console.py`：新建，`router = APIRouter(prefix="/v1", tags=["console"])`
- [ ] 4.2 `GET /v1/notifications`：参数 `status / provider / from / to / q / limit / offset`；SQLAlchemy 构造 where；count + items 两次 query；按 `created_at DESC` 排序
- [ ] 4.3 `GET /v1/providers`：从 `get_registry()` + `get_breaker().snapshot()` 合并；token 字段**只暴露 token_env 名字**不暴露值
- [ ] 4.4 `GET /v1/metrics/summary`：4 段 SQL（success_rate / inflight / dlq_total / by_provider）+ trend（`strftime('%Y-%m-%dT%H:00:00Z', created_at)` 桶）+ p95（ORDER BY last_elapsed_ms DESC LIMIT n*0.05）
- [ ] 4.5 `app/main.py` include 新 router

## 5. 测试

- [ ] 5.1 `tests/test_console_api.py::test_list_notifications_filter_by_status`：插入 SUCCEEDED / DEAD_LETTER 各 3 条，按 status 过滤返回正确
- [ ] 5.2 `test_list_notifications_pagination`：插 60 条，limit=20、offset=20 返回中间一段
- [ ] 5.3 `test_list_providers_returns_breaker_state`：把 demo-crm 打到 OPEN，接口返回 `breaker=OPEN`，`breaker_cooldown_seconds` 在合理区间
- [ ] 5.4 `test_list_providers_no_token_leak`：响应中**不**含 token 实际值（grep 测试 token 字符串）
- [ ] 5.5 `test_metrics_summary_empty_db`：空库返回全零结构、trend 长度 24
- [ ] 5.6 `test_metrics_summary_basic_aggregation`：插入混合 SUCCEEDED/DEAD_LETTER/PENDING/IN_FLIGHT，验证 success_rate / inflight / dlq_total 正确
- [ ] 5.7 `test_metrics_summary_p95`：插 100 条 last_elapsed_ms 等差数列，验证 p95 ≈ 第 95 大
- [ ] 5.8 `test_cors_preflight_localhost`：OPTIONS 请求带 Origin: http://localhost:3000，响应头放通

## 6. 前端对接

- [ ] 6.1 `web/lib/api/real.ts`：实现 `snakeToCamel<T>()` 递归转换工具（处理嵌套对象 / 数组 / 跳过 Date 字符串）
- [ ] 6.2 `listNotifications`：fetch `/v1/notifications?...` → snakeToCamel → 包成 `Page<Notification>`（注意：后端 items 字段直接是 `Notification[]`-like，缺 `attemptHistory` 字段，前端兼容缺失）
- [ ] 6.3 `listProviders`：fetch `/v1/providers` → snakeToCamel → 数组（注意 `successRateSeries` 后端不返，前端 fallback 到空数组或 mock 衍生）
- [ ] 6.4 `getMetrics`：fetch `/v1/metrics/summary` → snakeToCamel → `DashboardMetrics`
- [ ] 6.5 `web/lib/api/index.ts`：保留现有 `apiMode` 切换逻辑不动
- [ ] 6.6 `web/.env.local.example`：新建（不带敏感值），写 `NEXT_PUBLIC_API_BASE=http://localhost:8000`

## 7. 验证 & 文档

- [ ] 7.1 启动后端 `uvicorn app.main:app`，启动前端 `cd web && NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev`
- [ ] 7.2 浏览器访问 http://localhost:3000，依次点开 Dashboard / Notifications / Providers，**截屏验证三页都显示真实数据**
- [ ] 7.3 提交 5-10 条通知 → Dashboard 趋势 / DLQ 数 / Providers 熔断态实时变化
- [ ] 7.4 README "运行" 章节补充前后端联调命令；docs/demo.md 增"完整链路演示"章节
- [ ] 7.5 ruff 通过 + 测试 ≥ 55 个全过
