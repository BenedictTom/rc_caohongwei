"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { AnimatedNumber } from "@/components/animated-number"
import { TrendingDown, TrendingUp, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ReactNode } from "react"

interface Props {
  title: string
  value: number
  decimals?: number
  prefix?: string
  suffix?: string
  hint?: string
  icon: LucideIcon
  delta?: number
  positiveIsGood?: boolean
  accent?: "default" | "success" | "warning" | "info" | "danger"
  children?: ReactNode
}

const ACCENT: Record<NonNullable<Props["accent"]>, string> = {
  default: "from-primary/10 to-transparent text-foreground",
  success: "from-success/15 to-transparent text-success",
  warning: "from-warning/15 to-transparent text-warning",
  info: "from-info/15 to-transparent text-info",
  danger: "from-destructive/15 to-transparent text-destructive",
}

export function MetricCard({
  title,
  value,
  decimals,
  prefix,
  suffix,
  hint,
  icon: Icon,
  delta,
  positiveIsGood = true,
  accent = "default",
  children,
}: Props) {
  const positive = (delta ?? 0) >= 0
  const good = positive === positiveIsGood
  return (
    <Card className="group relative overflow-hidden transition-all hover:-translate-y-0.5 hover:shadow-md">
      <div
        className={cn(
          "pointer-events-none absolute inset-x-0 -top-px h-24 bg-gradient-to-b opacity-80 transition-opacity group-hover:opacity-100",
          ACCENT[accent],
        )}
      />
      <CardHeader className="relative pb-2">
        <CardTitle className="flex items-center justify-between text-xs font-medium text-muted-foreground">
          <span className="uppercase tracking-wider">{title}</span>
          <Icon className={cn("size-4", ACCENT[accent].split(" ").pop())} />
        </CardTitle>
      </CardHeader>
      <CardContent className="relative">
        <div className="flex items-baseline gap-2">
          <AnimatedNumber
            value={value}
            decimals={decimals}
            prefix={prefix}
            suffix={suffix}
            className="text-3xl font-semibold tabular-nums tracking-tight"
          />
          {delta !== undefined && (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-medium tabular-nums",
                good
                  ? "bg-success/10 text-success"
                  : "bg-destructive/10 text-destructive",
              )}
            >
              {positive ? (
                <TrendingUp className="size-3" />
              ) : (
                <TrendingDown className="size-3" />
              )}
              {delta > 0 ? "+" : ""}
              {delta.toFixed(1)}%
            </span>
          )}
        </div>
        {hint && (
          <p className="mt-1.5 text-xs text-muted-foreground">{hint}</p>
        )}
        {children}
      </CardContent>
    </Card>
  )
}
