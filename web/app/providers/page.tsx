"use client"

import { useEffect, useState } from "react"
import { useProviders } from "@/lib/hooks"
import { PageHeader } from "@/components/section"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { BreakerBadge } from "@/components/status-badge"
import { Skeleton } from "@/components/ui/skeleton"
import { CodeBlock } from "@/components/code-block"
import { motion } from "framer-motion"
import {
  ResponsiveContainer,
  Area,
  AreaChart,
  YAxis,
} from "recharts"
import { cn } from "@/lib/utils"
import { Lock, Shield, ShieldAlert, ShieldCheck } from "lucide-react"
import type { Provider } from "@/lib/types"

export default function ProvidersPage() {
  const { data, isLoading } = useProviders()

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Providers"
        title="供应商配置与健康度"
        description="从 providers.yaml 解析的全部供应商，含 URL / 鉴权 / 超时、当前熔断态与近 24 小时投递成功率。"
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {isLoading || !data
          ? Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-72" />
            ))
          : data.map((p, i) => (
              <motion.div
                key={p.name}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08, duration: 0.32 }}
              >
                <ProviderCard p={p} />
              </motion.div>
            ))}
      </div>
    </div>
  )
}

function ProviderCard({ p }: { p: Provider }) {
  const accent =
    p.breaker === "OPEN"
      ? "border-l-warning"
      : p.breaker === "HALF_OPEN"
        ? "border-l-info"
        : "border-l-success"
  const lastRate = (p.successRateSeries.at(-1)?.rate ?? 0) * 100
  const stroke =
    p.breaker === "OPEN" ? "var(--warning)" : "var(--success)"

  return (
    <Card
      className={cn(
        "group relative overflow-hidden border-l-4 transition-all hover:-translate-y-0.5 hover:shadow-md",
        accent,
      )}
    >
      <CardHeader className="space-y-1.5">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="text-base font-semibold">{p.name}</div>
            <div className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">
              {p.method} {p.url}
            </div>
          </div>
          <BreakerBadge state={p.breaker} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-3 gap-2 text-xs">
          <Stat label="鉴权" value={p.authType.toUpperCase()} icon={authIcon(p.authType)} />
          <Stat label="超时" value={`${p.timeoutMs} ms`} icon={Shield} />
          <Stat
            label="成功率"
            value={`${lastRate.toFixed(1)}%`}
            icon={p.breaker === "OPEN" ? ShieldAlert : ShieldCheck}
          />
        </div>

        <div className="-mx-2 h-16">
          <ResponsiveContainer>
            <AreaChart data={p.successRateSeries}>
              <defs>
                <linearGradient id={`fill-${p.name}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={stroke} stopOpacity={0.45} />
                  <stop offset="100%" stopColor={stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis hide domain={[0.5, 1]} />
              <Area
                type="monotone"
                dataKey="rate"
                stroke={stroke}
                strokeWidth={1.6}
                fill={`url(#fill-${p.name})`}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {p.breaker === "OPEN" && p.breakerCooldownSeconds && (
          <CooldownLine seconds={p.breakerCooldownSeconds} />
        )}

        <div>
          <div className="mb-1.5 text-[11px] uppercase tracking-wider text-muted-foreground">
            Body Template
          </div>
          <CodeBlock code={p.bodyTemplate} />
        </div>
      </CardContent>
    </Card>
  )
}

function Stat({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string
  icon: typeof Shield
}) {
  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2">
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
        <Icon className="size-3" />
        {label}
      </div>
      <div className="mt-0.5 truncate font-mono text-xs font-semibold">
        {value}
      </div>
    </div>
  )
}

function authIcon(type: Provider["authType"]) {
  if (type === "bearer") return Lock
  if (type === "header") return Shield
  return ShieldCheck
}

function CooldownLine({ seconds }: { seconds: number }) {
  const [s, setS] = useState(seconds)
  useEffect(() => {
    const t = setInterval(() => setS((p) => (p > 0 ? p - 1 : 0)), 1000)
    return () => clearInterval(t)
  }, [])
  const m = Math.floor(s / 60)
  const r = s % 60
  return (
    <div className="rounded-md border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
      熔断中 · {m} 分 {String(r).padStart(2, "0")} 秒后自动半开试探
    </div>
  )
}
