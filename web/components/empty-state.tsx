import { Inbox } from "lucide-react"
import type { ReactNode } from "react"

export function EmptyState({
  title = "暂无数据",
  hint,
  icon,
}: {
  title?: string
  hint?: string
  icon?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
        {icon ?? <Inbox className="size-5" />}
      </div>
      <div className="text-sm font-medium">{title}</div>
      {hint && (
        <p className="max-w-xs text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  )
}
