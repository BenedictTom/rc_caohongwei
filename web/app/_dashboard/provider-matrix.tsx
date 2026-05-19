"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BreakerBadge } from "@/components/status-badge"
import { useProviders } from "@/lib/hooks"
import { Skeleton } from "@/components/ui/skeleton"
import { ResponsiveContainer, Line, LineChart, YAxis } from "recharts"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

export function ProviderMatrix() {
  const { data, isLoading } = useProviders()

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-sm font-semibold tracking-tight">
          Provider 健康度
        </CardTitle>
        <span className="text-xs text-muted-foreground">最近 24h</span>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-3">
        {isLoading || !data ? (
          <>
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </>
        ) : (
          data.map((p, i) => {
            const accent =
              p.breaker === "OPEN"
                ? "border-l-warning"
                : p.breaker === "HALF_OPEN"
                  ? "border-l-info"
                  : "border-l-success"
            return (
              <motion.div
                key={p.name}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06, duration: 0.3 }}
                className={cn(
                  "group relative overflow-hidden rounded-xl border bg-card p-4 transition-all hover:-translate-y-0.5 hover:shadow-md border-l-4",
                  accent,
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold">{p.name}</div>
                    <div className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">
                      {p.method} {p.url.replace(/^https?:\/\//, "")}
                    </div>
                  </div>
                  <BreakerBadge state={p.breaker} />
                </div>
                <div className="-mx-2 mt-3 h-12">
                  <ResponsiveContainer>
                    <LineChart data={p.successRateSeries}>
                      <YAxis hide domain={[0.6, 1]} />
                      <Line
                        type="monotone"
                        dataKey="rate"
                        stroke={
                          p.breaker === "OPEN"
                            ? "var(--warning)"
                            : "var(--success)"
                        }
                        strokeWidth={1.6}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>
                    成功率{" "}
                    <span className="font-semibold tabular-nums text-foreground">
                      {(
                        (p.successRateSeries.at(-1)?.rate ?? 0) * 100
                      ).toFixed(1)}
                      %
                    </span>
                  </span>
                  {p.breaker === "OPEN" && p.breakerCooldownSeconds && (
                    <span className="text-warning">
                      剩余 {Math.round(p.breakerCooldownSeconds / 60)} 分钟
                    </span>
                  )}
                </div>
              </motion.div>
            )
          })
        )}
      </CardContent>
    </Card>
  )
}
