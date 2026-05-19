# AI 使用说明

> PDF 强制项。本文记录在本作业中 AI 与人类的协作过程，按"采纳 / 否决 / 人类原创"三类组织。

---

## 一、AI 在哪些关键节点提供了帮助

| # | 节点 | AI 贡献 | 我的处理 |
|---|------|---------|---------|
| 1 | 问题域梳理 | 列出通知系统典型失败模式：4xx/5xx/超时/限流/DNS/TLS/模板错 | ✅ 全部纳入 spec 错误分类表 |
| 2 | 退避序列经验值 | 提议 `1s, 5s, 25s, 2m, 10m, 1h, 6h, 24h`，覆盖 ~31h | ✅ 直接采纳 |
| 3 | Jitter 比例 | 初版 ±10% | ⚠️ **改为 ±20%**——多 worker 场景下打散惊群更稳 |
| 4 | OpenSpec 文档结构 | 给出 proposal / design / specs / tasks 的 markdown 模板 | ✅ 采纳，但精简了 design 模板 |
| 5 | 错误分类边界 | 提示 429 与 4xx 应区别处理 | ✅ 写进 classifier.py |
| 6 | 模板渲染策略 | 推荐 Jinja2 + StrictUndefined（缺字段直接抛错） | ✅ 采纳——比 silent skip 更安全 |
| 7 | SQLite WAL + UTC datetime | 提示 SQLite 默认不存 tzinfo | ✅ 在测试发现 bug 后用 `TypeDecorator` 修源头 |
| 8 | spec 边界追问 | 在写 spec 阶段追问"未带 Idempotency-Key 怎么办" | ✅ 触发"按 (provider, sha256(payload)) 兜底"的设计 |
| 9 | 前后端字段命名方案对比 | 列出 alias_generator / 前端映射层 / 前端改 snake_case 三选一并给出权衡 | ✅ 选 `alias_generator=to_camel`：JSON 出口 camelCase，Python 内部仍 PEP 8 |
| 10 | P95 估算思路 | 提议给 Histogram 加 `snapshot()` + bucket 线性插值估算 | ✅ 采纳——避免持久化每次延迟、不动表结构 |
| 11 | Dashboard 聚合接口拆分 | 建议跟 `/metrics`（Prometheus）并行新开一个 `/v1/metrics/summary`（JSON） | ✅ Prometheus 服务监控、JSON 聚合服务前端，互不依赖 |

---

## 二、AI 给出但我**未采纳**的建议

| # | AI 建议 | 否决理由 | 出处 |
|---|---------|---------|------|
| 1 | 一上来就上 Kafka + 多消费者组 | MVP < 100 QPS，多一个有状态依赖 + 故障域 + 运维成本，**对 MVP 是负担** | design 决策 2 |
| 2 | 引入 Celery + Redis broker 做异步任务 | APScheduler 单进程已够；Celery 的多 worker 收益要部署多容器才用得上 | design 决策 6 |
| 3 | 全套 OpenTelemetry + Jaeger + Span 传播 | 结构化日志已能回答 95% 排障问题；OTel 的 SDK 引入与 collector 部署成本 > 收益 | design 决策 7 |
| 4 | 引入 Saga / 事件溯源处理失败回滚 | 通知是无状态的"开火即忘"，无编排或回滚需求 | Non-Goals |
| 5 | 多租户配额 + 可视化模板配置后台 | 题目未要求；演示价值低 | Non-Goals |
| 6 | 把 4xx/5xx 当作可重试统一处理 | 4xx 是业务错（payload 不合法、鉴权失败），重试只是浪费 + 反复打供应商 | spec 错误分类表 |
| 7 | 每个 provider 写独立 Python class（SPI 风格） | 多一层抽象、需要 import 路径配置；**YAML + Jinja2 已能表达全部已知供应商** | design 决策 5 |
| 8 | 用 `prometheus_client` 完整库 | 我们只需要 4 类指标 + 文本输出；自实现 ~80 行，比库的 multiprocessing/CollectorRegistry 复杂度低得多 | `app/core/metrics.py` |
| 9 | 用 `RETRYING` 状态机分支 | 失败回写 `PENDING + next_retry_at` 后，用一条 SQL 谓词就能选出"该派发的"，状态机分支是冗余 | README 状态机说明 |

---

## 三、哪些**关键决策是我自己做的**（AI 没主动提出）

### 决策 1：承认 At-Least-Once，不假装 Exactly-Once

AI 一开始倾向回避这个表述，更愿意给出"我们尽力做到只投递一次"这种模糊语言。我把它改成显式承诺 At-Least-Once，并把幂等责任**按方向划分两段**写进设计文档：

- 入站（业务方 → 本系统）：`Idempotency-Key` + 唯一索引去重
- 出站（本系统 → 第三方）：在文档中**明确声明**业务方需保证下游接口幂等

这是我从工作经验出发的判断——含糊的语义会让调用方做错误假设，迟早翻车。

### 决策 2：DB 作队列 + 失败回写 PENDING（无 FAILED 状态）

AI 默认建议引入 `RETRYING` 中间态。我把它压扁——失败时直接把 `status` 写回 `PENDING` 并设置 `next_retry_at`，让调度器用一条 SQL 谓词就能选出工作单元：

```sql
WHERE status = 'PENDING' AND next_retry_at <= now()
```

调度逻辑因此简化为单一查询，回放与调试成本被压到最低。这是一个受 outbox 模式启发但去掉了多余状态的设计。

### 决策 3：熔断粒度 = vendor，不到 endpoint

AI 提议"按 (provider, endpoint) 二元组维护熔断状态"。我没采纳——同一供应商不同 endpoint 故障相关性极高（多半是其后端整体抖动），细粒度熔断反而失去保护意义，还增加状态空间。

### 决策 4：不做投递回执回调

AI 默认会给"成功后回调业务方 webhook"的设计。但 PDF 原文写的是"业务系统不需要关心外部 API 的返回值"——这是契约边界。做了就是越界，且会引入新的失败处理链路。

### 决策 5：metrics 自实现而非引库

PDF 评估重点中有"识别并主动管理复杂度"。`prometheus_client` 很优秀，但它带来 multiprocessing collector、CollectorRegistry 全局状态等抽象——MVP 阶段我用 80 行手写实现 Counter/Gauge/Histogram，**用代码量本身证明这个选择是合理的**。

### 决策 6：UTC 时区在数据层兜底，不在应用层处处补

写测试时发现 SQLite 把 `DateTime(timezone=True)` 取出来变成 naive。AI 提议每个读取点用 `if tzinfo is None: replace(tzinfo=utc)` 来补。我反而觉得这是源头问题——加一个 SQLAlchemy `TypeDecorator` 让模型层强制 UTC aware，应用层就不用处处防御。**让正确性靠类型而非靠纪律**。

### 决策 7：前后端字段命名 = 在转换层放置，让两边都符合各自惯例

前后端联调时面对一个跨语言惯例冲突：Python PEP 8 是 snake_case，TS/JS 业界是 camelCase。AI 列出了三个方案：(a) 后端 Pydantic `alias_generator=to_camel`；(b) 前端写映射函数；(c) 前端类型也改 snake_case。

我选 (a)，但**判断依据不是"工作量最小"**——而是**让转换发生在系统边界，让两侧的代码各自符合自己语言的惯例**。

- 方案 (b) 把转换分散到每个 API 调用点，加字段要在两处改，长期会漂；
- 方案 (c) 让 Python 代码偏离 PEP 8、连 SQLAlchemy 列名都得跟着别扭；
- 方案 (a) 一处配置（`CamelModel(model_config=ConfigDict(alias_generator=to_camel, populate_by_name=True))`）全模型继承生效，且把 "对外 JSON" 这层契约和 "Python 内部" 解耦——以后哪怕换前端语言，契约不变。

附带 trade-off：FastAPI 的 query 参数不走 model 的 alias_generator，需要在路由签名手动 `Query(alias="fromTs")`。这条 AI 没主动提，是我在第一次 422 之后才发现的——把它写进 spec 提醒下次。

### 决策 8：本地 mock provider 是演示设计的一部分，不是事后补丁

`tools/mock_provider.py` 是评审者第一次跑这个项目的"零阻力"保证。AI 默认会让你在 README 里写"请把 url 改成 httpbin.org/anything"——这就把演示成败寄托给了一个外部域名，而且评审者还要自己改 yaml。

我把它倒过来：仓库默认 `providers.yaml` 就指向 `127.0.0.1:8500/<name>`，加一个 ~50 行的 stdlib mock，clone 后两条 `uv run` 就能看到完整链路 + dashboard 真实样本。

---

## 四、AI 协作的工作方式

- **Spec-Driven**：所有需求和设计先用 OpenSpec markdown（proposal / design / specs / tasks）落到文件，AI 读这些文件再写代码。避免"AI 听了一句口头需求就开干"的失控。
- **小步提交、人类审稿**：每写完一个模块（backoff、classifier、breaker、renderer 等）我都会读一遍 AI 生成的代码，特别留意是否有"看起来对但实际是 happy path"的逻辑。比如 dispatcher 里 AI 一开始把 `time.perf_counter()` 写在 `with` 上下文里、异常路径返回了 0 elapsed——这种 bug 在 review 时被发现并修掉。
- **测试验证** 使用Qoder审核Claude生成的代码，完成覆盖测试用例，让代码服从测试，而不是让claude写代码，claude写测试（自己审核自己）
