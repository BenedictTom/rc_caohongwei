"use client"

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { TrendPoint } from "@/lib/types"

export function TrendChart({ data }: { data: TrendPoint[] }) {
  const formatted = data.map((p) => ({
    ...p,
    label: new Date(p.t).getHours().toString().padStart(2, "0") + ":00",
  }))

  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer>
        <AreaChart data={formatted} margin={{ top: 10, right: 8, left: -8, bottom: 0 }}>
          <defs>
            <linearGradient id="okFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-2)" stopOpacity={0.55} />
              <stop offset="100%" stopColor="var(--chart-2)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="failFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-4)" stopOpacity={0.4} />
              <stop offset="100%" stopColor="var(--chart-4)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            stroke="var(--border)"
            strokeDasharray="2 4"
            vertical={false}
          />
          <XAxis
            dataKey="label"
            stroke="var(--muted-foreground)"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval={2}
          />
          <YAxis
            stroke="var(--muted-foreground)"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={40}
          />
          <Tooltip
            contentStyle={{
              background: "var(--popover)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              fontSize: 12,
              boxShadow: "0 4px 24px -8px rgba(0,0,0,0.18)",
            }}
            cursor={{ stroke: "var(--border)", strokeDasharray: "3 3" }}
            labelStyle={{ color: "var(--foreground)", fontWeight: 600 }}
          />
          <Area
            type="monotone"
            dataKey="succeeded"
            stroke="var(--chart-2)"
            strokeWidth={2}
            fill="url(#okFill)"
            name="成功"
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
          <Area
            type="monotone"
            dataKey="failed"
            stroke="var(--chart-4)"
            strokeWidth={2}
            fill="url(#failFill)"
            name="失败"
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
