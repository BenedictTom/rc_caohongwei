import type {
  DashboardMetrics,
  DeadLettersQuery,
  Notification,
  NotificationsQuery,
  Page,
  Provider,
  SubmitNotificationInput,
  SubmitNotificationResult,
} from "@/lib/types"

/**
 * 真实后端客户端骨架。
 * MVP 阶段后端尚未实现，所有方法在被调用时会抛错；
 * 一旦后端就绪，按对应路由补 fetch 即可。
 */
export function createRealClient(base: string) {
  async function get<T>(path: string): Promise<T> {
    const res = await fetch(`${base}${path}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    })
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    return (await res.json()) as T
  }
  async function post<T>(path: string, body: unknown, headers: Record<string, string> = {}): Promise<T> {
    const res = await fetch(`${base}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    return (await res.json()) as T
  }

  return {
    listNotifications: (q: NotificationsQuery = {}) => {
      const sp = new URLSearchParams()
      Object.entries(q).forEach(([k, v]) => v != null && sp.set(k, String(v)))
      return get<Page<Notification>>(`/v1/notifications?${sp.toString()}`)
    },
    listDeadLetters: (q: DeadLettersQuery = {}) => {
      const sp = new URLSearchParams()
      Object.entries(q).forEach(([k, v]) => v != null && sp.set(k, String(v)))
      return get<Page<Notification>>(`/v1/dead-letters?${sp.toString()}`)
    },
    getMetrics: () => get<DashboardMetrics>(`/v1/metrics/summary`),
    listProviders: () => get<Provider[]>(`/v1/providers`),
    submitNotification: (input: SubmitNotificationInput) => {
      const headers: Record<string, string> = {}
      if (input.idempotencyKey) headers["Idempotency-Key"] = input.idempotencyKey
      return post<SubmitNotificationResult>(
        "/v1/notifications",
        { provider: input.provider, payload: input.payload },
        headers,
      )
    },
  }
}
