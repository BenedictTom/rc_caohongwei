export type NotificationStatus =
  | "PENDING"
  | "IN_FLIGHT"
  | "SUCCEEDED"
  | "DEAD_LETTER"

export type BreakerState = "CLOSED" | "HALF_OPEN" | "OPEN"

export type AuthType = "none" | "bearer" | "header"

export interface Provider {
  name: string
  url: string
  method: "POST" | "PUT" | "PATCH"
  authType: AuthType
  authHint?: string
  timeoutMs: number
  headers: Record<string, string>
  bodyTemplate: string
  /** 当前熔断态 */
  breaker: BreakerState
  /** 若 OPEN，多少秒后恢复 */
  breakerCooldownSeconds?: number
  /** 24h 成功率序列（每点一个时间桶） */
  successRateSeries: { t: string; rate: number }[]
}

export interface Notification {
  id: string
  idempotencyKey: string
  provider: string
  status: NotificationStatus
  attempts: number
  payload: Record<string, unknown>
  createdAt: string
  deliveredAt?: string
  nextRetryAt?: string
  lastError?: string
  lastResponseSummary?: string
}

export interface DashboardMetrics {
  /** 0–1 之间 */
  successRate: number
  inflight: number
  dlqTotal: number
  /** 毫秒 */
  p95LatencyMs: number
  /** 24 小时趋势 */
  trend: TrendPoint[]
  /** 各 provider 维度的本周累计 */
  byProvider: { provider: string; succeeded: number; failed: number; dlq: number }[]
}

export interface TrendPoint {
  /** ISO 时间 */
  t: string
  succeeded: number
  failed: number
  inflight: number
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface NotificationsQuery {
  status?: NotificationStatus
  provider?: string
  q?: string
  fromTs?: string
  toTs?: string
  limit?: number
  offset?: number
}

export interface DeadLettersQuery {
  provider?: string
  fromTs?: string
  toTs?: string
  limit?: number
  offset?: number
}

export interface SubmitNotificationInput {
  provider: string
  payload: Record<string, unknown>
  idempotencyKey?: string
}

export interface SubmitNotificationResult {
  id: string
  status: NotificationStatus
  duplicated: boolean
}
