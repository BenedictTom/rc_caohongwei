"use client"

import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Search, X } from "lucide-react"
import { useProviders } from "@/lib/hooks"
import type { NotificationStatus } from "@/lib/types"

interface Props {
  status?: NotificationStatus
  provider?: string
  q?: string
  onChange: (next: {
    status?: NotificationStatus
    provider?: string
    q?: string
  }) => void
}

const STATUS_OPTIONS: { value: NotificationStatus | "ALL"; label: string }[] = [
  { value: "ALL", label: "全部状态" },
  { value: "PENDING", label: "待发" },
  { value: "IN_FLIGHT", label: "投递中" },
  { value: "SUCCEEDED", label: "已送达" },
  { value: "DEAD_LETTER", label: "死信" },
]

export function FilterBar({ status, provider, q, onChange }: Props) {
  const { data: providers } = useProviders()
  const hasFilter = status || provider || q

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative flex-1 min-w-[220px] max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={q ?? ""}
          onChange={(e) => onChange({ q: e.target.value || undefined })}
          placeholder="搜索 ID / idempotency key / payload"
          className="pl-9"
        />
      </div>
      <Select
        value={status ?? "ALL"}
        onValueChange={(v) =>
          onChange({
            status: !v || v === "ALL" ? undefined : (v as NotificationStatus),
          })
        }
      >
        <SelectTrigger className="w-[140px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {STATUS_OPTIONS.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={provider ?? "ALL"}
        onValueChange={(v) =>
          onChange({ provider: !v || v === "ALL" ? undefined : v })
        }
      >
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder="Provider" />
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
      {hasFilter && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onChange({ status: undefined, provider: undefined, q: undefined })}
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="mr-1 size-3.5" />
          清除筛选
        </Button>
      )}
    </div>
  )
}
