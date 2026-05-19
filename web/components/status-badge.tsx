import { cn } from "@/lib/utils"
import type { BreakerState, NotificationStatus } from "@/lib/types"

const STATUS_STYLE: Record<NotificationStatus, string> = {
  PENDING: "bg-info/12 text-info border-info/30",
  IN_FLIGHT: "bg-info/15 text-info border-info/30",
  SUCCEEDED: "bg-success/12 text-success border-success/30",
  DEAD_LETTER: "bg-destructive/12 text-destructive border-destructive/30",
}

const STATUS_LABEL: Record<NotificationStatus, string> = {
  PENDING: "待发",
  IN_FLIGHT: "投递中",
  SUCCEEDED: "已送达",
  DEAD_LETTER: "死信",
}

export function StatusBadge({ status }: { status: NotificationStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        STATUS_STYLE[status],
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          status === "SUCCEEDED" && "bg-success",
          status === "DEAD_LETTER" && "bg-destructive",
          (status === "PENDING" || status === "IN_FLIGHT") && "bg-info",
        )}
      />
      {STATUS_LABEL[status]}
    </span>
  )
}

const BREAKER_STYLE: Record<BreakerState, string> = {
  CLOSED: "bg-success/12 text-success border-success/30",
  HALF_OPEN: "bg-info/12 text-info border-info/30",
  OPEN: "bg-warning/15 text-warning border-warning/40 pulse-soft",
}

const BREAKER_LABEL: Record<BreakerState, string> = {
  CLOSED: "运行中",
  HALF_OPEN: "半开试探",
  OPEN: "熔断中",
}

export function BreakerBadge({ state }: { state: BreakerState }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        BREAKER_STYLE[state],
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          state === "CLOSED" && "bg-success",
          state === "HALF_OPEN" && "bg-info",
          state === "OPEN" && "bg-warning",
        )}
      />
      {BREAKER_LABEL[state]}
    </span>
  )
}
