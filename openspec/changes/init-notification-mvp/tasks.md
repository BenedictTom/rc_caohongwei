## 1. 项目骨架

- [x] 1.1 创建 `pyproject.toml`，声明依赖：fastapi、uvicorn、sqlalchemy、apscheduler、httpx、jinja2、structlog、pydantic-settings、pyyaml；dev 组：pytest、pytest-asyncio、httpx[testing]、respx、ruff
- [x] 1.2 创建目录结构：`app/{api,core,delivery,models}/`、`tests/`
- [x] 1.3 添加 `.gitignore`（venv、__pycache__、*.db、.env、.pytest_cache）
- [x] 1.4 添加 `providers.example.yaml` 与 `.env.example`

## 2. 配置与基础设施

- [x] 2.1 `app/core/config.py`：基于 pydantic-settings 的配置类（DB URL、worker 间隔、最大重试次数、并发上限、熔断阈值、provider 配置文件路径）
- [x] 2.2 `app/core/logging.py`：structlog 初始化，输出 JSON 格式
- [x] 2.3 `app/core/db.py`：SQLAlchemy engine + session factory（SQLite，开启 WAL 模式）
- [x] 2.4 `app/core/providers.py`：加载并校验 `providers.yaml`，启动时校验 token_env 存在

## 3. 数据模型

- [x] 3.1 `app/models/notification.py`：`Notification` 模型，字段：`id`、`idempotency_key`（唯一索引）、`provider`、`payload`(JSON)、`status`、`attempts`、`next_retry_at`、`last_error`、`last_response_summary`、`created_at`、`delivered_at`
- [x] 3.2 `app/models/notification.py`：`DeadLetter` 视图或独立表（MVP 用同表 status=DEAD_LETTER 过滤即可）
- [x] 3.3 `app/cli.py`：`init-db` 命令创建表

## 4. Intake API（capability: notification-intake）

- [x] 4.1 `app/api/schemas.py`：请求 / 响应 pydantic 模型，`payload` 序列化大小校验（≤ 64KB）
- [x] 4.2 `app/api/routes_notifications.py`：`POST /v1/notifications`，处理流程：校验 provider 存在 → 计算 idempotency_key（header 优先，否则用 sha256(provider+payload)）→ INSERT or DO NOTHING → 返回已落库的 notification_id
- [x] 4.3 处理事务失败 → 返回 503
- [x] 4.4 `GET /healthz`：检查 DB 连通 + 调度器线程存活
- [x] 4.5 `app/main.py`：FastAPI app 装配，启动时初始化日志 / DB / Provider 配置 / 调度器

## 5. Delivery 调度器（capability: notification-delivery）

- [x] 5.1 `app/delivery/breaker.py`：vendor 维度熔断器（CLOSED/OPEN/HALF_OPEN 状态机），线程安全
- [x] 5.2 `app/delivery/backoff.py`：纯函数 `compute_next_retry_at(attempts) -> datetime`，含 ±20% jitter
- [x] 5.3 `app/delivery/classifier.py`：错误分类纯函数，输入响应/异常 → 输出 `RETRY` / `DEAD_LETTER`
- [x] 5.4 `app/delivery/renderer.py`：基于 provider 配置 + payload 渲染最终 HTTP 请求（method/url/headers/body）；模板异常抛特定错误
- [x] 5.5 `app/delivery/dispatcher.py`：核心投递函数 `dispatch(notification)`：渲染 → httpx.AsyncClient 发请求 → 分类结果 → 写状态机 → 更新 metrics
- [x] 5.6 `app/delivery/worker.py`：APScheduler 周期任务（默认每 1s），SQL 拉取 `PENDING AND next_retry_at <= now`，按 vendor 熔断状态过滤，提交到并发池
- [x] 5.7 并发控制：asyncio.Semaphore(默认 32)

## 6. 死信查询

- [x] 6.1 `app/api/routes_dlq.py`：`GET /v1/dead-letters`，支持 `provider`、`from`/`to` 过滤、分页

## 7. 可观测性

- [x] 7.1 `app/core/metrics.py`：定义 Counter / Histogram / Gauge
- [x] 7.2 `app/api/routes_metrics.py`：`GET /metrics` 输出 Prometheus 文本
- [x] 7.3 在 dispatcher / breaker 关键节点埋点
- [x] 7.4 全链路日志：每条通知至少 5 条日志（received / dispatched / response / state_change / final）

## 8. 测试（演示价值优先）

- [x] 8.1 单元：`backoff` 序列正确；jitter 在 ±20% 范围内
- [x] 8.2 单元：`classifier` 对各错误类型分类正确
- [x] 8.3 单元：`breaker` 状态转换 CLOSED → OPEN → HALF_OPEN → CLOSED
- [x] 8.4 单元：`renderer` 渲染缺字段时抛模板错
- [x] 8.5 集成：`POST /notifications` 幂等去重（用 sqlite + httpx TestClient）
- [x] 8.6 集成：用 respx mock 外部供应商，验证一条通知"5xx → 重试 → 2xx → SUCCEEDED"全链路
- [x] 8.7 集成：4xx 立即进 DLQ，attempts=1
- [x] 8.8 集成：连续失败触发熔断后，新单不被派发但仍可入库

## 9. 文档与演示

- [x] 9.1 在 README "运行" 章节补充实际命令验证可跑通
- [x] 9.2 补充 `docs/AI-USAGE.md`：明确分类记录"AI 帮助 / AI 被否决 / 人类决策"
- [x] 9.3 录一个 `docs/demo.md`：用 curl 演示成功投递、模拟 5xx 重试、模拟 4xx 死信三个场景
