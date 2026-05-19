import type {
  DashboardMetrics,
  DeadLettersQuery,
  Notification,
  NotificationsQuery,
  Page,
  Provider,
  SubmitNotificationInput,
  SubmitNotificationResult,
  TrendPoint,
} from "@/lib/types"

// ─────────────────────────────────────────────────────────────
// 工具：seed 随机，避免每次刷新数字大幅跳变（仍保持一些偶发性）
// ─────────────────────────────────────────────────────────────
function mulberry32(seed: number) {
  return () => {
    let t = (seed += 0x6d2b79f5)
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const rand = mulberry32(20260518)

function pick<T>(arr: T[]): T {
  return arr[Math.floor(rand() * arr.length)]
}

function uid(prefix = "ntf"): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`
}

// ─────────────────────────────────────────────────────────────
// Providers（与后端 providers.example.yaml 对齐）
// ─────────────────────────────────────────────────────────────
const PROVIDER_NAMES = ["demo-crm", "demo-ad-network", "demo-inventory"] as const

const PROVIDERS: Provider[] = [
  {
    name: "demo-crm",
    url: "https://crm.example.com/api/contacts",
    method: "POST",
    authType: "bearer",
    authHint: "CRM_TOKEN",
    timeoutMs: 5000,
    headers: { "Content-Type": "application/json", "X-Source": "rc_caohongwei" },
    bodyTemplate:
      '{\n  "contact_id": "{{ payload.user_id }}",\n  "status": "{{ payload.event }}"\n}',
    breaker: "CLOSED",
    successRateSeries: makeRateSeries(0.96),
  },
  {
    name: "demo-ad-network",
    url: "https://ads.example.com/v2/conversions",
    method: "POST",
    authType: "header",
    authHint: "AD_API_KEY",
    timeoutMs: 3000,
    headers: { "Content-Type": "application/json" },
    bodyTemplate:
      '{\n  "click_id": "{{ payload.click_id }}",\n  "event_type": "registration",\n  "ts": "{{ payload.ts }}"\n}',
    breaker: "OPEN",
    breakerCooldownSeconds: 218,
    successRateSeries: makeRateSeries(0.78),
  },
  {
    name: "demo-inventory",
    url: "https://inventory.example.com/stock/decrement",
    method: "POST",
    authType: "none",
    timeoutMs: 5000,
    headers: { "Content-Type": "application/json" },
    bodyTemplate:
      '{\n  "sku": "{{ payload.sku }}",\n  "qty": {{ payload.qty }}\n}',
    breaker: "HALF_OPEN",
    successRateSeries: makeRateSeries(0.91),
  },
]

function makeRateSeries(base: number) {
  const out: { t: string; rate: number }[] = []
  const now = Date.now()
  for (let i = 23; i >= 0; i--) {
    const t = new Date(now - i * 60 * 60 * 1000).toISOString()
    const wobble = (rand() - 0.5) * 0.08
    out.push({ t, rate: Math.max(0, Math.min(1, base + wobble)) })
  }
  return out
}

// ─────────────────────────────────────────────────────────────
// Notifications：生成 200 条覆盖各 status / provider 的样本
// ─────────────────────────────────────────────────────────────
const STATUS_DISTRIBUTION = [
  ..."SUCCEEDED ".repeat(70).split(" "),
  ..."PENDING ".repeat(12).split(" "),
  ..."IN_FLIGHT ".repeat(6).split(" "),
  ..."DEAD_LETTER ".repeat(12).split(" "),
].filter(Boolean) as Notification["status"][]

const ERR_REASONS = [
  "upstream_5xx",
  "timeout",
  "tcp_reset",
  "tls_handshake_failed",
  "rate_limited_429",
  "bad_request_400",
  "auth_failed_401",
  "template_render_error",
]

function buildPayloadFor(provider: string): Record<string, unknown> {
  if (provider === "demo-crm") {
    return {
      user_id: 1000 + Math.floor(rand() * 9000),
      event: pick(["subscription.paid", "subscription.canceled", "trial.ended"]),
    }
  }
  if (provider === "demo-ad-network") {
    return {
      click_id: `clk_${Math.random().toString(36).slice(2, 10)}`,
      ts: new Date(Date.now() - Math.floor(rand() * 1e7)).toISOString(),
    }
  }
  return {
    sku: `SKU-${Math.floor(rand() * 9000 + 1000)}`,
    qty: Math.ceil(rand() * 5),
  }
}

const NOTIFICATIONS: Notification[] = Array.from({ length: 220 }).map((_, i) => {
  const provider = pick([...PROVIDER_NAMES])
  const status = STATUS_DISTRIBUTION[i % STATUS_DISTRIBUTION.length]
  const createdAt = Date.now() - Math.floor(rand() * 1000 * 60 * 60 * 24 * 5)
  const attempts =
    status === "SUCCEEDED"
      ? rand() < 0.7
        ? 1
        : Math.ceil(rand() * 3)
      : status === "DEAD_LETTER"
        ? 1 + Math.floor(rand() * 8)
        : status === "IN_FLIGHT"
          ? 1
          : Math.ceil(rand() * 4)
  const isSuccess = status === "SUCCEEDED"
  const isDlq = status === "DEAD_LETTER"
  const lastCode = isSuccess
    ? 200
    : isDlq
      ? pick([400, 401, 403, 0])
      : pick([0, 429, 500, 502, 503, 504])
  return {
    id: uid("ntf"),
    idempotencyKey: `key_${Math.random().toString(36).slice(2, 10)}`,
    provider,
    status,
    attempts,
    payload: buildPayloadFor(provider),
    createdAt: new Date(createdAt).toISOString(),
    deliveredAt: isSuccess ? new Date(createdAt + 500).toISOString() : undefined,
    nextRetryAt:
      status === "PENDING"
        ? new Date(Date.now() + Math.floor(rand() * 3600 * 1000)).toISOString()
        : undefined,
    lastError: isSuccess ? undefined : pick(ERR_REASONS),
    lastResponseSummary:
      isSuccess
        ? '{"ok": true}'
        : lastCode === 0
          ? "(no response)"
          : `${lastCode} ${pick(["Internal Server Error", "Service Unavailable", "Bad Gateway", "Bad Request", "Unauthorized"])}`,
  }
})

NOTIFICATIONS.sort(
  (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
)

// ─────────────────────────────────────────────────────────────
// Trend / metrics
// ─────────────────────────────────────────────────────────────
function buildTrend(): TrendPoint[] {
  const out: TrendPoint[] = []
  const now = Date.now()
  for (let i = 23; i >= 0; i--) {
    const t = new Date(now - i * 60 * 60 * 1000).toISOString()
    const total = 220 + Math.floor(rand() * 180)
    const failedRatio = 0.04 + (rand() - 0.5) * 0.06
    const failed = Math.max(0, Math.round(total * failedRatio))
    out.push({
      t,
      succeeded: total - failed,
      failed,
      inflight: Math.floor(rand() * 14),
    })
  }
  return out
}

const TREND = buildTrend()

function buildMetrics(): DashboardMetrics {
  const total = TREND.reduce((s, p) => s + p.succeeded + p.failed, 0)
  const ok = TREND.reduce((s, p) => s + p.succeeded, 0)
  const inflight = NOTIFICATIONS.filter((n) => n.status === "IN_FLIGHT").length
  const dlq = NOTIFICATIONS.filter((n) => n.status === "DEAD_LETTER").length

  const byProvider = PROVIDER_NAMES.map((p) => {
    const items = NOTIFICATIONS.filter((n) => n.provider === p)
    return {
      provider: p,
      succeeded: items.filter((n) => n.status === "SUCCEEDED").length,
      failed: items.filter((n) => n.status === "DEAD_LETTER").length * 2,
      dlq: items.filter((n) => n.status === "DEAD_LETTER").length,
    }
  })

  return {
    successRate: ok / total,
    inflight,
    dlqTotal: dlq,
    p95LatencyMs: 320 + Math.floor(rand() * 240),
    trend: TREND,
    byProvider,
  }
}

// ─────────────────────────────────────────────────────────────
// 模拟网络延迟
// ─────────────────────────────────────────────────────────────
function delay<T>(value: T, ms = 280 + Math.floor(rand() * 380)): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms))
}

// ─────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────
export async function listNotifications(
  q: NotificationsQuery = {},
): Promise<Page<Notification>> {
  let items = NOTIFICATIONS.slice()
  if (q.status) items = items.filter((n) => n.status === q.status)
  if (q.provider) items = items.filter((n) => n.provider === q.provider)
  if (q.q) {
    const k = q.q.toLowerCase()
    items = items.filter(
      (n) =>
        n.id.toLowerCase().includes(k) ||
        n.idempotencyKey.toLowerCase().includes(k) ||
        JSON.stringify(n.payload).toLowerCase().includes(k),
    )
  }
  if (q.fromTs) items = items.filter((n) => n.createdAt >= q.fromTs!)
  if (q.toTs) items = items.filter((n) => n.createdAt <= q.toTs!)
  const offset = q.offset ?? 0
  const limit = q.limit ?? 25
  return delay({
    items: items.slice(offset, offset + limit),
    total: items.length,
    limit,
    offset,
  })
}

export async function listDeadLetters(
  q: DeadLettersQuery = {},
): Promise<Page<Notification>> {
  return listNotifications({ ...q, status: "DEAD_LETTER" })
}

export async function getMetrics(): Promise<DashboardMetrics> {
  return delay(buildMetrics())
}

export async function listProviders(): Promise<Provider[]> {
  return delay(PROVIDERS)
}

export async function submitNotification(
  input: SubmitNotificationInput,
): Promise<SubmitNotificationResult> {
  // 模拟偶发失败让 UI 错误路径有机会被看到
  if (rand() < 0.05) {
    await delay(null, 600)
    throw new Error("模拟后端错误：503 Service Unavailable")
  }
  // 模拟幂等命中
  const dup = NOTIFICATIONS.find(
    (n) =>
      n.provider === input.provider &&
      input.idempotencyKey &&
      n.idempotencyKey === input.idempotencyKey,
  )
  if (dup) return delay({ id: dup.id, status: "PENDING" as const, duplicated: true })

  const newNtf: Notification = {
    id: uid("ntf"),
    idempotencyKey:
      input.idempotencyKey ??
      `auto_${Math.random().toString(36).slice(2, 10)}`,
    provider: input.provider,
    status: "PENDING",
    attempts: 0,
    payload: input.payload,
    createdAt: new Date().toISOString(),
  }
  NOTIFICATIONS.unshift(newNtf)
  return delay({ id: newNtf.id, status: "PENDING" as const, duplicated: false })
}
