"use client"

import { useState } from "react"
import { useDeadLetters, useProviders } from "@/lib/hooks"
import { PageHeader } from "@/components/section"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { CodeBlock } from "@/components/code-block"
import { EmptyState } from "@/components/empty-state"
import { InlineError } from "@/components/inline-error"
import { RowSkeleton } from "@/components/skeletons"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { motion, AnimatePresence } from "framer-motion"
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Clock,
  RefreshCcw,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { format } from "date-fns"

export default function DeadLettersPage() {
  const [provider, setProvider] = useState<string | undefined>()
  const { data: providers } = useProviders()
  const { data, isLoading, isError, refetch } = useDeadLetters({
    provider,
    limit: 50,
  })
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const distinct = new Set(data?.items.map((i) => i.provider))

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Dead Letter Queue"
        title="死信队列"
        description="超出最大重试次数后的通知会进入此处。重投属危险动作，仅通过 CLI / 运维介入；本页仅做查询。"
      />

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4">
          <div className="flex items-center gap-2">
            <Select
              value={provider ?? "ALL"}
              onValueChange={(v) => setProvider(!v || v === "ALL" ? undefined : v)}
            >
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="全部 Provider" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">全部 Provider</SelectItem>
                {providers?.map((p) => (
                  <SelectItem key={p.name} value={p.name}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {data && (
              <span className="text-xs text-muted-foreground">
                共 <span className="font-semibold text-foreground">{data.total}</span>{" "}
                条 · 跨 <span className="font-semibold text-foreground">{distinct.size}</span>{" "}
                个 provider
              </span>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCcw className="mr-1.5 size-3.5" />
            刷新
          </Button>
        </div>

        {isError ? (
          <div className="p-6">
            <InlineError onRetry={() => refetch()} />
          </div>
        ) : isLoading || !data ? (
          <div className="divide-y">
            {Array.from({ length: 5 }).map((_, i) => (
              <RowSkeleton key={i} />
            ))}
          </div>
        ) : data.items.length === 0 ? (
          <EmptyState
            title="队列干净"
            hint="目前没有死信记录 — 这是好事。"
            icon={<AlertTriangle className="size-5" />}
          />
        ) : (
          <ul className="divide-y">
            <AnimatePresence initial={false}>
              {data.items.map((n, i) => {
                const isOpen = expanded.has(n.id)
                return (
                  <motion.li
                    key={n.id}
                    layout
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ delay: Math.min(i * 0.025, 0.4), duration: 0.22 }}
                    className="bg-card"
                  >
                    <button
                      type="button"
                      onClick={() =>
                        setExpanded((prev) => {
                          const next = new Set(prev)
                          if (next.has(n.id)) next.delete(n.id)
                          else next.add(n.id)
                          return next
                        })
                      }
                      className="flex w-full items-center gap-3 px-5 py-3 text-left text-sm transition-colors hover:bg-muted/40"
                    >
                      <span className="text-muted-foreground">
                        {isOpen ? (
                          <ChevronDown className="size-4" />
                        ) : (
                          <ChevronRight className="size-4" />
                        )}
                      </span>
                      <span className="font-mono text-[12.5px]">{n.id}</span>
                      <span className="text-muted-foreground">{n.provider}</span>
                      <span className="ml-auto inline-flex items-center gap-2">
                        <span className="rounded-md bg-destructive/10 px-1.5 py-0.5 font-mono text-[11px] text-destructive">
                          {n.attempts} attempts
                        </span>
                        <span className="text-xs text-muted-foreground">
                          <Clock className="mr-0.5 inline size-3 -translate-y-px" />
                          {format(new Date(n.createdAt), "MM-dd HH:mm")}
                        </span>
                      </span>
                    </button>
                    <AnimatePresence initial={false}>
                      {isOpen && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.24 }}
                          className="overflow-hidden border-t bg-muted/20"
                        >
                          <div className="grid gap-4 p-5 lg:grid-cols-2">
                            <div className="space-y-1.5">
                              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                                最后错误
                              </div>
                              <div
                                className={cn(
                                  "rounded-md border bg-background px-3 py-2 font-mono text-xs",
                                  "border-destructive/30 text-destructive",
                                )}
                              >
                                {n.lastError ?? "—"}
                              </div>
                              <div className="pt-2 text-[11px] uppercase tracking-wider text-muted-foreground">
                                最后响应
                              </div>
                              <div className="rounded-md border bg-background px-3 py-2 font-mono text-xs">
                                {n.lastResponseSummary ?? "—"}
                              </div>
                            </div>
                            <div className="space-y-1.5">
                              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                                Payload
                              </div>
                              <CodeBlock
                                code={JSON.stringify(n.payload, null, 2)}
                              />
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.li>
                )
              })}
            </AnimatePresence>
          </ul>
        )}
      </Card>
    </div>
  )
}
