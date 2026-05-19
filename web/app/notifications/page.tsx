"use client"

import { useNotifications } from "@/lib/hooks"
import { Suspense, useState, useTransition } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { PageHeader } from "@/components/section"
import { Card } from "@/components/ui/card"
import { FilterBar } from "./_components/filter-bar"
import { DetailSheet } from "./_components/detail-sheet"
import { StatusBadge } from "@/components/status-badge"
import { EmptyState } from "@/components/empty-state"
import { InlineError } from "@/components/inline-error"
import { RowSkeleton } from "@/components/skeletons"
import { motion, AnimatePresence } from "framer-motion"
import { Button, buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { ChevronLeft, ChevronRight, Plus } from "lucide-react"
import Link from "next/link"
import type { Notification, NotificationStatus } from "@/lib/types"
import { formatDistanceToNow } from "date-fns"
import { zhCN } from "date-fns/locale"

const PAGE_SIZE = 20

export default function NotificationsPage() {
  return (
    <Suspense fallback={null}>
      <NotificationsView />
    </Suspense>
  )
}

function NotificationsView() {
  const router = useRouter()
  const sp = useSearchParams()
  const [, startTransition] = useTransition()

  const status = (sp.get("status") || undefined) as NotificationStatus | undefined
  const provider = sp.get("provider") || undefined
  const q = sp.get("q") || undefined
  const offset = parseInt(sp.get("offset") || "0", 10) || 0

  const setParams = (next: Record<string, string | undefined>) => {
    const params = new URLSearchParams(sp.toString())
    Object.entries(next).forEach(([k, v]) => {
      if (v == null || v === "") params.delete(k)
      else params.set(k, v)
    })
    if (!("offset" in next)) params.delete("offset")
    startTransition(() => router.replace(`/notifications?${params.toString()}`))
  }

  const { data, isLoading, isError, refetch, isFetching } = useNotifications({
    status,
    provider,
    q,
    limit: PAGE_SIZE,
    offset,
  })

  const [selected, setSelected] = useState<Notification | null>(null)
  const [open, setOpen] = useState(false)

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Notifications"
        title="通知列表"
        description="按状态、Provider、关键字过滤；点击行查看 payload、渲染预览与重试时间线。"
        action={
          <Link
            href="/notifications/new"
            className={cn(buttonVariants(), "gap-1")}
          >
            <Plus className="size-4" />
            新建通知
          </Link>
        }
      />

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b p-4">
          <FilterBar
            status={status}
            provider={provider}
            q={q}
            onChange={(next) =>
              setParams({
                status: next.status,
                provider: next.provider,
                q: next.q,
              })
            }
          />
        </div>

        <div className="hidden grid-cols-[2fr_1fr_120px_72px_120px_1fr] items-center gap-3 border-b bg-muted/30 px-5 py-2.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground md:grid">
          <div>ID</div>
          <div>Provider</div>
          <div>状态</div>
          <div>Attempts</div>
          <div>创建</div>
          <div>最后错误</div>
        </div>

        {isError ? (
          <div className="p-6">
            <InlineError onRetry={() => refetch()} />
          </div>
        ) : isLoading || !data ? (
          <div className="divide-y">
            {Array.from({ length: 6 }).map((_, i) => (
              <RowSkeleton key={i} />
            ))}
          </div>
        ) : data.items.length === 0 ? (
          <EmptyState
            title="没有匹配的通知"
            hint="试试调整筛选条件，或先去新建一条"
          />
        ) : (
          <ul className="divide-y">
            <AnimatePresence initial={false}>
              {data.items.map((n, i) => (
                <motion.li
                  key={n.id}
                  layout
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ delay: Math.min(i * 0.025, 0.4), duration: 0.22 }}
                  onClick={() => {
                    setSelected(n)
                    setOpen(true)
                  }}
                  className="grid cursor-pointer grid-cols-1 gap-1 px-5 py-3 text-sm transition-colors hover:bg-muted/40 md:grid-cols-[2fr_1fr_120px_72px_120px_1fr] md:items-center md:gap-3"
                >
                  <div className="flex items-center gap-2 font-mono text-[12.5px] text-foreground/90">
                    {n.id}
                  </div>
                  <div className="text-muted-foreground md:text-foreground">
                    {n.provider}
                  </div>
                  <div>
                    <StatusBadge status={n.status} />
                  </div>
                  <div className="font-mono text-xs tabular-nums text-muted-foreground">
                    {n.attempts}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(n.createdAt), {
                      addSuffix: true,
                      locale: zhCN,
                    })}
                  </div>
                  <div className="truncate font-mono text-[11px] text-muted-foreground">
                    {n.lastError ?? "—"}
                  </div>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}

        {data && data.total > 0 && (
          <div className="flex items-center justify-between border-t px-5 py-3 text-xs text-muted-foreground">
            <div>
              共 <span className="font-medium text-foreground">{data.total}</span> 条
              {isFetching && <span className="ml-2 opacity-70">刷新中…</span>}
            </div>
            <div className="flex items-center gap-2">
              <span>
                第 <span className="font-medium text-foreground">{currentPage}</span> /{" "}
                {totalPages} 页
              </span>
              <Button
                variant="outline"
                size="icon"
                disabled={offset === 0}
                onClick={() => setParams({ offset: String(Math.max(0, offset - PAGE_SIZE)) })}
              >
                <ChevronLeft className="size-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                disabled={offset + PAGE_SIZE >= data.total}
                onClick={() => setParams({ offset: String(offset + PAGE_SIZE) })}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      <DetailSheet
        notification={selected}
        open={open}
        onOpenChange={setOpen}
      />
    </div>
  )
}
