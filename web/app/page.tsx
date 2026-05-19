"use client"

import { Activity, AlertTriangle, CheckCircle2, Timer } from "lucide-react"
import Link from "next/link"
import { useMetrics } from "@/lib/hooks"
import { MetricCard } from "@/app/_dashboard/metric-card"
import { TrendChart } from "@/app/_dashboard/trend-chart"
import { ProviderMatrix } from "@/app/_dashboard/provider-matrix"
import { PageHeader } from "@/components/section"
import { MetricCardSkeleton } from "@/components/skeletons"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { InlineError } from "@/components/inline-error"
import { Skeleton } from "@/components/ui/skeleton"

export default function DashboardPage() {
  const { data, isLoading, isError, refetch } = useMetrics()

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Notify Relay · Dashboard"
        title="通知投递概览"
        description="一站式查看通知投递成功率、堆积情况与 Provider 健康度。可通过 NEXT_PUBLIC_API_BASE 切换 mock / 真实后端。"
        action={
          <Link
            href="/notifications/new"
            className={cn(buttonVariants({ size: "default" }), "gap-1.5")}
          >
            新建通知
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {isLoading || !data ? (
          <>
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
          </>
        ) : isError ? (
          <div className="md:col-span-2 xl:col-span-4">
            <InlineError onRetry={() => refetch()} />
          </div>
        ) : (
          <>
            <MetricCard
              title="投递成功率"
              value={data.successRate * 100}
              decimals={2}
              suffix="%"
              hint="过去 24 小时合计"
              icon={CheckCircle2}
              delta={1.4}
              accent="success"
            />
            <MetricCard
              title="In-Flight"
              value={data.inflight}
              hint="当前正在投递"
              icon={Activity}
              accent="info"
            />
            <MetricCard
              title="DLQ 总量"
              value={data.dlqTotal}
              hint="待人工介入"
              icon={AlertTriangle}
              delta={-0.6}
              positiveIsGood={false}
              accent="warning"
            />
            <MetricCard
              title="P95 投递耗时"
              value={data.p95LatencyMs}
              suffix=" ms"
              hint="不含重试"
              icon={Timer}
              delta={-3.1}
              positiveIsGood={false}
            />
          </>
        )}
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-semibold tracking-tight">
            24 小时投递趋势
          </CardTitle>
          <span className="text-xs text-muted-foreground">每小时聚合</span>
        </CardHeader>
        <CardContent>
          {isLoading || !data ? (
            <Skeleton className="h-[280px] w-full" />
          ) : (
            <TrendChart data={data.trend} />
          )}
        </CardContent>
      </Card>

      <ProviderMatrix />
    </div>
  )
}
